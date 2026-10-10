# Testy portu

Po zbudowaniu Release: `python tests/emulator_checks.py`.
Opcje `--build` i `--emulator` wskazują inny katalog lub emulator.
Potrzebne są `riverride.rp6502` i odpowiadający plik `riverride.dbg`.
Nie są wymagane dodatkowe pakiety Pythona.

Scenariusze uruchamiają rzeczywisty kod CPU przy 8 MHz, bez okna i dźwięku.
Sprawdzają także komunikaty błędów emulatora, ponieważ niektóre wersje
zwracają kod zero mimo błędu skryptu. Pliki skryptów i PNG trafiają do
`build/cc65/release/checks`.

Rzadkie sytuacje przygotowujemy podczas pauzy przez zapis oryginalnych
zmiennych w RAM `$80–$FF`. Wybrane testy zerują maski terenu w bezpiecznym
korytarzu, aby odizolować sprawdzaną kolizję. Symbole hosta pochodzą z `.dbg`.
ROM nie zawiera poleceń testowych. Po wznowieniu wynik oblicza oryginalna
logika, a nie kod testu. Testy nie zastępują porównania z obrazem TIA.

## Diagnostyka XRAM `$0080`

32 bajty aktualizowane przez hosta, protokół **2**. Liczby wielobajtowe
są little endian. Dane służą obserwacji, nie sterowaniu grą.

| Offset | Znaczenie |
| --- | --- |
| 0–1 | Sygnatura `$52`, wersja 2 |
| 2 | 0 intro/oczekiwanie, 1 gra, 2 eksplozja, 3 koniec gry |
| 3–5 | X samolotu, liczba żyć, poziom |
| 6–7 | Paliwo, 16 bitów |
| 8–10 | Aktywny pocisk, X, oryginalne Y liczone od dołu |
| 11–13 | Pauza, oryginalny blockOffset, aktywny dźwięk tankowania |
| 14–15 | Licznik wykonanych kroków oryginalnej logiki |
| 16–21 | Niskie bajty sześciu wskaźników cyfr wyniku: 0/8/…/72, 80=`!`, 88=spacja |
| 22–23 | Oryginalne sectionBlock i joystick z historią poprzedniej klatki |
| 24–25 | Stan 16-bitowego LFSR |
| 26–27 | Oryginalne speedY i gameMode |
| 28–29 | Wariant gry 0/1, bieżący gracz 0/1 |
| 30–31 | Pominięte VSYNC, z pominięciem pełnej inicjalizacji ekranu |

Każdy przyrost jednostki przewijania korzysta z oryginalnego akumulatora.
Paliwo spala się o 32 na krok; tankowanie z pustą przestrzenią w zbiorniku
daje netto 480 na krok. Oryginalny wynik jest zapisany jako wskaźniki bitmap
cyfr, dlatego protokół nie przechowuje go jako liczby 32-bitowej.
