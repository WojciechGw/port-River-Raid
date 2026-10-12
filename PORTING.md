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
- przejście sekcji, eksplozja, odradzanie,
  tryby dla jednej i dwóch osób oraz przełączniki trudności;
- procedury dźwięku, tryb czarno-biały i wygaszacz kolorów.

Most rozpoczyna przejście sekcji. Numer poziomu zmienia się w generatorze
podczas przewijania, zgodnie z oryginałem. Początkowo przeciwnicy stoją;
statki i helikoptery zaczynają się poruszać od drugiego poziomu, samoloty
pojawiają się od trzeciego. Śmierć odtwarza zapamiętaną sekcję; port nie
dodaje nietykalności ani sztucznego, bezpiecznego korytarza.

F3 wybiera most startowy w cyklu 1 → 5 → 20 → 50 → 1 i rozpoczyna nową grę.
Wybór obejmuje obu graczy i pozostaje aktywny przy restarcie klawiszem R.
Pełna inicjalizacja stosuje wybrany poziom, a odradzanie i zmiana gracza
zachowują ich aktualną sekcję. W wykonywanej kopii procedur limit poziomów
zwiększono z 48 do 50; po sekcji 50 generator wraca do 49. Obraz oryginalnego
ROM pozostaje niezmieniony. Kierowanie pociskami przełączają teraz F5/F4.

Balony (ID 11) rozszerzają wykonywaną kopię procedur: od drugiego poziomu
zastępują część losowanych przeciwników, poruszają się i odbijają od brzegów
tak jak helikoptery. Trafienie daje 60 punktów, kontakt z samolotem eksplozję.
Czołg jest dodatkowym obiektem każdego bloku mostu, od pierwszego mostu;
przejeżdża po drodze i zawraca na jej krańcach. Jego stan przesuwa się razem
z blokiem terenu, pauza zatrzymuje ruch, a restart/odradzanie odtwarza stan.
Czołg na lądowej części drogi daje 250 punktów; trafienie mostu z czołgiem
na jego przęśle niszczy oba obiekty i daje łącznie 750 zamiast 500.
Dodatkowe 250 korzysta z oryginalnych dziesiętnych wskaźników cyfr,
przyznawania rezerw co 10 000 punktów, limitu 9 i przepełnienia wyniku.
Czołgi w tym wariancie nie strzelają ani nie patrolują brzegów od mostu 7.
Punktację balonu i mostu z czołgiem opisuje
[instrukcja Activision dla 5200](https://atariage.com/manual_html_page.php?SoftwareID=2101).

Pozostałe zmiany procedur dotyczą adresów sprzętu, zachowania stosu cc65, inicjalizacji
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
także na wyspach i przez wszystkie odcienie drogi przy moście. Na odcinkach
pionowych skarpa ma szerokość 3–5 pikseli logicznych. Nachylenie mierzone
z par próbek oddalonych o 2 i 4 wiersze zwęża ją stopniowo do 1 piksela na
stromych skosach; uwzględnia dwukrotne rozciągnięcie X na canvasie. Tabela
`bank_slope_width` w `src/graphics.h` opisuje tę zależność bez obliczeń
zmiennoprzecinkowych. Jednoliniowe połączenia zamykają kontur na stopniach.
Przy dołączeniu nowego bloku odświeżane są cztery poprzednie wiersze, których
nachylenie zależy od nowego sąsiada. Próbki wspólne dla par wierszy są
zapamiętywane w obrębie jednego przerysowania; pamięć podręczna jest
zerowana po zmianie danych przez logikę gry. Szerokość może
przekroczyć jeden kafelek. Generator 2600 nadal określa przebieg rzeki, ale
stopnie PF są interpolowane wewnątrz lądu do pojedynczych pikseli logicznych.
Sam kontur wody również ma drobne załamania: `bank_wave` odtwarza próbki
długiego brzegu z `original/Atari XL/image0.png` (wiersze logiczne 41–104).
Przesuwa granicę w głąb lądu o 0–3 piksele; profil jest związany z wierszem
terenu, więc przesuwa się razem z rzeką. Szybki reset korzysta z tej samej
granicy i gotowych kafelków dla każdej fazy, a góry zachowują dodatkowy
margines trzech pikseli od wody. Duże zakręty nadal wyznaczają dane generatora.
`river_left` i `river_right` przechowują dokładne granice dla rysowania oraz
kolizji; droga zachowuje oryginalną szerokość prześwitu mostu. Kafelki mieszają
kolory wody, skarpy i podłoża, a cały bufor nadal wymaga 40 bajtów na wiersz.
Samolot gracza może przelatywać nad brązową skarpą. Dla każdego wiersza
renderer zapamiętuje granice podłoża poza skarpą, osobno dla obu brzegów
i wyspy. `mask_player_land` sprawdza tylko te przedziały i oryginalne maski
terenu; kolizja pojawia się dopiero po wejściu nieprzezroczystego piksela
samolotu na ląd. Reset i przewijanie aktualizują te same granice.
Sprite'y odtwarzają strumienie A/B, kolory wierszy, rozmiary TIA, odbicia,
kopie eksplozji mostu i zawijanie samolotów na krawędzi. Samolot gracza
zajmuje przednią warstwę VGA (plane 2), nad obiektami gry na plane 1.
Panel wyświetla
bitmapy cyfr, paliwa i napisu Activision zamiast fontu VGA. Wynik oraz HI
korzystają z pogrubionych cyfr 6×6, odtworzonych z referencji Atari XL/5200.
P1/P2 i HI mają wąski krój 3×5, GAME szersze litery w komórkach 8×6,
a BRIDGE zachowuje osobną sześciowierszową bitmapę z odstępami oryginału.
Cyfra wariantu pod GAME oraz numer mostu używają tego samego kroju co wynik.
Pozycje pól odpowiadają załączonemu układowi: GAME po lewej, wskaźnik paliwa
obok, BRIDGE nad ikonami rezerw. Ramka paliwa z E, F oraz 1/2 jest czytelną
bitmapą 39×16 w `src/graphics.h`; żółty wskaźnik zależy od bieżącego paliwa.
W miejscu domu i drzewa z 2600 pojawiają się trzy warianty gór. Dwa odtworzono
z `original/Atari XL/image0.png`: wysoki masyw z niebieskimi stokami oraz
niższe brązowe szczyty z czarnymi grzbietami. Trzeci to pojedyncza góra
średniej wielkości z czarnym grzbietem. Wariant zależy od danych
obiektu i pozostaje ten sam po przesunięciu między blokami terenu.
Pozycja gór uwzględnia wspólny pas lądu na całej
wysokości bitmapy i sąsiednich wierszy interpolacji, również poza widocznym
obszarem. Margines uwzględnia trzy piksele wygładzania wody, do pięciu
pikseli skarpy i dwa piksele logiczne wolnego lądu. Zbyt wąskie wyspy
powodują przesunięcie gór na najbliższy dostatecznie szeroki pas lądu.
Pozycja jest zapamiętywana
do zmiany bloku terenu; rysowanie i kolizje korzystają z tego samego
przesunięcia i dokładnej nowej sylwetki.
Panel odtwarza układ 5200: P1/P2 i wynik po lewej, HI z rekordem po prawej,
GAME, paliwo i BRIDGE niżej, samoloty rezerwowe pod numerem mostu.
Rekord sesji jest wspólny dla obu graczy i pozostaje po R/restarcie gry;
liczba ikon rezerwowych odpowiada oryginalnemu licznikowi i może dojść do 9.
Cyfry liczników i ikony są przygotowane przy starcie; sprite'y aktualizują
tylko obraz/liczbę, bez ponownego rysowania bitmap w klatce gry.
Strumień A przypada na parzyste linie bloku, B na nieparzyste; ta kolejność
zachowuje czytelne litery FUEL wycięte w bitmapie zbiornika.
Most ma szerokość 32 pikseli logicznych i zajmuje zakres X 64–95, zgodny
z przewężeniem rzeki. Pozycję szerokiego sprite'a skorygowano o jeden piksel
względem wartości 63 przekazywanej przez oryginał do `CalcPosX`; ten sam
początek wykorzystują rysowanie i kolizje.
Panel zajmuje linie 182–218, z pojedynczą czarną linią oddzielającą go od gry.
Wynik rozpoczyna się w wierszu 5 panelu, GAME/BRIDGE w 18,
skala paliwa w 17, a rezerwy w 25. Współrzędne pól określa blok `HUD_*`
na początku `src/main.c`; zmiana kroju nie wymaga zmiany logiki gry.
Czarna stopka 219–229 mieści logo Activision skopiowane piksel po pikselu
z `original/Atari 5200/river_raid_5.gif` (obszar X 48–167, Y 211–217).
Bitmapa 120×7 zachowuje kształt napisu, pięć kolorów tęczy i ukośne
połączenie z literą A. Zaczyna się w X 48 canvasu, trzy wiersze pod górą
stopki. Osobny sprite i paleta zachowują kolory GIF-u po zaokrągleniu
do RGB555; przełącznik B&W i wygaszacz stosują oryginalne role kolorów.

Przed inicjalizacją gry `src/cover.asm` wyświetla okładkę `assets/cover.bmp`.
Bitmapa 320×180 zachowuje indeksy i wszystkie kolory palety, zaokrąglone
do RGB555. Zajmuje $1000–$F0FF XRAM; konfiguracja jest w $0280, paleta
w $0400, a bufor kolejnej palety w $0600. Obraz jest wyśrodkowany w Y=30
na canvasie 320×240. `tools/make_cover.py` przygotowuje 64 poziomy jasności
w obie strony.
Okładka, palety i bitmapa napisu są pakowane jako nazwane zasoby `.rp6502`:
`cover.bin`, `cover-fade.bin` i `cover-prompt.bin`. Program otwiera je na dysku
`ROM:` i czyta przez READ_XRAM; loader nie ładuje grafiki okładki automatycznie.
Palety są czytane do bufora, a po VSYNC kopiowane
do palety wyświetlanej, przed pierwszą linią okładki. Rozjaśnianie i wygaszanie
trwają po około sekundzie. Pod grafiką, w X=120, Y=222, jest wyśrodkowana
bitmapa „PRESS ANY KEY”: litery 5×7 w polu 80×8, białe na czarnym tle.
Osobna paleta w $0850 i bitmapa w $0800 pozostawiają kolory okładki bez zmian.
Konfiguracja w $02A0 przesuwa napis poza ekran co 30 VSYNC, co daje pół sekundy
widoczności i pół sekundy przerwy. Napis pojawia się po rozjaśnieniu i znika
po naciśnięciu klawisza, przed wygaszaniem.
Po rozjaśnieniu program czeka na dowolny klawisz HID,
również funkcyjny lub modyfikator; bity stanu LED nie zamykają okładki.
Klawisz zamykający ekran jest konsumowany wraz ze zwolnieniem, aby nie
uruchamiał dodatkowo sterowania grą. Kod i jego kilka bajtów roboczych leżą
w wolnej pamięci CPU od $D000, za oryginalnym ROM-em; nie zajmują stosu ani
buforów gry. Po wygaszeniu program przywraca pasek stopki z zasobu ROM,
a inicjalizacja gry odtwarza pozostałe zasoby w ponownie wykorzystywanym XRAM.

W trybie pokazowym stopkę zastępuje napis przewijany w lewo o jeden piksel
canvasu na klatkę. Tekst i czytelne glify są w `src/demo-footer.json`.
Po wyświetleniu pierwszej planszy licznik 180 VSYNC (3 sekundy) wstrzymuje
napis i pokaz. Oba ruszają w tej samej klatce. Pokaz wykonuje oryginalny
generator terenu i ruch przeciwników; pomija sterowanie samolotem, strzały,
zużycie paliwa i kolizje gracza. Pauza zatrzymuje również licznik oczekiwania.
Krój odtwarza grube litery 6×6 z próbek Atari XL/5200, w komórkach szerokości
8 pikseli logicznych; szersze „w” zajmuje 7 kolumn, a dodatkowy wiersz mieści
dolne części małych liter.
TM ma podniesione glify 3×5 i 5×5, bez odstępu przed znakiem. W miejscu `{Activision}`
wstawiana jest ta sama bitmapa logo z `src/graphics.h`. Generator
`tools/make_demo_footer.py` przygotowuje cały pasek przy budowaniu ROM-u;
program ładuje go do XRAM $3800 po zamknięciu okładki. VGA przewija bitmapę z zawijaniem poziomym,
bez rysowania liter przez CPU w każdej klatce. Osobna paleta zachowuje
jasnoszary kolor tekstu także przy wygaszaczu. Pauza zatrzymuje napis;
rozpoczęcie gry przywraca nieruchome logo, a koniec gry przywraca przewijanie.

Program oblicza kolizje pikseli przed wywołaniem oryginalnej logiki,
wypełniając jej flagi kolizji. Transfer linii i sprawdzanie sprite'ów z terenem
wykonuje asembler. Wejście obsługuje USB HID i dwa gamepady. Zegar gry
pochodzi z `RIA.vsync` przy 60 Hz. Licznik pominiętych klatek obejmuje
wszystkie operacje po początkowej konfiguracji obrazu, również restart,
odradzanie i zmianę gracza.

Pozycja przewijania, lista obiektów i przesunięcie napisu są przygotowywane
w RAM podczas poprzedniej klatki. Zaraz po VSYNC procedura asemblerowa
`present_frame` publikuje je razem w XRAM w około 0,3 ms przy 8 MHz,
przed dotarciem obrazu do pierwszej linii rzeki. Obliczenia terenu i kolizji
nie opóźniają tej publikacji. Sam brak pominiętych VSYNC nie wyklucza
rozrywania obrazu, gdy pozycję tła zmienia się w trakcie wyświetlania klatki.

Restart odtwarza początkowy, prosty korytarz szybką procedurą asemblerową.
W pomiarze Release przy 8 MHz koszt odtwarzania terenu spadł z około 391 ms
do 5–6 ms. Panel przesyła tylko kolumny zajęte przez cyfry, paliwo i logo;
rysowanie glifów wykonuje asembler, a częstotliwości PSG korzystają z tabel
przygotowanych przy starcie zamiast dzielenia w każdej klatce.
Zmiana gracza aktualizuje tylko paletę samolotu; pełna aktualizacja palet
pozostaje potrzebna przy zmianie trybu barw lub wygaszacza. Renderer brzegu
korzysta ze stałych buforów roboczych, ograniczając koszt dostępu do stosu cc65
podczas odradzania.
Przeliczanie koloru TIA i rozwijanie bitmapy samolotu do 4bpp wykonuje
asembler. Ogranicza to koszt klatki łączącej restart, odrysowanie panelu
i zmianę palety, bez zmiany pikseli samolotu ani barw.

PSG otrzymuje częstotliwości, głośność i rodzaj fali wynikające z oryginalnych
rejestrów AUDC/AUDF/AUDV. Sekwencje efektów pochodzą z oryginału, lecz szum
PSG nie odtwarza dokładnie generatorów wielomianowych TIA. RGB555 jest
przybliżeniem barw dopasowanym do dostarczonych screenshotów, a nie
analogowym modelem konkretnego telewizora.
Interfejsy sprzętowe opisują [VGA](https://picocomputer.github.io/vga.html)
i [RIA](https://picocomputer.github.io/ria.html).

## Referencje obrazu

Trzy PNG-y `s_RiverRaid_*.png` i pięć GIF-ów w `original/Atari 5200` są
odniesieniem dla palety, gór, skarp i układu panelu. PNG-y mają RGB:
woda (4, 37, 136), ciemny ląd (19, 102, 0), jasny ląd (79, 162, 26),
skarpa (74, 0, 0), panel (89, 89, 89). Palety GIF-ów i Atari XL są inne;
obecny port wybiera ciemniejsze kolory PNG-ów 5200.
Statki mają czerwony kadłub i turkusową dolną część, zbiorniki różowe
i szare pasy, helikoptery ciemny kadłub i złoty wirnik.
Host zaokrągla kolory do RGB555; mapowanie ról kolorów w `src/graphics.h`
zachowuje oryginalne przełączanie B&W i wygaszacz. Kolory nieobecne
w screenshotach nadal korzystają z przybliżenia odcienia TIA.

Trzy GIF-y w `original/Atari XL` i dziesięć JPEG-ów w `original/Atari 2600`
służą także do porównywania obiektów. Logika i generator trasy pochodzą
z 2600; ten port rozwija wygląd na podstawie XL/5200, a nie odtwarza rastra
ani reguł wersji XL/5200 1:1. Balony i czołgi są rozszerzeniami portu;
ich czytelne bitmapy w `src/graphics.h` odtwarzają sylwetki z PNG-ów 5200.
Oryginalny obraz danych 2600 pozostaje niezmieniony.

Skala paliwa pozostaje czarna dla obu graczy; ruchomy wskaźnik jest żółty.
Samolot drugiego gracza zachowuje czarną barwę z wcześniejszego wariantu
2600; panel i wynik obu graczy korzystają teraz z barw wzorowanych na 5200.
Lewy czarny pas blankingu HMOVE widoczny na obrazach Atari nie jest odtwarzany.
Screenshoty pokazują pojedyncze stany gry, więc nie potwierdzają jeszcze
zgodności faz ruchu, kolizji i animacji klatka po klatce.

## Weryfikacja i ograniczenia

`python tests/emulator_checks.py` sprawdza rzeczywisty ROM w RP6502-EMU
przy 8 MHz: wejście, pauzę, paliwo, trafienia, bonusowe życie, maksymalny
wynik, generator, śmierć, odradzanie, trudność, zmianę gracza i restart.
Scenariusz 1200 klatek sprawdza przewijanie z przyspieszaniem i strzelaniem.
Test terenu porównuje widoczne piksele kafelków, również skarp, z maskami
kolizji na całej wysokości pola gry. Sprawdza też dopasowanie mostu do brzegów,
ciągłość brązowego konturu na zakrętach i przejście skarp przez drogę.
Także pozostałe scenariusze kończące się w grze sprawdzają brak pominiętych
VSYNC, w tym odradzanie, tankowanie i zmiana gracza. Opcjonalny profil faz
klatki opisano w `tests/README.md`.
Testy są wyciszone, więc nie potwierdzają jakości brzmienia.

Pozostają odsłuch, porównanie rastra klatka po klatce z emulatorem Atari
i próba na fizycznym RP6502. Zachowanie logiki zachowano przez użycie
oryginalnych procedur; nie deklarujemy jeszcze zgodności obrazu i dźwięku 1:1.
