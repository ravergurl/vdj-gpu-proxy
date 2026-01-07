#include "logger.h"
#include <windows.h>
#include <shlobj.h>
#include <cstdio>
#include <cstdarg>
#include <ctime>
#include <mutex>
#include <atomic>

#pragma comment(lib, "shell32.lib")

namespace vdj {
namespace log {

static FILE* g_LogFile = nullptr;
static std::mutex g_LogMutex;
static std::atomic<int> g_LogLevel{static_cast<int>(Level::Info)};
static char g_LogPath[MAX_PATH] = {0};

static const char* LevelToString(Level level) {
    switch (level) {
        case Level::Trace: return "TRACE";
        case Level::Debug: return "DEBUG";
        case Level::Info:  return "INFO";
        case Level::Warn:  return "WARN";
        case Level::Err:   return "ERROR";
        case Level::Fatal: return "FATAL";
        default: return "UNKNOWN";
    }
}

static int64_t GetTimestampUs() {
    LARGE_INTEGER freq, counter;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&counter);
    return (counter.QuadPart * 1000000) / freq.QuadPart;
}

static void GetTimestamp(char* buf, size_t buf_size) {
    SYSTEMTIME st;
    GetLocalTime(&st);
    snprintf(buf, buf_size, "%04d-%02d-%02d %02d:%02d:%02d.%03d",
             st.wYear, st.wMonth, st.wDay,
             st.wHour, st.wMinute, st.wSecond, st.wMilliseconds);
}

void Initialize(const char* log_dir) {
    std::lock_guard<std::mutex> lock(g_LogMutex);
    
    if (g_LogFile) return;
    
    char dir[MAX_PATH];
    if (log_dir && log_dir[0]) {
        strncpy(dir, log_dir, MAX_PATH - 1);
        dir[MAX_PATH - 1] = '\0';
    } else {
        if (SUCCEEDED(SHGetFolderPathA(NULL, CSIDL_LOCAL_APPDATA, NULL, 0, dir))) {
            strncat(dir, "\\VDJ-GPU-Proxy", MAX_PATH - strlen(dir) - 1);
        } else {
            strcpy(dir, ".");
        }
    }
    
    CreateDirectoryA(dir, NULL);
    
    SYSTEMTIME st;
    GetLocalTime(&st);
    snprintf(g_LogPath, MAX_PATH, "%s\\vdj-proxy-%04d%02d%02d.log",
             dir, st.wYear, st.wMonth, st.wDay);
    
    g_LogFile = fopen(g_LogPath, "a");
    if (g_LogFile) {
        Log(Level::Info, __FILE__, __LINE__, "=== VDJ-GPU-Proxy started ===");
        Log(Level::Info, __FILE__, __LINE__, "Log file: %s", g_LogPath);
    }
    
    OutputDebugStringA("VDJ-GPU-Proxy: Logger initialized\n");
}

void Shutdown() {
    std::lock_guard<std::mutex> lock(g_LogMutex);
    if (g_LogFile) {
        fprintf(g_LogFile, "\n=== VDJ-GPU-Proxy shutdown ===\n\n");
        fclose(g_LogFile);
        g_LogFile = nullptr;
    }
}

void SetLevel(Level level) {
    g_LogLevel = static_cast<int>(level);
}

Level GetLevel() {
    return static_cast<Level>(g_LogLevel.load());
}

void Log(Level level, const char* file, int line, const char* fmt, ...) {
    if (static_cast<int>(level) < g_LogLevel.load()) return;
    
    char timestamp[32];
    GetTimestamp(timestamp, sizeof(timestamp));
    
    const char* filename = strrchr(file, '\\');
    if (!filename) filename = strrchr(file, '/');
    filename = filename ? filename + 1 : file;
    
    char message[2048];
    va_list args;
    va_start(args, fmt);
    vsnprintf(message, sizeof(message), fmt, args);
    va_end(args);
    
    char full_msg[4096];
    snprintf(full_msg, sizeof(full_msg), "[%s] [%s] [%s:%d] %s\n",
             timestamp, LevelToString(level), filename, line, message);
    
    {
        std::lock_guard<std::mutex> lock(g_LogMutex);
        if (g_LogFile) {
            fputs(full_msg, g_LogFile);
            fflush(g_LogFile);
        }
    }
    
    OutputDebugStringA(full_msg);
}

PerfTimer::PerfTimer(const char* operation_name) 
    : name(operation_name), start_us(GetTimestampUs()) {
    VDJ_LOG_TRACE("PERF START: %s", name);
}

PerfTimer::~PerfTimer() {
    int64_t elapsed = ElapsedUs();
    VDJ_LOG_DEBUG("PERF END: %s took %lld us (%.2f ms)", name, elapsed, elapsed / 1000.0);
}

int64_t PerfTimer::ElapsedUs() const {
    return GetTimestampUs() - start_us;
}

}  // namespace log
}  // namespace vdj
