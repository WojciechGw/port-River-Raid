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
    option(RIVER_PCM "Include PCM music, percussion and effects" OFF)
    set(RIVER_MANUAL ${CMAKE_CURRENT_SOURCE_DIR}/assets/manual.bmp)
    set(RIVER_MUSIC_ARGS)
    set(RIVER_MUSIC_ASSETS music.inc)
    if(RIVER_PCM)
        list(APPEND RIVER_MUSIC_ASSETS flight-score.bin flight-score.json flight-drums.pcm)
    else()
        set(RIVER_MANUAL ${CMAKE_CURRENT_SOURCE_DIR}/assets/manualOPL.bmp)
        list(APPEND RIVER_MUSIC_ARGS --opl-only)
    endif()
    set(RIVER_CORE ${CMAKE_CURRENT_BINARY_DIR}/original_core.asm)
    set(RIVER_INTRO_SCORE ${CMAKE_CURRENT_BINARY_DIR}/intro-score.bin)
    set(RIVER_GAMEOVER_SCORE ${CMAKE_CURRENT_BINARY_DIR}/gameover-score.bin)
    set(RIVER_VICTORY_SCORE ${CMAKE_CURRENT_BINARY_DIR}/victory-score.bin)
    foreach(synth opl)
        foreach(song intro flight gameover victory)
            list(APPEND RIVER_MUSIC_ASSETS ${song}-${synth}.bin)
        endforeach()
    endforeach()
    list(TRANSFORM RIVER_MUSIC_ASSETS PREPEND "${CMAKE_CURRENT_BINARY_DIR}/")
    add_custom_command(OUTPUT ${RIVER_MUSIC_ASSETS}
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/make_music.py
            ${CMAKE_CURRENT_SOURCE_DIR}/src ${CMAKE_CURRENT_BINARY_DIR} ${RIVER_MUSIC_ARGS}
        DEPENDS tools/make_music.py tools/make_intro.py src/intro-score.json
            src/gameover-score.json src/victory-score.json
        VERBATIM)
    add_custom_command(OUTPUT ${RIVER_VICTORY_SCORE} ${CMAKE_CURRENT_BINARY_DIR}/victory-score.inc
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/make_gameover.py
            ${CMAKE_CURRENT_SOURCE_DIR}/src/victory-score.json ${RIVER_VICTORY_SCORE}
            ${CMAKE_CURRENT_BINARY_DIR}/victory-score.inc --prefix VICTORY
        DEPENDS src/victory-score.json tools/make_gameover.py
        VERBATIM)
    add_custom_command(OUTPUT ${RIVER_GAMEOVER_SCORE} ${CMAKE_CURRENT_BINARY_DIR}/gameover-score.inc
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/make_gameover.py
            ${CMAKE_CURRENT_SOURCE_DIR}/src/gameover-score.json ${RIVER_GAMEOVER_SCORE}
            ${CMAKE_CURRENT_BINARY_DIR}/gameover-score.inc
        DEPENDS src/gameover-score.json tools/make_gameover.py
        VERBATIM)
    add_custom_command(OUTPUT ${RIVER_INTRO_SCORE} ${CMAKE_CURRENT_BINARY_DIR}/intro-score.inc
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/make_intro.py
            ${CMAKE_CURRENT_SOURCE_DIR}/src/intro-score.json ${RIVER_INTRO_SCORE}
            --include ${CMAKE_CURRENT_BINARY_DIR}/intro-score.inc
        DEPENDS src/intro-score.json tools/make_intro.py
        VERBATIM)
    set(RIVER_MOUNTAINS ${CMAKE_CURRENT_BINARY_DIR}/mountains.h)
    set(RIVER_SOUND_ICONS ${CMAKE_CURRENT_BINARY_DIR}/sound_icons.h)
    add_custom_command(OUTPUT ${RIVER_SOUND_ICONS}
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/pack_sound_icons.py
            ${CMAKE_CURRENT_SOURCE_DIR}/src/graphics.h ${RIVER_SOUND_ICONS}
        DEPENDS src/graphics.h tools/pack_sound_icons.py
        VERBATIM)
    add_custom_command(OUTPUT ${RIVER_MOUNTAINS}
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/pack_mountains.py
            ${CMAKE_CURRENT_SOURCE_DIR}/src/graphics.h ${RIVER_MOUNTAINS}
        DEPENDS src/graphics.h tools/pack_mountains.py
        VERBATIM)
    set(RIVER_FOOTER_IMAGE ${CMAKE_CURRENT_BINARY_DIR}/demo_footer.bin)
    set(RIVER_DEMO_SPLASH)
    foreach(scene plane areyouready gameover)
        set(sprite_asset ${CMAKE_CURRENT_BINARY_DIR}/splash-${scene}.bin)
        list(APPEND RIVER_DEMO_SPLASH ${sprite_asset})
        add_custom_command(OUTPUT ${sprite_asset}
            COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/make_demo_splash.py
                ${CMAKE_CURRENT_SOURCE_DIR}/assets/splash_${scene}.bmp ${sprite_asset}
            DEPENDS assets/splash_${scene}.bmp tools/make_demo_splash.py
            VERBATIM)
    endforeach()
    set(RIVER_FOOTER_HEADER ${CMAKE_CURRENT_BINARY_DIR}/demo_footer.h)
    set(RIVER_DUO_FOOTER_IMAGE ${CMAKE_CURRENT_BINARY_DIR}/duo_demo_footer.bin)
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
    add_custom_command(OUTPUT ${RIVER_FOOTER_IMAGE} ${RIVER_FOOTER_HEADER} ${RIVER_DUO_FOOTER_IMAGE}
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/make_demo_footer.py
            ${CMAKE_CURRENT_SOURCE_DIR}/src/demo-footer.json
            ${CMAKE_CURRENT_SOURCE_DIR}/src/graphics.h
            ${RIVER_FOOTER_IMAGE} ${RIVER_FOOTER_HEADER} ${RIVER_DUO_FOOTER_IMAGE}
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
            --manual ${RIVER_MANUAL}
            --outro ${CMAKE_CURRENT_SOURCE_DIR}/assets/outro.bmp
            --duo-footer ${RIVER_DUO_FOOTER_IMAGE}
        DEPENDS assets/cover.bmp ${RIVER_MANUAL} assets/outro.bmp tools/make_cover.py ${RIVER_FOOTER_IMAGE} ${RIVER_DUO_FOOTER_IMAGE}
        VERBATIM)
    add_custom_command(OUTPUT ${RIVER_CORE}
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/port_original.py
            ${CMAKE_CURRENT_SOURCE_DIR}/original/riverraid.asm ${RIVER_CORE}
        DEPENDS original/riverraid.asm tools/port_original.py
        VERBATIM)
    add_executable(riverraid
        src/riverraid.asm src/duo.asm src/cover.asm src/intro.asm src/fade.c src/fade.asm src/main.c src/audio.c src/audio.asm src/sound_status.asm src/demo_footer.asm src/demo_splash.asm ${RIVER_CORE}
        ${RIVER_INTRO_SCORE} ${RIVER_GAMEOVER_SCORE} ${RIVER_VICTORY_SCORE} src/gameover.asm src/music.asm ${RIVER_MUSIC_ASSETS}
        ${RIVER_FOOTER_HEADER} ${RIVER_COVER_INCLUDE} ${RIVER_MOUNTAINS} ${RIVER_SOUND_ICONS} ${RIVER_DEMO_SPLASH})
    target_link_options(riverraid PRIVATE -C ${CMAKE_CURRENT_SOURCE_DIR}/src/riverraid.cfg)
    set_property(TARGET riverraid APPEND PROPERTY LINK_DEPENDS
        ${CMAKE_CURRENT_SOURCE_DIR}/src/riverraid.cfg)
    target_include_directories(riverraid PRIVATE ${CMAKE_CURRENT_BINARY_DIR})
    target_compile_definitions(riverraid PRIVATE RIVER_PCM=$<BOOL:${RIVER_PCM}>)
    # cl65's -D reaches C only; pass the same switch to ca65 explicitly.
    target_compile_options(riverraid PRIVATE
        "$<$<COMPILE_LANGUAGE:ASM>:--asm-define;RIVER_PCM=$<BOOL:${RIVER_PCM}>>")
    # DUO and all audio backends share a fixed 64 KiB CPU map. Both presets
    # need compact C code; retain source symbols for DAP and memory fixtures.
    target_compile_options(riverraid PRIVATE -g "$<$<COMPILE_LANGUAGE:C>:-Oirs>")
    option(RIVER_PROFILE "Measure frame phases in XRAM (adds timing overhead)" OFF)
    if(RIVER_PROFILE)
        target_compile_definitions(riverraid PRIVATE RIVER_PROFILE)
    endif()
    rp6502_map(riverraid src/xram.h "XRAM_.*")
    # Derive both help variants from the same keyboard/gameplay description.
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS src/help.txt)
    file(READ ${CMAKE_CURRENT_SOURCE_DIR}/src/help.txt RIVER_HELP)
    if(NOT RIVER_PCM)
        string(REPLACE " /opl2 | /pcm" " /opl2" RIVER_HELP "${RIVER_HELP}")
        string(REPLACE "No option: OPL2. /auto: PCM if supported, otherwise OPL2."
            "OPL2-only build. All music, percussion and effects use OPL2." RIVER_HELP "${RIVER_HELP}")
        string(REPLACE "Only /pcm requires the PCM firmware extension. /help shows usage."
            "/auto and /opl2 select OPL2. /help shows usage." RIVER_HELP "${RIVER_HELP}")
        string(REGEX REPLACE "F10:[^\n]*\n" "" RIVER_HELP "${RIVER_HELP}")
        string(REPLACE "/v always shows the sound icon and backend below the scroller."
            "/v always shows the sound icon below the scroller." RIVER_HELP "${RIVER_HELP}")
    endif()
    file(CONFIGURE OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/help.txt CONTENT "${RIVER_HELP}" @ONLY)
    rp6502_asset(riverraid help ${CMAKE_CURRENT_BINARY_DIR}/help.txt)
    rp6502_byproducts(riverraid ${CMAKE_CURRENT_BINARY_DIR}/riverraid.intro)
    rp6502_asset(riverraid intro.bin ${CMAKE_CURRENT_BINARY_DIR}/riverraid.intro)
    if(RIVER_PCM)
        rp6502_asset(riverraid intro-drums.pcm assets/intro-drums.pcm)
        rp6502_asset(riverraid intro-score.bin ${RIVER_INTRO_SCORE})
    endif()
    foreach(asset IN LISTS RIVER_MUSIC_ASSETS)
        get_filename_component(name ${asset} NAME)
        if(name MATCHES "\\.(bin|pcm)$")
            rp6502_asset(riverraid ${name} ${asset})
        endif()
    endforeach()
    rp6502_byproducts(riverraid ${CMAKE_CURRENT_BINARY_DIR}/riverraid.gameover)
    rp6502_asset(riverraid gameover-code.bin ${CMAKE_CURRENT_BINARY_DIR}/riverraid.gameover)
    if(RIVER_PCM)
        rp6502_asset(riverraid gameover-score.bin ${RIVER_GAMEOVER_SCORE})
        rp6502_asset(riverraid gameover.pcm assets/gameover.pcm)
        rp6502_asset(riverraid victory-score.bin ${RIVER_VICTORY_SCORE})
        rp6502_asset(riverraid victory.pcm assets/victory.pcm)
    endif()
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
    foreach(scene plane areyouready gameover)
        rp6502_asset(riverraid splash-${scene}.bin ${CMAKE_CURRENT_BINARY_DIR}/splash-${scene}.bin)
    endforeach()
    rp6502_asset(riverraid duo-demo-footer.bin ${RIVER_DUO_FOOTER_IMAGE})
    # Cover helpers and tank extensions share CPU RAM above the reference ROM.
    rp6502_byproducts(riverraid ${CMAKE_CURRENT_BINARY_DIR}/riverraid.splash)
    rp6502_asset(riverraid RAM(0xD000) ${CMAKE_CURRENT_BINARY_DIR}/riverraid.splash)
    add_custom_command(TARGET riverraid POST_BUILD
        COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/pack_music_rom.py
            ${CMAKE_CURRENT_BINARY_DIR}/riverraid.rom ${CMAKE_CURRENT_BINARY_DIR}/riverraid.music
            ${CMAKE_CURRENT_BINARY_DIR}/riverraid.soundrom
        VERBATIM)
    set_property(TARGET riverraid APPEND PROPERTY LINK_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/tools/pack_music_rom.py)
    rp6502_byproducts(riverraid ${CMAKE_CURRENT_BINARY_DIR}/riverraid.rom
        ${CMAKE_CURRENT_BINARY_DIR}/riverraid.music ${CMAKE_CURRENT_BINARY_DIR}/riverraid.soundrom)
    rp6502_asset(riverraid RAM(0xC000) ${CMAKE_CURRENT_BINARY_DIR}/riverraid.soundrom)
    rp6502_executable(riverraid DATA 0x0300 RESET 0x0300)
    rp6502_web(riverraid)
endif()
