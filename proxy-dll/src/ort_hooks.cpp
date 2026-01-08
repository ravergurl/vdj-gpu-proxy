#include "ort_hooks.h"
#include "grpc_client.h"
#include "tensor_utils.h"
#include "logger.h"
#include "../include/onnxruntime_c_api.h"
#include <windows.h>
#include <synchapi.h>
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
        vdj::GrpcClient* client = vdj::GetGrpcClient();
        client->Disconnect();
        g_ServerConnected = false;
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
    g_OriginalApiBase = g_OriginalOrtGetApiBase();
    if (!g_OriginalApiBase) {
        OutputDebugStringA("VDJ-GPU-Proxy: Failed to get original API base\n");
        return FALSE;
    }

    uint32_t version = g_RequestedApiVersion > 0 ? g_RequestedApiVersion : ORT_API_VERSION;
    char msg[128];
    snprintf(msg, sizeof(msg), "VDJ-GPU-Proxy: Requesting API version %u\n", version);
    OutputDebugStringA(msg);

    g_OriginalApi = g_OriginalApiBase->GetApi(version);
    if (!g_OriginalApi) {
        OutputDebugStringA("VDJ-GPU-Proxy: Failed to get original API, trying version 1\n");
        g_OriginalApi = g_OriginalApiBase->GetApi(1);
    }
    
    if (!g_OriginalApi) {
        OutputDebugStringA("VDJ-GPU-Proxy: Failed to get any API version\n");
        return FALSE;
    }

    memcpy(&g_HookedApi, g_OriginalApi, sizeof(OrtApi));
    g_OriginalRun = g_HookedApi.Run;
    g_HookedApi.Run = HookedRun;

    OutputDebugStringA("VDJ-GPU-Proxy: API hooks installed\n");
    return TRUE;
}

static const OrtApi* ORT_API_CALL HookedGetApi(uint32_t version) noexcept {
    g_RequestedApiVersion = version;
    InitOnceExecuteOnce(&g_InitOnce, InitializeApiCallback, NULL, NULL);
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
        wcscpy_s(lastSlash + 1, remainingSize, L"onnxruntime_real.dll");
    }

    char pathMsg[1024];
    WideCharToMultiByte(CP_UTF8, 0, modulePath, -1, pathMsg, sizeof(pathMsg), NULL, NULL);
    OutputDebugStringA("VDJ-GPU-Proxy: Loading real DLL from: ");
    OutputDebugStringA(pathMsg);
    OutputDebugStringA("\n");
    
    g_hOriginalDll = LoadLibraryW(modulePath);
    if (!g_hOriginalDll) {
        g_hOriginalDll = LoadLibraryW(L"onnxruntime_real.dll");
    }

    if (!g_hOriginalDll) {
        OutputDebugStringA("VDJ-GPU-Proxy: Failed to load onnxruntime_real.dll\n");
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
                wcscpy_s(lastSlash + 1, MAX_PATH - (lastSlash - modulePath) - 1, L"onnxruntime_real.dll");
            }
            g_hOriginalDll = LoadLibraryW(modulePath);
            if (!g_hOriginalDll) {
                g_hOriginalDll = LoadLibraryW(L"onnxruntime_real.dll");
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

static void TryConnectToServer() {
    if (g_ServerConnected) return;
    if (!g_Config.enabled) return;
    
    vdj::GrpcClient* client = vdj::GetGrpcClient();
    bool connected = false;
    
    if (g_Config.use_tunnel && g_Config.tunnel_url[0] != '\0') {
        OutputDebugStringA("VDJ-GPU-Proxy: Connecting via tunnel...\n");
        connected = client->ConnectWithTunnel(g_Config.tunnel_url);
    } else if (g_Config.server_address[0] != '\0') {
        OutputDebugStringA("VDJ-GPU-Proxy: Connecting to server...\n");
        connected = client->Connect(g_Config.server_address, g_Config.server_port);
    }
    
    g_ServerConnected = connected;
    OutputDebugStringA(connected ? "VDJ-GPU-Proxy: Connected!\n" : "VDJ-GPU-Proxy: Connection failed\n");
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
    
    vdj::GrpcClient* client = vdj::GetGrpcClient();
    if (!client->IsConnected()) {
        if (g_Config.fallback_to_local) {
            return g_OriginalRun(session, run_options, input_names, inputs,
                                input_len, output_names, output_names_len, outputs);
        }
        return g_OriginalApi->CreateStatus(ORT_FAIL, "GPU server not connected");
    }

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
            return g_OriginalApi->CreateStatus(ORT_FAIL, "Failed to extract input tensor");
        }
        input_tensors.push_back(std::move(td));
    }

    for (size_t i = 0; i < output_names_len; i++) {
        output_name_vec.push_back(output_names[i]);
    }

    uint64_t session_id = ++g_SessionCounter;
    vdj::InferenceResult result = client->RunInference(
        session_id, input_name_vec, input_tensors, output_name_vec
    );

    if (!result.success) {
        char msg[512];
        snprintf(msg, sizeof(msg), "VDJ-GPU-Proxy: Remote inference failed: %s\n", 
                 result.error_message.c_str());
        OutputDebugStringA(msg);
        
        if (g_Config.fallback_to_local) {
            OutputDebugStringA("VDJ-GPU-Proxy: Falling back to local inference\n");
            return g_OriginalRun(session, run_options, input_names, inputs,
                                input_len, output_names, output_names_len, outputs);
        }
        return g_OriginalApi->CreateStatus(ORT_FAIL, result.error_message.c_str());
    }

    if (result.outputs.size() != output_names_len) {
        OutputDebugStringA("VDJ-GPU-Proxy: Output count mismatch\n");
        if (g_Config.fallback_to_local) {
            return g_OriginalRun(session, run_options, input_names, inputs,
                                input_len, output_names, output_names_len, outputs);
        }
        return g_OriginalApi->CreateStatus(ORT_FAIL, "Output count mismatch from server");
    }

    for (size_t i = 0; i < output_names_len; i++) {
        void* buffer = nullptr;
        OrtValue* ort_value = vdj::CreateOrtValue(g_OriginalApi, result.outputs[i], &buffer);
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
            return g_OriginalApi->CreateStatus(ORT_FAIL, "Failed to create output tensor");
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
