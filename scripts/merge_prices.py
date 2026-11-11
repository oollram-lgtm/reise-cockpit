"""Merge a fresh price snapshot into site/data/prices.json.

Usage:  python scripts/merge_prices.py snapshot.json

snapshot.json (written by the daily agent from the browser) looks like:
{
  "cabins":  [{"code":"I","prem":{"1":..,"2":..},"ai":{...}}, ...],
  "tariffs": {"LIGHT":false,"CLASSIC":false,"PREMIUM":true,"PREMIUM_AI":true},
  "beds":    {"I": {"3": {"sub":"IA","prem":2050,"ai":2740}}},   # Pflicht-Unterkategorie ohne Pullman-Bett
  "rail":    {"hin":[{"ab":"06:15","an":"10:29","zug":"...","k2":{"1":..,"5":..,"6":..},"k1":{...}}], "rueck":[...]}
}
Any part may be missing (e.g. if bahn.de failed); missing parts keep the old values.
Prints a short summary; lines starting with "ALERT:" mean prices dropped or a tariff appeared.
"""
import json, sys, datetime, pathlib
sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "site" / "data" / "prices.json"
DROP_EUR = 20  # report drops of at least this many euros per cabin


def main(snapshot_path):
    data = json.loads(DATA.read_text(encoding="utf-8"))
    snap = json.loads(pathlib.Path(snapshot_path).read_text(encoding="utf-8"))
    now = datetime.datetime.now().astimezone()
    today = now.date().isoformat()
    alerts = []

    old = {c["code"]: c for c in data["cabins"]}
    if snap.get("cabins"):
        for c in snap["cabins"]:
            o = old.get(c["code"])
            if not o:
                continue
            for tarif, label in (("prem", "PREMIUM"), ("ai", "All Inclusive")):
                for occ, price in (c.get(tarif) or {}).items():
                    prev = (o.get(tarif) or {}).get(occ)
                    if price is not None and prev is not None and prev - price >= DROP_EUR:
                        alerts.append({"date": today, "type": "down",
                                       "text": f"{o['name']} {label} für {occ} Pers.: {prev:.0f} € → {price:.0f} € (−{prev - price:.0f} €)"})
            o["prem"] = c.get("prem") or o["prem"]
            o["ai"] = c.get("ai") or o["ai"]

    # Pflicht-Unterkategorien (ohne Pullman-Bett), z. B. Innen zu dritt nur IA
    for code, occs in (snap.get("beds") or {}).items():
        for occ, new in occs.items():
            cur = ((data.get("beds") or {}).get(code) or {}).get(occ)
            if not new or not cur:
                continue
            name = next((c["name"] for c in data["cabins"] if c["code"] == code), code)
            for tarif, label in (("prem", "PREMIUM"), ("ai", "All Inclusive")):
                prev, price = cur.get(tarif), new.get(tarif)
                if price is not None and prev is not None and prev - price >= DROP_EUR:
                    alerts.append({"date": today, "type": "down",
                                   "text": f"{name} {cur['sub']} {label} für {occ} Pers.: {prev:.0f} € → {price:.0f} € (−{prev - price:.0f} €)"})
                if price is not None:
                    cur[tarif] = price
            data["beds"]["checked"] = today

    if snap.get("tariffs"):
        for k, v in snap["tariffs"].items():
            if v and not data["tariffs"].get(k):
                alerts.append({"date": today, "type": "down", "text": f"Neuer Tarif buchbar: {k} – meist günstiger als PREMIUM!"})
        data["tariffs"] = snap["tariffs"]

    def cheapest(lst, key, n):
        vals = [t.get(key, {}).get(n) for t in lst]
        vals = [v for v in vals if v is not None]
        return min(vals) if vals else None

    if snap.get("rail"):
        for direction in ("hin", "rueck"):
            new = snap["rail"].get(direction)
            # nur vollständige Daten übernehmen (Gruppenpreise 5 und 6 Pers., 2. Klasse)
            if not new or not all(t.get("k2", {}).get("6") is not None and t.get("k2", {}).get("5") is not None for t in new):
                if new:
                    print(f"WARN: Bahn {direction} unvollständig – alte Werte bleiben")
                continue
            prev6 = cheapest(data["rail"][direction], "k2", "6")
            now6 = cheapest(new, "k2", "6")
            if prev6 and now6 and prev6 - now6 >= 10:
                alerts.append({"date": today, "type": "down",
                               "text": f"Bahn {'Hinfahrt' if direction == 'hin' else 'Rückfahrt'} (6er-Gruppe): {prev6:.2f} € → {now6:.2f} €"})
            data["rail"][direction] = new

    cab = {c["code"]: c for c in data["cabins"]}
    point = {"date": today}
    beds = data.get("beds") or {}
    for code in ("I", "B"):
        for occ in ("2", "3"):
            rule = (beds.get(code) or {}).get(occ)
            point[f"{code}{occ}"] = rule["prem"] if rule else cab[code]["prem"].get(occ)
            point[f"{code}{occ}AI"] = rule["ai"] if rule else cab[code]["ai"].get(occ)
    point["railHin6"] = cheapest(data["rail"]["hin"], "k2", "6")
    point["railRueck6"] = cheapest(data["rail"]["rueck"], "k2", "6")
    point["railHin5"] = cheapest(data["rail"]["hin"], "k2", "5")
    point["railRueck5"] = cheapest(data["rail"]["rueck"], "k2", "5")
    data["history"] = [h for h in data["history"] if h["date"] != today] + [point]

    data["alerts"] = (data.get("alerts") or []) + alerts
    data["alerts"] = data["alerts"][-30:]
    data["updated"] = now.isoformat(timespec="seconds")

    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK {today}: {len(data['history'])} Messpunkte")
    for a in alerts:
        print("ALERT:", a["text"])


if __name__ == "__main__":
    main(sys.argv[1])
