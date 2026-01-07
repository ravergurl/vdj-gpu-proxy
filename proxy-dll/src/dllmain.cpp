#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "ort_hooks.h"

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpReserved) {
    switch (fdwReason) {
        case DLL_PROCESS_ATTACH:
            DisableThreadLibraryCalls(hinstDLL);
            if (!InitializeOrtProxy()) {
                return FALSE;
            }
            break;
        case DLL_PROCESS_DETACH:
            ShutdownOrtProxy();
            break;
    }
    return TRUE;
}
