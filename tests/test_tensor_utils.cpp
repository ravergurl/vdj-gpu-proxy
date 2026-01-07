#include <gtest/gtest.h>
#include "tensor_utils.h"

namespace vdj {
namespace {

TEST(TensorUtilsTest, GetElementSizeFloat) {
    EXPECT_EQ(GetElementSize(ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT), 4);
}

TEST(TensorUtilsTest, GetElementSizeDouble) {
    EXPECT_EQ(GetElementSize(ONNX_TENSOR_ELEMENT_DATA_TYPE_DOUBLE), 8);
}

TEST(TensorUtilsTest, GetElementSizeInt64) {
    EXPECT_EQ(GetElementSize(ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64), 8);
}

TEST(TensorUtilsTest, GetElementSizeInt32) {
    EXPECT_EQ(GetElementSize(ONNX_TENSOR_ELEMENT_DATA_TYPE_INT32), 4);
}

TEST(TensorUtilsTest, GetElementSizeInt16) {
    EXPECT_EQ(GetElementSize(ONNX_TENSOR_ELEMENT_DATA_TYPE_INT16), 2);
}

TEST(TensorUtilsTest, GetElementSizeInt8) {
    EXPECT_EQ(GetElementSize(ONNX_TENSOR_ELEMENT_DATA_TYPE_INT8), 1);
}

TEST(TensorUtilsTest, GetElementSizeUint8) {
    EXPECT_EQ(GetElementSize(ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT8), 1);
}

TEST(TensorUtilsTest, GetElementSizeUndefined) {
    EXPECT_EQ(GetElementSize(ONNX_TENSOR_ELEMENT_DATA_TYPE_UNDEFINED), 0);
}

TEST(TensorUtilsTest, GetElementSizeUnknown) {
    EXPECT_EQ(GetElementSize(999), 0);
}

TEST(TensorUtilsTest, ExtractTensorDataNullApi) {
    TensorData result = ExtractTensorData(nullptr, nullptr);
    EXPECT_TRUE(result.shape.empty());
    EXPECT_TRUE(result.data.empty());
}

TEST(TensorUtilsTest, CreateOrtValueNullApi) {
    TensorData td;
    td.dtype = ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT;
    td.shape = {1, 2, 3};
    td.data.resize(24);
    
    void* buffer = nullptr;
    OrtValue* result = CreateOrtValue(nullptr, td, &buffer);
    EXPECT_EQ(result, nullptr);
    EXPECT_EQ(buffer, nullptr);
}

TEST(TensorUtilsTest, CreateOrtValueNullBuffer) {
    TensorData td;
    td.dtype = ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT;
    td.shape = {1, 2, 3};
    td.data.resize(24);
    
    OrtValue* result = CreateOrtValue(nullptr, td, nullptr);
    EXPECT_EQ(result, nullptr);
}

TEST(TensorUtilsTest, CreateOrtValueInvalidDtype) {
    TensorData td;
    td.dtype = 999;
    td.shape = {1, 2, 3};
    td.data.resize(24);
    
    void* buffer = nullptr;
    OrtValue* result = CreateOrtValue(nullptr, td, &buffer);
    EXPECT_EQ(result, nullptr);
}

TEST(TensorUtilsTest, CreateOrtValueZeroDimension) {
    TensorData td;
    td.dtype = ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT;
    td.shape = {1, 0, 3};
    td.data.resize(24);
    
    void* buffer = nullptr;
    OrtValue* result = CreateOrtValue(nullptr, td, &buffer);
    EXPECT_EQ(result, nullptr);
}

TEST(TensorUtilsTest, CreateOrtValueNegativeDimension) {
    TensorData td;
    td.dtype = ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT;
    td.shape = {1, -1, 3};
    td.data.resize(24);
    
    void* buffer = nullptr;
    OrtValue* result = CreateOrtValue(nullptr, td, &buffer);
    EXPECT_EQ(result, nullptr);
}

TEST(TensorUtilsTest, CreateOrtValueInsufficientData) {
    TensorData td;
    td.dtype = ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT;
    td.shape = {2, 3, 4};
    td.data.resize(10);
    
    void* buffer = nullptr;
    OrtValue* result = CreateOrtValue(nullptr, td, &buffer);
    EXPECT_EQ(result, nullptr);
}

}  // namespace
}  // namespace vdj
