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
    set(RIVER_MOUNTAINS ${CMAKE_CURRENT_BINARY_DIR}/mountains.h)
    add_custom_command(OUTPUT ${RIVER_MOUNTAINS}
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/pack_mountains.py
            ${CMAKE_CURRENT_SOURCE_DIR}/src/graphics.h ${RIVER_MOUNTAINS}
        DEPENDS src/graphics.h tools/pack_mountains.py
        VERBATIM)
    set(RIVER_FOOTER_IMAGE ${CMAKE_CURRENT_BINARY_DIR}/demo_footer.bin)
    set(RIVER_FOOTER_HEADER ${CMAKE_CURRENT_BINARY_DIR}/demo_footer.h)
    set(RIVER_COVER_IMAGE ${CMAKE_CURRENT_BINARY_DIR}/cover.bin)
    set(RIVER_COVER_FADES ${CMAKE_CURRENT_BINARY_DIR}/cover_fade.bin)
    set(RIVER_COVER_PROMPT ${CMAKE_CURRENT_BINARY_DIR}/cover_prompt.bin)
    set(RIVER_OUTRO_PROMPT ${CMAKE_CURRENT_BINARY_DIR}/outro_prompt.bin)
    set(RIVER_MANUAL_IMAGE ${CMAKE_CURRENT_BINARY_DIR}/manual.bin)
    set(RIVER_MANUAL_FADES ${CMAKE_CURRENT_BINARY_DIR}/manual_fade.bin)
    set(RIVER_MANUAL_PROMPT ${CMAKE_CURRENT_BINARY_DIR}/manual_prompt.bin)
    set(RIVER_OUTRO_IMAGE ${CMAKE_CURRENT_BINARY_DIR}/outro.bin)
    set(RIVER_OUTRO_FADES ${CMAKE_CURRENT_BINARY_DIR}/outro_fade.bin)
    set(RIVER_COVER_INCLUDE ${CMAKE_CURRENT_BINARY_DIR}/cover.inc)
    add_custom_command(OUTPUT ${RIVER_FOOTER_IMAGE} ${RIVER_FOOTER_HEADER}
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/make_demo_footer.py
            ${CMAKE_CURRENT_SOURCE_DIR}/src/demo-footer.json
            ${CMAKE_CURRENT_SOURCE_DIR}/src/graphics.h
            ${RIVER_FOOTER_IMAGE} ${RIVER_FOOTER_HEADER}
        DEPENDS src/demo-footer.json src/graphics.h tools/make_demo_footer.py
        VERBATIM)
    add_custom_command(OUTPUT ${RIVER_COVER_IMAGE} ${RIVER_COVER_FADES}
        ${RIVER_COVER_PROMPT} ${RIVER_COVER_INCLUDE} ${RIVER_OUTRO_PROMPT}
        ${RIVER_MANUAL_IMAGE} ${RIVER_MANUAL_FADES} ${RIVER_MANUAL_PROMPT}
        ${RIVER_OUTRO_IMAGE} ${RIVER_OUTRO_FADES}
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/make_cover.py
            ${CMAKE_CURRENT_SOURCE_DIR}/assets/cover.bmp
            ${RIVER_COVER_IMAGE} ${RIVER_COVER_FADES} ${RIVER_COVER_PROMPT} ${RIVER_COVER_INCLUDE}
            ${RIVER_FOOTER_IMAGE}
            ${RIVER_OUTRO_PROMPT}
            --manual ${CMAKE_CURRENT_SOURCE_DIR}/assets/manual.bmp
            --outro ${CMAKE_CURRENT_SOURCE_DIR}/assets/outro.bmp
        DEPENDS assets/cover.bmp assets/manual.bmp assets/outro.bmp tools/make_cover.py ${RIVER_FOOTER_IMAGE}
        VERBATIM)
    add_custom_command(OUTPUT ${RIVER_CORE}
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/port_original.py
            ${CMAKE_CURRENT_SOURCE_DIR}/original/riverraid.asm ${RIVER_CORE}
        DEPENDS original/riverraid.asm tools/port_original.py
        VERBATIM)
    add_executable(riverraid
        src/riverraid.asm src/duo.asm src/cover.asm src/fade.c src/fade.asm src/main.c src/audio.c src/audio.asm src/engine.asm ${RIVER_CORE}
        ${RIVER_FOOTER_HEADER} ${RIVER_COVER_INCLUDE} ${RIVER_MOUNTAINS})
    target_link_options(riverraid PRIVATE -C ${CMAKE_CURRENT_SOURCE_DIR}/src/riverraid.cfg)
    set_property(TARGET riverraid APPEND PROPERTY LINK_DEPENDS
        ${CMAKE_CURRENT_SOURCE_DIR}/src/riverraid.cfg)
    target_include_directories(riverraid PRIVATE ${CMAKE_CURRENT_BINARY_DIR})
    # DUO and all audio backends share a fixed 64 KiB CPU map. Both presets
    # need compact C code; retain source symbols for DAP and memory fixtures.
    target_compile_options(riverraid PRIVATE -g "$<$<COMPILE_LANGUAGE:C>:-Oirs>")
    option(RIVER_PROFILE "Measure frame phases in XRAM (adds timing overhead)" OFF)
    if(RIVER_PROFILE)
        target_compile_definitions(riverraid PRIVATE RIVER_PROFILE)
    endif()
    rp6502_map(riverraid src/xram.h "XRAM_.*")
    rp6502_asset(riverraid help src/help.txt)
    # Named assets are read from ROM: on demand; they are not preloaded to XRAM.
    rp6502_asset(riverraid cover.bin ${RIVER_COVER_IMAGE})
    rp6502_asset(riverraid cover-fade.bin ${RIVER_COVER_FADES})
    rp6502_asset(riverraid cover-prompt.bin ${RIVER_COVER_PROMPT})
    rp6502_asset(riverraid outro-prompt.bin ${RIVER_OUTRO_PROMPT})
    rp6502_asset(riverraid manual.bin ${RIVER_MANUAL_IMAGE})
    rp6502_asset(riverraid manual-fade.bin ${RIVER_MANUAL_FADES})
    rp6502_asset(riverraid manual-prompt.bin ${RIVER_MANUAL_PROMPT})
    rp6502_asset(riverraid outro.bin ${RIVER_OUTRO_IMAGE})
    rp6502_asset(riverraid outro-fade.bin ${RIVER_OUTRO_FADES})
    rp6502_asset(riverraid demo-footer.bin ${RIVER_FOOTER_IMAGE})
    # Cover helpers and tank extensions share CPU RAM above the reference ROM.
    rp6502_byproducts(riverraid ${CMAKE_CURRENT_BINARY_DIR}/riverraid.splash)
    rp6502_asset(riverraid RAM(0xD000) ${CMAKE_CURRENT_BINARY_DIR}/riverraid.splash)
    rp6502_byproducts(riverraid ${CMAKE_CURRENT_BINARY_DIR}/riverraid.rom)
    rp6502_asset(riverraid RAM(0xC000) ${CMAKE_CURRENT_BINARY_DIR}/riverraid.rom)
    rp6502_executable(riverraid DATA 0x0300 RESET 0x0300)
    rp6502_web(riverraid)
endif()
