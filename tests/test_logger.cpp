#include <gtest/gtest.h>
#include "logger.h"
#include <cstdio>
#include <fstream>
#include <string>

#ifdef _WIN32
#include <windows.h>
#include <direct.h>
#define mkdir(path, mode) _mkdir(path)
#else
#include <sys/stat.h>
#endif

namespace vdj {
namespace log {
namespace {

class LoggerTest : public ::testing::Test {
protected:
    void SetUp() override {
        test_dir_ = "test_logs";
        mkdir(test_dir_.c_str(), 0755);
    }
    
    void TearDown() override {
        Shutdown();
#ifdef _WIN32
        system(("rmdir /s /q " + test_dir_).c_str());
#else
        system(("rm -rf " + test_dir_).c_str());
#endif
    }
    
    std::string test_dir_;
};

TEST_F(LoggerTest, InitializeCreatesLogFile) {
    Initialize(test_dir_.c_str());
    
    bool found = false;
#ifdef _WIN32
    WIN32_FIND_DATAA fd;
    HANDLE h = FindFirstFileA((test_dir_ + "\\*.log").c_str(), &fd);
    if (h != INVALID_HANDLE_VALUE) {
        found = true;
        FindClose(h);
    }
#else
    DIR* dir = opendir(test_dir_.c_str());
    if (dir) {
        struct dirent* entry;
        while ((entry = readdir(dir)) != nullptr) {
            if (strstr(entry->d_name, ".log")) {
                found = true;
                break;
            }
        }
        closedir(dir);
    }
#endif
    EXPECT_TRUE(found);
}

TEST_F(LoggerTest, SetAndGetLevel) {
    SetLevel(Level::Debug);
    EXPECT_EQ(GetLevel(), Level::Debug);
    
    SetLevel(Level::Err);
    EXPECT_EQ(GetLevel(), Level::Err);
}

TEST_F(LoggerTest, LogMacrosCompile) {
    Initialize(test_dir_.c_str());
    SetLevel(Level::Trace);
    
    VDJ_LOG_TRACE("Trace message %d", 1);
    VDJ_LOG_DEBUG("Debug message %d", 2);
    VDJ_LOG_INFO("Info message %d", 3);
    VDJ_LOG_WARN("Warn message %d", 4);
    VDJ_LOG_ERROR("Error message %d", 5);
    VDJ_LOG_FATAL("Fatal message %d", 6);
}

TEST_F(LoggerTest, PerfTimerMeasuresTime) {
    Initialize(test_dir_.c_str());
    SetLevel(Level::Trace);
    
    {
        PerfTimer timer("test_operation");
#ifdef _WIN32
        Sleep(10);
#else
        usleep(10000);
#endif
        EXPECT_GT(timer.ElapsedUs(), 5000);
    }
}

TEST_F(LoggerTest, MultipleInitializeIsSafe) {
    Initialize(test_dir_.c_str());
    Initialize(test_dir_.c_str());
    Initialize(test_dir_.c_str());
}

TEST_F(LoggerTest, ShutdownWithoutInitializeIsSafe) {
    Shutdown();
    Shutdown();
}

}  // namespace
}  // namespace log
}  // namespace vdj
