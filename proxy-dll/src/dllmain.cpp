#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "ort_hooks.h"

static HINSTANCE g_hInstance = nullptr;

HINSTANCE GetProxyInstance() {
    return g_hInstance;
}

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpReserved) {
    switch (fdwReason) {
        case DLL_PROCESS_ATTACH:
            g_hInstance = hinstDLL;
            DisableThreadLibraryCalls(hinstDLL);
            break;
        case DLL_PROCESS_DETACH:
            if (lpReserved == nullptr) {
                ShutdownOrtProxy();
            }
            break;
    }
    return TRUE;
}
