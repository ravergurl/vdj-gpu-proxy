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
    PLUGIN "protoc-gen-grpc=$<TARGET_FILE:gRPC::grpc_cpp_plugin>"
)
add_dependencies(stems_proto gRPC::grpc_cpp_plugin)

target_include_directories(stems_proto PUBLIC ${CMAKE_CURRENT_BINARY_DIR})
