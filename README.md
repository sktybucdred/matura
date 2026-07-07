# 📐 Mapa maturalnej matematyki

**Interaktywny dashboard analityczny (Streamlit): gdzie w Polsce matura
z matematyki idzie najgorzej — per powiat i per szkoła, na tle języka
polskiego i angielskiego, w latach 2023–2025.**

🔗 **Działająca aplikacja:** [matura-w-polsce.streamlit.app](https://matura-w-polsce.streamlit.app)

## Co robi aplikacja

- **📊 Wąskie gardło** — pokazuje, że to matematyka (a nie polski czy angielski)
  jest przedmiotem, który najczęściej odbiera świadectwo dojrzałości
  (najsłabsza z trójki w ~94% powiato-lat).
- **🗺️ Mapa powiatów** — choropleth 379 powiatów: zdawalność, szacowana liczba
  oblewających (wolumen rynku) i odsetek podchodzących do rozszerzenia.
- **🏫 Rozwarstwienie** — rozkłady wyników szkół: LO vs technikum (luka rośnie:
  5,0 → 8,0 p.p. w rok), miasto vs wieś, publiczne vs niepubliczne.
- **🎯 Ambicje i trendy** — związek uczestnictwa w poziomie rozszerzonym ze
  skutecznością na podstawowym + trend 2023–2025 (z porównywalną linią
  „tylko LO").
- **💰 Rynek** — segmentacja rynku: liczba oblewających × zamożność powiatu
  (wynagrodzenia GUS BDL), ćwiartki od korepetycji premium po tanią naukę online.
- **📌 Wnioski** — synteza całości + konkretne listy powiatów do targetowania
  (premium / online / pilność), liczone na żywo z danych.
- **ℹ️ O danych** — metodologia, decyzje przy czyszczeniu, zastrzeżenia.

Filtry (rok, województwa, przedmiot, typ szkoły) przeliczają na żywo KPI,
wykresy i tabele. 7 typów wizualizacji: mapa choropleth, słupkowy, liniowy,
histogram, boxplot, scatter, heatmapa.

## Najważniejsze wnioski (2025)

1. **Matematyka to wąskie gardło matury** — zdawalność 88,4% vs 95,4% (polski)
   i 94,3% (angielski); najsłabszy przedmiot w ~94% powiatów. Rynek „ratowania
   matury" to ~30 tys. osób rocznie i rośnie.
2. **Geografia jest trwała** — rozstrzał między powiatami ~35 p.p., korelacja
   wyników rok-do-roku ~0,7: słabe powiaty to cecha strukturalna, nie szum.
3. **Technika to (ponad) połowa rynku** — ~15,5 tys. oblewających rocznie,
   w liczbach bezwzględnych **więcej niż licea** (~13,9 tys.) przy wyraźnie
   mniejszej liczbie zdających (94 vs 163 tys.); luka do LO rośnie
   (5,0 → 8,0 p.p. w rok).
4. **Zamożność wiąże się z ambicjami mocniej niż ze zdawalnością** — korelacja
   ważona płac GUS ze zdawalnością: 0,35; z odsetkiem podchodzących do
   rozszerzenia: 0,58 (współwystępowanie, nie przyczynowość).
5. **Dwa produkty, dwie geografie** — premium 1:1 w metropoliach (wolumen ×
   siła nabywcza); tania aplikacja online tam, gdzie oblewających dużo, a płace
   poniżej mediany, oraz na wsi (szkoły wiejskie słabsze nawet w ramach tego
   samego typu). Szczegóły i listy powiatów: zakładka **📌 Wnioski**.

## Dlaczego ten projekt

Prowadzę korepetycje z matematyki (głównie licealiści) i buduję aplikację do
treningu matematyki dla uczniów 12–18 lat. Ten dashboard to jednocześnie
research rynkowy: **gdzie popyt na wsparcie z matematyki jest największy** —
geograficznie (mapa powiatów), strukturalnie (LO/technikum, miasto/wieś,
szkoły dla dorosłych) i w czasie (trendy po reformie formuły egzaminu).
Przykładowe ustalenia: rynek „ratowania matury" to ~30 tys. osób rocznie;
wolumen siedzi w metropoliach, ale najostrzejsza potrzeba — w powiatach
o zdawalności ~65%, gdzie podaż stacjonarnych korepetycji jest najmniejsza.

## Skąd dane

| Źródło | Zakres | Licencja / warunki |
|---|---|---|
| **CKE — [mapa.wyniki.edu.pl](https://mapa.wyniki.edu.pl)** | Wyniki egzaminu maturalnego w **Formule 2023**, eksporty XLSX per powiat i per szkoła, lata 2023–2025, **aktualizacja wrześniowa (09)** = sesja główna + poprawkowa | dane publiczne administracji oświatowej |
| **GUS — Bank Danych Lokalnych** ([bdl.stat.gov.pl](https://bdl.stat.gov.pl)) | przeciętne miesięczne wynagrodzenia brutto per powiat (zmienna 64428, rok 2024), pobrane z publicznego API skryptem `scripts/fetch_bdl_wages.py` | dane publiczne GUS; **uwaga:** wynagrodzenia liczone wg **miejsca pracy**, nie zamieszkania (efekt powiatów „sypialnianych"), podmioty >9 pracujących |
| **Państwowy Rejestr Granic (PRG)** — [Geoportal](https://www.geoportal.gov.pl) | granice powiatów | dane publiczne GUGiK, udostępniane nieodpłatnie (art. 40a ust. 2 pkt 1 ustawy Prawo geodezyjne i kartograficzne) |
| [waszkiewiczja/GeoJSON-Polska-…](https://github.com/waszkiewiczja/GeoJSON-Polska-Wojewodztwa-Powiaty-Gminy) | konwersja PRG → GeoJSON/WGS84, uproszczenie geometrii (stan: 08.2025) | repozytorium publiczne; dopasowanie po kodach TERYT (`JPT_KOD_JE`) |

Surowe pliki XLSX leżą w `data/raw/` i są jedynym źródłem prawdy. Ponieważ
parsowanie ~20 MB XLSX trwa ~minutę, oczyszczone ramki są cache'owane w
`data/processed/*.parquet`; **dorzucenie pliku za nowy rok (np.
`EM2023_2026_powiaty_09.xlsx`) do `data/raw/` automatycznie przebudowuje
cache** — bez zmian w kodzie.

## Decyzje przy czyszczeniu danych (`data.py`)

- **Walidacja plików**: eksporty z portalu bywają stronami HTML (~5 KB) —
  odrzucane po rozmiarze i teście struktury ZIP.
- **Trzyrzędowy nagłówek** XLSX (pasmo → przedmiot+poziom → metryka) składany
  przez forward-fill scalonych komórek; normalizacja nazw (prefiks `* `,
  białe znaki, znaki nowej linii, wielkość liter).
- Używamy **wyłącznie wariantów przedmiotów z sufiksem „(M)"** — bliźniacze
  kolumny bez „(M)" są w źródle puste.
- Z ~75 wariantów przedmiot×poziom zawężenie do: **matematyka PP i PR, język
  polski PP, język angielski PP, zdawalność ogólna** — reszta nie służy
  narracji.
- **TERYT jako tekst** (wiodące zera, np. `0401`); rok egzaminu z nazwy pliku,
  nie z zawartości.
- Usunięte **pseudo-powiaty „OKRĘGOWA KOMISJA EGZAMINACYJNA…"** (8 wierszy/rok,
  po kilkunastu–kilkudziesięciu zdających przypisanych wprost do OKE) —
  dublowały kody TERYT miast-siedzib komisji i psuły mapę.
- **Braki danych**: puste metryki małych jednostek zostają jako NaN i są
  jawnie pomijane per wykres. Wyjątek: pusta „liczba zdających" PR oznacza
  **0 zdających** (portal raportuje nawet n=1, utajnia dopiero wyniki), więc
  wskaźnik ambicji traktuje ją jako zero.
- **Kolumny pochodne**: wskaźnik ambicji (zdający PR / zdający PP), luki
  polski−matematyka i angielski−matematyka, odchylenia od średniej krajowej
  **ważonej liczbą zdających**, flagi LO/technikum i miasto/wieś.

## Zastrzeżenia metodologiczne

- **Rok 2023 obejmuje niemal wyłącznie licea** — technika kończyły wtedy
  jeszcze Formułę 2015 (w danych: 16 techników vs ~1 750 od 2024 r.).
  Porównania LO/technikum liczone są od 2024 r., a rocznik 2023 na trendach
  ma adnotację wprost na wykresie. Lata „niepełne" wykrywane są dynamicznie
  (`partial_coverage_years`), nie hardcodowane.
- **Poziom rozszerzony nie ma zdawalności** — dla przedmiotów dodatkowych nie
  istnieje próg zdania; porównujemy uczestnictwo i średnie wyniki.
- Dane są **zagregowane per lokalizacja** — wnioski dotyczą powiatów/szkół,
  nie pojedynczych uczniów (ryzyko błędu ekologicznego).
- Korelacje w aplikacji są **ważone liczbą zdających** — mikropowiaty to
  głównie szum małych prób; bez ważenia korelacja płace↔zdawalność spada
  z 0,35 do ~0,17 (ujawniamy obie wartości, dobór metody nie jest
  cherry-pickingiem).
- „Liczba oblewających" to szacunek: `zdający × (1 − zdawalność)`.

## Jak uruchomić lokalnie

Wymagany Python 3.11+.

```bash
git clone https://github.com/sktybucdred/matura.git
cd matura
pip install -r requirements.txt
streamlit run app.py
```

Aplikacja wstanie na `http://localhost:8501`. Pierwsze uruchomienie czyta
gotowe parquety (~1 s); pełne przeparsowanie surowych XLSX można wymusić
przez `python data.py` (~1 min, przy okazji drukuje raport kontrolny).

## Struktura projektu

```
app.py                 # orkiestrator Streamlit: filtry, KPI, zakładki
charts.py              # wykresy Plotly (7 typów, polskie formatowanie liczb)
data.py                # walidacja, parser, czyszczenie, cache parquet, GeoJSON
notebooks/eda.ipynb    # analiza eksploracyjna: 5 wzorców z liczbami
data/raw/              # surowe eksporty XLSX z mapa.wyniki.edu.pl (źródło prawdy)
data/processed/        # cache parquet + manifest (auto-przebudowa)
data/geo/              # granice powiatów (GeoJSON, PRG/Geoportal)
requirements.txt
```
