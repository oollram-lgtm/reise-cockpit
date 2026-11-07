# Reise-Cockpit: AIDA Skandinavien 2027

Webseite für unsere Gruppe (5–6 Erwachsene): Kabinen-Konstellationen, Bahnanreise ab Hanau,
Preisverlauf und Buchungsfahrplan. Geplante Adresse: **https://reise.bigbanker.de**

## Aufbau
| Pfad | Inhalt |
|---|---|
| `site/index.html` | Die komplette Webseite (statisch, ohne Server) |
| `site/data/prices.json` | Alle Preise + Verlauf + Hinweise; wird täglich aktualisiert |
| `scripts/merge_prices.py` | Übernimmt einen neuen Preis-Schnappschuss, erkennt Preissenkungen |
| `AGENT.md` | Arbeitsanweisung für den täglichen Preis-Agenten |

## Lokal ansehen
```bash
python -m http.server 8765 --directory site
```
Dann http://localhost:8765 öffnen.

## Online stellen (GitHub Pages + IONOS)
1. GitHub-Konto anlegen, Repository `reise-cockpit` erstellen, diesen Ordner hochladen.
2. Repository → Settings → Pages: Quelle „GitHub Actions“ oder Branch `main`, Ordner `/site`
   (falls nur `/` oder `/docs` angeboten wird: Workflow `.github/workflows/pages.yml` nutzen).
3. Custom domain: `reise.bigbanker.de` eintragen, „Enforce HTTPS“ aktivieren.
4. IONOS → Domains & SSL → bigbanker.de → DNS → Eintrag hinzufügen:
   Typ **CNAME**, Host **reise**, Ziel **<github-name>.github.io**.
5. Nach 10–60 Minuten ist die Seite unter https://reise.bigbanker.de erreichbar.

Die Seite hat kein Passwort, ist aber per `noindex` für Suchmaschinen gesperrt.
