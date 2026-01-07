#pragma once

#include <memory>
#include <string>
#include <vector>
#include <cstdint>

namespace vdj {

struct TensorData {
    std::vector<int64_t> shape;
    int32_t dtype;
    std::vector<uint8_t> data;
};

struct InferenceResult {
    bool success;
    std::string error_message;
    std::vector<TensorData> outputs;
};

class GrpcClient {
public:
    GrpcClient();
    ~GrpcClient();

    bool Connect(const std::string& address, uint16_t port);
    void Disconnect();
    bool IsConnected() const;

    InferenceResult RunInference(
        uint64_t session_id,
        const std::vector<std::string>& input_names,
        const std::vector<TensorData>& inputs,
        const std::vector<std::string>& output_names
    );

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

// Global client instance
GrpcClient* GetGrpcClient();

} // namespace vdj
