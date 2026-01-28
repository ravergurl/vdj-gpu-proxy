#include "vdjstem_writer.h"
#include <windows.h>
#include <fstream>
#include <cstdio>
#include <cstring>
#include <sstream>
#include <iomanip>

namespace vdj {

// File-based logging helper (writes to %LOCALAPPDATA%\VDJ-GPU-Proxy.log)
static void DebugLog(const char* fmt, ...) {
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

    char buf[2048];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);

    OutputDebugStringA(buf);

    if (logFile) {
        SYSTEMTIME st;
        GetLocalTime(&st);
        fprintf(logFile, "[%02d:%02d:%02d.%03d] %s",
                st.wHour, st.wMinute, st.wSecond, st.wMilliseconds, buf);
        fflush(logFile);
    }
}

// Write a simple WAV file
static bool WriteWavFile(const std::string& path, const float* data,
                         size_t num_samples, int channels, int sample_rate) {
    std::ofstream file(path, std::ios::binary);
    if (!file) return false;

    // Convert float to 16-bit PCM
    std::vector<int16_t> pcm_data(num_samples);
    for (size_t i = 0; i < num_samples; i++) {
        float sample = data[i];
        if (sample > 1.0f) sample = 1.0f;
        if (sample < -1.0f) sample = -1.0f;
        pcm_data[i] = (int16_t)(sample * 32767.0f);
    }

    uint32_t data_size = (uint32_t)(num_samples * sizeof(int16_t));
    uint32_t file_size = 36 + data_size;

    // RIFF header
    file.write("RIFF", 4);
    file.write((char*)&file_size, 4);
    file.write("WAVE", 4);

    // fmt chunk
    file.write("fmt ", 4);
    uint32_t fmt_size = 16;
    file.write((char*)&fmt_size, 4);
    uint16_t audio_format = 1;  // PCM
    file.write((char*)&audio_format, 2);
    uint16_t num_channels = (uint16_t)channels;
    file.write((char*)&num_channels, 2);
    uint32_t sr = (uint32_t)sample_rate;
    file.write((char*)&sr, 4);
    uint32_t byte_rate = sr * num_channels * 2;
    file.write((char*)&byte_rate, 4);
    uint16_t block_align = num_channels * 2;
    file.write((char*)&block_align, 2);
    uint16_t bits_per_sample = 16;
    file.write((char*)&bits_per_sample, 2);

    // data chunk
    file.write("data", 4);
    file.write((char*)&data_size, 4);
    file.write((char*)pcm_data.data(), data_size);

    return true;
}

// Run ffmpeg to create MP4 with multiple audio streams
static bool RunFfmpeg(const std::vector<std::string>& wav_files,
                      const std::vector<std::string>& stream_titles,
                      const std::string& output_path) {
    // Build ffmpeg command - use full path since VDJ might not have PATH set
    std::stringstream cmd;
    // Try common ffmpeg locations
    const char* ffmpegPath = "C:\\ProgramData\\chocolatey\\bin\\ffmpeg.exe";
    DebugLog("VDJStem: Checking for ffmpeg at: %s\n", ffmpegPath);
    if (GetFileAttributesA(ffmpegPath) == INVALID_FILE_ATTRIBUTES) {
        DebugLog("VDJStem: Not found, trying C:\\ffmpeg\\bin\\ffmpeg.exe\n");
        ffmpegPath = "C:\\ffmpeg\\bin\\ffmpeg.exe";
    }
    if (GetFileAttributesA(ffmpegPath) == INVALID_FILE_ATTRIBUTES) {
        DebugLog("VDJStem: Not found, falling back to PATH\n");
        ffmpegPath = "ffmpeg";
    }
    DebugLog("VDJStem: Using ffmpeg: %s\n", ffmpegPath);
    cmd << "\"" << ffmpegPath << "\" -y";

    for (const auto& wav : wav_files) {
        cmd << " -i \"" << wav << "\"";
    }

    // Map all audio streams
    for (size_t i = 0; i < wav_files.size(); i++) {
        cmd << " -map " << i << ":a";
    }

    // Add metadata title for each stream (required by VDJ)
    for (size_t i = 0; i < stream_titles.size(); i++) {
        cmd << " -metadata:s:" << i << " title=" << stream_titles[i];
    }

    // Max quality: 320k bitrate per stream
    cmd << " -c:a aac -b:a 320k -ar 44100 -ac 2 \"" << output_path << "\"";

    std::string cmdStr = cmd.str();
    DebugLog("VDJStem: Running ffmpeg: %s\n", cmdStr.c_str());

    // Run ffmpeg
    STARTUPINFOA si = {0};
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;

    PROCESS_INFORMATION pi = {0};

    char cmdLine[4096];
    strncpy_s(cmdLine, cmdStr.c_str(), sizeof(cmdLine) - 1);

    if (!CreateProcessA(NULL, cmdLine, NULL, NULL, FALSE,
                        CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) {
        DWORD err = GetLastError();
        DebugLog("VDJStem: Failed to run ffmpeg (err=%u)\n", err);
        return false;
    }

    // Wait for completion (max 5 minutes)
    DWORD waitResult = WaitForSingleObject(pi.hProcess, 300000);

    DWORD exitCode = 1;
    GetExitCodeProcess(pi.hProcess, &exitCode);

    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);

    if (waitResult == WAIT_TIMEOUT) {
        DebugLog("VDJStem: ffmpeg timed out\n");
        return false;
    }

    if (exitCode != 0) {
        DebugLog("VDJStem: ffmpeg failed with exit code %u\n", exitCode);
        return false;
    }

    DebugLog("VDJStem: ffmpeg completed successfully\n");
    return true;
}

bool CreateVdjStemFile(
    const std::vector<std::pair<std::string, std::vector<float>>>& stems,
    const std::string& output_path,
    int sample_rate
) {
    if (stems.size() != 4) {
        DebugLog("VDJStem: Expected 4 stems, got %zu\n", stems.size());
        return false;
    }

    // Get temp directory
    char tempDir[MAX_PATH];
    GetTempPathA(MAX_PATH, tempDir);

    std::string tempBase = std::string(tempDir) + "vdjstem_";

    // Stem mapping: model output name -> VDJ stream title
    // VDJ expects specific stream titles: vocal, instruments, bass, drums (or hihat/kick)
    struct StemMapping {
        const char* model_name;   // Name from model/server
        const char* vdj_title;    // Title for VDJ stream metadata
    };
    const StemMapping stem_mappings[] = {
        {"vocals", "vocal"},      // Model "vocals" -> VDJ "vocal" (no 's')
        {"other", "instruments"}, // Model "other" -> VDJ "instruments"
        {"bass", "bass"},
        {"drums", "drums"}
    };

    std::vector<std::string> wav_files;
    std::vector<std::string> stream_titles;

    // Write each stem as WAV
    for (const auto& mapping : stem_mappings) {
        const char* stem_name = mapping.model_name;
        // Find this stem in the input
        const std::vector<float>* stem_data = nullptr;
        for (const auto& s : stems) {
            if (s.first == stem_name) {
                stem_data = &s.second;
                break;
            }
        }

        if (!stem_data) {
            DebugLog("VDJStem: Missing stem: %s\n", stem_name);
            return false;
        }

        std::string wav_path = tempBase + stem_name + ".wav";

        // Assume stereo interleaved: data is [ch0_s0, ch1_s0, ch0_s1, ch1_s1, ...]
        // Or deinterleaved: [ch0_s0, ch0_s1, ...] then [ch1_s0, ch1_s1, ...]
        // Our tensors are shape (2, samples), so deinterleaved
        size_t total_samples = stem_data->size();
        size_t samples_per_channel = total_samples / 2;

        // Interleave for WAV
        std::vector<float> interleaved(total_samples);
        const float* ch0 = stem_data->data();
        const float* ch1 = stem_data->data() + samples_per_channel;
        for (size_t i = 0; i < samples_per_channel; i++) {
            interleaved[i * 2] = ch0[i];
            interleaved[i * 2 + 1] = ch1[i];
        }

        if (!WriteWavFile(wav_path, interleaved.data(), total_samples, 2, sample_rate)) {
            DebugLog("VDJStem: Failed to write WAV: %s\n", wav_path.c_str());
            return false;
        }

        wav_files.push_back(wav_path);
        stream_titles.push_back(mapping.vdj_title);
        DebugLog("VDJStem: Wrote %s (%zu samples) -> title=%s\n", wav_path.c_str(), total_samples, mapping.vdj_title);
    }

    // Create output directory
    size_t lastSlash = output_path.find_last_of("\\/");
    if (lastSlash != std::string::npos) {
        std::string dir = output_path.substr(0, lastSlash);
        CreateDirectoryA(dir.c_str(), NULL);
    }

    // Run ffmpeg to create MP4
    bool success = RunFfmpeg(wav_files, stream_titles, output_path);

    // Clean up temp WAV files
    for (const auto& wav : wav_files) {
        DeleteFileA(wav.c_str());
    }

    if (success) {
        DebugLog("VDJStem: Created %s\n", output_path.c_str());
    }

    return success;
}

std::string ComputeAudioHash(const float* audio_data, size_t num_samples) {
    // Use first 10 seconds at 44100Hz stereo
    size_t max_samples = 44100 * 10 * 2;
    size_t samples_to_hash = (num_samples < max_samples) ? num_samples : max_samples;

    // Simple hash using polynomial rolling hash
    uint64_t hash = 0;
    const uint64_t prime = 31;
    for (size_t i = 0; i < samples_to_hash; i++) {
        int16_t sample = (int16_t)(audio_data[i] * 32767);
        hash = hash * prime + (uint64_t)(uint16_t)sample;
    }

    // Convert to hex string
    char hex[17];
    snprintf(hex, sizeof(hex), "%016llx", (unsigned long long)hash);
    return std::string(hex);
}

std::string GetVdjStemPath(const std::string& audio_hash, const std::string& stems_folder) {
    std::string subdir = audio_hash.substr(0, 2);
    return stems_folder + "\\" + subdir + "\\" + audio_hash + ".vdjstems";
}

bool VdjStemExists(const std::string& audio_hash, const std::string& stems_folder) {
    std::string path = GetVdjStemPath(audio_hash, stems_folder);
    DWORD attrs = GetFileAttributesA(path.c_str());
    return (attrs != INVALID_FILE_ATTRIBUTES && !(attrs & FILE_ATTRIBUTE_DIRECTORY));
}

} // namespace vdj
