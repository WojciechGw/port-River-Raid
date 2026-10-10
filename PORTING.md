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

VGA: canvas 320×240, pole gry na liniach 21–180, współrzędne logiczne 160×160.
Rzeka korzysta z oryginalnej kolejności bitów PF0/PF1/PF2, odbicia oraz
tablic drogi. Bufor kołowy 40×192 przechowuje indeksy kafelków
8×1 pikseli: jeden kafelek odpowiada bitowi playfield Atari. Dopisuje jedynie
nowe linie, przesyłając 40 zamiast 160 bajtów na wiersz.
Kafelki na styku lądu i wody dodają brązową skarpę od strony lądu,
także na wyspach. Woda i maski kolizji zachowują te same granice.
Sprite'y odtwarzają strumienie A/B, kolory wierszy, rozmiary TIA, odbicia,
kopie eksplozji mostu i zawijanie samolotów na krawędzi. Panel wyświetla
oryginalne bitmapy cyfr, paliwa i napisu Activision/copyright zamiast fontu VGA.
W miejscu domu i drzewa z 2600 pojawiają się dwa szczyty górskie, wzorowane
na XL i mieszczące się w dotychczasowym obszarze sprite'a. Ich maska kolizji
odpowiada nowej sylwetce. Boczne pola panelu pokazują P1/P2, GAME i numer
wariantu oraz BRIDGE z bieżącym poziomem; aktualizują tylko zmienione pola.
Cyfry tych liczników są przygotowane przy starcie i wyświetlane przez trzy
sprite'y w obszarze panelu, bez ponownego rysowania ich bitmap w klatce gry.
Strumień A przypada na parzyste linie bloku, B na nieparzyste; ta kolejność
zachowuje czytelne litery FUEL wycięte w bitmapie zbiornika.
Most ma szerokość 32 pikseli logicznych i zajmuje zakres X 64–95, zgodny
z przewężeniem rzeki. Pozycję szerokiego sprite'a skorygowano o jeden piksel
względem wartości 63 przekazywanej przez oryginał do `CalcPosX`; ten sam
początek wykorzystują rysowanie i kolizje.
Panel zajmuje linie 182–218, z pojedynczą czarną linią oddzielającą go od gry.
Wynik rozpoczyna się w wierszu 1 panelu, skala paliwa w 11, a życia i logo w 28.
Cały obraz jest wyśrodkowany pionowo, z czarnymi marginesami po 21 linii.

Program oblicza kolizje pikseli przed wywołaniem oryginalnej logiki,
wypełniając jej flagi kolizji. Transfer linii i sprawdzanie sprite'ów z terenem
wykonuje asembler. Wejście obsługuje USB HID i dwa gamepady. Zegar gry
pochodzi z `RIA.vsync` przy 60 Hz. Licznik pominiętych klatek obejmuje
wszystkie operacje po początkowej konfiguracji obrazu, również restart,
odradzanie i zmianę gracza.

Restart odtwarza początkowy, prosty korytarz szybką procedurą asemblerową.
W pomiarze Release przy 8 MHz koszt odtwarzania terenu spadł z około 391 ms
do 5–6 ms. Panel przesyła tylko kolumny zajęte przez cyfry, paliwo i logo;
rysowanie glifów wykonuje asembler, a częstotliwości PSG korzystają z tabel
przygotowanych przy starcie zamiast dzielenia w każdej klatce.

PSG otrzymuje częstotliwości, głośność i rodzaj fali wynikające z oryginalnych
rejestrów AUDC/AUDF/AUDV. Sekwencje efektów pochodzą z oryginału, lecz szum
PSG nie odtwarza dokładnie generatorów wielomianowych TIA. RGB555 jest
przybliżeniem barw dopasowanym do dostarczonych screenshotów, a nie
analogowym modelem konkretnego telewizora.
Interfejsy sprzętowe opisują [VGA](https://picocomputer.github.io/vga.html)
i [RIA](https://picocomputer.github.io/ria.html).

## Referencje obrazu

Trzy bezstratne GIF-y w `original/Atari XL` są odniesieniem dla aktualnej
palety i dekoracji. Ich płaskie kolory mają RGB: woda (83, 70, 255), ciemny
ląd (0, 85, 16), jasny ląd (89, 158, 0), skarpa (85, 19, 0), panel
(171, 171, 171). Statki mają czerwony kadłub i zieloną dolną część,
zbiorniki różowe i białe pasy, helikoptery ciemny kadłub i złoty wirnik.
Host zaokrągla kolory do RGB555; mapowanie ról kolorów w `src/graphics.h`
zachowuje oryginalne przełączanie B&W i wygaszacz. Kolory nieobecne
w screenshotach nadal korzystają z przybliżenia odcienia TIA.

Dziesięć JPEG-ów w `original/Atari 2600` służy do porównywania sylwetek
obiektów i podstawowego układu panelu. Logika i generator trasy pochodzą
z 2600; ta wersja portu rozwija wygląd na podstawie XL, a nie odtwarza
rastra ani reguł wersji XL 1:1.

Skala paliwa pozostaje czarna dla obu graczy; ruchomy wskaźnik jest żółty.
Screenshot 02 pokazuje czarny samolot, wynik i logo drugiego gracza.
Odstępy pionowe panelu porównano ze screenshotami i procedurą `FinishDigits`.
Lewy czarny pas blankingu HMOVE widoczny na obrazach Atari nie jest odtwarzany.
Screenshoty pokazują pojedyncze stany gry, więc nie potwierdzają jeszcze
zgodności faz ruchu, kolizji i animacji klatka po klatce.

## Weryfikacja i ograniczenia

`python tests/emulator_checks.py` sprawdza rzeczywisty ROM w RP6502-EMU
przy 8 MHz: wejście, pauzę, paliwo, trafienia, bonusowe życie, maksymalny
wynik, generator, śmierć, odradzanie, trudność, zmianę gracza i restart.
Scenariusz 1200 klatek sprawdza przewijanie z przyspieszaniem i strzelaniem.
Test terenu porównuje widoczne piksele kafelków, również skarp, z maskami
kolizji na całej wysokości pola gry. Sprawdza też dopasowanie mostu do brzegów.
Także pozostałe scenariusze kończące się w grze sprawdzają brak pominiętych
VSYNC, w tym odradzanie, tankowanie i zmiana gracza. Opcjonalny profil faz
klatki opisano w `tests/README.md`.
Testy są wyciszone, więc nie potwierdzają jakości brzmienia.

Pozostają odsłuch, porównanie rastra klatka po klatce z emulatorem Atari
i próba na fizycznym RP6502. Zachowanie logiki zachowano przez użycie
oryginalnych procedur; nie deklarujemy jeszcze zgodności obrazu i dźwięku 1:1.
