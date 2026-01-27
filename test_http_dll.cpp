// Standalone test for HTTP client
// Compile: cl /EHsc /std:c++17 test_http_dll.cpp /I proxy-dll/src /link winhttp.lib

#include <windows.h>
#include <iostream>
#include <vector>
#include <cstdint>

// Minimal TensorData for testing
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

struct ServerInfo {
    std::string version;
    std::string model_name;
    bool ready;
    int max_batch_size;
};

// Include HTTP client directly (copy-paste for standalone compilation)
#include "proxy-dll/src/http_client.h"

int main() {
    std::cout << "=== VDJ HTTP Client Test ===" << std::endl;

    // Test connection
    vdj::HttpClient* client = vdj::GetHttpClient();
    std::cout << "Client created" << std::endl;

    std::string url = "https://vdj-gpu-direct.ai-smith.net";
    std::cout << "Connecting to: " << url << std::endl;

    bool connected = client->Connect(url);
    std::cout << "Connected: " << (connected ? "YES" : "NO") << std::endl;

    if (!connected) {
        std::cout << "Connection failed!" << std::endl;
        return 1;
    }

    // Get server info
    std::cout << "\nGetting server info..." << std::endl;
    vdj::ServerInfo info = client->GetServerInfo();
    std::cout << "Version: " << info.version << std::endl;
    std::cout << "Model: " << info.model_name << std::endl;
    std::cout << "Ready: " << (info.ready ? "YES" : "NO") << std::endl;

    // Test inference with small fake data
    std::cout << "\nTesting inference..." << std::endl;

    // Create fake audio: 1 second stereo @ 44100 (float32)
    std::vector<float> audio_data(2 * 44100, 0.1f);

    vdj::HttpTensorData input;
    input.shape = {2, 44100};
    input.dtype = 1; // FLOAT
    input.data.resize(audio_data.size() * sizeof(float));
    memcpy(input.data.data(), audio_data.data(), input.data.size());

    std::vector<std::string> input_names = {"audio"};
    std::vector<vdj::HttpTensorData> inputs = {input};
    std::vector<std::string> output_names = {"drums", "bass", "other", "vocals"};

    std::cout << "Running inference..." << std::endl;
    vdj::HttpInferenceResult result = client->RunInference(1, input_names, inputs, output_names);

    if (result.success) {
        std::cout << "SUCCESS! Got " << result.outputs.size() << " outputs" << std::endl;
        for (size_t i = 0; i < result.outputs.size(); i++) {
            std::cout << "  Output " << i << ": shape=[";
            for (size_t j = 0; j < result.outputs[i].shape.size(); j++) {
                if (j > 0) std::cout << ",";
                std::cout << result.outputs[i].shape[j];
            }
            std::cout << "] dtype=" << result.outputs[i].dtype;
            std::cout << " dataLen=" << result.outputs[i].data.size() << std::endl;
        }
    } else {
        std::cout << "FAILED: " << result.error_message << std::endl;
        return 1;
    }

    std::cout << "\n=== Test Complete ===" << std::endl;
    return 0;
}
