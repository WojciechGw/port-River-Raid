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
    set(RIVER_FOOTER_IMAGE ${CMAKE_CURRENT_BINARY_DIR}/demo_footer.bin)
    set(RIVER_FOOTER_HEADER ${CMAKE_CURRENT_BINARY_DIR}/demo_footer.h)
    set(RIVER_COVER_IMAGE ${CMAKE_CURRENT_BINARY_DIR}/cover.bin)
    set(RIVER_COVER_FADES ${CMAKE_CURRENT_BINARY_DIR}/cover_fade.bin)
    set(RIVER_COVER_PROMPT ${CMAKE_CURRENT_BINARY_DIR}/cover_prompt.bin)
    set(RIVER_COVER_INCLUDE ${CMAKE_CURRENT_BINARY_DIR}/cover.inc)
    add_custom_command(OUTPUT ${RIVER_FOOTER_IMAGE} ${RIVER_FOOTER_HEADER}
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/make_demo_footer.py
            ${CMAKE_CURRENT_SOURCE_DIR}/src/demo-footer.json
            ${CMAKE_CURRENT_SOURCE_DIR}/src/graphics.h
            ${RIVER_FOOTER_IMAGE} ${RIVER_FOOTER_HEADER}
        DEPENDS src/demo-footer.json src/graphics.h tools/make_demo_footer.py
        VERBATIM)
    add_custom_command(OUTPUT ${RIVER_COVER_IMAGE} ${RIVER_COVER_FADES}
        ${RIVER_COVER_PROMPT} ${RIVER_COVER_INCLUDE}
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/make_cover.py
            ${CMAKE_CURRENT_SOURCE_DIR}/assets/cover.bmp
            ${RIVER_COVER_IMAGE} ${RIVER_COVER_FADES} ${RIVER_COVER_PROMPT} ${RIVER_COVER_INCLUDE}
            ${RIVER_FOOTER_IMAGE}
        DEPENDS assets/cover.bmp tools/make_cover.py ${RIVER_FOOTER_IMAGE}
        VERBATIM)
    add_custom_command(OUTPUT ${RIVER_CORE}
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/port_original.py
            ${CMAKE_CURRENT_SOURCE_DIR}/original/riverraid.asm ${RIVER_CORE}
        DEPENDS original/riverraid.asm tools/port_original.py
        VERBATIM)
    add_executable(riverride
        src/riverraid.asm src/cover.asm src/main.c ${RIVER_CORE}
        ${RIVER_FOOTER_HEADER} ${RIVER_COVER_INCLUDE})
    target_link_options(riverride PRIVATE -C ${CMAKE_CURRENT_SOURCE_DIR}/src/riverraid.cfg)
    set_property(TARGET riverride APPEND PROPERTY LINK_DEPENDS
        ${CMAKE_CURRENT_SOURCE_DIR}/src/riverraid.cfg)
    target_include_directories(riverride PRIVATE ${CMAKE_CURRENT_BINARY_DIR})
    # Keep source symbols for DAP and memory fixtures even in optimized builds.
    target_compile_options(riverride PRIVATE -g)
    option(RIVER_PROFILE "Measure frame phases in XRAM (adds timing overhead)" OFF)
    if(RIVER_PROFILE)
        target_compile_definitions(riverride PRIVATE RIVER_PROFILE)
    endif()
    rp6502_map(riverride src/xram.h "XRAM_.*")
    rp6502_asset(riverride help src/help.txt)
    # Named assets are read from ROM: on demand; they are not preloaded to XRAM.
    rp6502_asset(riverride cover.bin ${RIVER_COVER_IMAGE})
    rp6502_asset(riverride cover-fade.bin ${RIVER_COVER_FADES})
    rp6502_asset(riverride cover-prompt.bin ${RIVER_COVER_PROMPT})
    rp6502_asset(riverride demo-footer.bin ${RIVER_FOOTER_IMAGE})
    # Splash helpers use the free CPU RAM above the original 4 KiB reference ROM.
    rp6502_byproducts(riverride ${CMAKE_CURRENT_BINARY_DIR}/riverride.splash)
    rp6502_asset(riverride RAM(0xD000) ${CMAKE_CURRENT_BINARY_DIR}/riverride.splash)
    rp6502_byproducts(riverride ${CMAKE_CURRENT_BINARY_DIR}/riverride.rom)
    rp6502_asset(riverride RAM(0xC000) ${CMAKE_CURRENT_BINARY_DIR}/riverride.rom)
    rp6502_executable(riverride DATA 0x0300 RESET 0x0300)
    rp6502_web(riverride)
endif()
