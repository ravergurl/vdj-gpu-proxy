#pragma once

#include <memory>
#include <string>
#include <vector>
#include <cstdint>
#include <functional>

namespace vdj {

struct HttpTensorData {
    std::vector<int64_t> shape;
    int32_t dtype;
    std::vector<uint8_t> data;
};

struct HttpInferenceResult {
    bool success;
    std::string error_message;
    std::vector<HttpTensorData> outputs;
};

struct ServerInfo {
    std::string version;
    std::string model_name;
    bool ready;
    int max_batch_size;
};

struct VdjStemResult {
    bool success;
    std::string error_message;
    std::string audio_hash;
    std::string local_path;      // Where the file was saved locally
    bool cache_hit;              // Was this a cache hit on the server?
    std::vector<HttpTensorData> outputs;  // Tensor data for immediate use
};

class HttpClient {
public:
    HttpClient();
    ~HttpClient();

    // Connect to HTTP gateway (e.g., https://vdj-gpu-direct.ai-smith.net)
    bool Connect(const std::string& base_url);
    void Disconnect();
    bool IsConnected() const;

    // Get server info
    ServerInfo GetServerInfo();

    // Run inference via HTTP POST
    HttpInferenceResult RunInference(
        uint64_t session_id,
        const std::vector<std::string>& input_names,
        const std::vector<HttpTensorData>& inputs,
        const std::vector<std::string>& output_names
    );

    // Run inference via binary protobuf (more efficient)
    HttpInferenceResult RunInferenceBinary(
        uint64_t session_id,
        const std::vector<std::string>& input_names,
        const std::vector<HttpTensorData>& inputs,
        const std::vector<std::string>& output_names
    );

    // Create a VDJStem file from audio data
    // Saves the .vdjstem file next to the track (if track_path provided)
    // or in stems_folder/hash.vdjstem as fallback
    VdjStemResult CreateVdjStem(
        uint64_t session_id,
        const HttpTensorData& audio_input,
        const std::string& output_dir,    // Directory to save to (track dir or stems folder)
        const std::string& track_path = "" // Full path to track (for naming the stem file)
    );

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

HttpClient* GetHttpClient();

} // namespace vdj
