cmake_minimum_required(VERSION 3.20)
project(laya_cpp VERSION 0.0.0 LANGUAGES CXX)

option(LAYA_BUILD_TESTS "Build the GoogleTest suite" ON)
option(LAYA_ONNX "Build the ONNX Runtime backend (not implemented yet)" OFF)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Floating point must match the Python reference bit for bit: no fused multiply-add, no fast math.
if(MSVC)
  set(LAYA_FP_FLAGS /fp:precise)
  set(LAYA_WARN_FLAGS /W4 /WX)
else()
  set(LAYA_FP_FLAGS -ffp-contract=off -fno-fast-math)
  set(LAYA_WARN_FLAGS -Wall -Wextra -Wpedantic -Werror)
endif()

function(laya_target_flags target)
  target_compile_options(${target} PRIVATE ${LAYA_FP_FLAGS} ${LAYA_WARN_FLAGS})
endfunction()

add_library(laya src/version.cpp)
target_include_directories(laya PUBLIC include)
laya_target_flags(laya)

if(LAYA_ONNX)
  message(FATAL_ERROR "LAYA_ONNX is not implemented yet")
endif()

if(LAYA_BUILD_TESTS)
  include(FetchContent)
  # Pinned by commit, not tag: tags move. This is the commit of googletest v1.18.0.
  FetchContent_Declare(googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG 063de7e9578f82b369302001269680b4b1553359)
  set(INSTALL_GTEST OFF CACHE BOOL "" FORCE)
  set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
  FetchContent_MakeAvailable(googletest)

  enable_testing()
  add_executable(laya_tests tests/version_test.cpp)
  target_link_libraries(laya_tests PRIVATE laya GTest::gtest_main)
  laya_target_flags(laya_tests)

  include(GoogleTest)
  gtest_discover_tests(laya_tests)

  # compile_commands.json is the record of what the compiler was really given, so this fails if
  # the floating point flags are dropped from either target.
  # Spelled out here, not derived from LAYA_FP_FLAGS, so dropping a flag above cannot also drop the
  # requirement.
  if(MSVC)
    set(LAYA_FP_FLAGS_ARG "/fp:precise")
  else()
    set(LAYA_FP_FLAGS_ARG "-ffp-contract=off|-fno-fast-math")
  endif()
  add_test(NAME compile_flags
    COMMAND ${CMAKE_COMMAND}
      -DCOMPILE_COMMANDS=${CMAKE_BINARY_DIR}/compile_commands.json
      -DSOURCE_DIR=${CMAKE_CURRENT_SOURCE_DIR}
      -DREQUIRED_FLAGS=${LAYA_FP_FLAGS_ARG}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/cmake/check_compile_flags.cmake)
endif()
