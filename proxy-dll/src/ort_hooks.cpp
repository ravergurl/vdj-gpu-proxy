#include "ort_hooks.h"
#include "../include/onnxruntime_c_api.h"
#include <windows.h>
#include <synchapi.h>
#include <cstring>
#include <cstdio>

// OrtStatusPtr typedef for convenience
typedef OrtStatus* OrtStatusPtr;

// Global state
static HMODULE g_hOriginalDll = nullptr;
static const OrtApiBase* g_OriginalApiBase = nullptr;
static const OrtApi* g_OriginalApi = nullptr;
static OrtApi g_HookedApi;
static OrtApiBase g_HookedApiBase;
static ProxyConfig g_Config = {
    "127.0.0.1",
    50051,
    true,
    true
};

// Thread safety for API initialization
static INIT_ONCE g_InitOnce = INIT_ONCE_STATIC_INIT;

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
    // Load from registry or config file
    // HKEY_CURRENT_USER\Software\VDJ-GPU-Proxy
    HKEY hKey;
    if (RegOpenKeyExA(HKEY_CURRENT_USER, "Software\\VDJ-GPU-Proxy", 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
        DWORD size = sizeof(g_Config.server_address);
        LONG result = RegQueryValueExA(hKey, "ServerAddress", nullptr, nullptr, (LPBYTE)g_Config.server_address, &size);
        if (result != ERROR_SUCCESS || size == 0) {
            g_Config.server_address[0] = '\0';  // Clear on error
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
}

bool InitializeOrtProxy() {
    LoadConfig();

    // Find original DLL path - look in same directory with _real suffix
    wchar_t modulePath[MAX_PATH];
    GetModuleFileNameW(nullptr, modulePath, MAX_PATH);

    // Replace filename with onnxruntime_real.dll
    wchar_t* lastSlash = wcsrchr(modulePath, L'\\');
    if (lastSlash) {
        // Calculate remaining buffer size to prevent buffer overflow
        size_t remainingSize = (MAX_PATH - (lastSlash - modulePath) - 1);
        wcscpy_s(lastSlash + 1, remainingSize, L"onnxruntime_real.dll");
    }

    g_hOriginalDll = LoadLibraryW(modulePath);
    if (!g_hOriginalDll) {
        // Try system path
        g_hOriginalDll = LoadLibraryW(L"onnxruntime_real.dll");
    }

    if (!g_hOriginalDll) {
        OutputDebugStringA("VDJ-GPU-Proxy: Failed to load onnxruntime_real.dll\n");
        return false;
    }

    g_OriginalOrtGetApiBase = (PFN_OrtGetApiBase)GetProcAddress(g_hOriginalDll, "OrtGetApiBase");
    if (!g_OriginalOrtGetApiBase) {
        OutputDebugStringA("VDJ-GPU-Proxy: Failed to find OrtGetApiBase\n");
        FreeLibrary(g_hOriginalDll);
        return false;
    }

    OutputDebugStringA("VDJ-GPU-Proxy: Initialized successfully\n");
    return true;
}

void ShutdownOrtProxy() {
    if (g_hOriginalDll) {
        FreeLibrary(g_hOriginalDll);
        g_hOriginalDll = nullptr;
    }
}

static BOOL CALLBACK InitializeApiCallback(PINIT_ONCE InitOnce, PVOID Parameter, PVOID *lpContext) {
    // Get the original API base
    g_OriginalApiBase = g_OriginalOrtGetApiBase();
    if (!g_OriginalApiBase) {
        OutputDebugStringA("VDJ-GPU-Proxy: Failed to get original API base\n");
        return FALSE;
    }

    // Get API version 1
    g_OriginalApi = g_OriginalApiBase->GetApi(1);
    if (!g_OriginalApi) {
        OutputDebugStringA("VDJ-GPU-Proxy: Failed to get original API\n");
        return FALSE;
    }

    // Copy entire function table
    memcpy(&g_HookedApi, g_OriginalApi, sizeof(OrtApi));

    // Save original Run pointer from struct member (safe direct access)
    g_OriginalRun = g_HookedApi.Run;

    // Replace Run with our hook
    g_HookedApi.Run = HookedRun;

    return TRUE;
}

static const OrtApi* ORT_API_CALL HookedGetApi(uint32_t version) noexcept {
    // Thread-safe one-time initialization
    InitOnceExecuteOnce(&g_InitOnce, InitializeApiCallback, NULL, NULL);
    return &g_HookedApi;
}

extern "C" __declspec(dllexport)
const OrtApiBase* ORT_API_CALL OrtGetApiBase(void) noexcept {
    if (g_OriginalApiBase == nullptr && g_OriginalOrtGetApiBase) {
        g_OriginalApiBase = g_OriginalOrtGetApiBase();

        g_HookedApiBase.GetApi = HookedGetApi;
        g_HookedApiBase.GetVersionString = g_OriginalApiBase->GetVersionString;
    }
    return &g_HookedApiBase;
}

// The actual hook - this is where the magic happens
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

    // TODO: Implement remote inference
    // 1. Extract tensor data from inputs
    // 2. Serialize to protobuf
    // 3. Send via gRPC to server
    // 4. Receive response
    // 5. Create output OrtValues
    // 6. Return

    // For now, fallback to local
    OutputDebugStringA("VDJ-GPU-Proxy: HookedRun called - forwarding to local\n");
    return g_OriginalRun(session, run_options, input_names, inputs,
                        input_len, output_names, output_names_len, outputs);
}
