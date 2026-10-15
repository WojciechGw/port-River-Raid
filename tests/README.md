# Testy portu

Po zbudowaniu Release: `python tests/emulator_checks.py`.
`python tests/emulator_checks.py --bridge-tanks-only` sprawdza przetrwanie
czołgów na dojazdach po zniszczeniu mostu, zatrzymanie przed przerwą,
punktację, bezpośrednie trafienia oraz przewijanie i restart etapu.
Testy `duo-bridge-spares-tank-*` sprawdzają tę regułę dla obu graczy DUO.
Zestaw obejmuje także strzelanie ocalałego czołgu w stronę rzeki, równoczesne
działanie trzech czołgów, pauzę, przewijanie, restart i zachowanie pocisku po F1.
Testy `duo-road-gunner-phase*` sprawdzają bezpieczny przelot pocisku oraz
śmiertelny rozbryzg dla każdego z graczy.
Opcje `--build` i `--emulator` wskazują inny katalog lub emulator.
Potrzebne są `riverraid.rp6502` i odpowiadający plik `riverraid.dbg`.
Nie są wymagane dodatkowe pakiety Pythona.

Scenariusze uruchamiają rzeczywisty kod CPU przy 8 MHz, bez okna i dźwięku.
Sprawdzają także komunikaty błędów emulatora, ponieważ niektóre wersje
zwracają kod zero mimo błędu skryptu. Pliki skryptów i PNG trafiają do
`build/cc65/release/checks`.
Scenariusze `cover-*` porównują bitmapę z `assets/cover.bmp`, sprawdzają
wszystkie poziomy palety fade in/out oraz zachowanie okładki podczas
oczekiwania na klawisz. Parser ROM sprawdza nazwane zasoby okładki, palet
i napisu oraz brak automatycznego wczytywania okładki do XRAM.
`python tests/emulator_checks.py --screens-only` uruchamia testy plansz.
`manual-fades-and-wait` sprawdza obraz z `assets/manual.bmp`, wszystkie poziomy
fade in/out, napis PRESS ANY KEY TO START THE GAME oraz oczekiwanie na osobny
klawisz. `manual-key-*` sprawdzają różne klawisze i ich zużycie przed ekranem
wyboru trybu.
`outro-fades-hold-and-exit` sprawdza `assets/outro.bmp` po Esc, wszystkie poziomy
obu fade, napis SEE YOU NEXT TIME!, pełne 180 klatek i wyjście dopiero po czerni.
Test utrzymuje Esc i inne klawisze; napis pozostaje nieruchomy i nie miga.
`outro-*-held-escape` sprawdzają wyjście z pokazu i z gry oraz zatrzymanie
wszystkich trzech backendów dźwięku przed ponownym użyciem pamięci okładki.
`audio-*` wymagają emulatora z rozszerzeniem PCM (`XREG(0,1,2,base)`).
Sprawdzają format 8 kHz mono, reakcję silnika na gaz, priorytet wybuchu,
tankowania i alarmu, pauzę oraz ciszę w trybie pokazowym. Test strumienia
symuluje odbiór 8000 próbek/s przez 1200 klatek przy przewijaniu i strzelaniu;
kontroluje czas klatki z działającym generatorem, ponieważ `--mute` sam nie
opróżnia bufora PCM. Testy próbek wymuszają odbiór kolejnych bloków i sprawdzają
zawijanie bufora oraz publikowanie tylko kompletnych stron.
`checks/audio/*-cpu.wav` zawierają próbki wygenerowane przez rzeczywisty kod
6502: wolny/szybki silnik, wybuch i pocisk. To surowe PCM 8 kHz, bez
interpolacji miksera i toru audio fizycznego komputera.
Opcja `--audio-only` uruchamia wyłącznie scenariusze dźwięku.
Testy `f10-*` obejmują cykl PSG/OPL2/PCM, przytrzymanie klawisza,
pauzę, F9, powrót z F1 oraz przełączanie podczas lotu solo i DUO.
Ponieważ emulator obsługuje PCM, brak tego interfejsu jest sprawdzany przez
symulację negatywnego wyniku funkcji wykrywającej jego dostępność.
Sam zestaw przełączania można uruchomić opcją `--audio-switch-only`.
Pełny zestaw wymaga PCM, natomiast scenariusze `audio-psg-*` i `audio-opl2-*`
wybierają backend przez rzeczywiste argumenty programu. Sprawdzają wzrost
względnej szerokości pasma silnika przy przyspieszaniu, niezależność efektów,
wyciszenie pauzy/demo, wyjście i 1200 klatek gry przy 8 MHz dla obu syntezatorów.
Sprawdzają także jednoczesne działanie silnika, pocisku, wybuchu i tankowania
na wszystkich ośmiu oscylatorach PSG / dziewięciu kanałach OPL2 oraz płynne
obniżanie częstotliwości pocisku przez cały czas jego dźwięku.
W OPL2 sprawdzają również szumowy instrument wybuchu, jego pełny czas zaniku
oraz opadanie pasma i głośności podczas eksplozji.
`audio-opl2-small-speed-change` odtwarza ten sam stan generatora szumu przy
dwóch bliskich prędkościach, aby wykryć skokowe sterowanie pasmem silnika.
`audio-*-capture-engine-ramp` używa rzeczywistych klawiszy przyspieszania,
zwalniania i ponownego przyspieszania. `audio-psg-clock-pause` sprawdza, że
licznik próbek szumu zatrzymuje się podczas pauzy i rusza po jej wyłączeniu.
Scenariusze opcji obejmują domyślny OPL2, wybór `/psg`, `/opl2`, `/pcm`, `/auto`,
pierwszeństwo ostatniej opcji, wielkie litery, pomoc i odrzucenie nieznanego
parametru. Testy PCM przekazują jawnie `/pcm`.
Pliki `audio-psg-*.json` i `audio-opl2-*.json` zawierają rejestry odczytane
z uruchomionego programu w kolejnych klatkach. `tools/preview_synth.py`
tworzy z nich odsłuchy oraz pomiary FFT i energii detali Haara. OPL2 wymaga
dodatkowo biblioteki z `tools/opl_preview.c` i źródła emu8950 z firmware
(`--opl-library`); nie jest ona potrzebna do testów ROM-u ani do kompilacji gry.
Te odsłuchy są modelami syntezatorów, a nie nagraniami fizycznego toru audio.
Ślad PSG zawiera również spójny stan generatora szumu i licznik wykonanych
przerwań VIA. Model odtwarza rzeczywistą sekwencję binarną, rozkładając te
przerwania równomiernie wewnątrz klatki; nie odtwarza czasu każdego zapisu na magistrali.
Po wygenerowaniu wszystkich dwunastu próbek `tools/compare_synth.py --previews
build/audio-v2` sprawdza pasmo silnika, jego zmianę wraz z gazem, brak dominującego
stałego tonu, nadmiaru wysokich częstotliwości i przesterowania przy nakładaniu
efektów. Opcjonalne `--reference ścieżka/do/RiverRaid.wav` dodaje odsłuch
porównawczy: oryginał XL/XE, model PSG, model OPL2, z wyrównanym poziomem RMS.
Próbki nagrania oryginalnego pozostają poza ROM-em i plikami śledzonymi przez Git.
`audio-engine-response` zapisuje ustawienia odczytane z ROM-u do
`audio-engine.json`. `python tools/preview_audio.py build/cc65/release/checks/audio-engine.json`
tworzy próbki WAV przed/po zmianie oraz pomiary modeli PSG/PCM; nie są to
nagrania z urządzenia audio emulatora ani z fizycznego Picocomputera.
`cover-prompt-blink` sprawdza pozycję, mały biały napis, zmianę widoczności
co 30 klatek, niezmienność palety okładki oraz ukrycie tekstu podczas fade.
`cover-prompt-on.png` i `cover-prompt-off.png` pokazują obie fazy.
Testy obejmują klawisze zwykłe, funkcyjne, modyfikatory,
Escape, przytrzymanie przed rozjaśnieniem, stan diod klawiatury oraz pamięć
wypełnioną zerami, $FF i losowo. Klawisz zamykający okładkę nie może uruchomić
sterowania grą. Zrzuty `cover-full.png`, `cover-half.png` i `cover-black.png`
pokazują kolejne fazy. Pozostałe scenariusze zamykają okładkę przed testowaniem gry.
`function-key-mapping` sprawdza niezależne przełączanie sterowania pociskiem
przez F5 (P1) i F8 (P2), brak powtarzania przy przytrzymaniu oraz brak funkcji F6.
`python tests/emulator_checks.py --controls-only` sprawdza F4 (kolorystyka),
F5/F8 i instrukcję pod F1. Testy powrotu porównują stan gry, teren, HUD,
samoloty i palety przed i po instrukcji we wszystkich trzech trybach.
Obejmują przytrzymane F1, ponowne otwarcie, zachowanie pauzy oraz backendy audio.
Testy `f9-mute-*` sprawdzają wyciszenie i przywrócenie dźwięku we wszystkich
trybach gry i backendach, przytrzymanie klawisza oraz zachowanie ustawienia
po F1, restarcie i zmianie trybu.
Testy `sound-status-*` sprawdzają położenie (0,0), czcionkę 8×8, białą paletę,
ikony nutki i przekreślonej nutki, odstęp jednej kolumny tekstowej,
wszystkie generatory i powrót z F1 w każdym trybie gry.
Obejmują pełny pasek z `/v` (także `/V`) oraz domyślny widok, w którym
pojawia się wyłącznie przekreślona nutka po wyciszeniu dźwięku.
Zapisują także obrazy `sound-status-on-game*.png` i `sound-status-off-game*.png`.
Test `game2-player-hud-colors` sprawdza kolor etykiety, punktów i zapasowych
samolotów po rzeczywistym przekazaniu tury P1 do P2, po F4 i powrocie z F1.
Sprawdza też zachowanie koloru mostu i przezroczystość tła ikon żyć.
Scenariusze `bridge-difficulty-*` sprawdzają cykl F3: 1 → 5 → 20 → 50 → 1,
brak powtarzania przy przytrzymaniu klawisza, cyfry BRIDGE w HUD, restart z pauzy,
zachowanie wyboru przy R, poziomy obu graczy, odradzanie oraz przejście 49 → 50.
`maximum-level-wrap` sprawdza powrót 50 → 49 przy nowym limicie.
Scenariusze `demo-footer-*` sprawdzają ruch napisu o piksel na klatkę,
zawijanie po całym przebiegu, jasnoszarą paletę także po aktywacji wygaszacza,
podniesione i mniejsze TM, zatrzymanie przy pauzie oraz przejście między
przewijanym napisem w pokazie i nieruchomym logo podczas gry.
Scenariusz `game-fade-all-palettes` sprawdza rozjaśnianie całego ekranu po
okładce: wszystkie 288 kolorów, zachowanie przezroczystości, 32 kroki co dwa
VSYNC-i oraz dokładne przywrócenie palet. Potwierdza nieruchomą scenę podczas
przejścia i wspólny start napisu oraz rzeki zaraz po nim. Zrzuty
`game-fade-black.png`, `game-fade-16.png` i `game-fade-32.png` pokazują przebieg.
`game-start-during-fade` sprawdza start gry klawiszem przytrzymanym w trakcie przejścia.
Scenariusz `fuel-lettering` odczytuje przesłaną do XRAM bitmapę zbiornika
i sprawdza kształty liter F, U, E oraz L w jej przezroczystych pikselach.
Wykrywa zamianę kolejności przeplatanych wierszy sprite'a.
Porównuje także całą bitmapę z referencją Atari 5200: cztery pasy po sześć
wierszy, F i E na różowym tle, U i L na jasnoszarym oraz pełny wiersz pod L.
Scenariusze `5200-enemy-bitmaps`, `balloon-*` i `score-object-11` sprawdzają
kolorową czaszę, nieprzezroczystą czerń czołgu, generowanie balonu, kolizje,
odbicie od brzegu i 60 punktów. `tank-*` sprawdzają ruch, pauzę, restart,
przesuwanie stanu wraz z blokiem terenu, punkty 250/750, dodatkowe życie,
limit rezerw i przepełnienie wyniku. `enemies-5200.png` pokazuje oba dodatki.
`bridge-tank-edge-entry-*` sprawdzają wjazd od obu krawędzi planszy, odbicie
bitmapy i pauzę, a `bridge-tank-past-old-turn-*` brak zawracania wewnątrz planszy.
Scenariusze `bank-*` sprawdzają czołgi dojeżdżające z obu stron od mostu 7,
odstęp od widocznego brzegu, punkty, pauzę, restart i budżet klatki przy 8 MHz.
`bank-round-falling-*` sprawdzają biały pocisk opadający od lufy do dolnej
linii gąsienic w obu kierunkach oraz wybuch na końcowej wysokości lotu.
Pocisk przelatuje bezpiecznie przez samolot, ale jego wybuch powoduje kolizję.
Odczyt bitmap potwierdza białe, wypełnione koła o średnicach 4, 8 i 16 pikseli,
z fazą skasowania po każdym rozmiarze; skasowane koło nie zagraża samolotowi.
Trafienie FUEL przez pocisk czołgu niszczy zbiornik bez punktów dla gracza;
pocisk mijający nieprzezroczyste piksele zbiornika nie niszczy go.
Podglądy: `bank-tanks.png` i `tank-circle-*.png`.
Scenariusze `bank-random-range-*` sprawdzają różne zasięgi kolejnych strzałów
z obu stron rzeki, zakręty, wyspy oraz wstrzymanie ognia w zbyt wąskim lub
zamkniętym kanale. Cały największy wybuch musi mieścić się w wodzie.
`bank-tank-wider-bitmaps` sprawdza rysunek 9×9, przezroczyste wypełnienie
sprite'a i trzy klatki gąsienic. `tank-three-track-phases` sprawdza cykl animacji
czołgów na drodze i obu brzegach, stały rytm przy zawinięciu licznika klatek
oraz zatrzymanie podczas pauzy; `bank-tank-ninth-column-*` sprawdzają
trafienie dziewiątej kolumny i chybienie tuż obok dla obu kierunków czołgu.
Scenariusze `helicopter-*` sprawdzają obie sylwetki i klatki wirnika, jasny
poziomy pocisk tylko dla typu 2, oba kierunki lotu pocisku, pauzę, restart,
kolizję z samolotem oraz budżet klatki przy kilku strzelających helikopterach.
`helicopter-frequency-level-*` sprawdzają brak typu 2 przed poziomem 5
i proporcję jednego strzelającego na cztery nowe helikoptery.
`helicopter-shot-shore-*` sprawdzają znikanie pocisku na obu brzegach
i z obu stron wyspy; pocisk przelatujący przez wodę pozostaje aktywny.
`helicopter-shot-immediate-refire-*` sprawdzają klatka po klatce kolejny
strzał bez przerwy po trafieniu w brzeg, w obu kierunkach.
`helicopter-shot-refire-blocked-*` sprawdzają, że nie strzela zniszczony
helikopter, typ 1 ani helikopter z wylotem pocisku na lądzie.
`helicopter-type-block-scroll` sprawdza zachowanie typu przy zmianie bloku.
`bank-splash-cleared-on-death-*` sprawdzają natychmiastowe ukrycie obu
wybuchów i usunięcie pocisków po śmierci gracza, także wskutek kolizji z lądem.
`bank-tank-last-life-scroll-*` sprawdzają oba brzegi po utracie ostatniego
życia: zgodne przewijanie czołgu i scenerii, pauzę oraz usunięcie czołgu
po wyjechaniu poza ekran, bez nowych strzałów i nowych czołgów w trybie demo.
Scenariusz `scores-start-at-zero` sprawdza zerowe wyniki P1, P2 i HI po
uruchomieniu oraz zmianie trybu F2; numer GAME nie może trafić do punktacji.
Scenariusz `hud-record-and-reserves` sprawdza zapis wyniku 500 w polu HI,
zachowanie rekordu po restarcie oraz zgodność ikon samolotów rezerwowych
z oryginalnym licznikiem gry.
Scenariusz `mountains-stay-on-land` sprawdza wszystkie widoczne piksele
gór przy zakrętach, wąskich i szerokich wyspach oraz odbiciu bitmapy.
Zmiana przesunięcia pionowego nie może zmieniać poziomej pozycji gór;
test obejmuje jednoczesne dopasowanie sześciu obiektów i zmianę wzorów terenu.
Sprawdza wszystkie warianty gór (pięć) i wybiera do porównania bitmapę używaną
przez sprite. Każdy widoczny piksel musi pozostawiać co najmniej dwa piksele
logiczne odstępu od wody i brązowej skarpy, również po przekątnej. Scenariusz
obejmuje szeroką skarpę w przygotowanym terenie; test przewijania sprawdza
ten sam odstęp na planszy utworzonej przez grę.
Scenariusz `bridge-bank-alignment` tworzy drogę oryginalnym generatorem
i porównuje pozycję oraz szerokość sprite'a mostu z brzegami w buforze terenu.
Pomost zachodzi na oba brzegi po osiem logicznych pikseli.
`bridge-5200-structure` porównuje brązowe belki, środkowy pas, dolne czarne
podpory i kolory z referencją 5200 oraz sprawdza wyrównanie pasa na drodze.
`bridge-edge-*` sprawdzają trafienie i chybienie obu poszerzonych krawędzi.
Dekoduje też tekstury kafelków i porównuje wszystkie widoczne piksele terenu
z maskami kolizji; brązowe skarpy muszą pozostać po stronie lądu.
Scenariusz `river-bank-contours` sprawdza brązowy kolor na każdym styku
wody z lądem, również na poziomych stopniach zakrętów i przez pas drogi.
Porównuje też szerokości skarp po obu stronach rzeki. Kafelki mieszające wodę
ze skarpą muszą odpowiadać interpolowanym granicom `river_left`/`river_right`;
na prostych szerokość zmienia się najwyżej o jeden piksel między wierszami.
`river-banks.png` pokazuje ten kontur w emulatorze.
Pomiar szerokości widocznego brązowego pasa prostopadle do rzeki porównuje
odcinki pionowe, łagodnie nachylone i strome; grubość musi maleć w tej
kolejności. Sprawdzany jest obraz intro i teren po 1200 klatkach przewijania.
Nachylenie dużych odcinków określają maski rodzimego terenu, niezależnie od
drobnych ząbków. Osobny pomiar sprawdza, czy na długim prostym fragmencie
granica wody odchyla się o 0–3 piksele i kilkukrotnie zmienia kierunek,
jak brzeg na referencji Atari XL. Wykrywa pas skarpy przy idealnie prostej wodzie.
Próba mostu zmienia ręcznie kontekst generatora nad zachowanym terenem intro,
więc sprawdza ciągłość i kolizje, a gładkość szerokości mierzymy w scenach
wygenerowanych podczas normalnego działania gry.
Testy `bridge-edge-63` i `bridge-edge-95` sprawdzają trafienia przy obu krawędziach.
Scenariusze `smoothed-bank-*` sprawdzają rzeczywistą kolizję pocisku po obu
stronach interpolowanej granicy zewnętrznego brzegu i wyspy, także gdy
oryginalne bity PF wskazują jeszcze ląd. Po 1200 klatkach przewijania test
ponownie porównuje teren z maskami, kontur skarp i piksele gór z wodą.
`player-*-rim` sprawdzają przelot samolotu nad skarpą obu brzegów i obu
krawędzi wyspy. `player-*-ground` przesuwają go o jeden piksel, aby skrzydło
dotknęło podłoża, i sprawdzają utratę samolotu. `missile-*-rim` sprawdzają
kolizję pocisku w tych samych miejscach. Granice kolizji gracza są także
porównywane ze wszystkimi widocznymi pikselami terenu po starcie i po
1200 klatkach przewijania: woda i brązowa skarpa muszą być bezpieczne.
`jet-bitmap` porównuje wynik szybkiej konwersji 4bpp z oryginalną bitmapą CPU.
Każdy scenariusz kończący się w grze sprawdza również zerowy licznik pominiętych
VSYNC; pomiar obejmuje restart, odradzanie, tankowanie i zmianę gracza.
`two-player-switch` sprawdza także nieprzezroczystą czarną paletę samolotu
drugiego gracza po przełączeniu.
Scenariusz `vsync-world-presentation` sprawdza buforowanie metadanych obrazu:
pozycja tła i cała lista obiektów są publikowane przy następnej klatce,
wraz z przesunięciem napisu, a przygotowanie kolejnego obrazu nie zmienia
deskryptorów wyświetlanej już klatki.
Test `scroll-and-performance` wykonuje dodatkowo 1200 klatek z przyspieszaniem
i ciągłym strzelaniem. `restart-and-palette-performance` łączy odtwarzanie
terenu z przełączaniem palety po rozgrywce. Wymagany jest zoptymalizowany
wariant Release.

Rzadkie sytuacje przygotowujemy podczas pauzy przez zapis oryginalnych
zmiennych w RAM `$80–$FF`. Wybrane testy zerują maski terenu w bezpiecznym
korytarzu, aby odizolować sprawdzaną kolizję. Symbole hosta pochodzą z `.dbg`.
ROM nie zawiera poleceń testowych. Po wznowieniu wynik oblicza oryginalna
logika, a nie kod testu. Testy nie zastępują porównania z obrazem TIA.

## Diagnostyka XRAM `$0080`

32 bajty aktualizowane przez hosta, protokół **3**. Liczby wielobajtowe
są little endian. Dane służą obserwacji, nie sterowaniu grą.

| Offset | Znaczenie |
| --- | --- |
| 0–1 | Sygnatura `$52`, wersja 3 |
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
| 28–29 | Wariant gry 0/1/2, bieżący gracz 0/1 |
| 30–31 | Pominięte VSYNC po początkowej konfiguracji obrazu, łącznie z restartem i odradzaniem |

Każdy przyrost jednostki przewijania korzysta z oryginalnego akumulatora.
Paliwo spala się o 32 na krok; tankowanie z pustą przestrzenią w zbiorniku
daje netto 480 na krok. Oryginalny wynik jest zapisany jako wskaźniki bitmap
cyfr, dlatego protokół nie przechowuje go jako liczby 32-bitowej.

## Diagnostyka okładki XRAM `$00B0`

Pierwszy bajt określa fazę: 1 rozjaśnianie, 2 oczekiwanie na klawisz,
3 wygaszanie, 4 czerń i oczekiwanie na zwolnienie klawisza, 0 przejście do gry.
Drugi bajt to wyświetlany poziom jasności 0–63. Sygnatura gry w `$0080`
pozostaje zerowa do przygotowania pierwszej planszy. Bajt `$00B4` określa
wyświetlany obraz: 0 okładka, 1 outro, 2 instrukcja.

## Opcjonalny profil czasu

Opcja CMake `-DRIVER_PROFILE=ON` dodaje pomiar faz klatki przez
`RIA_ATTR_CLK_RUN_MS`. Domyślnie jest wyłączona. XRAM `$00A0–$00AB`
zawiera sześć maksymalnych czasów w milisekundach, jako 16-bitowe liczby
little endian: wejście, kolizje, logika oryginału, teren, rysowanie wraz
z panelem i dźwiękiem, cała klatka bez oczekiwania na VSYNC.
Maksima są niezależne i nie należy ich sumować. Profil dodaje koszt
odczytów zegara; testy płynności wykonujemy z `RIVER_PROFILE=OFF`.

## GAME 3 DUO

`python tests/emulator_checks.py --duo-only` sprawdza osobne sterowanie,
prędkości, zasoby, punktację i odradzanie, a także wyprzedzanie, kolizje oraz
pociski na różnych wysokościach. Każdy scenariusz kontroluje licznik
pominiętych VSYNC przy 8 MHz. Pełny zestaw uruchamia również te scenariusze.
Testy wspólnej porażki sprawdzają pojedyncze odjęcie życia za samolot,
restart aktualnego etapu z jego zapisanym stanem generatora, zachowanie
wyników, pełne paliwo, wyzerowanie przewagi oraz kontynuację z jednym graczem
bez żyć. Koniec gry następuje dopiero po wyczerpaniu obu pul żyć.
Testy limitu żyć obejmują premię 9 → 10 i zatrzymanie na 10 dla obu graczy,
zarówno za zwykłe obiekty, jak i czołgi, oraz utratę samolotu z pełnej puli.
Ikony żyć są sprawdzane w układzie 5+5 i przy przejściu do GAME 1.

Diagnostyka XRAM `$00C0` zawiera dwa rekordy po **23 bajty**, kolejno P1 i P2:
pola 0–18 odwzorowują rejestry gracza z `src/duo.asm`, 19 to stan
(0 wyeliminowany, 1 aktywny, 2 czeka na most, 3 czeka na bezpieczne miejsce),
20 to licznik eksplozji, 21 to kandydat X odrodzenia, a 22 to ekranowe Y
samolotu w obszarze rzeki (bez przesunięcia `RIVER_TOP`). Y dotyczy bieżącej
klatki; prędkość w polu 3 uwzględnia już przyspieszenie do następnego kroku.
