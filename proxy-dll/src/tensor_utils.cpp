#include "tensor_utils.h"
#include "../include/onnxruntime_c_api.h"
#include <cstring>
#include <cstdlib>
#include <cmath>
#include <cstdio>
#include <windows.h>

namespace vdj {

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

TensorData ExtractTensorData(const OrtApi* api, const OrtValue* value) {
    TensorData result;
    
    // Null parameter checks
    if (!api || !value) {
        return result;
    }
    
    OrtTensorTypeAndShapeInfo* info = nullptr;
    
    OrtStatus* status = api->GetTensorTypeAndShape(value, &info);
    if (status) {
        api->ReleaseStatus(status);
        return result;
    }

    size_t num_dims = 0;
    status = api->GetDimensionsCount(info, &num_dims);
    if (status) {
        api->ReleaseStatus(status);
        api->ReleaseTensorTypeAndShapeInfo(info);
        return result;
    }

    result.shape.resize(num_dims);
    status = api->GetDimensions(info, result.shape.data(), num_dims);
    if (status) {
        api->ReleaseStatus(status);
        api->ReleaseTensorTypeAndShapeInfo(info);
        return result;
    }

    ONNXTensorElementDataType dtype;
    status = api->GetTensorElementType(info, &dtype);
    if (status) {
        api->ReleaseStatus(status);
        api->ReleaseTensorTypeAndShapeInfo(info);
        return result;
    }
    result.dtype = static_cast<int32_t>(dtype);

    size_t element_count = 0;
    status = api->GetTensorShapeElementCount(info, &element_count);
    if (status) {
        api->ReleaseStatus(status);
        api->ReleaseTensorTypeAndShapeInfo(info);
        return result;
    }

    void* data_ptr = nullptr;
    status = api->GetTensorMutableData(const_cast<OrtValue*>(value), &data_ptr);
    if (status) {
        api->ReleaseStatus(status);
        api->ReleaseTensorTypeAndShapeInfo(info);
        return result;
    }

    if (data_ptr && element_count > 0) {
        size_t element_size = GetElementSize(result.dtype);
        result.data.resize(element_count * element_size);
        memcpy(result.data.data(), data_ptr, result.data.size());
    }

    api->ReleaseTensorTypeAndShapeInfo(info);
    return result;
}

OrtValue* CreateOrtValue(
    const OrtApi* api,
    const TensorData& tensor,
    void** out_buffer
) {
    if (!api || !out_buffer) {
        return nullptr;
    }

    *out_buffer = nullptr;

    size_t element_size = GetElementSize(tensor.dtype);
    if (element_size == 0) {
        return nullptr;
    }

    size_t total_elements = 1;
    for (int64_t dim : tensor.shape) {
        if (dim <= 0) {
            return nullptr;
        }
        if (total_elements > SIZE_MAX / static_cast<size_t>(dim)) {
            return nullptr;
        }
        total_elements *= static_cast<size_t>(dim);
    }

    if (total_elements > SIZE_MAX / element_size) {
        return nullptr;
    }
    size_t buffer_size = total_elements * element_size;

    if (tensor.data.size() < buffer_size) {
        return nullptr;
    }

    // Validate data - check for NaN/Inf in float data
    if (tensor.dtype == ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT) {
        const float* fdata = reinterpret_cast<const float*>(tensor.data.data());
        size_t num_floats = buffer_size / sizeof(float);
        bool has_invalid = false;
        float min_val = fdata[0], max_val = fdata[0];
        for (size_t i = 0; i < num_floats && i < 1000; i++) {  // Check first 1000
            if (std::isnan(fdata[i]) || std::isinf(fdata[i])) {
                has_invalid = true;
                break;
            }
            if (fdata[i] < min_val) min_val = fdata[i];
            if (fdata[i] > max_val) max_val = fdata[i];
        }
        // Log data stats for debugging (will be visible in DebugView)
        char msg[256];
        snprintf(msg, sizeof(msg), "VDJ-GPU-Proxy: Tensor data stats - min=%.4f max=%.4f invalid=%d\n",
                 min_val, max_val, has_invalid ? 1 : 0);
        OutputDebugStringA(msg);
    }

    // Use ORT's internal allocator - this is what the session uses
    OrtAllocator* allocator = nullptr;
    OrtStatus* status = api->GetAllocatorWithDefaultOptions(&allocator);
    if (status) {
        api->ReleaseStatus(status);
        return nullptr;
    }

    // Create tensor using ORT's allocator (internally managed memory)
    OrtValue* ort_value = nullptr;
    status = api->CreateTensorAsOrtValue(
        allocator,
        tensor.shape.data(),
        tensor.shape.size(),
        static_cast<ONNXTensorElementDataType>(tensor.dtype),
        &ort_value
    );

    if (status) {
        api->ReleaseStatus(status);
        return nullptr;
    }

    // Get pointer to internal buffer and copy our data
    void* ort_data = nullptr;
    status = api->GetTensorMutableData(ort_value, &ort_data);
    if (status) {
        api->ReleaseStatus(status);
        api->ReleaseValue(ort_value);
        return nullptr;
    }

    // Copy our data into ORT's buffer
    memcpy(ort_data, tensor.data.data(), buffer_size);

    // out_buffer is not used with this approach, but keep for API compatibility
    *out_buffer = nullptr;

    return ort_value;
}

}
