#pragma once

#include <string>
#include <vector>
#include <cstdint>

namespace vdj {

/**
 * Create a VDJStem MP4 file from stem tensor data.
 *
 * @param stems Map of stem name to audio data (float32, shape [channels, samples])
 * @param output_path Path to write the .vdjstem file
 * @param sample_rate Audio sample rate (default 44100)
 * @return true if successful
 */
bool CreateVdjStemFile(
    const std::vector<std::pair<std::string, std::vector<float>>>& stems,
    const std::string& output_path,
    int sample_rate = 44100
);

/**
 * Compute audio hash for caching.
 * Uses first 10 seconds of audio.
 */
std::string ComputeAudioHash(const float* audio_data, size_t num_samples);

/**
 * Get the path where a VDJStem file should be stored.
 */
std::string GetVdjStemPath(const std::string& audio_hash, const std::string& stems_folder);

/**
 * Check if a VDJStem file exists for the given hash.
 */
bool VdjStemExists(const std::string& audio_hash, const std::string& stems_folder);

} // namespace vdj
