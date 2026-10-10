# River Raid na Picocomputer 6502

Port River Raid dla Picocomputera 6502 z natywną logiką oryginału.
Punktem odniesienia jest `original/riverraid.asm`: komentowany disassembly
wersji **Atari 2600**, autorstwa Thomasa Jentzscha. Oryginalna gra i grafika:
Activision, 1982; projektantka Carol Shaw.

Oryginalne procedury 6502 odpowiadają za trasę, przeciwników, przyspieszenie,
paliwo, punktację, dodatkowe życia, odradzanie w zapamiętanej sekcji i grę
dla dwóch osób. Grafika łączy oryginalne bitmapy z paletą i dekoracjami
inspirowanymi screenshotami Atari XL: brązowe skarpy, góry i wyraźniejsze
kolory obiektów. Panel pokazuje oryginalne cyfry i wskaźnik paliwa oraz
gracza, wariant gry i numer mostu. Dźwięk przekłada rejestry TIA na PSG.
RGB555 oraz szum pozostają przybliżone. Zakres zgodności i ograniczenia
opisuje [PORTING.md](PORTING.md).

## Budowanie i uruchamianie

Wymagane: CMake 3.21+, Ninja, Python 3 oraz cc65 z obsługą targetu `rp6502`.
Instrukcja instalacji SDK: https://picocomputer.github.io/sdk.html

```powershell
cmake --preset cc65/Release
cmake --build --preset cc65/Release
.\tools\rp6502-emu.exe .\build\cc65\release\riverride.rp6502
```

Nazwa artefaktu `riverride` zachowuje dotychczasową nazwę targetu projektu.
W VS Code wybierz preset `cc65/Release`, target `riverride` i konfigurację
uruchamiania `RP6502-EMU`. F5 uruchamia emulator z obsługą debuggera.
Symbole źródłowe są dostępne także w Release. `cc65/Debug` służy do pracy
bez optymalizacji; pomiary płynności wykonuj w Release.

Port korzysta z ca65. Presety llvm-mos ze starego szablonu nie są obecnie
obsługiwane przez kod portu. Gałąź BASIC pozostaje przykładem z szablonu.

## Sterowanie

| Klawiatura | Działanie |
| --- | --- |
| Strzałki | Gracz 1: ruch; góra przyspiesza, dół zwalnia |
| WASD, lewy Ctrl | Gracz 2: ruch i strzał; w grze solo także sterują graczem 1 |
| Spacja lub Enter | Strzał; rozpoczęcie gry i powrót po końcu gry |
| F1 | Kolor / obraz czarno-biały |
| F2 | SELECT: wariant dla jednej lub dwóch osób |
| F3, F4 | Trudność gracza 1 / 2: pociski kierowane lub lecące prosto |
| P | Pauza |
| R | Nowa gra |
| Escape | Wyjście do konsoli |

Obsługiwane są dwa gamepady: krzyżak lub lewy drążek steruje, cztery główne przyciski służą do
strzelania, Start włącza pauzę, Select rozpoczyna nową grę. Zbiornik paliwa
uzupełnia paliwo po najechaniu samolotem; zestrzelenie zbiornika daje punkty.
Zniszczenie mostu daje 500 punktów; przewinięcie sekcji zwiększa poziom.
W wariancie dla dwóch osób gracz zmienia się po utracie samolotu.

## Testy w emulatorze

```powershell
python tests/emulator_checks.py
```

Skrypt testuje rzeczywisty ROM przy 8 MHz bez okna. Sprawdza sterowanie,
pauzę, trzy rodzaje gamepadów, dokładne spalanie i tankowanie, punktację,
bonusowe życie, maksymalny wynik, kolizje, odradzanie, kierowanie pociskiem,
zmianę gracza, restart, oryginalny LFSR i inicjalizację RAM.
Sprawdza też brak pominiętych VSYNC podczas przewijania i strzelania,
tankowania, odradzania oraz zmiany gracza.
Zrzuty ekranu i scenariusze trafiają do `build/cc65/release/checks`.
Opis diagnostyki: [tests/README.md](tests/README.md).

## Kod

- `src/main.c`: konfiguracja RIA/VGA/PSG, raster, wejście i kolizje.
- `src/graphics.h`: paleta wzorowana na Atari XL, góry i litery panelu.
- `src/riverraid.asm`: szybki transfer linii i kolizje sprite'ów z terenem.
- `src/riverraid.cfg`: mapa RAM z zarezerwowaną stroną zerową oryginału.
- `src/xram.h`: mapa XRAM i sprawdzane podczas kompilacji struktury PIX.
- `tools/port_original.py`: automatyczne tłumaczenie DASM na ca65 i wybór
  oryginalnych procedur. Tworzy `original_core.asm` w katalogu budowania.
- `original/riverraid.asm`: niezmienione źródło odniesienia.

<!-- rp6502
preset: cc65/Release
publish: riverride.zip
-->
