# ONNX Runtime C API - Tensor Operations Documentation

## Overview

This document provides complete function signatures and usage patterns for 8 critical ONNX Runtime C API functions for tensor operations. All information is sourced directly from the official ONNX Runtime C API header file.

**Source**: [onnxruntime_c_api.h](https://github.com/microsoft/onnxruntime/blob/517e06c6807f946d6a8589f876db94bde2a49f21/include/onnxruntime/core/session/onnxruntime_c_api.h)

---

## Function Reference

### 1. GetTensorTypeAndShape

**Purpose**: Extract shape and type information from an OrtValue tensor

**Signature**:
```c
ORT_API2_STATUS(GetTensorTypeAndShape, 
    _In_ const OrtValue* value, 
    _Outptr_ OrtTensorTypeAndShapeInfo** out);
```

**Parameters**:
- `value`: OrtValue tensor (must be a tensor, not map/sequence)
- `out`: Output OrtTensorTypeAndShapeInfo (must free with ReleaseTensorTypeAndShapeInfo)

**Returns**: OrtStatus (NULL = success)

**Source**: [Line 1779](https://github.com/microsoft/onnxruntime/blob/517e06c6807f946d6a8589f876db94bde2a49f21/include/onnxruntime/core/session/onnxruntime_c_api.h#L1779)

---

### 2. GetDimensionsCount

**Purpose**: Get the number of dimensions in a tensor

**Signature**:
```c
ORT_API2_STATUS(GetDimensionsCount, 
    _In_ const OrtTensorTypeAndShapeInfo* info, 
    _Out_ size_t* out);
```

**Parameters**:
- `info`: OrtTensorTypeAndShapeInfo from GetTensorTypeAndShape
- `out`: Receives dimension count

**Returns**: OrtStatus (NULL = success)

**Source**: [Line 1726](https://github.com/microsoft/onnxruntime/blob/517e06c6807f946d6a8589f876db94bde2a49f21/include/onnxruntime/core/session/onnxruntime_c_api.h#L1726)

---

### 3. GetDimensions

**Purpose**: Get actual dimension values from tensor shape

**Signature**:
```c
ORT_API2_STATUS(GetDimensions, 
    _In_ const OrtTensorTypeAndShapeInfo* info, 
    _Out_ int64_t* dim_values,
    size_t dim_values_length);
```

**Parameters**:
- `info`: OrtTensorTypeAndShapeInfo from GetTensorTypeAndShape
- `dim_values`: Array to receive dimension values
- `dim_values_length`: Array size (use GetDimensionsCount to get this)

**Returns**: OrtStatus (NULL = success)

**Example**: For shape [2, 3, 4], dim_values will be {2, 3, 4}

**Source**: [Line 1736](https://github.com/microsoft/onnxruntime/blob/517e06c6807f946d6a8589f876db94bde2a49f21/include/onnxruntime/core/session/onnxruntime_c_api.h#L1736)

---

### 4. GetTensorElementType

**Purpose**: Get the data type of tensor elements

**Signature**:
```c
ORT_API2_STATUS(GetTensorElementType, 
    _In_ const OrtTensorTypeAndShapeInfo* info,
    _Out_ enum ONNXTensorElementDataType* out);
```

**Parameters**:
- `info`: OrtTensorTypeAndShapeInfo from GetTensorTypeAndShape
- `out`: Receives ONNXTensorElementDataType enum value

**Returns**: OrtStatus (NULL = success)

**Possible Values**:
```c
ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT      // float (32-bit)
ONNX_TENSOR_ELEMENT_DATA_TYPE_DOUBLE     // double (64-bit)
ONNX_TENSOR_ELEMENT_DATA_TYPE_INT32      // int32_t
ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64      // int64_t
ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT8      // uint8_t
ONNX_TENSOR_ELEMENT_DATA_TYPE_INT8       // int8_t
ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT16     // uint16_t
ONNX_TENSOR_ELEMENT_DATA_TYPE_INT16      // int16_t
ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT32     // uint32_t
ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT64     // uint64_t
ONNX_TENSOR_ELEMENT_DATA_TYPE_BOOL       // bool
ONNX_TENSOR_ELEMENT_DATA_TYPE_STRING     // std::string
ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT16    // float16
ONNX_TENSOR_ELEMENT_DATA_TYPE_BFLOAT16   // bfloat16
ONNX_TENSOR_ELEMENT_DATA_TYPE_COMPLEX64  // complex64
ONNX_TENSOR_ELEMENT_DATA_TYPE_COMPLEX128 // complex128
ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT8E4M3FN
ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT8E4M3FNUZ
ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT8E5M2
ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT8E5M2FNUZ
ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT4
ONNX_TENSOR_ELEMENT_DATA_TYPE_INT4
ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT4E2M1
```

**Source**: [Line 1714](https://github.com/microsoft/onnxruntime/blob/517e06c6807f946d6a8589f876db94bde2a49f21/include/onnxruntime/core/session/onnxruntime_c_api.h#L1714)

---

### 5. GetTensorShapeElementCount

**Purpose**: Get total number of elements in tensor (product of all dimensions)

**Signature**:
```c
ORT_API2_STATUS(GetTensorShapeElementCount, 
    _In_ const OrtTensorTypeAndShapeInfo* info, 
    _Out_ size_t* out);
```

**Parameters**:
- `info`: OrtTensorTypeAndShapeInfo from GetTensorTypeAndShape
- `out`: Receives total element count

**Returns**: OrtStatus (NULL = success)

**Behavior**:
- `[]` (0 dimensions) = 1
- `[1,3,4]` = 12
- `[2,0,4]` = 0
- `[-1,3,4]` = -1 (dynamic dimension)

**Source**: [Line 1766](https://github.com/microsoft/onnxruntime/blob/517e06c6807f946d6a8589f876db94bde2a49f21/include/onnxruntime/core/session/onnxruntime_c_api.h#L1766)

---

### 6. GetTensorMutableData

**Purpose**: Get pointer to raw tensor data for reading/writing

**Signature**:
```c
ORT_API2_STATUS(GetTensorMutableData, 
    _In_ OrtValue* value, 
    _Outptr_ void** out);
```

**Parameters**:
- `value`: OrtValue tensor (string tensors not supported)
- `out`: Receives pointer to internal storage

**Returns**: OrtStatus (NULL = success)

**Important**: Pointer is valid until OrtValue is destroyed

**Source**: [Line 1605](https://github.com/microsoft/onnxruntime/blob/517e06c6807f946d6a8589f876db94bde2a49f21/include/onnxruntime/core/session/onnxruntime_c_api.h#L1605)

---

### 7. CreateMemoryInfo

**Purpose**: Create memory information descriptor for CPU or device memory

**Signature**:
```c
ORT_API2_STATUS(CreateMemoryInfo, 
    _In_ const char* name, 
    enum OrtAllocatorType type, 
    int id,
    enum OrtMemType mem_type, 
    _Outptr_ OrtMemoryInfo** out);
```

**Parameters**:
- `name`: Device name ("Cpu", "Cuda", "DML", "TensorRT", etc.)
- `type`: Allocator type (OrtDeviceAllocator=0, OrtArenaAllocator=1, etc.)
- `id`: Device ID (0 for CPU, GPU device index for GPU)
- `mem_type`: Memory type (OrtMemTypeDefault=0, OrtMemTypeCPU=-1, etc.)
- `out`: Newly created OrtMemoryInfo (must free with ReleaseMemoryInfo)

**Returns**: OrtStatus (NULL = success)

**Allocator Types**:
```c
OrtInvalidAllocator = -1
OrtDeviceAllocator = 0
OrtArenaAllocator = 1
OrtReadOnlyAllocator = 2
```

**Memory Types**:
```c
OrtMemTypeCPUInput = -2      // CPU memory used by non-CPU execution provider
OrtMemTypeCPUOutput = -1     // CPU accessible memory from non-CPU execution provider
OrtMemTypeCPU = OrtMemTypeCPUOutput
OrtMemTypeDefault = 0        // Default allocator for execution provider
```

**Source**: [Line 1813](https://github.com/microsoft/onnxruntime/blob/517e06c6807f946d6a8589f876db94bde2a49f21/include/onnxruntime/core/session/onnxruntime_c_api.h#L1813)

---

### 8. CreateTensorWithDataAsOrtValue

**Purpose**: Create OrtValue tensor from existing data buffer

**Signature**:
```c
ORT_API2_STATUS(CreateTensorWithDataAsOrtValue, 
    _In_ const OrtMemoryInfo* info, 
    _Inout_ void* p_data,
    size_t p_data_len, 
    _In_ const int64_t* shape, 
    size_t shape_len, 
    ONNXTensorElementDataType type,
    _Outptr_ OrtValue** out);
```

**Parameters**:
- `info`: OrtMemoryInfo from CreateMemoryInfo or CreateCpuMemoryInfo
- `p_data`: Pointer to data buffer
- `p_data_len`: Size of data buffer in bytes
- `shape`: Array of dimension values
- `shape_len`: Number of dimensions
- `type`: Data type (ONNXTensorElementDataType)
- `out`: Newly created OrtValue (must free with ReleaseValue)

**Returns**: OrtStatus (NULL = success)

**Important**:
- User is responsible for managing buffer lifetime
- Buffer must remain valid for lifetime of OrtValue
- OrtValue does NOT take ownership of buffer

**Source**: [Line 1582](https://github.com/microsoft/onnxruntime/blob/517e06c6807f946d6a8589f876db94bde2a49f21/include/onnxruntime/core/session/onnxruntime_c_api.h#L1582)

---

## Complete Usage Example

```c
#include <onnxruntime_c_api.h>
#include <stdlib.h>
#include <stdio.h>

int main() {
    const OrtApi* api = OrtGetApiBase()->GetApi(ORT_API_VERSION);
    
    // Assume output_
