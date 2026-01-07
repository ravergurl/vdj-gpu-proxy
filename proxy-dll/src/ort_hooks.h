#pragma once

#include <cstdint>

// Forward declarations matching ONNX Runtime C API
struct OrtApi;
struct OrtApiBase;
struct OrtSession;
struct OrtRunOptions;
struct OrtValue;
struct OrtStatus;
struct OrtMemoryInfo;
struct OrtTensorTypeAndShapeInfo;

// Internal functions
bool InitializeOrtProxy();
void ShutdownOrtProxy();

// Configuration
struct ProxyConfig {
    char server_address[256];
    uint16_t server_port;
    bool fallback_to_local;
    bool enabled;
};

ProxyConfig* GetProxyConfig();
