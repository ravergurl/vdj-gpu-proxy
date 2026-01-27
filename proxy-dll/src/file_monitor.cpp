#include "file_monitor.h"
#include <algorithm>
#include <mutex>
#include <cctype>

namespace vdj {

static void DebugLog(const char* fmt, ...) {
    char buf[1024];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    OutputDebugStringA(buf);
}

// Global state
static std::mutex g_FileMutex;
static std::wstring g_LastAudioPath;
static bool g_Initialized = false;

// Original function pointers
typedef HANDLE(WINAPI* PFN_CreateFileW)(
    LPCWSTR lpFileName,
    DWORD dwDesiredAccess,
    DWORD dwShareMode,
    LPSECURITY_ATTRIBUTES lpSecurityAttributes,
    DWORD dwCreationDisposition,
    DWORD dwFlagsAndAttributes,
    HANDLE hTemplateFile
);

typedef HANDLE(WINAPI* PFN_CreateFileA)(
    LPCSTR lpFileName,
    DWORD dwDesiredAccess,
    DWORD dwShareMode,
    LPSECURITY_ATTRIBUTES lpSecurityAttributes,
    DWORD dwCreationDisposition,
    DWORD dwFlagsAndAttributes,
    HANDLE hTemplateFile
);

static PFN_CreateFileW g_OriginalCreateFileW = nullptr;
static PFN_CreateFileA g_OriginalCreateFileA = nullptr;

// Audio extensions we care about
static const wchar_t* g_AudioExtensions[] = {
    L".mp3", L".wav", L".flac", L".aiff", L".aif", L".m4a", L".aac",
    L".ogg", L".wma", L".alac", L".opus", L".mp4", L".m4v"
};

static std::wstring ToLower(const std::wstring& str) {
    std::wstring result = str;
    std::transform(result.begin(), result.end(), result.begin(), ::towlower);
    return result;
}

static std::string ToLower(const std::string& str) {
    std::string result = str;
    std::transform(result.begin(), result.end(), result.begin(), ::tolower);
    return result;
}

bool IsAudioExtension(const std::wstring& path) {
    std::wstring lower = ToLower(path);
    for (const wchar_t* ext : g_AudioExtensions) {
        if (lower.size() >= wcslen(ext)) {
            if (lower.compare(lower.size() - wcslen(ext), wcslen(ext), ext) == 0) {
                return true;
            }
        }
    }
    return false;
}

bool IsAudioExtension(const std::string& path) {
    std::string lower = ToLower(path);
    const char* extensions[] = {
        ".mp3", ".wav", ".flac", ".aiff", ".aif", ".m4a", ".aac",
        ".ogg", ".wma", ".alac", ".opus", ".mp4", ".m4v"
    };
    for (const char* ext : extensions) {
        size_t extLen = strlen(ext);
        if (lower.size() >= extLen) {
            if (lower.compare(lower.size() - extLen, extLen, ext) == 0) {
                return true;
            }
        }
    }
    return false;
}

static std::string WideToUtf8(const std::wstring& wstr) {
    if (wstr.empty()) return "";
    int size = WideCharToMultiByte(CP_UTF8, 0, wstr.c_str(), (int)wstr.size(), nullptr, 0, nullptr, nullptr);
    std::string result(size, 0);
    WideCharToMultiByte(CP_UTF8, 0, wstr.c_str(), (int)wstr.size(), &result[0], size, nullptr, nullptr);
    return result;
}

static std::wstring Utf8ToWide(const std::string& str) {
    if (str.empty()) return L"";
    int size = MultiByteToWideChar(CP_UTF8, 0, str.c_str(), (int)str.size(), nullptr, 0);
    std::wstring result(size, 0);
    MultiByteToWideChar(CP_UTF8, 0, str.c_str(), (int)str.size(), &result[0], size);
    return result;
}

// Hooked CreateFileW
static HANDLE WINAPI HookedCreateFileW(
    LPCWSTR lpFileName,
    DWORD dwDesiredAccess,
    DWORD dwShareMode,
    LPSECURITY_ATTRIBUTES lpSecurityAttributes,
    DWORD dwCreationDisposition,
    DWORD dwFlagsAndAttributes,
    HANDLE hTemplateFile
) {
    // Check if this is an audio file being opened for reading
    if (lpFileName && (dwDesiredAccess & GENERIC_READ)) {
        if (IsAudioExtension(lpFileName)) {
            std::lock_guard<std::mutex> lock(g_FileMutex);
            g_LastAudioPath = lpFileName;

            char msg[512];
            std::string utf8Path = WideToUtf8(lpFileName);
            snprintf(msg, sizeof(msg), "VDJ-FileMonitor: Audio file opened: %s\n", utf8Path.c_str());
            OutputDebugStringA(msg);
        }
    }

    return g_OriginalCreateFileW(lpFileName, dwDesiredAccess, dwShareMode,
                                  lpSecurityAttributes, dwCreationDisposition,
                                  dwFlagsAndAttributes, hTemplateFile);
}

// Hooked CreateFileA
static HANDLE WINAPI HookedCreateFileA(
    LPCSTR lpFileName,
    DWORD dwDesiredAccess,
    DWORD dwShareMode,
    LPSECURITY_ATTRIBUTES lpSecurityAttributes,
    DWORD dwCreationDisposition,
    DWORD dwFlagsAndAttributes,
    HANDLE hTemplateFile
) {
    // Check if this is an audio file being opened for reading
    if (lpFileName && (dwDesiredAccess & GENERIC_READ)) {
        if (IsAudioExtension(lpFileName)) {
            std::lock_guard<std::mutex> lock(g_FileMutex);
            g_LastAudioPath = Utf8ToWide(lpFileName);

            char msg[512];
            snprintf(msg, sizeof(msg), "VDJ-FileMonitor: Audio file opened (A): %s\n", lpFileName);
            OutputDebugStringA(msg);
        }
    }

    return g_OriginalCreateFileA(lpFileName, dwDesiredAccess, dwShareMode,
                                  lpSecurityAttributes, dwCreationDisposition,
                                  dwFlagsAndAttributes, hTemplateFile);
}

// Simple IAT hooking
static bool HookIAT(HMODULE hModule, const char* dllName, const char* funcName, void* hookFunc, void** origFunc) {
    PIMAGE_DOS_HEADER dosHeader = (PIMAGE_DOS_HEADER)hModule;
    if (dosHeader->e_magic != IMAGE_DOS_SIGNATURE) return false;

    PIMAGE_NT_HEADERS ntHeaders = (PIMAGE_NT_HEADERS)((BYTE*)hModule + dosHeader->e_lfanew);
    if (ntHeaders->Signature != IMAGE_NT_SIGNATURE) return false;

    PIMAGE_IMPORT_DESCRIPTOR importDesc = (PIMAGE_IMPORT_DESCRIPTOR)((BYTE*)hModule +
        ntHeaders->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);

    if (importDesc == (PIMAGE_IMPORT_DESCRIPTOR)hModule) return false;

    for (; importDesc->Name; importDesc++) {
        const char* modName = (const char*)((BYTE*)hModule + importDesc->Name);
        if (_stricmp(modName, dllName) != 0) continue;

        PIMAGE_THUNK_DATA thunk = (PIMAGE_THUNK_DATA)((BYTE*)hModule + importDesc->FirstThunk);
        PIMAGE_THUNK_DATA origThunk = (PIMAGE_THUNK_DATA)((BYTE*)hModule + importDesc->OriginalFirstThunk);

        for (; thunk->u1.Function; thunk++, origThunk++) {
            if (origThunk->u1.Ordinal & IMAGE_ORDINAL_FLAG) continue;

            PIMAGE_IMPORT_BY_NAME importByName = (PIMAGE_IMPORT_BY_NAME)((BYTE*)hModule + origThunk->u1.AddressOfData);
            if (strcmp((const char*)importByName->Name, funcName) != 0) continue;

            // Found it - save original and patch
            *origFunc = (void*)thunk->u1.Function;

            DWORD oldProtect;
            if (VirtualProtect(&thunk->u1.Function, sizeof(void*), PAGE_READWRITE, &oldProtect)) {
                thunk->u1.Function = (ULONG_PTR)hookFunc;
                VirtualProtect(&thunk->u1.Function, sizeof(void*), oldProtect, &oldProtect);
                return true;
            }
        }
    }
    return false;
}

bool InitFileMonitor() {
    if (g_Initialized) return true;

    DebugLog("VDJ-FileMonitor: Initializing...\n");

    // Get the main module (VirtualDJ.exe)
    HMODULE hMain = GetModuleHandle(nullptr);
    if (!hMain) {
        DebugLog("VDJ-FileMonitor: Failed to get main module\n");
        return false;
    }

    // Also get kernel32 for direct calls
    g_OriginalCreateFileW = (PFN_CreateFileW)GetProcAddress(GetModuleHandleA("kernel32.dll"), "CreateFileW");
    g_OriginalCreateFileA = (PFN_CreateFileA)GetProcAddress(GetModuleHandleA("kernel32.dll"), "CreateFileA");

    if (!g_OriginalCreateFileW || !g_OriginalCreateFileA) {
        DebugLog("VDJ-FileMonitor: Failed to get original functions\n");
        return false;
    }

    // Hook IAT in main module
    bool hookedW = HookIAT(hMain, "kernel32.dll", "CreateFileW", (void*)HookedCreateFileW, (void**)&g_OriginalCreateFileW);
    bool hookedA = HookIAT(hMain, "kernel32.dll", "CreateFileA", (void*)HookedCreateFileA, (void**)&g_OriginalCreateFileA);

    if (hookedW || hookedA) {
        DebugLog("VDJ-FileMonitor: IAT hooks installed (W=%d, A=%d)\n", hookedW ? 1 : 0, hookedA ? 1 : 0);
    } else {
        DebugLog("VDJ-FileMonitor: IAT hooks failed, using fallback monitoring\n");
    }

    g_Initialized = true;
    DebugLog("VDJ-FileMonitor: Initialized\n");
    return true;
}

void ShutdownFileMonitor() {
    // Note: We don't unhook IAT on shutdown to avoid crashes
    g_Initialized = false;
    DebugLog("VDJ-FileMonitor: Shutdown\n");
}

std::string GetLastAudioFilePath() {
    std::lock_guard<std::mutex> lock(g_FileMutex);
    return WideToUtf8(g_LastAudioPath);
}

std::string GetLastAudioFileDirectory() {
    std::lock_guard<std::mutex> lock(g_FileMutex);
    if (g_LastAudioPath.empty()) return "";

    std::wstring path = g_LastAudioPath;
    size_t lastSlash = path.find_last_of(L"\\/");
    if (lastSlash != std::wstring::npos) {
        return WideToUtf8(path.substr(0, lastSlash));
    }
    return "";
}

void ClearLastAudioFilePath() {
    std::lock_guard<std::mutex> lock(g_FileMutex);
    g_LastAudioPath.clear();
}

} // namespace vdj
