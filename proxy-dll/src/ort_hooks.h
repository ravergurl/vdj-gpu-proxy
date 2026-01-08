#pragma once

#include <cstdint>

struct OrtApi;
struct OrtApiBase;
struct OrtSession;
struct OrtRunOptions;
struct OrtValue;
struct OrtStatus;
struct OrtMemoryInfo;
struct OrtTensorTypeAndShapeInfo;

bool InitializeOrtProxy();
void ShutdownOrtProxy();

struct ProxyConfig {
    char server_address[256];
    char tunnel_url[512];
    uint16_t server_port;
    bool fallback_to_local;
    bool enabled;
    bool use_tunnel;
};

ProxyConfig* GetProxyConfig();
