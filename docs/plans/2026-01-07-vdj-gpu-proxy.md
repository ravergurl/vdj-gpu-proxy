# VDJ-GPU-Proxy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create an ONNX Runtime proxy DLL that intercepts VirtualDJ's stems inference calls and offloads them to a remote GPU server over gRPC.

**Architecture:** Local proxy DLL hooks `OrtGetApiBase()`, replaces `OrtApi.Run` with our `HookedRun()` that serializes input tensors, sends via gRPC to remote server running Demucs on CUDA, receives stem tensors back, and returns them to VDJ as if processed locally.

**Tech Stack:** C++ (proxy DLL), gRPC + Protobuf, ONNX Runtime, Python (server), PyTorch/Demucs, CUDA

---

## Task 1: Project Structure & Build System

**Files:**
- Create: `CMakeLists.txt` (root)
- Create: `proto/stems.proto`
- Create: `proxy-dll/CMakeLists.txt`
- Create: `server/requirements.txt`
- Create: `server/pyproject.toml`

**Step 1: Create root CMakeLists.txt**

```cmake
cmake_minimum_required(VERSION 3.20)
project(vdj-gpu-proxy VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Find dependencies
find_package(protobuf CONFIG REQUIRED)
find_package(gRPC CONFIG REQUIRED)

# Proto generation
add_subdirectory(proto)

# Proxy DLL
add_subdirectory(proxy-dll)
```

**Step 2: Create proto/CMakeLists.txt**

```cmake
find_package(protobuf CONFIG REQUIRED)
find_package(gRPC CONFIG REQUIRED)

set(PROTO_FILES stems.proto)

add_library(stems_proto STATIC)
target_link_libraries(stems_proto PUBLIC protobuf::libprotobuf gRPC::grpc++)

protobuf_generate(TARGET stems_proto PROTOS ${PROTO_FILES})
protobuf_generate(
    TARGET stems_proto
    PROTOS ${PROTO_FILES}
    LANGUAGE grpc
    GENERATE_EXTENSIONS .grpc.pb.h .grpc.pb.cc
    PLUGIN "protoc-gen-grpc=\$<TARGET_FILE:gRPC::grpc_cpp_plugin>"
)

target_include_directories(stems_proto PUBLIC ${CMAKE_CURRENT_BINARY_DIR})
```

**Step 3: Create proto/stems.proto**

```protobuf
syntax = "proto3";

package vdj.stems;

option cc_enable_arenas = true;

service StemsInference {
  rpc RunInference(InferenceRequest) returns (InferenceResponse);
  rpc StreamInference(stream AudioChunk) returns (stream StemChunk);
  rpc GetServerInfo(Empty) returns (ServerInfo);
}

message Empty {}

message ServerInfo {
  string version = 1;
  string model_name = 2;
  int32 gpu_memory_mb = 3;
  bool ready = 4;
}

message TensorShape {
  repeated int64 dims = 1;
}

message Tensor {
  TensorShape shape = 1;
  int32 dtype = 2;  // ONNXTensorElementDataType
  bytes data = 3;   // Raw float32 data
}

message InferenceRequest {
  uint64 session_id = 1;
  repeated string input_names = 2;
  repeated Tensor inputs = 3;
  repeated string output_names = 4;
}

message InferenceResponse {
  uint64 session_id = 1;
  int32 status = 2;  // 0 = success
  string error_message = 3;
  repeated Tensor outputs = 4;
}

message AudioChunk {
  uint64 session_id = 1;
  int64 chunk_index = 2;
  int32 sample_rate = 3;
  int32 channels = 4;
  bytes audio_data = 5;  // float32 interleaved
}

message StemChunk {
  uint64 session_id = 1;
  int64 chunk_index = 2;
  string stem_name = 3;  // vocals, drums, bass, other
  bytes audio_data = 4;
}
```

**Step 4: Create server/requirements.txt**

```
grpcio>=1.60.0
grpcio-tools>=1.60.0
protobuf>=4.25.0
torch>=2.1.0
torchaudio>=2.1.0
demucs>=4.0.0
onnxruntime-gpu>=1.16.0
numpy>=1.24.0
```

**Step 5: Create server/pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "vdj-stems-server"
version = "1.0.0"
description = "GPU server for VirtualDJ stems offloading"
requires-python = ">=3.10"
dependencies = [
    "grpcio>=1.60.0",
    "grpcio-tools>=1.60.0",
    "protobuf>=4.25.0",
    "torch>=2.1.0",
    "torchaudio>=2.1.0",
    "demucs>=4.0.0",
    "numpy>=1.24.0",
]

[project.scripts]
vdj-stems-server = "vdj_stems_server.main:main"

[tool.setuptools.packages.find]
where = ["src"]
```

**Step 6: Commit**

```bash
git init
git add -A
git commit -m "chore: initial project structure with proto definition"
```

---

## Task 2: Proxy DLL - Core Structure

**Files:**
- Create: `proxy-dll/CMakeLists.txt`
- Create: `proxy-dll/src/dllmain.cpp`
- Create: `proxy-dll/src/ort_hooks.h`
- Create: `proxy-dll/src/ort_hooks.cpp`
- Create: `proxy-dll/onnxruntime_proxy.def`

**Step 1: Create proxy-dll/CMakeLists.txt**

```cmake
add_library(onnxruntime SHARED
    src/dllmain.cpp
    src/ort_hooks.cpp
    src/grpc_client.cpp
    src/tensor_utils.cpp
)

target_include_directories(onnxruntime PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

target_link_libraries(onnxruntime PRIVATE
    stems_proto
    gRPC::grpc++
)

set_target_properties(onnxruntime PROPERTIES
    OUTPUT_NAME "onnxruntime"
    PREFIX ""
    DEFINE_SYMBOL "ORT_PROXY_EXPORTS"
)

# Module definition for exports
if(WIN32)
    target_sources(onnxruntime PRIVATE onnxruntime_proxy.def)
endif()
```

**Step 2: Create proxy-dll/onnxruntime_proxy.def**

```def
LIBRARY onnxruntime
EXPORTS
    OrtGetApiBase @1
```

**Step 3: Create proxy-dll/src/dllmain.cpp**

```cpp
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "ort_hooks.h"

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpReserved) {
    switch (fdwReason) {
        case DLL_PROCESS_ATTACH:
            DisableThreadLibraryCalls(hinstDLL);
            if (!InitializeOrtProxy()) {
                return FALSE;
            }
            break;
        case DLL_PROCESS_DETACH:
            ShutdownOrtProxy();
            break;
    }
    return TRUE;
}
```

**Step 4: Create proxy-dll/src/ort_hooks.h**

```cpp
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

// Our exports
extern "C" {
    __declspec(dllexport) const OrtApiBase* ORT_API_CALL OrtGetApiBase(void);
}

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
```

**Step 5: Create proxy-dll/src/ort_hooks.cpp**

```cpp
#include "ort_hooks.h"
#include <windows.h>
#include <cstring>
#include <cstdio>

// ONNX Runtime type definitions (from onnxruntime_c_api.h)
#define ORT_API_CALL __stdcall

typedef struct OrtStatus OrtStatus;
typedef OrtStatus* OrtStatusPtr;

typedef struct OrtApiBase {
    const OrtApi* (ORT_API_CALL* GetApi)(uint32_t version);
    const char* (ORT_API_CALL* GetVersionString)(void);
} OrtApiBase;

// Partial OrtApi - only what we need
typedef struct OrtApi {
    // We'll fill this with 200+ function pointers
    // For now, placeholder - full struct needed at compile time
    void* functions[300];
} OrtApi;

// Global state
static HMODULE g_hOriginalDll = nullptr;
static const OrtApiBase* g_OriginalApiBase = nullptr;
static const OrtApi* g_OriginalApi = nullptr;
static OrtApi g_HookedApi;
static OrtApiBase g_HookedApiBase;
static ProxyConfig g_Config = {
    "127.0.0.1",
    50051,
    true,
    true
};

// Function pointer types
typedef const OrtApiBase* (ORT_API_CALL* PFN_OrtGetApiBase)(void);
typedef OrtStatusPtr (ORT_API_CALL* PFN_Run)(
    OrtSession* session,
    const OrtRunOptions* run_options,
    const char* const* input_names,
    const OrtValue* const* inputs,
    size_t input_len,
    const char* const* output_names,
    size_t output_names_len,
    OrtValue** outputs
);

static PFN_OrtGetApiBase g_OriginalOrtGetApiBase = nullptr;
static PFN_Run g_OriginalRun = nullptr;

// Forward declaration
OrtStatusPtr ORT_API_CALL HookedRun(
    OrtSession* session,
    const OrtRunOptions* run_options,
    const char* const* input_names,
    const OrtValue* const* inputs,
    size_t input_len,
    const char* const* output_names,
    size_t output_names_len,
    OrtValue** outputs
);

ProxyConfig* GetProxyConfig() {
    return &g_Config;
}

static void LoadConfig() {
    // Load from registry or config file
    // HKEY_CURRENT_USER\Software\VDJ-GPU-Proxy
    HKEY hKey;
    if (RegOpenKeyExA(HKEY_CURRENT_USER, "Software\\VDJ-GPU-Proxy", 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
        DWORD size = sizeof(g_Config.server_address);
        RegQueryValueExA(hKey, "ServerAddress", nullptr, nullptr, (LPBYTE)g_Config.server_address, &size);

        DWORD port = 0;
        size = sizeof(port);
        if (RegQueryValueExA(hKey, "ServerPort", nullptr, nullptr, (LPBYTE)&port, &size) == ERROR_SUCCESS) {
            g_Config.server_port = (uint16_t)port;
        }

        DWORD enabled = 1;
        size = sizeof(enabled);
        if (RegQueryValueExA(hKey, "Enabled", nullptr, nullptr, (LPBYTE)&enabled, &size) == ERROR_SUCCESS) {
            g_Config.enabled = (enabled != 0);
        }

        RegCloseKey(hKey);
    }
}

bool InitializeOrtProxy() {
    LoadConfig();

    // Find original DLL path - look in same directory with _real suffix
    wchar_t modulePath[MAX_PATH];
    GetModuleFileNameW(nullptr, modulePath, MAX_PATH);

    // Replace filename with onnxruntime_real.dll
    wchar_t* lastSlash = wcsrchr(modulePath, L'\\');
    if (lastSlash) {
        wcscpy(lastSlash + 1, L"onnxruntime_real.dll");
    }

    g_hOriginalDll = LoadLibraryW(modulePath);
    if (!g_hOriginalDll) {
        // Try system path
        g_hOriginalDll = LoadLibraryW(L"onnxruntime_real.dll");
    }

    if (!g_hOriginalDll) {
        OutputDebugStringA("VDJ-GPU-Proxy: Failed to load onnxruntime_real.dll\n");
        return false;
    }

    g_OriginalOrtGetApiBase = (PFN_OrtGetApiBase)GetProcAddress(g_hOriginalDll, "OrtGetApiBase");
    if (!g_OriginalOrtGetApiBase) {
        OutputDebugStringA("VDJ-GPU-Proxy: Failed to find OrtGetApiBase\n");
        FreeLibrary(g_hOriginalDll);
        return false;
    }

    OutputDebugStringA("VDJ-GPU-Proxy: Initialized successfully\n");
    return true;
}

void ShutdownOrtProxy() {
    if (g_hOriginalDll) {
        FreeLibrary(g_hOriginalDll);
        g_hOriginalDll = nullptr;
    }
}

static const OrtApi* ORT_API_CALL HookedGetApi(uint32_t version) {
    if (g_OriginalApi == nullptr) {
        g_OriginalApiBase = g_OriginalOrtGetApiBase();
        g_OriginalApi = g_OriginalApiBase->GetApi(version);

        // Copy entire function table
        memcpy(&g_HookedApi, g_OriginalApi, sizeof(OrtApi));

        // The Run function is at a specific offset in OrtApi
        // OrtApi version 18 has Run at offset 38 (0-indexed)
        // We need the actual header to know exact offset
        // For now, we'll use Detours-style hooking after GetApi returns

        // Save original Run pointer (offset varies by ORT version)
        // This is a simplification - real code needs onnxruntime_c_api.h
        g_OriginalRun = (PFN_Run)g_HookedApi.functions[38];
        g_HookedApi.functions[38] = (void*)HookedRun;
    }
    return &g_HookedApi;
}

extern "C" __declspec(dllexport)
const OrtApiBase* ORT_API_CALL OrtGetApiBase(void) {
    if (g_OriginalApiBase == nullptr && g_OriginalOrtGetApiBase) {
        g_OriginalApiBase = g_OriginalOrtGetApiBase();

        g_HookedApiBase.GetApi = HookedGetApi;
        g_HookedApiBase.GetVersionString = g_OriginalApiBase->GetVersionString;
    }
    return &g_HookedApiBase;
}

// The actual hook - this is where the magic happens
OrtStatusPtr ORT_API_CALL HookedRun(
    OrtSession* session,
    const OrtRunOptions* run_options,
    const char* const* input_names,
    const OrtValue* const* inputs,
    size_t input_len,
    const char* const* output_names,
    size_t output_names_len,
    OrtValue** outputs
) {
    if (!g_Config.enabled) {
        return g_OriginalRun(session, run_options, input_names, inputs,
                            input_len, output_names, output_names_len, outputs);
    }

    // TODO: Implement remote inference
    // 1. Extract tensor data from inputs
    // 2. Serialize to protobuf
    // 3. Send via gRPC to server
    // 4. Receive response
    // 5. Create output OrtValues
    // 6. Return

    // For now, fallback to local
    OutputDebugStringA("VDJ-GPU-Proxy: HookedRun called - forwarding to local\n");
    return g_OriginalRun(session, run_options, input_names, inputs,
                        input_len, output_names, output_names_len, outputs);
}
```

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: proxy DLL core structure with OrtGetApiBase hook"
```

---

## Task 3: Proxy DLL - gRPC Client

**Files:**
- Create: `proxy-dll/src/grpc_client.h`
- Create: `proxy-dll/src/grpc_client.cpp`
- Create: `proxy-dll/src/tensor_utils.h`
- Create: `proxy-dll/src/tensor_utils.cpp`

**Step 1: Create proxy-dll/src/grpc_client.h**

```cpp
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
```

**Step 2: Create proxy-dll/src/grpc_client.cpp**

```cpp
#include "grpc_client.h"
#include <grpcpp/grpcpp.h>
#include "stems.grpc.pb.h"
#include <mutex>

namespace vdj {

class GrpcClient::Impl {
public:
    std::unique_ptr<stems::StemsInference::Stub> stub;
    std::shared_ptr<grpc::Channel> channel;
    std::mutex mutex;
    bool connected = false;
};

GrpcClient::GrpcClient() : impl_(std::make_unique<Impl>()) {}
GrpcClient::~GrpcClient() = default;

bool GrpcClient::Connect(const std::string& address, uint16_t port) {
    std::lock_guard<std::mutex> lock(impl_->mutex);

    std::string target = address + ":" + std::to_string(port);

    grpc::ChannelArguments args;
    args.SetMaxReceiveMessageSize(100 * 1024 * 1024); // 100MB for large tensors
    args.SetMaxSendMessageSize(100 * 1024 * 1024);

    impl_->channel = grpc::CreateCustomChannel(
        target,
        grpc::InsecureChannelCredentials(),
        args
    );

    impl_->stub = stems::StemsInference::NewStub(impl_->channel);

    // Test connection
    grpc::ClientContext context;
    context.set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(5));

    stems::Empty request;
    stems::ServerInfo response;

    grpc::Status status = impl_->stub->GetServerInfo(&context, request, &response);

    impl_->connected = status.ok() && response.ready();
    return impl_->connected;
}

void GrpcClient::Disconnect() {
    std::lock_guard<std::mutex> lock(impl_->mutex);
    impl_->stub.reset();
    impl_->channel.reset();
    impl_->connected = false;
}

bool GrpcClient::IsConnected() const {
    return impl_->connected;
}

InferenceResult GrpcClient::RunInference(
    uint64_t session_id,
    const std::vector<std::string>& input_names,
    const std::vector<TensorData>& inputs,
    const std::vector<std::string>& output_names
) {
    InferenceResult result;
    result.success = false;

    if (!impl_->connected || !impl_->stub) {
        result.error_message = "Not connected to server";
        return result;
    }

    std::lock_guard<std::mutex> lock(impl_->mutex);

    // Build request
    stems::InferenceRequest request;
    request.set_session_id(session_id);

    for (const auto& name : input_names) {
        request.add_input_names(name);
    }

    for (const auto& tensor : inputs) {
        auto* t = request.add_inputs();
        for (int64_t dim : tensor.shape) {
            t->mutable_shape()->add_dims(dim);
        }
        t->set_dtype(tensor.dtype);
        t->set_data(tensor.data.data(), tensor.data.size());
    }

    for (const auto& name : output_names) {
        request.add_output_names(name);
    }

    // Call server
    grpc::ClientContext context;
    context.set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(30));

    stems::InferenceResponse response;
    grpc::Status status = impl_->stub->RunInference(&context, request, &response);

    if (!status.ok()) {
        result.error_message = "gRPC error: " + status.error_message();
        return result;
    }

    if (response.status() != 0) {
        result.error_message = response.error_message();
        return result;
    }

    // Extract outputs
    for (const auto& tensor : response.outputs()) {
        TensorData td;
        for (int i = 0; i < tensor.shape().dims_size(); i++) {
            td.shape.push_back(tensor.shape().dims(i));
        }
        td.dtype = tensor.dtype();
        const std::string& data = tensor.data();
        td.data.assign(data.begin(), data.end());
        result.outputs.push_back(std::move(td));
    }

    result.success = true;
    return result;
}

// Global instance
static std::unique_ptr<GrpcClient> g_client;
static std::once_flag g_client_init;

GrpcClient* GetGrpcClient() {
    std::call_once(g_client_init, []() {
        g_client = std::make_unique<GrpcClient>();
    });
    return g_client.get();
}

} // namespace vdj
```

**Step 3: Create proxy-dll/src/tensor_utils.h**

```cpp
#pragma once

#include "grpc_client.h"
#include "ort_hooks.h"
#include <vector>

namespace vdj {

// Extract tensor data from OrtValue using OrtApi
TensorData ExtractTensorData(const OrtApi* api, const OrtValue* value);

// Create OrtValue from TensorData
// Returns nullptr on failure
// Caller must track allocated memory for cleanup
OrtValue* CreateOrtValue(
    const OrtApi* api,
    const TensorData& tensor,
    void** out_buffer  // Receives pointer to allocated buffer
);

// Get element size for data type
size_t GetElementSize(int32_t dtype);

} // namespace vdj
```

**Step 4: Create proxy-dll/src/tensor_utils.cpp**

```cpp
#include "tensor_utils.h"
#include <cstring>

namespace vdj {

// ONNXTensorElementDataType values
enum OrtDataType {
    ONNX_TENSOR_ELEMENT_DATA_TYPE_UNDEFINED = 0,
    ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT = 1,
    ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT8 = 2,
    ONNX_TENSOR_ELEMENT_DATA_TYPE_INT8 = 3,
    ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT16 = 4,
    ONNX_TENSOR_ELEMENT_DATA_TYPE_INT16 = 5,
    ONNX_TENSOR_ELEMENT_DATA_TYPE_INT32 = 6,
    ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64 = 7,
    ONNX_TENSOR_ELEMENT_DATA_TYPE_STRING = 8,
    ONNX_TENSOR_ELEMENT_DATA_TYPE_BOOL = 9,
    ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT16 = 10,
    ONNX_TENSOR_ELEMENT_DATA_TYPE_DOUBLE = 11,
};

size_t GetElementSize(int32_t dtype) {
    switch (dtype) {
        case ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT: return 4;
        case ONNX_TENSOR_ELEMENT_DATA_TYPE_DOUBLE: return 8;
        case ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64: return 8;
        case ONNX_TENSOR_ELEMENT_DATA_TYPE_INT32: return 4;
        case ONNX_TENSOR_ELEMENT_DATA_TYPE_INT16: return 2;
        case ONNX_TENSOR_ELEMENT_DATA_TYPE_INT8: return 1;
        case ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT8: return 1;
        case ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT16: return 2;
        case ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT16: return 2;
        case ONNX_TENSOR_ELEMENT_DATA_TYPE_BOOL: return 1;
        default: return 0;
    }
}

// Note: These functions require the actual OrtApi function pointers
// The implementation below is pseudocode showing the pattern
// Real implementation needs proper OrtApi struct with function pointers

TensorData ExtractTensorData(const OrtApi* api, const OrtValue* value) {
    TensorData result;

    // This is pseudocode - real impl needs actual OrtApi calls
    // api->GetTensorTypeAndShape(value, &shape_info);
    // api->GetDimensionsCount(shape_info, &num_dims);
    // api->GetDimensions(shape_info, dims.data(), num_dims);
    // api->GetTensorElementType(shape_info, &dtype);
    // api->GetTensorShapeElementCount(shape_info, &count);
    // api->GetTensorMutableData(value, &data_ptr);

    // Placeholder - will be implemented with real OrtApi
    return result;
}

OrtValue* CreateOrtValue(
    const OrtApi* api,
    const TensorData& tensor,
    void** out_buffer
) {
    // Allocate buffer
    size_t element_size = GetElementSize(tensor.dtype);
    size_t total_elements = 1;
    for (int64_t dim : tensor.shape) {
        total_elements *= dim;
    }
    size_t buffer_size = total_elements * element_size;

    *out_buffer = malloc(buffer_size);
    if (!*out_buffer) {
        return nullptr;
    }

    memcpy(*out_buffer, tensor.data.data(), buffer_size);

    // Create OrtValue wrapping buffer
    // api->CreateMemoryInfo("Cpu", OrtArenaAllocator, 0, OrtMemTypeDefault, &mem_info);
    // api->CreateTensorWithDataAsOrtValue(mem_info, *out_buffer, buffer_size,
    //                                      shape, shape_len, dtype, &ort_value);

    // Placeholder - will be implemented with real OrtApi
    return nullptr;
}

} // namespace vdj
```

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: gRPC client and tensor utilities for proxy DLL"
```

---

## Task 4: Python GPU Server - Core

**Files:**
- Create: `server/src/vdj_stems_server/__init__.py`
- Create: `server/src/vdj_stems_server/main.py`
- Create: `server/src/vdj_stems_server/inference.py`
- Create: `server/src/vdj_stems_server/grpc_server.py`

**Step 1: Create server directory structure**

```bash
mkdir -p server/src/vdj_stems_server
```

**Step 2: Create server/src/vdj_stems_server/__init__.py**

```python
"""VDJ Stems GPU Server - Remote inference for VirtualDJ stems separation."""

__version__ = "1.0.0"
```

**Step 3: Create server/src/vdj_stems_server/inference.py**

```python
"""Stems separation inference engine using Demucs."""

import torch
import torchaudio
from demucs.pretrained import get_model
from demucs.apply import apply_model
import numpy as np
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class StemsInferenceEngine:
    """Handles stems separation using Demucs model."""

    STEM_NAMES = ["drums", "bass", "other", "vocals"]

    def __init__(
        self,
        model_name: str = "htdemucs",
        device: str = "cuda",
        segment_length: float = 7.8,
        overlap: float = 0.25,
    ):
        self.device = device
        self.segment_length = segment_length
        self.overlap = overlap

        logger.info(f"Loading Demucs model: {model_name}")
        self.model = get_model(model_name)
        self.model.to(device)
        self.model.eval()

        self.sample_rate = self.model.samplerate
        logger.info(f"Model loaded. Sample rate: {self.sample_rate}")

    @property
    def gpu_memory_mb(self) -> int:
        """Get GPU memory usage in MB."""
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() // (1024 * 1024)
        return 0

    def separate(
        self,
        audio: np.ndarray,
        sample_rate: int = 44100
    ) -> Dict[str, np.ndarray]:
        """
        Separate audio into stems.

        Args:
            audio: Input audio as numpy array, shape (channels, samples) or (samples,)
            sample_rate: Input sample rate

        Returns:
            Dictionary mapping stem names to numpy arrays
        """
        # Ensure 2D (channels, samples)
        if audio.ndim == 1:
            audio = np.stack([audio, audio])  # Mono to stereo

        # Convert to torch tensor
        waveform = torch.from_numpy(audio).float()

        # Resample if needed
        if sample_rate != self.sample_rate:
            waveform = torchaudio.functional.resample(
                waveform, sample_rate, self.sample_rate
            )

        # Add batch dimension
        waveform = waveform.unsqueeze(0).to(self.device)

        # Run separation
        with torch.no_grad():
            sources = apply_model(
                self.model,
                waveform,
                segment=self.segment_length,
                overlap=self.overlap,
                device=self.device,
                progress=False,
            )

        # sources shape: (batch, num_stems, channels, samples)
        sources = sources[0].cpu().numpy()

        # Resample back if needed
        result = {}
        for i, name in enumerate(self.STEM_NAMES):
            stem = sources[i]
            if sample_rate != self.sample_rate:
                stem_tensor = torch.from_numpy(stem)
                stem_tensor = torchaudio.functional.resample(
                    stem_tensor, self.sample_rate, sample_rate
                )
                stem = stem_tensor.numpy()
            result[name] = stem

        return result

    def separate_tensor(
        self,
        input_tensor: np.ndarray,
        input_shape: List[int],
        dtype: int,
    ) -> Tuple[np.ndarray, List[int], int]:
        """
        Separate stems from raw tensor data (for ONNX-style interface).

        Args:
            input_tensor: Raw tensor bytes as numpy array
            input_shape: Tensor shape
            dtype: ONNX data type (1 = float32)

        Returns:
            Tuple of (output_data, output_shape, dtype)
        """
        # Reshape input
        audio = input_tensor.reshape(input_shape)

        # If shape is (batch, channels, samples), take first batch
        if len(input_shape) == 3:
            audio = audio[0]

        # Separate
        stems = self.separate(audio, self.sample_rate)

        # Stack into single tensor: (num_stems, channels, samples)
        output = np.stack([stems[name] for name in self.STEM_NAMES])

        # Add batch dim: (1, num_stems, channels, samples)
        output = output[np.newaxis, ...]

        return output, list(output.shape), dtype


# Global engine instance
_engine: StemsInferenceEngine = None


def get_engine() -> StemsInferenceEngine:
    """Get or create the global inference engine."""
    global _engine
    if _engine is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _engine = StemsInferenceEngine(device=device)
    return _engine
```

**Step 4: Create server/src/vdj_stems_server/grpc_server.py**

```python
"""gRPC server implementation for stems inference."""

import grpc
from concurrent import futures
import numpy as np
import logging
from typing import Optional

# Generated protobuf imports (will be generated from stems.proto)
from . import stems_pb2
from . import stems_pb2_grpc
from .inference import get_engine, StemsInferenceEngine

logger = logging.getLogger(__name__)


class StemsInferenceServicer(stems_pb2_grpc.StemsInferenceServicer):
    """gRPC servicer for stems inference."""

    def __init__(self, engine: Optional[StemsInferenceEngine] = None):
        self.engine = engine or get_engine()

    def GetServerInfo(self, request, context):
        """Return server information."""
        return stems_pb2.ServerInfo(
            version="1.0.0",
            model_name="htdemucs",
            gpu_memory_mb=self.engine.gpu_memory_mb,
            ready=True,
        )

    def RunInference(self, request, context):
        """Run stems separation inference."""
        try:
            session_id = request.session_id
            logger.info(f"Inference request: session={session_id}, "
                       f"inputs={len(request.inputs)}")

            # Process each input tensor
            outputs = []
            for i, tensor in enumerate(request.inputs):
                # Convert protobuf to numpy
                shape = list(tensor.shape.dims)
                dtype = tensor.dtype
                data = np.frombuffer(tensor.data, dtype=np.float32)

                logger.debug(f"Input tensor {i}: shape={shape}, dtype={dtype}")

                # Run separation
                output_data, output_shape, output_dtype = \
                    self.engine.separate_tensor(data, shape, dtype)

                # Convert back to protobuf
                output_tensor = stems_pb2.Tensor(
                    shape=stems_pb2.TensorShape(dims=output_shape),
                    dtype=output_dtype,
                    data=output_data.astype(np.float32).tobytes(),
                )
                outputs.append(output_tensor)

            return stems_pb2.InferenceResponse(
                session_id=session_id,
                status=0,
                outputs=outputs,
            )

        except Exception as e:
            logger.exception("Inference error")
            return stems_pb2.InferenceResponse(
                session_id=request.session_id,
                status=1,
                error_message=str(e),
            )

    def StreamInference(self, request_iterator, context):
        """Stream-based inference for real-time processing."""
        # TODO: Implement streaming for lower latency
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Streaming not yet implemented")
        return


def serve(host: str = "0.0.0.0", port: int = 50051, max_workers: int = 4):
    """Start the gRPC server."""
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=max_workers),
        options=[
            ("grpc.max_receive_message_length", 100 * 1024 * 1024),
            ("grpc.max_send_message_length", 100 * 1024 * 1024),
        ],
    )

    stems_pb2_grpc.add_StemsInferenceServicer_to_server(
        StemsInferenceServicer(),
        server,
    )

    address = f"{host}:{port}"
    server.add_insecure_port(address)

    logger.info(f"Starting gRPC server on {address}")
    server.start()

    return server
```

**Step 5: Create server/src/vdj_stems_server/main.py**

```python
"""Main entry point for VDJ Stems Server."""

import argparse
import logging
import signal
import sys

from .grpc_server import serve
from .inference import get_engine


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="VDJ Stems GPU Server - Remote inference for VirtualDJ"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=50051,
        help="Port to listen on (default: 50051)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of worker threads (default: 4)",
    )
    parser.add_argument(
        "--model",
        default="htdemucs",
        help="Demucs model to use (default: htdemucs)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)

    # Pre-load inference engine
    logger.info("Initializing inference engine...")
    engine = get_engine()
    logger.info(f"Engine ready. GPU memory: {engine.gpu_memory_mb}MB")

    # Start server
    server = serve(args.host, args.port, args.workers)

    # Handle shutdown
    def shutdown(sig, frame):
        logger.info("Shutting down...")
        server.stop(grace=5)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("Server running. Press Ctrl+C to stop.")
    server.wait_for_termination()


if __name__ == "__main__":
    main()
```

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: Python GPU server with Demucs inference engine"
```

---

## Task 5: Proto Generation Scripts

**Files:**
- Create: `scripts/generate_proto.py`
- Create: `scripts/generate_proto.ps1`

**Step 1: Create scripts/generate_proto.py**

```python
#!/usr/bin/env python3
"""Generate Python protobuf/gRPC code from stems.proto."""

import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).parent.parent
    proto_dir = root / "proto"
    output_dir = root / "server" / "src" / "vdj_stems_server"

    proto_file = proto_dir / "stems.proto"

    if not proto_file.exists():
        print(f"Error: {proto_file} not found")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate protobuf
    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        f"-I{proto_dir}",
        f"--python_out={output_dir}",
        f"--grpc_python_out={output_dir}",
        f"--pyi_out={output_dir}",
        str(proto_file),
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("Proto generation failed")
        sys.exit(1)

    # Fix imports in generated files
    grpc_file = output_dir / "stems_pb2_grpc.py"
    if grpc_file.exists():
        content = grpc_file.read_text()
        content = content.replace(
            "import stems_pb2",
            "from . import stems_pb2"
        )
        grpc_file.write_text(content)

    print("Proto generation complete!")


if __name__ == "__main__":
    main()
```

**Step 2: Create scripts/generate_proto.ps1**

```powershell
# Generate C++ protobuf/gRPC code from stems.proto

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$protoDir = Join-Path $root "proto"
$outputDir = Join-Path $root "proxy-dll" "generated"

# Create output directory
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$protoFile = Join-Path $protoDir "stems.proto"

# Find protoc and grpc_cpp_plugin
$vcpkgRoot = $env:VCPKG_ROOT
if (-not $vcpkgRoot) {
    $vcpkgRoot = "C:\vcpkg"
}

$protoc = Join-Path $vcpkgRoot "installed\x64-windows\tools\protobuf\protoc.exe"
$grpcPlugin = Join-Path $vcpkgRoot "installed\x64-windows\tools\grpc\grpc_cpp_plugin.exe"

if (-not (Test-Path $protoc)) {
    Write-Error "protoc not found at $protoc. Install via: vcpkg install protobuf:x64-windows"
    exit 1
}

if (-not (Test-Path $grpcPlugin)) {
    Write-Error "grpc_cpp_plugin not found at $grpcPlugin. Install via: vcpkg install grpc:x64-windows"
    exit 1
}

# Generate protobuf
Write-Host "Generating protobuf..."
& $protoc `
    --proto_path=$protoDir `
    --cpp_out=$outputDir `
    $protoFile

if ($LASTEXITCODE -ne 0) {
    Write-Error "Protobuf generation failed"
    exit 1
}

# Generate gRPC
Write-Host "Generating gRPC..."
& $protoc `
    --proto_path=$protoDir `
    --grpc_out=$outputDir `
    --plugin=protoc-gen-grpc=$grpcPlugin `
    $protoFile

if ($LASTEXITCODE -ne 0) {
    Write-Error "gRPC generation failed"
    exit 1
}

Write-Host "Proto generation complete!"
Write-Host "Output: $outputDir"
```

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: proto generation scripts for Python and C++"
```

---

## Task 6: Installation Scripts

**Files:**
- Create: `scripts/install_proxy.ps1`
- Create: `scripts/install_server.sh`
- Create: `README.md`

**Step 1: Create scripts/install_proxy.ps1**

```powershell
# Install VDJ GPU Proxy DLL

param(
    [string]$VdjPath = "",
    [string]$ServerAddress = "127.0.0.1",
    [int]$ServerPort = 50051
)

$ErrorActionPreference = "Stop"

# Find VirtualDJ installation
if (-not $VdjPath) {
    $possiblePaths = @(
        "$env:ProgramFiles\VirtualDJ",
        "${env:ProgramFiles(x86)}\VirtualDJ",
        "$env:LOCALAPPDATA\VirtualDJ"
    )

    foreach ($path in $possiblePaths) {
        if (Test-Path (Join-Path $path "VirtualDJ.exe")) {
            $VdjPath = $path
            break
        }
    }
}

if (-not $VdjPath -or -not (Test-Path $VdjPath)) {
    Write-Error "VirtualDJ installation not found. Please specify -VdjPath"
    exit 1
}

Write-Host "VirtualDJ found at: $VdjPath"

$ortDll = Join-Path $VdjPath "onnxruntime.dll"
$ortRealDll = Join-Path $VdjPath "onnxruntime_real.dll"
$proxyDll = Join-Path $PSScriptRoot "..\build\Release\onnxruntime.dll"

# Backup original
if (Test-Path $ortDll) {
    if (-not (Test-Path $ortRealDll)) {
        Write-Host "Backing up original onnxruntime.dll..."
        Copy-Item $ortDll $ortRealDll
    }
}

# Copy proxy DLL
if (-not (Test-Path $proxyDll)) {
    Write-Error "Proxy DLL not found. Build the project first."
    exit 1
}

Write-Host "Installing proxy DLL..."
Copy-Item $proxyDll $ortDll -Force

# Configure registry
Write-Host "Configuring settings..."
$regPath = "HKCU:\Software\VDJ-GPU-Proxy"
if (-not (Test-Path $regPath)) {
    New-Item -Path $regPath -Force | Out-Null
}

Set-ItemProperty -Path $regPath -Name "ServerAddress" -Value $ServerAddress
Set-ItemProperty -Path $regPath -Name "ServerPort" -Value $ServerPort
Set-ItemProperty -Path $regPath -Name "Enabled" -Value 1

Write-Host ""
Write-Host "Installation complete!"
Write-Host "Server: ${ServerAddress}:${ServerPort}"
Write-Host ""
Write-Host "To uninstall, run: .\uninstall_proxy.ps1"
```

**Step 2: Create scripts/uninstall_proxy.ps1**

```powershell
# Uninstall VDJ GPU Proxy DLL

param(
    [string]$VdjPath = ""
)

$ErrorActionPreference = "Stop"

# Find VirtualDJ installation
if (-not $VdjPath) {
    $possiblePaths = @(
        "$env:ProgramFiles\VirtualDJ",
        "${env:ProgramFiles(x86)}\VirtualDJ",
        "$env:LOCALAPPDATA\VirtualDJ"
    )

    foreach ($path in $possiblePaths) {
        if (Test-Path (Join-Path $path "VirtualDJ.exe")) {
            $VdjPath = $path
            break
        }
    }
}

if (-not $VdjPath -or -not (Test-Path $VdjPath)) {
    Write-Error "VirtualDJ installation not found."
    exit 1
}

$ortDll = Join-Path $VdjPath "onnxruntime.dll"
$ortRealDll = Join-Path $VdjPath "onnxruntime_real.dll"

# Restore original
if (Test-Path $ortRealDll) {
    Write-Host "Restoring original onnxruntime.dll..."
    Copy-Item $ortRealDll $ortDll -Force
    Remove-Item $ortRealDll
}

# Remove registry settings
$regPath = "HKCU:\Software\VDJ-GPU-Proxy"
if (Test-Path $regPath) {
    Remove-Item -Path $regPath -Recurse
}

Write-Host "Uninstall complete!"
```

**Step 3: Create scripts/install_server.sh**

```bash
#!/bin/bash
# Install VDJ Stems Server on GPU machine

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Installing VDJ Stems Server..."

# Check Python version
python3 --version || { echo "Python 3 required"; exit 1; }

# Check CUDA
if command -v nvidia-smi &> /dev/null; then
    echo "CUDA GPU detected:"
    nvidia-smi --query-gpu=name,memory.total --format=csv
else
    echo "Warning: No NVIDIA GPU detected. Server will use CPU."
fi

# Create virtual environment
cd "$ROOT_DIR/server"
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -e .

# Generate proto files
cd "$ROOT_DIR"
pip install grpcio-tools
python scripts/generate_proto.py

echo ""
echo "Installation complete!"
echo ""
echo "To start the server:"
echo "  cd $ROOT_DIR/server"
echo "  source venv/bin/activate"
echo "  vdj-stems-server --host 0.0.0.0 --port 50051"
```

**Step 4: Create README.md**

```markdown
# VDJ-GPU-Proxy

Offload VirtualDJ's stems separation to a remote GPU server.

## Architecture

```
┌─────────────────────────┐     gRPC      ┌─────────────────────────┐
│   Local PC (VirtualDJ)  │◄─────────────►│  GPU Server (Demucs)    │
│   onnxruntime.dll proxy │               │  RTX 3080/4080          │
└─────────────────────────┘               └─────────────────────────┘
```

## Requirements

### Local (VirtualDJ) Machine
- Windows 10/11
- VirtualDJ 2023+
- Visual C++ Redistributable 2019+

### GPU Server
- NVIDIA GPU with 6GB+ VRAM
- CUDA 11.8+
- Python 3.10+

## Quick Start

### 1. Build the Proxy DLL (on Windows)

```powershell
# Install vcpkg dependencies
vcpkg install grpc:x64-windows protobuf:x64-windows

# Generate proto files
.\scripts\generate_proto.ps1

# Build
cmake -B build -S . -DCMAKE_TOOLCHAIN_FILE=C:/vcpkg/scripts/buildsystems/vcpkg.cmake
cmake --build build --config Release
```

### 2. Install Server (on GPU machine)

```bash
./scripts/install_server.sh
```

### 3. Start Server

```bash
cd server
source venv/bin/activate
vdj-stems-server --host 0.0.0.0 --port 50051
```

### 4. Install Proxy (on VirtualDJ machine)

```powershell
.\scripts\install_proxy.ps1 -ServerAddress "192.168.1.100" -ServerPort 50051
```

### 5. Launch VirtualDJ

Stems processing will now be offloaded to your GPU server!

## Configuration

Registry key: `HKCU\Software\VDJ-GPU-Proxy`

| Value | Type | Description |
|-------|------|-------------|
| ServerAddress | REG_SZ | IP/hostname of GPU server |
| ServerPort | REG_DWORD | Port (default: 50051) |
| Enabled | REG_DWORD | 1 = enabled, 0 = disabled |

## Troubleshooting

### Check server connectivity
```bash
grpcurl -plaintext 192.168.1.100:50051 vdj.stems.StemsInference/GetServerInfo
```

### View proxy logs
Enable DebugView or check Windows Event Viewer for `VDJ-GPU-Proxy` messages.

### Fallback to local processing
Set `Enabled` to 0 in registry, or rename `onnxruntime_real.dll` back to `onnxruntime.dll`.

## License

MIT
```

**Step 5: Commit**

```bash
git add -A
git commit -m "docs: installation scripts and README"
```

---

## Task 7: Full OrtApi Header Integration

**Files:**
- Download: `proxy-dll/include/onnxruntime_c_api.h`
- Modify: `proxy-dll/src/ort_hooks.cpp`
- Modify: `proxy-dll/src/tensor_utils.cpp`

**Step 1: Download ONNX Runtime C API header**

```bash
curl -L -o proxy-dll/include/onnxruntime_c_api.h \
  https://raw.githubusercontent.com/microsoft/onnxruntime/v1.16.0/include/onnxruntime/core/session/onnxruntime_c_api.h
```

**Step 2: Update ort_hooks.cpp with real OrtApi**

Replace the placeholder OrtApi struct with includes from the real header and implement proper function pointer access.

**Step 3: Update tensor_utils.cpp with real implementations**

Implement `ExtractTensorData` and `CreateOrtValue` using actual OrtApi function pointers.

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: integrate real ONNX Runtime C API header"
```

---

## Task 8: Integration Testing

**Files:**
- Create: `tests/test_grpc_roundtrip.py`
- Create: `tests/test_tensor_serialization.cpp`

**Step 1: Create tests/test_grpc_roundtrip.py**

```python
"""Test gRPC roundtrip with mock data."""

import numpy as np
import grpc
import sys
sys.path.insert(0, "server/src")

from vdj_stems_server import stems_pb2, stems_pb2_grpc


def test_server_info():
    """Test GetServerInfo RPC."""
    channel = grpc.insecure_channel("localhost:50051")
    stub = stems_pb2_grpc.StemsInferenceStub(channel)

    response = stub.GetServerInfo(stems_pb2.Empty())

    assert response.ready
    assert response.version == "1.0.0"
    print(f"Server ready: {response.model_name}, GPU: {response.gpu_memory_mb}MB")


def test_inference_roundtrip():
    """Test full inference roundtrip."""
    channel = grpc.insecure_channel("localhost:50051")
    stub = stems_pb2_grpc.StemsInferenceStub(channel)

    # Create test audio (10 seconds of stereo noise)
    sample_rate = 44100
    duration = 10
    audio = np.random.randn(2, sample_rate * duration).astype(np.float32)

    # Build request
    request = stems_pb2.InferenceRequest(
        session_id=1,
        input_names=["audio"],
        inputs=[
            stems_pb2.Tensor(
                shape=stems_pb2.TensorShape(dims=[1, 2, sample_rate * duration]),
                dtype=1,  # float32
                data=audio.tobytes(),
            )
        ],
        output_names=["stems"],
    )

    # Run inference
    response = stub.RunInference(request)

    assert response.status == 0, f"Error: {response.error_message}"
    assert len(response.outputs) == 1

    # Check output shape
    output = response.outputs[0]
    shape = list(output.shape.dims)
    print(f"Output shape: {shape}")

    # Should be (1, 4, 2, samples) - batch, stems, channels, samples
    assert shape[0] == 1
    assert shape[1] == 4  # drums, bass, other, vocals
    assert shape[2] == 2  # stereo

    print("Inference roundtrip successful!")


if __name__ == "__main__":
    test_server_info()
    test_inference_roundtrip()
```

**Step 2: Run tests**

```bash
# Start server first
cd server && source venv/bin/activate && vdj-stems-server &

# Run tests
python tests/test_grpc_roundtrip.py
```

**Step 3: Commit**

```bash
git add -A
git commit -m "test: gRPC roundtrip integration test"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Project structure & build | CMakeLists, proto, pyproject |
| 2 | Proxy DLL core | dllmain, ort_hooks |
| 3 | gRPC client | grpc_client, tensor_utils |
| 4 | Python server | inference, grpc_server, main |
| 5 | Proto generation | generate_proto scripts |
| 6 | Installation | install/uninstall scripts, README |
| 7 | OrtApi integration | Real header, implementations |
| 8 | Integration testing | Test scripts |

**Total estimated tasks: 8 major, ~40 bite-sized steps**
