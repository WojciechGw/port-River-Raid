# River Raid na Picocomputer 6502

Port River Raid dla Picocomputera 6502 z natywną logiką oryginału.
Punktem odniesienia jest `original/riverraid.asm`: komentowany disassembly
wersji **Atari 2600**, autorstwa Thomasa Jentzscha. Oryginalna gra i grafika:
Activision, 1982; projektantka Carol Shaw.

Oryginalne procedury 6502 odpowiadają za trasę, przeciwników, przyspieszenie,
paliwo, punktację, dodatkowe życia, odradzanie w zapamiętanej sekcji i grę
dla dwóch osób. Grafika łączy oryginalne bitmapy z paletą i dekoracjami
inspirowanymi screenshotami Atari XL i 5200: wygładzone brązowe skarpy o zmiennej
szerokości, dwa warianty gór (niebieskie zbocza lub czarne grzbiety)
i ciemnoniebieska woda. Dodane balony
mają wielobarwną czaszę i kosz, a czołgi przejeżdżają drogami przez mosty. Panel
pokazuje wynik, paliwo, gracza, wariant gry, numer mostu, rekord sesji HI
i samoloty rezerwowe. Dźwięk przekłada rejestry TIA na PSG.
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
| F3 | Nowa gra od mostu BRIDGE: 1 → 5 → 20 → 50 → 1 |
| F5, F4 | Gracz 1 / 2: pociski kierowane lub lecące prosto |
| P | Pauza |
| R | Nowa gra od mostu wybranego przez F3 |
| Escape | Wyjście do konsoli |

Obsługiwane są dwa gamepady: krzyżak lub lewy drążek steruje, cztery główne przyciski służą do
strzelania, Start włącza pauzę, Select rozpoczyna nową grę. Zbiornik paliwa
uzupełnia paliwo po najechaniu samolotem; zestrzelenie zbiornika daje punkty.
Balon daje 60 punktów, czołg na drodze 250, most 500,
a most z czołgiem 750. Przewinięcie sekcji zwiększa poziom.
W wariancie dla dwóch osób gracz zmienia się po utracie samolotu.

W trybie pokazowym stopka przewija jasnoszary napis z tytułem gry,
autorką, datami copyright, logo Activision i instrukcją rozpoczęcia gry.
Najpierw program pokazuje `assets/cover.bmp` z płynnym rozjaśnianiem
(około sekundy). Dowolny klawisz rozpoczyna wygaszanie; po jego zakończeniu
i zwolnieniu klawisza pojawia się plansza gry. Okładka zachowuje proporcje
320×180 i jest wyśrodkowana na czarnym tle.
Pod grafiką miga niewielki biały napis „PRESS ANY KEY”, widoczny przez pół
sekundy i ukryty przez pół sekundy. Okładka i jej palety są nazwanymi zasobami
w pliku `.rp6502`, wczytywanymi z `ROM:cover.bin` i `ROM:cover-fade.bin`;
bitmapa napisu jest ładowana z `ROM:cover-prompt.bin`.
Po wyświetleniu planszy gry program czeka 3 sekundy, a następnie
jednocześnie uruchamia przewijanie napisu i pokaz z przewijaną rzeką.
Tekst oraz glify można edytować w `src/demo-footer.json`.

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
- `src/graphics.h`: paleta wzorowana na Atari 5200, czytelne bitmapy balonów,
  czołgów, gór, skarp i liter panelu.
- `src/riverraid.asm`: szybki transfer linii i kolizje sprite'ów z terenem.
- `src/cover.asm`: wyświetlanie okładki, fade i oczekiwanie na klawisz.
- `src/riverraid.cfg`: mapa RAM z zarezerwowaną stroną zerową oryginału.
- `src/xram.h`: mapa XRAM i sprawdzane podczas kompilacji struktury PIX.
- `tools/port_original.py`: automatyczne tłumaczenie DASM na ca65 i wybór
  oryginalnych procedur. Tworzy `original_core.asm` w katalogu budowania.
- `tools/make_cover.py`: konwersja `assets/cover.bmp` i przygotowanie palet fade.
- `original/riverraid.asm`: niezmienione źródło odniesienia.

<!-- rp6502
preset: cc65/Release
publish: riverride.zip
-->
