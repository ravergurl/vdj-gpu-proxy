/*
 * ONNX Runtime C API - Complete Usage Examples
 * 
 * This file demonstrates how to use the 8 key tensor operation functions
 * from the ONNX Runtime C API.
 * 
 * Source: https://github.com/microsoft/onnxruntime/blob/main/include/onnxruntime/core/session/onnxruntime_c_api.h
 */

#include <onnxruntime_c_api.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ============================================================================
 * EXAMPLE 1: Reading Output Tensor Information
 * 
 * Demonstrates:
 * - GetTensorTypeAndShape
 * - GetDimensionsCount
 * - GetDimensions
 * - GetTensorElementType
 * - GetTensorShapeElementCount
 * - GetTensorMutableData
 * ============================================================================ */

void example_read_output_tensor(const OrtApi* api, OrtValue* output_tensor) {
    printf("\n=== EXAMPLE 1: Reading Output Tensor ===\n");
    
    // Step 1: Get tensor type and shape info
    OrtTensorTypeAndShapeInfo* tensor_info = NULL;
    OrtStatus* status = api->GetTensorTypeAndShape(output_tensor, &tensor_info);
    if (status != NULL) {
        fprintf(stderr, "GetTensorTypeAndShape failed: %s\n", api->GetErrorMessage(status));
        api->ReleaseStatus(status);
        return;
    }
    
    // Step 2: Get dimension count
    size_t num_dims = 0;
    status = api->GetDimensionsCount(tensor_info, &num_dims);
    if (status != NULL) {
        fprintf(stderr, "GetDimensionsCount failed\n");
        api->ReleaseStatus(status);
        api->ReleaseTensorTypeAndShapeInfo(tensor_info);
        return;
    }
    printf("Number of dimensions: %zu\n", num_dims);
    
    // Step 3: Get dimension values
    int64_t* dims = (int64_t*)malloc(num_dims * sizeof(int64_t));
    if (dims == NULL) {
        fprintf(stderr, "Memory allocation failed\n");
        api->ReleaseTensorTypeAndShapeInfo(tensor_info);
        return;
    }
    
    status = api->GetDimensions(tensor_info, dims, num_dims);
    if (status != NULL) {
        fprintf(stderr, "GetDimensions failed\n");
        api->ReleaseStatus(status);
        free(dims);
        api->ReleaseTensorTypeAndShapeInfo(tensor_info);
        return;
    }
    
    printf("Dimensions: [");
    for (size_t i = 0; i < num_dims; i++) {
        printf("%ld%s", dims[i], i < num_dims - 1 ? ", " : "");
    }
    printf("]\n");
    
    // Step 4: Get element type
    ONNXTensorElementDataType elem_type;
    status = api->GetTensorElementType(tensor_info, &elem_type);
    if (status != NULL) {
        fprintf(stderr, "GetTensorElementType failed\n");
        api->ReleaseStatus(status);
        free(dims);
        api->ReleaseTensorTypeAndShapeInfo(tensor_info);
        return;
    }
    
    const char* type_name = "UNKNOWN";
    switch (elem_type) {
        case ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT:
            type_name = "FLOAT (32-bit)";
            break;
        case ONNX_TENSOR_ELEMENT_DATA_TYPE_DOUBLE:
            type_name = "DOUBLE (64-bit)";
            break;
        case ONNX_TENSOR_ELEMENT_DATA_TYPE_INT32:
            type_name = "INT32";
            break;
        case ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64:
            type_name = "INT64";
            break;
        case ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT8:
            type_name = "UINT8";
            break;
        case ONNX_TENSOR_ELEMENT_DATA_TYPE_INT8:
            type_name = "INT8";
            break;
        default:
            type_name = "OTHER";
    }
    printf("Element type: %s (%d)\n", type_name, elem_type);
    
    // Step 5: Get total element count
    size_t element_count = 0;
    status = api->GetTensorShapeElementCount(tensor_info, &element_count);
    if (status != NULL) {
        fprintf(stderr, "GetTensorShapeElementCount failed\n");
        api->ReleaseStatus(status);
        free(dims);
        api->ReleaseTensorTypeAndShapeInfo(tensor_info);
        return;
    }
    printf("Total elements: %zu\n", element_count);
    
    // Step 6: Get pointer to tensor data
    float* tensor_data = NULL;
    status = api->GetTensorMutableData(output_tensor, (void**)&tensor_data);
    if (status != NULL) {
        fprintf(stderr, "GetTensorMutableData failed\n");
        api->ReleaseStatus(status);
        free(dims);
        api->ReleaseTensorTypeAndShapeInfo(tensor_info);
        return;
    }
    
    // Now you can read/write the tensor data
    printf("First 5 elements: ");
    size_t print_count = element_count < 5 ? element_count : 5;
    for (size_t i = 0; i < print_count; i++) {
        printf("%f%s", tensor_data[i], i < print_count - 1 ? ", " : "");
    }
    printf("\n");
    
    // Cleanup
    api->ReleaseTensorTypeAndShapeInfo(tensor_info);
    free(dims);
}

/* ============================================================================
 * EXAMPLE 2: Creating Input Tensor from Buffer
 * 
 * Demonstrates:
 * - CreateMemoryInfo
 * - CreateTensorWithDataAsOrtValue
 * ============================================================================ */

OrtValue* example_create_input_tensor(const OrtApi* api) {
    printf("\n=== EXAMPLE 2: Creating Input Tensor ===\n");
    
    // Step 1: Create memory info for CPU
    OrtMemoryInfo* memory_info = NULL;
    OrtStatus* status = api->CreateCpuMemoryInfo(OrtArenaAllocator, OrtMemTypeDefault, &memory_info);
    if (status != NULL) {
        fprintf(stderr, "CreateCpuMemoryInfo failed\n");
        api->ReleaseStatus(status);
        return NULL;
    }
    printf("Created CPU memory info\n");
    
    // Step 2: Prepare input data
    float input_data[] = {1.0f, 2.0f, 3.0f, 4.0f, 5.0f, 6.0f};
    int64_t input_shape[] = {2, 3};  // 2x3 matrix
    size_t input_data_len = 6 * sizeof(float);
    
    printf("Input shape: [2, 3]\n");
    printf("Input data: [");
    for (int i = 0; i < 6; i++) {
        printf("%f%s", input_data[i], i < 5 ? ", " : "");
    }
    printf("]\n");
    
    // Step 3: Create OrtValue tensor from buffer
    OrtValue* input_tensor = NULL;
    status = api->CreateTensorWithDataAsOrtValue(
        memory_info,
        input_data,
        input_data_len,
        input_shape,
        2,  // shape_len
        ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT,
        &input_tensor
    );
    
    if (status != NULL) {
        fprintf(stderr, "CreateTensorWithDataAsOrtValue failed\n");
        api->ReleaseStatus(status);
        api->ReleaseMemoryInfo(memory_info);
        return NULL;
    }
    printf("Created input tensor successfully\n");
    
    // Note: We don't release memory_info here because it's still needed
    // In a real application, you would manage its lifetime appropriately
    api->ReleaseMemoryInfo(memory_info);
    
    return input_tensor;
}

/* ============================================================================
 * EXAMPLE 3: Complete Inference Loop
 * 
 * Demonstrates the full workflow:
 * 1. Create input tensor
 * 2. Run inference
 * 3. Read output tensor
 * 4. Cleanup
 * ============================================================================ */

void example_complete_inference(const OrtApi* api, OrtSession* session) {
    printf("\n=== EXAMPLE 3: Complete Inference Loop ===\n");
    
    // Create input tensor
    OrtMemoryInfo* memory_info = NULL;
    OrtStatus* status = api->CreateCpuMemoryInfo(OrtArenaAllocator, OrtMemTypeDefault, &memory_info);
    if (status != NULL) {
        fprintf(stderr, "CreateCpuMemoryInfo failed\n");
        api->ReleaseStatus(status);
        return;
    }
    
    // Prepare input data
    float input_data[] = {1.0f, 2.0f, 3.0f};
    int64_t input_shape[] = {1, 3};
    OrtValue* input_tensor = NULL;
    
    status = api->CreateTensorWithDataAsOrtValue(
        memory_info,
        input_data,
        3 * sizeof(float),
        input_shape,
        2,
        ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT,
        &input_tensor
    );
    
    if (status != NULL) {
        fprintf(stderr, "CreateTensorWithDataAsOrtValue failed\n");
        api->ReleaseStatus(status);
        api->ReleaseMemoryInfo(memory_info);
        return;
    }
    
    printf("Created input tensor\n");
    
    // Run inference (ass
