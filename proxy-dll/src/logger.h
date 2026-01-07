#pragma once

#include <cstdint>
#include <string>

namespace vdj {
namespace log {

enum class Level {
    Trace = 0,
    Debug = 1,
    Info = 2,
    Warn = 3,
    Err = 4,
    Fatal = 5
};

void Initialize(const char* log_dir = nullptr);
void Shutdown();
void SetLevel(Level level);
Level GetLevel();

void Log(Level level, const char* file, int line, const char* fmt, ...);

struct PerfTimer {
    const char* name;
    int64_t start_us;
    PerfTimer(const char* operation_name);
    ~PerfTimer();
    int64_t ElapsedUs() const;
};

}  // namespace log
}  // namespace vdj

#define VDJ_LOG_TRACE(fmt, ...) ::vdj::log::Log(::vdj::log::Level::Trace, __FILE__, __LINE__, fmt, ##__VA_ARGS__)
#define VDJ_LOG_DEBUG(fmt, ...) ::vdj::log::Log(::vdj::log::Level::Debug, __FILE__, __LINE__, fmt, ##__VA_ARGS__)
#define VDJ_LOG_INFO(fmt, ...)  ::vdj::log::Log(::vdj::log::Level::Info,  __FILE__, __LINE__, fmt, ##__VA_ARGS__)
#define VDJ_LOG_WARN(fmt, ...)  ::vdj::log::Log(::vdj::log::Level::Warn,  __FILE__, __LINE__, fmt, ##__VA_ARGS__)
#define VDJ_LOG_ERROR(fmt, ...) ::vdj::log::Log(::vdj::log::Level::Err,   __FILE__, __LINE__, fmt, ##__VA_ARGS__)
#define VDJ_LOG_FATAL(fmt, ...) ::vdj::log::Log(::vdj::log::Level::Fatal, __FILE__, __LINE__, fmt, ##__VA_ARGS__)

#define VDJ_PERF_TIMER(name) ::vdj::log::PerfTimer _perf_timer_##__LINE__(name)
