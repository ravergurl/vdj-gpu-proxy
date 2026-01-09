#include "ort_hooks.h"
#include "grpc_client.h"
#include "http_client.h"
#include "tensor_utils.h"
#include "logger.h"
#include "../include/onnxruntime_c_api.h"
#include <windows.h>
#include <synchapi.h>
#include <mutex>
#include <cstring>
#include <cstdio>
#include <vector>
#include <string>
#include <atomic>

// OrtStatusPtr typedef for convenience
typedef OrtStatus* OrtStatusPtr;

// Global state
static HMODULE g_hOriginalDll = nullptr;
static const OrtApiBase* g_OriginalApiBase = nullptr;
static const OrtApi* g_OriginalApi = nullptr;
static OrtApi g_HookedApi;
static OrtApiBase g_HookedApiBase;
static ProxyConfig g_Config = {};

static void InitDefaultConfig() {
    strcpy_s(g_Config.server_address, "127.0.0.1");
    g_Config.tunnel_url[0] = '\0';
    g_Config.server_port = 50051;
    g_Config.fallback_to_local = true;
    g_Config.enabled = true;
    g_Config.use_tunnel = false;
}

// Connection state
static std::atomic<bool> g_ServerConnected{false};
static std::atomic<bool> g_UsingHttpClient{false};
static std::atomic<uint64_t> g_SessionCounter{0};

// Output buffer tracking for cleanup
static std::vector<void*> g_AllocatedBuffers;
static CRITICAL_SECTION g_BufferLock;
static bool g_BufferLockInitialized = false;

// Thread safety for API initialization
static INIT_ONCE g_InitOnce = INIT_ONCE_STATIC_INIT;
static INIT_ONCE g_ProxyInitOnce = INIT_ONCE_STATIC_INIT;
static bool g_ProxyInitialized = false;

static BOOL CALLBACK InitializeProxyCallback(PINIT_ONCE InitOnce, PVOID Parameter, PVOID *lpContext);

// Function pointer types
typedef const OrtApiBase* (ORT_API_CALL* PFN_OrtGetApiBase)(void);
typedef OrtStatusPtr (ORT_API_CALL* PFN_Run)(
    OrtSession* session,
    const OrtRunOptions* run_options,
    const char* const* input_names,
    const OrtValue* const* inputs,
    size_t input_len,
    const char* const* output_names,
    size_t output_names_len,
    OrtValue** outputs
);

static PFN_OrtGetApiBase g_OriginalOrtGetApiBase = nullptr;
static PFN_Run g_OriginalRun = nullptr;

// Forward declaration
OrtStatusPtr ORT_API_CALL HookedRun(
    OrtSession* session,
    const OrtRunOptions* run_options,
    const char* const* input_names,
    const OrtValue* const* inputs,
    size_t input_len,
    const char* const* output_names,
    size_t output_names_len,
    OrtValue** outputs
) noexcept;

ProxyConfig* GetProxyConfig() {
    return &g_Config;
}

static void LoadConfig() {
    InitDefaultConfig();
    
    HKEY hKey;
    if (RegOpenKeyExA(HKEY_CURRENT_USER, "Software\\VDJ-GPU-Proxy", 0, KEY_READ, &hKey) != ERROR_SUCCESS) {
        return;
    }

    DWORD size = sizeof(g_Config.tunnel_url);
    LONG result = RegQueryValueExA(hKey, "TunnelUrl", nullptr, nullptr, (LPBYTE)g_Config.tunnel_url, &size);
    if (result == ERROR_SUCCESS && size > 1 && g_Config.tunnel_url[0] != '\0') {
        g_Config.use_tunnel = true;
    }

    size = sizeof(g_Config.server_address);
    result = RegQueryValueExA(hKey, "ServerAddress", nullptr, nullptr, (LPBYTE)g_Config.server_address, &size);
    if (result != ERROR_SUCCESS || size == 0) {
        g_Config.server_address[0] = '\0';
    }

    DWORD port = 0;
    size = sizeof(port);
    if (RegQueryValueExA(hKey, "ServerPort", nullptr, nullptr, (LPBYTE)&port, &size) == ERROR_SUCCESS) {
        g_Config.server_port = (uint16_t)port;
    }

    DWORD enabled = 1;
    size = sizeof(enabled);
    if (RegQueryValueExA(hKey, "Enabled", nullptr, nullptr, (LPBYTE)&enabled, &size) == ERROR_SUCCESS) {
        g_Config.enabled = (enabled != 0);
    }

    RegCloseKey(hKey);
}

bool InitializeOrtProxy() {
    InitOnceExecuteOnce(&g_ProxyInitOnce, InitializeProxyCallback, NULL, NULL);
    return g_ProxyInitialized;
}

void ShutdownOrtProxy() {
    if (g_ServerConnected) {
        if (g_UsingHttpClient) {
            vdj::GetHttpClient()->Disconnect();
        } else {
            vdj::GetGrpcClient()->Disconnect();
        }
        g_ServerConnected = false;
        g_UsingHttpClient = false;
    }
    
    if (g_BufferLockInitialized) {
        EnterCriticalSection(&g_BufferLock);
        for (void* buf : g_AllocatedBuffers) {
            free(buf);
        }
        g_AllocatedBuffers.clear();
        LeaveCriticalSection(&g_BufferLock);
        DeleteCriticalSection(&g_BufferLock);
        g_BufferLockInitialized = false;
    }
    
    if (g_hOriginalDll) {
        FreeLibrary(g_hOriginalDll);
        g_hOriginalDll = nullptr;
    }
}

static uint32_t g_RequestedApiVersion = 0;

static BOOL CALLBACK InitializeApiCallback(PINIT_ONCE InitOnce, PVOID Parameter, PVOID *lpContext) {
    OutputDebugStringA("VDJ-GPU-Proxy: InitializeApiCallback starting\n");
    
    if (!g_OriginalApiBase) {
        OutputDebugStringA("VDJ-GPU-Proxy: g_OriginalApiBase is null, getting it now\n");
        if (g_OriginalOrtGetApiBase) {
            g_OriginalApiBase = g_OriginalOrtGetApiBase();
        }
    }
    
    if (!g_OriginalApiBase) {
        OutputDebugStringA("VDJ-GPU-Proxy: Failed to get original API base\n");
        return FALSE;
    }

    uint32_t version = g_RequestedApiVersion > 0 ? g_RequestedApiVersion : ORT_API_VERSION;
    char msg[128];
    snprintf(msg, sizeof(msg), "VDJ-GPU-Proxy: Requesting API version %u (ORT_API_VERSION=%d)\n", version, ORT_API_VERSION);
    OutputDebugStringA(msg);

    g_OriginalApi = g_OriginalApiBase->GetApi(version);
    if (!g_OriginalApi) {
        snprintf(msg, sizeof(msg), "VDJ-GPU-Proxy: GetApi(%u) returned null, trying lower versions\n", version);
        OutputDebugStringA(msg);
        for (uint32_t v = version - 1; v >= 1 && !g_OriginalApi; v--) {
            g_OriginalApi = g_OriginalApiBase->GetApi(v);
            if (g_OriginalApi) {
                snprintf(msg, sizeof(msg), "VDJ-GPU-Proxy: Got API version %u\n", v);
                OutputDebugStringA(msg);
            }
        }
    }
    
    if (!g_OriginalApi) {
        OutputDebugStringA("VDJ-GPU-Proxy: Failed to get any API version\n");
        return FALSE;
    }

    OutputDebugStringA("VDJ-GPU-Proxy: Copying API struct and installing hooks\n");
    memcpy(&g_HookedApi, g_OriginalApi, sizeof(OrtApi));
    g_OriginalRun = g_HookedApi.Run;
    g_HookedApi.Run = HookedRun;

    OutputDebugStringA("VDJ-GPU-Proxy: API hooks installed successfully\n");
    return TRUE;
}

static const OrtApi* ORT_API_CALL HookedGetApi(uint32_t version) noexcept {
    char msg[128];
    snprintf(msg, sizeof(msg), "VDJ-GPU-Proxy: HookedGetApi called with version %u\n", version);
    OutputDebugStringA(msg);
    
    g_RequestedApiVersion = version;
    BOOL initResult = InitOnceExecuteOnce(&g_InitOnce, InitializeApiCallback, NULL, NULL);
    
    snprintf(msg, sizeof(msg), "VDJ-GPU-Proxy: InitOnceExecuteOnce returned %d, g_OriginalApi=%p\n", 
             initResult, (void*)g_OriginalApi);
    OutputDebugStringA(msg);
    
    if (!g_OriginalApi) {
        OutputDebugStringA("VDJ-GPU-Proxy: g_OriginalApi is null, returning original API directly\n");
        if (g_OriginalApiBase) {
            return g_OriginalApiBase->GetApi(version);
        }
        return nullptr;
    }
    
    return &g_HookedApi;
}

// Callback for lazy proxy initialization (called once, outside DllMain context)
static BOOL CALLBACK InitializeProxyCallback(PINIT_ONCE InitOnce, PVOID Parameter, PVOID *lpContext) {
    OutputDebugStringA("VDJ-GPU-Proxy: InitializeProxyCallback starting\n");
    
    if (!g_BufferLockInitialized) {
        InitializeCriticalSection(&g_BufferLock);
        g_BufferLockInitialized = true;
    }
    OutputDebugStringA("VDJ-GPU-Proxy: CritSec initialized\n");
    
    LoadConfig();
    OutputDebugStringA("VDJ-GPU-Proxy: Config loaded\n");

    wchar_t modulePath[MAX_PATH];
    HMODULE hSelf = nullptr;
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                       (LPCWSTR)InitializeProxyCallback, &hSelf);
    if (hSelf) {
        GetModuleFileNameW(hSelf, modulePath, MAX_PATH);
    } else {
        GetModuleFileNameW(nullptr, modulePath, MAX_PATH);
    }

    wchar_t* lastSlash = wcsrchr(modulePath, L'\\');
    if (lastSlash) {
        size_t remainingSize = (MAX_PATH - (lastSlash - modulePath) - 1);
        wcscpy_s(lastSlash + 1, remainingSize, L"ml1151_real.dll");
    }

    char pathMsg[1024];
    WideCharToMultiByte(CP_UTF8, 0, modulePath, -1, pathMsg, sizeof(pathMsg), NULL, NULL);
    OutputDebugStringA("VDJ-GPU-Proxy: Loading real DLL from: ");
    OutputDebugStringA(pathMsg);
    OutputDebugStringA("\n");
    
    g_hOriginalDll = LoadLibraryW(modulePath);
    if (!g_hOriginalDll) {
        g_hOriginalDll = LoadLibraryW(L"ml1151_real.dll");
    }

    if (!g_hOriginalDll) {
        OutputDebugStringA("VDJ-GPU-Proxy: Failed to load ml1151_real.dll\n");
        return FALSE;
    }

    g_OriginalOrtGetApiBase = (PFN_OrtGetApiBase)GetProcAddress(g_hOriginalDll, "OrtGetApiBase");
    if (!g_OriginalOrtGetApiBase) {
        OutputDebugStringA("VDJ-GPU-Proxy: Failed to find OrtGetApiBase\n");
        FreeLibrary(g_hOriginalDll);
        g_hOriginalDll = nullptr;
        return FALSE;
    }

    OutputDebugStringA("VDJ-GPU-Proxy: Real DLL loaded successfully\n");
    
    g_ProxyInitialized = true;
    return TRUE;
}

const OrtApiBase* ORT_API_CALL OrtGetApiBase(void) noexcept {
    OutputDebugStringA("VDJ-GPU-Proxy: OrtGetApiBase called\n");
    
    InitOnceExecuteOnce(&g_ProxyInitOnce, InitializeProxyCallback, NULL, NULL);
    
    if (!g_ProxyInitialized || !g_OriginalOrtGetApiBase) {
        OutputDebugStringA("VDJ-GPU-Proxy: Init failed, attempting emergency fallback\n");
        
        if (!g_hOriginalDll) {
            wchar_t modulePath[MAX_PATH];
            HMODULE hSelf = nullptr;
            GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                               (LPCWSTR)OrtGetApiBase, &hSelf);
            if (hSelf) {
                GetModuleFileNameW(hSelf, modulePath, MAX_PATH);
            } else {
                GetModuleFileNameW(nullptr, modulePath, MAX_PATH);
            }
            wchar_t* lastSlash = wcsrchr(modulePath, L'\\');
            if (lastSlash) {
                wcscpy_s(lastSlash + 1, MAX_PATH - (lastSlash - modulePath) - 1, L"ml1151_real.dll");
            }
            g_hOriginalDll = LoadLibraryW(modulePath);
            if (!g_hOriginalDll) {
                g_hOriginalDll = LoadLibraryW(L"ml1151_real.dll");
            }
        }
        
        if (g_hOriginalDll && !g_OriginalOrtGetApiBase) {
            g_OriginalOrtGetApiBase = (PFN_OrtGetApiBase)GetProcAddress(g_hOriginalDll, "OrtGetApiBase");
        }
        
        if (g_OriginalOrtGetApiBase) {
            OutputDebugStringA("VDJ-GPU-Proxy: Emergency fallback succeeded, using real DLL directly\n");
            return g_OriginalOrtGetApiBase();
        }
        
        OutputDebugStringA("VDJ-GPU-Proxy: Emergency fallback failed, returning nullptr\n");
        return nullptr;
    }
    
    if (g_OriginalApiBase == nullptr) {
        g_OriginalApiBase = g_OriginalOrtGetApiBase();
        if (g_OriginalApiBase) {
            g_HookedApiBase.GetApi = HookedGetApi;
            g_HookedApiBase.GetVersionString = g_OriginalApiBase->GetVersionString;
        }
    }
    
    OutputDebugStringA("VDJ-GPU-Proxy: Returning hooked API\n");
    return &g_HookedApiBase;
}

static std::once_flag g_ConnectOnce;

static void TryConnectToServer() {
    if (g_ServerConnected) return;
    if (!g_Config.enabled) return;

    std::call_once(g_ConnectOnce, []() {
        if (g_ServerConnected) return;

        bool connected = false;

        if (g_Config.use_tunnel && g_Config.tunnel_url[0] != '\0') {
            std::string tunnelUrl(g_Config.tunnel_url);

            // Use HTTP client for HTTPS URLs (Cloudflare tunnel)
            if (tunnelUrl.find("https://") == 0 || tunnelUrl.find("http://") == 0) {
                OutputDebugStringA("VDJ-GPU-Proxy: Connecting via HTTP gateway...\n");
                OutputDebugStringA(g_Config.tunnel_url);
                OutputDebugStringA("\n");

                vdj::HttpClient* httpClient = vdj::GetHttpClient();
                connected = httpClient->Connect(tunnelUrl);

                if (connected) {
                    g_UsingHttpClient = true;
                    vdj::ServerInfo info = httpClient->GetServerInfo();
                    char msg[256];
                    snprintf(msg, sizeof(msg), "VDJ-GPU-Proxy: Connected to %s (model: %s)\n",
                             info.version.c_str(), info.model_name.c_str());
                    OutputDebugStringA(msg);
                }
            } else {
                // Try gRPC with TLS for non-HTTP tunnel URLs (legacy)
                OutputDebugStringA("VDJ-GPU-Proxy: Connecting via gRPC tunnel...\n");
                vdj::GrpcClient* grpcClient = vdj::GetGrpcClient();
                connected = grpcClient->ConnectWithTunnel(tunnelUrl);
                g_UsingHttpClient = false;
            }
        } else if (g_Config.server_address[0] != '\0') {
            // Local/LAN connection uses gRPC (more efficient)
            OutputDebugStringA("VDJ-GPU-Proxy: Connecting to gRPC server...\n");
            vdj::GrpcClient* grpcClient = vdj::GetGrpcClient();
            connected = grpcClient->Connect(g_Config.server_address, g_Config.server_port);
            g_UsingHttpClient = false;
        }

        g_ServerConnected = connected;
        OutputDebugStringA(connected ? "VDJ-GPU-Proxy: Connected!\n" : "VDJ-GPU-Proxy: Connection failed\n");
    });
}

OrtStatusPtr ORT_API_CALL HookedRun(
    OrtSession* session,
    const OrtRunOptions* run_options,
    const char* const* input_names,
    const OrtValue* const* inputs,
    size_t input_len,
    const char* const* output_names,
    size_t output_names_len,
    OrtValue** outputs
) noexcept {
    if (!g_Config.enabled) {
        return g_OriginalRun(session, run_options, input_names, inputs,
                            input_len, output_names, output_names_len, outputs);
    }

    TryConnectToServer();

    // Check connection based on which client we're using
    bool isConnected = false;
    if (g_UsingHttpClient) {
        isConnected = vdj::GetHttpClient()->IsConnected();
    } else {
        isConnected = vdj::GetGrpcClient()->IsConnected();
    }

    if (!isConnected) {
        if (g_Config.fallback_to_local) {
            return g_OriginalRun(session, run_options, input_names, inputs,
                                input_len, output_names, output_names_len, outputs);
        }
        if (g_OriginalApi) return g_OriginalApi->CreateStatus(ORT_FAIL, "GPU server not connected");
        return nullptr;
    }

    // Extract input tensors
    std::vector<std::string> input_name_vec;
    std::vector<vdj::TensorData> input_tensors;
    std::vector<std::string> output_name_vec;

    for (size_t i = 0; i < input_len; i++) {
        input_name_vec.push_back(input_names[i]);
        vdj::TensorData td = vdj::ExtractTensorData(g_OriginalApi, inputs[i]);
        if (td.shape.empty()) {
            OutputDebugStringA("VDJ-GPU-Proxy: Failed to extract input tensor\n");
            if (g_Config.fallback_to_local) {
                return g_OriginalRun(session, run_options, input_names, inputs,
                                    input_len, output_names, output_names_len, outputs);
            }
            if (g_OriginalApi) return g_OriginalApi->CreateStatus(ORT_FAIL, "Failed to extract input tensor");
            return nullptr;
        }

        // Server expects 2D audio tensor (channels, samples)
        // If first dimension is 1 (batch size), squeeze it out
        if (i == 0 && td.shape.size() == 3 && td.shape[0] == 1) {
            char msg[128];
            snprintf(msg, sizeof(msg), "VDJ-GPU-Proxy: Squeezing batch dimension from input[0]: [%lld,%lld,%lld] -> [%lld,%lld]\n",
                     td.shape[0], td.shape[1], td.shape[2], td.shape[1], td.shape[2]);
            OutputDebugStringA(msg);

            // Remove first dimension
            td.shape.erase(td.shape.begin());
        }

        input_tensors.push_back(std::move(td));
    }

    // Server expects specific stem names, not generic output names
    // Always request all 4 stems regardless of what VDJ asks for
    const std::vector<std::string> stem_names = {"drums", "bass", "other", "vocals"};

    if (output_names_len == 4) {
        // VDJ is asking for 4 outputs - use correct stem names
        output_name_vec = stem_names;
    } else if (output_names_len == 2) {
        // VDJ is asking for 2 outputs - still need to request all 4 from server
        // We'll return only the first 2 to VDJ
        output_name_vec = stem_names;
    } else {
        // Use what VDJ requested (fallback)
        for (size_t i = 0; i < output_names_len; i++) {
            output_name_vec.push_back(output_names[i]);
        }
    }

    uint64_t session_id = ++g_SessionCounter;

    // Run inference via appropriate client
    bool inferenceSuccess = false;
    std::string errorMessage;
    std::vector<vdj::TensorData> outputTensors;

    if (g_UsingHttpClient) {
        // Use HTTP client
        std::vector<vdj::HttpTensorData> httpInputs;
        for (const auto& t : input_tensors) {
            vdj::HttpTensorData ht;
            ht.shape = t.shape;
            ht.dtype = t.dtype;
            ht.data = t.data;
            httpInputs.push_back(std::move(ht));
        }

        vdj::HttpInferenceResult httpResult = vdj::GetHttpClient()->RunInferenceBinary(
            session_id, input_name_vec, httpInputs, output_name_vec
        );

        inferenceSuccess = httpResult.success;
        errorMessage = httpResult.error_message;

        if (inferenceSuccess) {
            for (auto& ht : httpResult.outputs) {
                vdj::TensorData td;
                td.shape = std::move(ht.shape);
                td.dtype = ht.dtype;
                td.data = std::move(ht.data);
                outputTensors.push_back(std::move(td));
            }
        }
    } else {
        // Use gRPC client
        vdj::InferenceResult result = vdj::GetGrpcClient()->RunInference(
            session_id, input_name_vec, input_tensors, output_name_vec
        );

        inferenceSuccess = result.success;
        errorMessage = result.error_message;
        outputTensors = std::move(result.outputs);
    }

    if (!inferenceSuccess) {
        char msg[512];
        snprintf(msg, sizeof(msg), "VDJ-GPU-Proxy: Remote inference failed: %s\n",
                 errorMessage.c_str());
        OutputDebugStringA(msg);

        if (g_Config.fallback_to_local) {
            OutputDebugStringA("VDJ-GPU-Proxy: Falling back to local inference\n");
            return g_OriginalRun(session, run_options, input_names, inputs,
                                input_len, output_names, output_names_len, outputs);
        }
        if (g_OriginalApi) return g_OriginalApi->CreateStatus(ORT_FAIL, errorMessage.c_str());
        return nullptr;
    }

    // Check if we got the expected outputs from server
    // We requested stem_names.size() outputs (4 stems)
    if (output_name_vec.size() == 4) {
        // We requested 4 stems
        if (outputTensors.size() != 4) {
            char msg[256];
            snprintf(msg, sizeof(msg), "VDJ-GPU-Proxy: Server returned %zu outputs, expected 4 stems\n",
                     outputTensors.size());
            OutputDebugStringA(msg);
            if (g_Config.fallback_to_local) {
                return g_OriginalRun(session, run_options, input_names, inputs,
                                    input_len, output_names, output_names_len, outputs);
            }
            if (g_OriginalApi) return g_OriginalApi->CreateStatus(ORT_FAIL, "Incorrect output count from server");
            return nullptr;
        }

        // VDJ might want fewer outputs than we got (e.g., VDJ wants 2, we got 4)
        // Just return the first N outputs VDJ requested
        if (outputTensors.size() < output_names_len) {
            OutputDebugStringA("VDJ-GPU-Proxy: VDJ wants more outputs than server returned\n");
            if (g_Config.fallback_to_local) {
                return g_OriginalRun(session, run_options, input_names, inputs,
                                    input_len, output_names, output_names_len, outputs);
            }
            if (g_OriginalApi) return g_OriginalApi->CreateStatus(ORT_FAIL, "Not enough outputs from server");
            return nullptr;
        }
    } else {
        // Normal case: we requested exactly what VDJ wants
        if (outputTensors.size() != output_names_len) {
            char msg[256];
            snprintf(msg, sizeof(msg), "VDJ-GPU-Proxy: Output count mismatch (got %zu, expected %zu)\n",
                     outputTensors.size(), output_names_len);
            OutputDebugStringA(msg);
            if (g_Config.fallback_to_local) {
                return g_OriginalRun(session, run_options, input_names, inputs,
                                    input_len, output_names, output_names_len, outputs);
            }
            if (g_OriginalApi) return g_OriginalApi->CreateStatus(ORT_FAIL, "Output count mismatch from server");
            return nullptr;
        }
    }

    // Return only the outputs VDJ requested
    for (size_t i = 0; i < output_names_len; i++) {
        void* buffer = nullptr;
        OrtValue* ort_value = vdj::CreateOrtValue(g_OriginalApi, outputTensors[i], &buffer);
        if (!ort_value) {
            OutputDebugStringA("VDJ-GPU-Proxy: Failed to create output OrtValue\n");
            for (size_t j = 0; j < i; j++) {
                if (outputs[j]) {
                    g_OriginalApi->ReleaseValue(outputs[j]);
                    outputs[j] = nullptr;
                }
            }
            if (g_Config.fallback_to_local) {
                return g_OriginalRun(session, run_options, input_names, inputs,
                                    input_len, output_names, output_names_len, outputs);
            }
            if (g_OriginalApi) return g_OriginalApi->CreateStatus(ORT_FAIL, "Failed to create output tensor");
            return nullptr;
        }
        outputs[i] = ort_value;
        if (buffer && g_BufferLockInitialized) {
            EnterCriticalSection(&g_BufferLock);
            g_AllocatedBuffers.push_back(buffer);
            LeaveCriticalSection(&g_BufferLock);
        }
    }

    OutputDebugStringA("VDJ-GPU-Proxy: Remote inference successful\n");
    return nullptr;
}

typedef OrtStatusPtr (ORT_API_CALL* PFN_OrtSessionOptionsAppendExecutionProvider_CPU)(
    OrtSessionOptions* options, int use_arena);

extern "C" ORT_EXPORT OrtStatusPtr ORT_API_CALL OrtSessionOptionsAppendExecutionProvider_CPU(
    OrtSessionOptions* options, int use_arena) {
    
    static PFN_OrtSessionOptionsAppendExecutionProvider_CPU s_RealFunc = nullptr;
    
    if (!s_RealFunc && g_hOriginalDll) {
        s_RealFunc = (PFN_OrtSessionOptionsAppendExecutionProvider_CPU)
            GetProcAddress(g_hOriginalDll, "OrtSessionOptionsAppendExecutionProvider_CPU");
    }
    
    if (s_RealFunc) {
        return s_RealFunc(options, use_arena);
    }
    
    return nullptr;
}

typedef OrtStatusPtr (ORT_API_CALL* PFN_OrtSessionOptionsAppendExecutionProvider_DML)(
    OrtSessionOptions* options, int device_id);

extern "C" ORT_EXPORT OrtStatusPtr ORT_API_CALL OrtSessionOptionsAppendExecutionProvider_DML(
    OrtSessionOptions* options, int device_id) {
    
    static PFN_OrtSessionOptionsAppendExecutionProvider_DML s_RealFunc = nullptr;
    
    if (!s_RealFunc && g_hOriginalDll) {
        s_RealFunc = (PFN_OrtSessionOptionsAppendExecutionProvider_DML)
            GetProcAddress(g_hOriginalDll, "OrtSessionOptionsAppendExecutionProvider_DML");
    }
    
    if (s_RealFunc) {
        return s_RealFunc(options, device_id);
    }
    
    return nullptr;
}

typedef OrtStatusPtr (ORT_API_CALL* PFN_OrtSessionOptionsAppendExecutionProviderEx_DML)(
    OrtSessionOptions* options, const void* dml_device, const void* command_queue);

extern "C" ORT_EXPORT OrtStatusPtr ORT_API_CALL OrtSessionOptionsAppendExecutionProviderEx_DML(
    OrtSessionOptions* options, const void* dml_device, const void* command_queue) {
    
    static PFN_OrtSessionOptionsAppendExecutionProviderEx_DML s_RealFunc = nullptr;
    
    if (!s_RealFunc && g_hOriginalDll) {
        s_RealFunc = (PFN_OrtSessionOptionsAppendExecutionProviderEx_DML)
            GetProcAddress(g_hOriginalDll, "OrtSessionOptionsAppendExecutionProviderEx_DML");
    }
    
    if (s_RealFunc) {
        return s_RealFunc(options, dml_device, command_queue);
    }
    
    return nullptr;
}
