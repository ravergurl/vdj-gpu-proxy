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

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

HttpClient* GetHttpClient();

} // namespace vdj
