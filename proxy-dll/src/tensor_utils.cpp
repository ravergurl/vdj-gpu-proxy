#include "tensor_utils.h"
#include "../include/onnxruntime_c_api.h"
#include <cstring>
#include <cstdlib>

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

    *out_buffer = malloc(buffer_size);
    if (!*out_buffer) {
        return nullptr;
    }

    memcpy(*out_buffer, tensor.data.data(), buffer_size);

    OrtMemoryInfo* mem_info = nullptr;
    OrtStatus* status = api->CreateMemoryInfo("Cpu", OrtArenaAllocator, 0, OrtMemTypeDefault, &mem_info);
    if (status) {
        api->ReleaseStatus(status);
        free(*out_buffer);
        *out_buffer = nullptr;
        return nullptr;
    }

    OrtValue* ort_value = nullptr;
    status = api->CreateTensorWithDataAsOrtValue(
        mem_info,
        *out_buffer,
        buffer_size,
        tensor.shape.data(),
        tensor.shape.size(),
        static_cast<ONNXTensorElementDataType>(tensor.dtype),
        &ort_value
    );

    api->ReleaseMemoryInfo(mem_info);

    if (status) {
        api->ReleaseStatus(status);
        free(*out_buffer);
        *out_buffer = nullptr;
        return nullptr;
    }

    return ort_value;
}

}
