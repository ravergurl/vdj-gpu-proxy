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
