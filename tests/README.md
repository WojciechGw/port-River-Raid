# Testy portu

Po zbudowaniu Release: `python tests/emulator_checks.py`.
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
`cover-prompt-blink` sprawdza pozycję, mały biały napis, zmianę widoczności
co 30 klatek, niezmienność palety okładki oraz ukrycie tekstu podczas fade.
`cover-prompt-on.png` i `cover-prompt-off.png` pokazują obie fazy.
Testy obejmują klawisze zwykłe, funkcyjne, modyfikatory,
Escape, przytrzymanie przed rozjaśnieniem, stan diod klawiatury oraz pamięć
wypełnioną zerami, $FF i losowo. Klawisz zamykający okładkę nie może uruchomić
sterowania grą. Zrzuty `cover-full.png`, `cover-half.png` i `cover-black.png`
pokazują kolejne fazy. Pozostałe scenariusze zamykają okładkę przed testowaniem gry.
Scenariusze `bridge-difficulty-*` sprawdzają cykl F3: 1 → 5 → 20 → 50 → 1,
brak powtarzania przy przytrzymaniu klawisza, cyfry BRIDGE w HUD, restart z pauzy,
zachowanie wyboru przy R, poziomy obu graczy, odradzanie oraz przejście 49 → 50.
`maximum-level-wrap` sprawdza powrót 50 → 49 przy nowym limicie.
Scenariusze `demo-footer-*` sprawdzają ruch napisu o piksel na klatkę,
zawijanie po całym przebiegu, jasnoszarą paletę także po aktywacji wygaszacza,
podniesione i mniejsze TM, zatrzymanie przy pauzie oraz przejście między
przewijanym napisem w pokazie i nieruchomym logo podczas gry.
Scenariusze `demo-startup-*` i `demo-start-before-delay` sprawdzają
trzysekundowe oczekiwanie po zamknięciu okładki, wspólny start napisu i ruchu rzeki, pauzę licznika
oraz rozpoczęcie gry przed upływem oczekiwania.
Scenariusz `fuel-lettering` odczytuje przesłaną do XRAM bitmapę zbiornika
i sprawdza kształty liter F, U, E oraz L w jej przezroczystych pikselach.
Wykrywa zamianę kolejności przeplatanych wierszy sprite'a.
Scenariusze `5200-enemy-bitmaps`, `balloon-*` i `score-object-11` sprawdzają
kolorową czaszę, nieprzezroczystą czerń czołgu, generowanie balonu, kolizje,
odbicie od brzegu i 60 punktów. `tank-*` sprawdzają ruch, pauzę, restart,
przesuwanie stanu wraz z blokiem terenu, punkty 250/750, dodatkowe życie,
limit rezerw i przepełnienie wyniku. `enemies-5200.png` pokazuje oba dodatki.
Scenariusze `bank-*` sprawdzają czołgi dojeżdżające z obu stron od mostu 7,
odstęp od widocznego brzegu, punkty, pauzę, restart i budżet klatki przy 8 MHz.
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
sprite'a i obie klatki gąsienic; `bank-tank-ninth-column-*` sprawdzają
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
Scenariusz `hud-record-and-reserves` sprawdza zapis wyniku 500 w polu HI,
zachowanie rekordu po restarcie oraz zgodność ikon samolotów rezerwowych
z oryginalnym licznikiem gry.
Scenariusz `mountains-stay-on-land` sprawdza wszystkie widoczne piksele
gór przy zakrętach, wąskich i szerokich wyspach oraz odbiciu bitmapy.
Zmiana przesunięcia pionowego nie może zmieniać poziomej pozycji gór;
test obejmuje jednoczesne dopasowanie sześciu obiektów i zmianę wzorów terenu.
Sprawdza wszystkie trzy warianty gór i wybiera do porównania bitmapę używaną
przez sprite. Każdy widoczny piksel musi pozostawiać co najmniej dwa piksele
logiczne odstępu od wody i brązowej skarpy, również po przekątnej. Scenariusz
obejmuje szeroką skarpę w przygotowanym terenie; test przewijania sprawdza
ten sam odstęp na planszy utworzonej przez grę.
Scenariusz `bridge-bank-alignment` tworzy drogę oryginalnym generatorem
i porównuje pozycję oraz szerokość sprite'a mostu z brzegami w buforze terenu.
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
| 28–29 | Wariant gry 0/1, bieżący gracz 0/1 |
| 30–31 | Pominięte VSYNC po początkowej konfiguracji obrazu, łącznie z restartem i odradzaniem |

Każdy przyrost jednostki przewijania korzysta z oryginalnego akumulatora.
Paliwo spala się o 32 na krok; tankowanie z pustą przestrzenią w zbiorniku
daje netto 480 na krok. Oryginalny wynik jest zapisany jako wskaźniki bitmap
cyfr, dlatego protokół nie przechowuje go jako liczby 32-bitowej.

## Diagnostyka okładki XRAM `$00B0`

Pierwszy bajt określa fazę: 1 rozjaśnianie, 2 oczekiwanie na klawisz,
3 wygaszanie, 4 czerń i oczekiwanie na zwolnienie klawisza, 0 przejście do gry.
Drugi bajt to wyświetlany poziom jasności 0–63. Sygnatura gry w `$0080`
pozostaje zerowa do przygotowania pierwszej planszy.

## Opcjonalny profil czasu

Opcja CMake `-DRIVER_PROFILE=ON` dodaje pomiar faz klatki przez
`RIA_ATTR_CLK_RUN_MS`. Domyślnie jest wyłączona. XRAM `$00A0–$00AB`
zawiera sześć maksymalnych czasów w milisekundach, jako 16-bitowe liczby
little endian: wejście, kolizje, logika oryginału, teren, rysowanie wraz
z panelem i dźwiękiem, cała klatka bez oczekiwania na VSYNC.
Maksima są niezależne i nie należy ich sumować. Profil dodaje koszt
odczytów zegara; testy płynności wykonujemy z `RIVER_PROFILE=OFF`.
