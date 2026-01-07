find_package(GTest CONFIG REQUIRED)

add_executable(vdj_proxy_tests
    test_tensor_utils.cpp
    test_logger.cpp
)

target_include_directories(vdj_proxy_tests PRIVATE
    ${CMAKE_SOURCE_DIR}/proxy-dll/src
    ${CMAKE_SOURCE_DIR}/proxy-dll/include
)

target_link_libraries(vdj_proxy_tests PRIVATE
    GTest::gtest
    GTest::gtest_main
    stems_proto
    gRPC::grpc++
)

if(WIN32)
    target_link_libraries(vdj_proxy_tests PRIVATE kernel32 shell32 advapi32)
endif()

target_sources(vdj_proxy_tests PRIVATE
    ${CMAKE_SOURCE_DIR}/proxy-dll/src/tensor_utils.cpp
    ${CMAKE_SOURCE_DIR}/proxy-dll/src/logger.cpp
)

include(GoogleTest)
gtest_discover_tests(vdj_proxy_tests)
