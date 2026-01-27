#include "ort_hooks.h"
#include "grpc_client.h"
#include "http_client.h"
#include "tensor_utils.h"
#include "logger.h"
#include "file_monitor.h"
#include "../include/onnxruntime_c_api.h"
#include <windows.h>
#include <synchapi.h>
#include <mutex>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <string>
#include <atomic>
#include <fstream>

// File-based logging for debugging
static void FileLog(const char* fmt, ...) {
    static FILE* logFile = nullptr;
    static bool logInitialized = false;

    if (!logInitialized) {
        char logPath[MAX_PATH];
        char* localAppData = nullptr;
        size_t len = 0;
        if (_dupenv_s(&localAppData, &len, "LOCALAPPDATA") == 0 && localAppData) {
            snprintf(logPath, MAX_PATH, "%s\\VDJ-GPU-Proxy.log", localAppData);
            free(localAppData);
        } else {
            strcpy_s(logPath, "C:\\VDJ-GPU-Proxy.log");
        }
        logFile = fopen(logPath, "a");
        logInitialized = true;
    }

    if (logFile) {
        SYSTEMTIME st;
        GetLocalTime(&st);
        fprintf(logFile, "[%02d:%02d:%02d.%03d] ", st.wHour, st.wMinute, st.wSecond, st.wMilliseconds);

        va_list args;
        va_start(args, fmt);
        vfprintf(logFile, fmt, args);
        va_end(args);
        fflush(logFile);
    }

    // Also OutputDebugString
    char buf[1024];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    OutputDebugStringA(buf);
}

// OrtStatusPtr typedef for convenience
typedef OrtStatus* OrtStatusPtr;

// Global state
static HMODULE g_hOriginalDll = nullptr;
static const OrtApiBase* g_OriginalApiBase = nullptr;
static const OrtApi* g_OriginalApi = nullptr;
static OrtApi g_HookedApi;
static OrtApiBase g_HookedApiBase;
static ProxyConfig g_Config = {};

// Stems folder for VDJStem files
static char g_StemsFolder[MAX_PATH] = "";
static bool g_UseVdjStemMode = false;

static void InitDefaultConfig() {
    strcpy_s(g_Config.server_address, "127.0.0.1");
    g_Config.tunnel_url[0] = '\0';
    g_Config.server_port = 50051;
    g_Config.fallback_to_local = false;  // NEVER fallback to local inference
    g_Config.enabled = true;
    g_Config.use_tunnel = false;

    // Default stems folder
    char* localAppData = nullptr;
    size_t len = 0;
    if (_dupenv_s(&localAppData, &len, "LOCALAPPDATA") == 0 && localAppData) {
        snprintf(g_StemsFolder, MAX_PATH, "%s\\VDJ-Stems", localAppData);
        free(localAppData);
    } else {
        strcpy_s(g_StemsFolder, "C:\\VDJ-Stems");
    }
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

    // Read VDJStem mode
    DWORD vdjStemMode = 0;
    size = sizeof(vdjStemMode);
    if (RegQueryValueExA(hKey, "UseVdjStemMode", nullptr, nullptr, (LPBYTE)&vdjStemMode, &size) == ERROR_SUCCESS) {
        g_UseVdjStemMode = (vdjStemMode != 0);
    }

    // Read stems folder
    size = sizeof(g_StemsFolder);
    RegQueryValueExA(hKey, "StemsFolder", nullptr, nullptr, (LPBYTE)g_StemsFolder, &size);

    RegCloseKey(hKey);
}

bool InitializeOrtProxy() {
    InitOnceExecuteOnce(&g_ProxyInitOnce, InitializeProxyCallback, NULL, NULL);
    return g_ProxyInitialized;
}

void ShutdownOrtProxy() {
    if (g_ServerConnected) {
        vdj::GetHttpClient()->Disconnect();
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

    // Initialize file monitor to track audio file access
    if (vdj::InitFileMonitor()) {
        OutputDebugStringA("VDJ-GPU-Proxy: File monitor initialized\n");
    } else {
        OutputDebugStringA("VDJ-GPU-Proxy: File monitor init failed (non-fatal)\n");
    }

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
    FileLog("OrtGetApiBase called\n");
    
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

        // Always use HTTP client - no gRPC
        g_UsingHttpClient = true;

        std::string serverUrl;
        if (g_Config.tunnel_url[0] != '\0') {
            serverUrl = g_Config.tunnel_url;
        } else {
            // Default to the known server
            serverUrl = "https://vdj-gpu-direct.ai-smith.net";
        }

        FileLog("Connecting to HTTP server: %s\n", serverUrl.c_str());

        vdj::HttpClient* httpClient = vdj::GetHttpClient();
        bool connected = httpClient->Connect(serverUrl);

        if (connected) {
            FileLog("HTTP connected!\n");
            vdj::ServerInfo info = httpClient->GetServerInfo();
            FileLog("Server: version=%s, model=%s\n", info.version.c_str(), info.model_name.c_str());
        } else {
            FileLog("HTTP connection FAILED\n");
        }

        g_ServerConnected = connected;
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
    FileLog("HookedRun called: inputs=%zu, outputs=%zu, enabled=%d, vdjStemMode=%d\n",
            input_len, output_names_len, g_Config.enabled ? 1 : 0, g_UseVdjStemMode ? 1 : 0);

    // Check if VDJ pre-allocated output buffers
    for (size_t i = 0; i < output_names_len; i++) {
        FileLog("Pre-check outputs[%zu] = %p\n", i, (void*)outputs[i]);
    }

    if (!g_Config.enabled) {
        FileLog("Proxy disabled - but local inference blocked, returning error\n");
        if (g_OriginalApi) return g_OriginalApi->CreateStatus(ORT_FAIL, "Proxy disabled and local inference blocked");
        return nullptr;
    }

    FileLog("TryConnectToServer... tunnel_url='%s'\n", g_Config.tunnel_url);
    TryConnectToServer();

    // Always use HTTP client
    bool isConnected = vdj::GetHttpClient()->IsConnected();
    FileLog("HTTP connected=%d\n", isConnected ? 1 : 0);

    if (!isConnected) {
        FileLog("NOT CONNECTED - BLOCKING local inference, must use remote\n");
        // NEVER allow local inference - always require remote server
        if (g_OriginalApi) return g_OriginalApi->CreateStatus(ORT_FAIL, "Remote GPU server not connected - local inference disabled");
        return nullptr;
    }

    FileLog("Connected! Proceeding with remote inference\n");

    // Extract input tensors
    std::vector<std::string> input_name_vec;
    std::vector<vdj::TensorData> input_tensors;
    std::vector<std::string> output_name_vec;
    bool squeezed_batch_dim = false;
    bool has_2d_audio = false;

    for (size_t i = 0; i < input_len; i++) {
        input_name_vec.push_back(input_names[i]);
        vdj::TensorData td = vdj::ExtractTensorData(g_OriginalApi, inputs[i]);
        if (td.shape.empty()) {
            FileLog("Failed to extract input tensor %zu\n", i);
            if (g_OriginalApi) return g_OriginalApi->CreateStatus(ORT_FAIL, "Failed to extract input tensor");
            return nullptr;
        }

        // Log input shape
        std::string shapeStr;
        for (size_t j = 0; j < td.shape.size(); j++) {
            if (j > 0) shapeStr += ",";
            shapeStr += std::to_string(td.shape[j]);
        }
        FileLog("Input[%zu] '%s' shape=[%s] dtype=%d dataLen=%zu\n",
                i, input_names[i], shapeStr.c_str(), td.dtype, td.data.size());

        // Check if this is 2D audio tensor (channels, samples) or 3D with batch
        // Server expects 2D audio tensor (channels, samples)
        // If first dimension is 1 (batch size), squeeze it out
        if (i == 0 && td.shape.size() == 3 && td.shape[0] == 1) {
            FileLog("Squeezing batch dim: [%lld,%lld,%lld] -> [%lld,%lld]\n",
                     td.shape[0], td.shape[1], td.shape[2], td.shape[1], td.shape[2]);

            // Remove first dimension
            td.shape.erase(td.shape.begin());
            squeezed_batch_dim = true;
            has_2d_audio = true;
        } else if (td.shape.size() == 2) {
            // Already 2D audio
            has_2d_audio = true;
        }

        input_tensors.push_back(std::move(td));
    }

    // If no 2D audio input found (e.g., only 4D spectrograms), allow local for analysis
    // VDJ makes multiple types of calls: stems separation (2D audio) and analysis (4D spectrograms)
    // Server only handles stems separation - let analysis run locally
    if (!has_2d_audio) {
        FileLog("Analysis call (spectrogram) - allowing local\n");
        return g_OriginalRun(session, run_options, input_names, inputs,
                            input_len, output_names, output_names_len, outputs);
    }

    // Log what VDJ actually requested
    std::string vdj_requested_names;
    for (size_t i = 0; i < output_names_len; i++) {
        if (i > 0) vdj_requested_names += ", ";
        vdj_requested_names += output_names[i];
    }
    FileLog("VDJ requested %zu outputs: [%s]\n", output_names_len, vdj_requested_names.c_str());

    // DEBUG: Try running original first to see output format
    static bool g_DiagnosticMode = false;
    if (g_DiagnosticMode && g_OriginalRun) {
        FileLog("DIAGNOSTIC: Calling original Run to see output format\n");
        OrtStatusPtr origStatus = g_OriginalRun(session, run_options, input_names, inputs,
                                                 input_len, output_names, output_names_len, outputs);
        if (!origStatus) {
            for (size_t i = 0; i < output_names_len; i++) {
                if (outputs[i]) {
                    vdj::TensorData td = vdj::ExtractTensorData(g_OriginalApi, outputs[i]);
                    std::string shapeStr;
                    for (size_t j = 0; j < td.shape.size(); j++) {
                        if (j > 0) shapeStr += ",";
                        shapeStr += std::to_string(td.shape[j]);
                    }
                    FileLog("DIAGNOSTIC: Original output[%zu] shape=[%s] dtype=%d dataLen=%zu\n",
                            i, shapeStr.c_str(), td.dtype, td.data.size());
                }
            }
            FileLog("DIAGNOSTIC: Returning original result for comparison\n");
            return origStatus;
        } else {
            const char* errMsg = nullptr;
            g_OriginalApi->GetErrorMessage(origStatus, &errMsg);
            FileLog("DIAGNOSTIC: Original Run failed: %s\n", errMsg ? errMsg : "unknown");
            g_OriginalApi->ReleaseStatus(origStatus);
        }
    }

    // Server always needs all 4 stem names to work correctly
    const std::vector<std::string> stem_names = {"drums", "bass", "other", "vocals"};

    // Always request all 4 stems from server
    output_name_vec = stem_names;
    FileLog("Requesting 4 stems from server, will return %zu to VDJ\n", output_names_len);

    uint64_t session_id = ++g_SessionCounter;

    // Run inference via appropriate client
    bool inferenceSuccess = false;
    std::string errorMessage;
    std::vector<vdj::TensorData> outputTensors;

    // Always use HTTP client
    {
        std::vector<vdj::HttpTensorData> httpInputs;
        for (const auto& t : input_tensors) {
            vdj::HttpTensorData ht;
            ht.shape = t.shape;
            ht.dtype = t.dtype;
            ht.data = t.data;
            httpInputs.push_back(std::move(ht));
        }

        // Check if VDJStem mode is enabled
        if (g_UseVdjStemMode && !httpInputs.empty()) {
            FileLog("VDJStem mode active, httpInputs=%zu\n", httpInputs.size());

            // Get the track path from file monitor
            std::string trackPath = vdj::GetLastAudioFilePath();
            std::string trackDir = vdj::GetLastAudioFileDirectory();

            FileLog("Track path: '%s', dir: '%s'\n", trackPath.c_str(), trackDir.c_str());

            // Use track directory if available, otherwise fall back to stems folder
            std::string outputDir = trackDir.empty() ? std::string(g_StemsFolder) : trackDir;
            FileLog("Output dir: '%s'\n", outputDir.c_str());

            // Create VDJStem file and get tensors
            FileLog("Calling CreateVdjStem...\n");
            vdj::VdjStemResult stemResult = vdj::GetHttpClient()->CreateVdjStem(
                session_id, httpInputs[0], outputDir, trackPath
            );

            FileLog("CreateVdjStem returned: success=%d, error='%s', hash='%s', path='%s'\n",
                    stemResult.success ? 1 : 0, stemResult.error_message.c_str(),
                    stemResult.audio_hash.c_str(), stemResult.local_path.c_str());

            inferenceSuccess = stemResult.success;
            errorMessage = stemResult.error_message;

            if (stemResult.success) {
                FileLog("VDJStem SUCCESS - outputs=%zu\n", stemResult.outputs.size());

                // Return tensors to VDJ for immediate use
                // The .vdjstem file is also saved for future caching
                for (auto& ht : stemResult.outputs) {
                    vdj::TensorData td;
                    td.shape = std::move(ht.shape);
                    td.dtype = ht.dtype;
                    td.data = std::move(ht.data);
                    outputTensors.push_back(std::move(td));
                }
            } else {
                FileLog("VDJStem FAILED\n");
            }
        } else {
            FileLog("NOT using VDJStem mode (vdjStemMode=%d, httpInputs=%zu)\n",
                    g_UseVdjStemMode ? 1 : 0, httpInputs.size());
            // Standard binary inference (no VDJStem file creation)
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
        }
    }

    if (!inferenceSuccess) {
        FileLog("Remote inference FAILED: %s\n", errorMessage.c_str());
        if (g_OriginalApi) return g_OriginalApi->CreateStatus(ORT_FAIL, errorMessage.c_str());
        return nullptr;
    }

    // Check if we got the expected outputs from server
    // We requested stem_names.size() outputs (4 stems)
    if (output_name_vec.size() == 4) {
        // We requested 4 stems
        if (outputTensors.size() != 4) {
            FileLog("Server returned %zu outputs, expected 4 stems\n", outputTensors.size());
            if (g_OriginalApi) return g_OriginalApi->CreateStatus(ORT_FAIL, "Incorrect output count from server");
            return nullptr;
        }

        if (outputTensors.size() < output_names_len) {
            FileLog("VDJ wants more outputs than server returned\n");
            if (g_OriginalApi) return g_OriginalApi->CreateStatus(ORT_FAIL, "Not enough outputs from server");
            return nullptr;
        }
    } else {
        if (outputTensors.size() != output_names_len) {
            FileLog("Output count mismatch (got %zu, expected %zu)\n", outputTensors.size(), output_names_len);
            if (g_OriginalApi) return g_OriginalApi->CreateStatus(ORT_FAIL, "Output count mismatch from server");
            return nullptr;
        }
    }

    // VDJ expects 2 outputs: "output" (vocals) and "output2" (instrumental)
    // We have 4 stems: drums=0, bass=1, other=2, vocals=3
    // Need to combine drums+bass+other into instrumental

    // Create instrumental tensor by summing drums + bass + other
    vdj::TensorData instrumental;
    if (outputTensors.size() >= 4) {
        instrumental.shape = outputTensors[0].shape;  // Same shape as drums
        instrumental.dtype = outputTensors[0].dtype;
        instrumental.data.resize(outputTensors[0].data.size());

        // Sum the three stem tensors (as floats)
        size_t numFloats = instrumental.data.size() / sizeof(float);
        float* instData = reinterpret_cast<float*>(instrumental.data.data());
        const float* drumsData = reinterpret_cast<const float*>(outputTensors[0].data.data());
        const float* bassData = reinterpret_cast<const float*>(outputTensors[1].data.data());
        const float* otherData = reinterpret_cast<const float*>(outputTensors[2].data.data());

        for (size_t j = 0; j < numFloats; j++) {
            instData[j] = drumsData[j] + bassData[j] + otherData[j];
        }
        FileLog("Created instrumental tensor by combining drums+bass+other\n");
    }

    // Return outputs that VDJ requested
    for (size_t i = 0; i < output_names_len; i++) {
        std::string requestedName = output_names[i];
        vdj::TensorData* tensorToUse = nullptr;

        // Map VDJ's generic names to our stems
        // output = vocals, output2 = instrumental (common convention)
        if (requestedName == "output") {
            tensorToUse = &outputTensors[3];  // vocals
            FileLog("VDJ wants '%s' -> using vocals\n", requestedName.c_str());
        } else if (requestedName == "output2") {
            tensorToUse = &instrumental;  // combined instrumental
            FileLog("VDJ wants '%s' -> using instrumental (drums+bass+other)\n", requestedName.c_str());
        } else if (requestedName == "drums") {
            tensorToUse = &outputTensors[0];
        } else if (requestedName == "bass") {
            tensorToUse = &outputTensors[1];
        } else if (requestedName == "other") {
            tensorToUse = &outputTensors[2];
        } else if (requestedName == "vocals") {
            tensorToUse = &outputTensors[3];
        } else {
            // Unknown name - use sequential
            tensorToUse = &outputTensors[i % outputTensors.size()];
            FileLog("VDJ wants unknown '%s' -> using tensor[%zu]\n", requestedName.c_str(), i % outputTensors.size());
        }

        // If we squeezed batch dimension from input, add it back to outputs
        // VDJ expects same shape format: [1, channels, samples]
        if (squeezed_batch_dim && tensorToUse->shape.size() == 2) {
            FileLog("Restoring batch dimension for output %zu\n", i);
            tensorToUse->shape.insert(tensorToUse->shape.begin(), 1);
        }

        // Log final output shape
        std::string outShapeStr;
        for (size_t j = 0; j < tensorToUse->shape.size(); j++) {
            if (j > 0) outShapeStr += ",";
            outShapeStr += std::to_string(tensorToUse->shape[j]);
        }
        FileLog("Creating OrtValue for output %zu '%s': shape=[%s] dtype=%d dataLen=%zu\n",
                i, output_names[i], outShapeStr.c_str(), tensorToUse->dtype, tensorToUse->data.size());

        void* buffer = nullptr;
        OrtValue* ort_value = vdj::CreateOrtValue(g_OriginalApi, *tensorToUse, &buffer);
        if (!ort_value) {
            FileLog("FAILED to create output OrtValue %zu\n", i);
            for (size_t j = 0; j < i; j++) {
                if (outputs[j]) {
                    g_OriginalApi->ReleaseValue(outputs[j]);
                    outputs[j] = nullptr;
                }
            }
            if (g_OriginalApi) return g_OriginalApi->CreateStatus(ORT_FAIL, "Failed to create output tensor");
            return nullptr;
        }
        FileLog("Created OrtValue %zu successfully: ptr=%p\n", i, (void*)ort_value);
        outputs[i] = ort_value;
        // Note: buffer is nullptr when using ORT's internal allocator (CreateTensorAsOrtValue)
        // ORT manages the memory internally, so we don't need to track it
    }

    FileLog("Remote inference SUCCESS - returned %zu outputs to VDJ\n", output_names_len);
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
