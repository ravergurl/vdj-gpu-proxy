#pragma once

#include <cstdint>
#include "../include/onnxruntime_c_api.h"

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
