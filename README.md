# Image Resizer

Offline Windows aplikacija za pripremu slika. Korisnik ubaci jednu sliku, izabere jednu ili više gotovih dimenzija, način uklapanja i format, pregleda rezultat i sačuva sve izabrane veličine odjednom. Sve se obrađuje na računaru.

## Glavne mogućnosti

- Prevlačenje slike ili izbor fajla, uz pregled, ime, dimenzije, format i veličinu.
- Ugrađeni formati: Full HD, HD, Square, Portrait, Story / Reel, Web Banner, Website Hero, Thumbnail i Small Thumbnail. Katalog je u `src/image_resizer/resources/default_presets.json`.
- Više formata odjednom. Svaki daje poseban fajl.
- Sopstveni formati: ime, širina i visina, čuvanje za naredna pokretanja, izmena i brisanje. Menjaju se samo formati koje je korisnik napravio.
- Tri načina: **Crop** (popuni okvir i odseci višak, podrazumevano iz centra, uz ručno pomeranje), **Fit** (cela slika, dopuna pozadinom ili providnošću) i **Stretch** (tačne dimenzije, uz upozorenje da slika može da se izobliči).
- Pregled prati izabrani format i način. Crop se pamti posebno za svaki izabrani format. Izvoz koristi istu geometriju kao pregled.
- Izlazni format JPEG, PNG ili WEBP. Kvalitet za JPEG i WEBP, podrazumevano 90.
- Izvoz u izabrani folder, u podfolder sa imenom izvorne slike: `ime_1920x1080.jpg`. Ako fajl postoji, podrazumevano se preimenuje; može i da se preskoči ili prepiše.
- Tokom izvoza prozor ostaje odzivan. Na kraju su pregled rezultata i otvaranje izlaznog foldera.
- Svetla i tamna tema. Poslednji folder, format, kvalitet, tema, način uklapanja i boja pozadine pamte se lokalno.

Podešavanja i sopstveni formati nisu u instalacionom folderu. Na Windows-u su u `%APPDATA%\ImageResizer`. Na Linuxu su u `$XDG_DATA_HOME/ImageResizer` ili `~/.local/share/ImageResizer`.

## Podržani formati slika

Ulaz: JPG / JPEG, PNG, WEBP, BMP, TIFF.

Izlaz: JPEG, PNG, WEBP.

EXIF orijentacija se primenjuje pri učitavanju. JPEG ne čuva providnost; providne površine idu na izabranu boju pozadine. PNG i WEBP mogu da zadrže alfa kanal.

## Podešavanje razvojnog okruženja

Potreban je Python 3.12 ili noviji.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Na Windows-u se okruženje aktivira sa `.venv\Scripts\Activate.ps1`. Za pakovanje, na istoj mašini, dodatno:

```powershell
python -m pip install -e ".[dev,packaging]"
```

Virtuelno okruženje napravljeno na Linuxu ne radi na Windows-u. `packaging\build_windows.ps1` u tom slučaju staje i traži da se `.venv` obriše, pa pravi novo Windows okruženje.

## Pokretanje aplikacije

Iz korena projekta, sa aktivnim okruženjem:

```bash
python -m image_resizer
```

Ista komanda je `image-resizer` nakon instalacije paketa.

## Pokretanje testova

```bash
pytest
```

Testovi pokrivaju geometriju, učitavanje, izvoz, preset-e, podešavanja i deo prozora. Provere pakovanja ne pokreću PyInstaller ni Inno Setup; proveravaju spec, instalacionu skriptu, build skriptu, ikonicu i putanje resursa.

## Windows instalacioni paket

Instalacioni `.exe` se pravi samo na 64-bitnom Windows-u 10 ili novijem. Potrebni su:

- Python 3.12 ili noviji, 64-bitni
- [Inno Setup](https://jrsoftware.org/isinfo.php) 6.3 ili noviji (`ISCC.exe`)

Iz korena projekta:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_windows.ps1
```

Skripta odbija pokretanje van Windows-a. Pravi ili koristi `.venv`, instalira projekat sa dodatkom `packaging` (PyInstaller 6.11 ili noviji), sklapa aplikaciju u jedan folder bez konzolnog prozora i zatim zove Inno Setup. Verzija instalera dolazi iz `image_resizer.__version__` (trenutno 1.0.0).

Uspešan Windows build ostavlja:

```text
dist\ImageResizer\ImageResizer.exe
dist\ImageResizer\_internal\...
installer\ImageResizer-Setup-1.0.0.exe
```

`ImageResizer.exe` je ulaz. Python, PySide6, Pillow, `default_presets.json` i `app.ico` su u `_internal`. U razvoju se ti fajlovi čitaju iz paketa `image_resizer`. U spakovanom programu čitaju se iz `sys._MEIPASS\image_resizer\resources`.

Instaler se podrazumevano pokreće kao običan korisnik. Program ide u `%LOCALAPPDATA%\Programs\Image Resizer`, pravi prečicu u Start meniju i nudi neobaveznu prečicu na radnoj površini. Deinstalacija ide kroz Windows podešavanja ili stavku „Uninstall Image Resizer“ u Start meniju. Noviji instaler sa istim identifikatorom aplikacije menja postojeću instalaciju. Podešavanja u `%APPDATA%\ImageResizer` ostaju na mestu.

PyInstaller spec je `packaging/pyinstaller.spec`, Inno skripta je `packaging/installer.iss`. Ikonica programa i instalera je originalni `src/image_resizer/resources/app.ico`.

Izvršni fajl i instaler nisu digitalno potpisani. Windows SmartScreen može da upozori korisnika pri prvom pokretanju. Za deljenje klijentima potreban je code signing sertifikat.

## Poznata ograničenja

- Obrađuje se jedna izvorna slika. Nema grupnog unosa više fajlova.
- Stranica izlaza može imati najviše 16.384 piksela.
- Fajl veći od 512 MB se odbija. Slika sa više od 40 miliona piksela dobija upozorenje. Pillow i dalje odbija dekompresionu bombu, podrazumevano oko 179 miliona piksela.
- Pregled na ekranu je smanjen na najdužu stranicu od 1.600 piksela. Izvezena slika ima tačne dimenzije izabranog formata.
- Ako je izlaz veći od izvora, korisnik vidi da će slika biti uvećana.
- Stretch može da izobliči sliku. JPEG spaja providnost sa bojom pozadine.
- Windows instaler se pravi na 64-bitnom Windows-u, skriptom `packaging\build_windows.ps1`.
