cmake_minimum_required(VERSION 3.12)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/dist")

project(sssekai_streaming_hca_decoder)
add_executable (sssekai_streaming_hca_decoder "main.cpp" )
