#pragma once

#include <string>
#include <windows.h>

namespace vdj {

/**
 * Initialize file monitoring hooks to track audio file access.
 * Call this once during DLL initialization.
 */
bool InitFileMonitor();

/**
 * Shutdown file monitoring and restore original functions.
 */
void ShutdownFileMonitor();

/**
 * Get the path of the last audio file opened by the host application.
 * Returns empty string if no audio file has been tracked.
 */
std::string GetLastAudioFilePath();

/**
 * Get the directory containing the last audio file.
 */
std::string GetLastAudioFileDirectory();

/**
 * Clear the tracked audio file path.
 */
void ClearLastAudioFilePath();

/**
 * Check if a file extension is a supported audio format.
 */
bool IsAudioExtension(const std::wstring& path);
bool IsAudioExtension(const std::string& path);

} // namespace vdj
