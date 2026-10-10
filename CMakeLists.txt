cmake_minimum_required(VERSION 3.21)

include(${CMAKE_CURRENT_LIST_DIR}/tools/rp6502.cmake)

if(RP6502_BASIC)
    project(MY-RP6502-PROJECT BASIC)
    add_executable(hello)
    rp6502_asset(hello help src/help.txt)
    rp6502_asset(hello hello.bas src/main.bas)
    rp6502_basic(hello hello.bas)
    rp6502_web(hello)
else()
    project(RIVER-RAID C ASM)
    if(NOT CC65_TARGET_SYSTEM)
        message(FATAL_ERROR "River Raid uses ca65. Select cc65/Release or cc65/Debug.")
    endif()
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    set(RIVER_CORE ${CMAKE_CURRENT_BINARY_DIR}/original_core.asm)
    add_custom_command(OUTPUT ${RIVER_CORE}
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/port_original.py
            ${CMAKE_CURRENT_SOURCE_DIR}/original/riverraid.asm ${RIVER_CORE}
        DEPENDS original/riverraid.asm tools/port_original.py
        VERBATIM)
    add_executable(riverride
        src/riverraid.asm src/main.c ${RIVER_CORE})
    target_link_options(riverride PRIVATE -C ${CMAKE_CURRENT_SOURCE_DIR}/src/riverraid.cfg)
    set_property(TARGET riverride APPEND PROPERTY LINK_DEPENDS
        ${CMAKE_CURRENT_SOURCE_DIR}/src/riverraid.cfg)
    target_include_directories(riverride PRIVATE ${CMAKE_CURRENT_BINARY_DIR})
    # Keep source symbols for DAP and memory fixtures even in optimized builds.
    target_compile_options(riverride PRIVATE -g)
    rp6502_map(riverride src/xram.h "XRAM_.*")
    rp6502_asset(riverride help src/help.txt)
    rp6502_byproducts(riverride ${CMAKE_CURRENT_BINARY_DIR}/riverride.rom)
    rp6502_asset(riverride RAM(0xC000) ${CMAKE_CURRENT_BINARY_DIR}/riverride.rom)
    rp6502_executable(riverride DATA 0x0300 RESET 0x0300)
    rp6502_web(riverride)
endif()
