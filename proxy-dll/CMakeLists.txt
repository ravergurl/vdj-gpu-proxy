add_library(onnxruntime SHARED
    src/dllmain.cpp
    src/ort_hooks.cpp
    src/grpc_client.cpp
    src/tensor_utils.cpp
    src/logger.cpp
)

target_include_directories(onnxruntime PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# Platform-specific link libraries
if(WIN32)
    target_link_libraries(onnxruntime PRIVATE kernel32 shell32 advapi32)
endif()

target_link_libraries(onnxruntime PRIVATE
    stems_proto
    gRPC::grpc++
    protobuf::libprotobuf
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
