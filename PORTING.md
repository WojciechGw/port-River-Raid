# Stan portu

Port wykonuje natywnie oryginalne procedury gry z `original/riverraid.asm`.
Źródło odniesienia to wersja **Atari 2600 NTSC**, z układami TIA i RIOT.
Autorka gry: Carol Shaw, Activision (1982); autor komentarzy disassembly:
Thomas Jentzsch. Źródło oryginału pozostaje niezmienione.

## Logika oryginału

`tools/port_original.py` tłumaczy DASM na ca65, zachowuje kompletny obraz
4 KB jako dane odniesienia i wyprowadza osobne, wykonywalne procedury:

- generator `PFPat`, zmiany brzegów i wysp, rozmieszczenie domów, paliwa,
  statków, helikopterów, samolotów oraz mostów;
- oryginalny LFSR, zapamiętywanie nasiona sekcji i odtwarzanie trasy po śmierci;
- ułamkowe przewijanie, przyspieszenie poziome i pionowe, rytm ruchu oraz animacji;
- spalanie 32 jednostek paliwa na klatkę i oryginalne tankowanie;
- punktacja 100/60/30/500/80, dodatkowe życie co 10 000 punktów, limit
  dziewięciu żyć oraz zachowanie przy przekroczeniu 999 990 punktów;
- przejście sekcji i ograniczenie poziomów do 48, eksplozja, odradzanie,
  tryby dla jednej i dwóch osób oraz przełączniki trudności;
- procedury dźwięku, tryb czarno-biały i wygaszacz kolorów.

Most rozpoczyna przejście sekcji. Numer poziomu zmienia się w generatorze
podczas przewijania, zgodnie z oryginałem. Początkowo przeciwnicy stoją;
statki i helikoptery zaczynają się poruszać od drugiego poziomu, samoloty
pojawiają się od trzeciego. Śmierć odtwarza zapamiętaną sekcję; port nie
dodaje nietykalności ani sztucznego, bezpiecznego korytarza.

Zmiany procedur dotyczą adresów sprzętu, zachowania stosu cc65, inicjalizacji
zarezerwowanej strony zerowej oraz pominięcia oczekiwania na zegar RIOT.
Rozszerzone skoki ca65 zachowują warunki i flagi procesora. Generator sprawdza
rozmiar obrazu i położenie ważnych fragmentów źródła; zmiana układu disassembly
wymaga przeglądu zakresów wybieranych do portu.

## Warstwa Picocomputera

RAM `$0000–$007F` służy cc65, `$0080–$00FF` zachowuje zmienne gry,
`$0200–$02FF` zawiera odczyty wejścia i wyjściowe rejestry dźwięku.
Program rozpoczyna się pod `$0300`. Oryginalny obraz ROM znajduje się jako
dane pod `$C000–$CFFF`; zachowuje bajty zmontowane dla Atari pod `$F000`.
Wykonywane procedury mają przeniesione odwołania i osobną tabelę inicjalizacji.
Kod Atari odpowiedzialny za raster nie jest wykonywany. Nie ma emulacji CPU Atari.

VGA: canvas 320×240, pole gry na liniach 8–167, współrzędne logiczne 160×160.
Rzeka korzysta z oryginalnej kolejności bitów PF0/PF1/PF2, odbicia oraz
tablic drogi. Bufor kołowy 320×192 w 4 bpp dopisuje jedynie nowe linie.
Sprite'y odtwarzają strumienie A/B, kolory wierszy, rozmiary TIA, odbicia,
kopie eksplozji mostu i zawijanie samolotów na krawędzi. Panel wyświetla
oryginalne bitmapy cyfr, paliwa i napisu Activision/copyright zamiast fontu VGA.

Program oblicza kolizje pikseli przed wywołaniem oryginalnej logiki,
wypełniając jej flagi kolizji. Transfer linii i sprawdzanie sprite'ów z terenem
wykonuje asembler. Wejście obsługuje USB HID i dwa gamepady. Zegar gry
pochodzi z `RIA.vsync` przy 60 Hz. Pełne przygotowanie ekranu podczas startu
i odradzania jest wyłączone z licznika pominiętych klatek.

PSG otrzymuje częstotliwości, głośność i rodzaj fali wynikające z oryginalnych
rejestrów AUDC/AUDF/AUDV. Sekwencje efektów pochodzą z oryginału, lecz szum
PSG nie odtwarza dokładnie generatorów wielomianowych TIA. RGB555 jest
przybliżeniem barw NTSC, a nie analogowym modelem konkretnego telewizora.
Interfejsy sprzętowe opisują [VGA](https://picocomputer.github.io/vga.html)
i [RIA](https://picocomputer.github.io/ria.html).

## Weryfikacja i ograniczenia

`python tests/emulator_checks.py` sprawdza rzeczywisty ROM w RP6502-EMU
przy 8 MHz: wejście, pauzę, paliwo, trafienia, bonusowe życie, maksymalny
wynik, generator, śmierć, odradzanie, trudność, zmianę gracza i restart.
Scenariusz 1200 klatek z przyspieszaniem i strzelaniem mierzy pominięte VSYNC.
Testy są wyciszone, więc nie potwierdzają jakości brzmienia.

Pozostają odsłuch, porównanie rastra klatka po klatce z emulatorem Atari
i próba na fizycznym RP6502. Zachowanie logiki zachowano przez użycie
oryginalnych procedur; nie deklarujemy jeszcze zgodności obrazu i dźwięku 1:1.
