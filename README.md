# Webperf trends

Den här webbplatsen visar en historik över Webperf Core-körningar för
Helsingborgs stad. Den publiceras som GitHub Pages och byggs automatiskt när
`helsingborg-stad/webperf_core` har avslutat en mätning.

## Vad som sparas

Varje körning läggs i `data/runs/` som två filer:

- `<tidpunkt>.json` – det oförändrade råresultatet från Webperf Core.
- `<tidpunkt>.meta.json` – URL, mätprofil och Core-commit som användes.

`scripts/build.py` bygger sedan `data/summary.json`, startsidan och en
detaljrapport i `reports/` för varje körning. Radera inte råfilerna om
historiken ska gå att reproducera.

## Första publiceringen

1. Lägg till Actions-hemligheten `WEBPERF_TRENDS_TOKEN` i
   `helsingborg-stad/webperf_core`. Tokenen behöver **Contents: Read and
   write** för just detta repository.
2. Aktivera GitHub Pages för `helsingborg-stad/webperf_trends` och välj
   **Deploy from a branch**, `main` och mappen `/(root)`.
3. Kör workflowet **Webperf trend report** manuellt i Core-forken för att
   skapa den första datapunkten.

Efter det körs rapporten automatiskt varje måndag. Ändra mål-URL eller
mätprofil via workflowets manuella formulär; ändringen sparas i respektive
datapunkts metadata.

## Uppdatera Webperf Core

Använd GitHubs **Sync fork** i `helsingborg-stad/webperf_core` när ni vill
hämta ändringar från `Webperf-se/webperf_core`. Dashboarden och historiken
ligger här i ett separat repo och påverkas inte. Om tester eller deras poäng
ändras uppstår en tydlig versionsgräns i metadata för den körning där
uppdateringen infördes.

## Lokal ombyggnad

Efter att nya råresultat lagts i `data/runs/`:

```bash
python3 scripts/build.py
```

Det kräver bara Python 3.11 eller senare och inga externa paket.
