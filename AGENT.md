# Täglicher Preis-Agent – Arbeitsanweisung

Ziel: Einmal täglich die Preise der AIDA-Reise NO07270424 (24.04.–01.05.2027, AIDAnova ab Hamburg)
erfassen (Bahnpreise nur von Hand, siehe Abschnitt 2), in `site/data/prices.json` übernehmen,
veröffentlichen und bei Preissenkungen Oliver benachrichtigen.

Wichtig: aida.de und bahn.de blockieren Abrufe ohne echten Browser (HTTP 403).
Daher läuft der Agent lokal in der Claude-Desktop-App mit dem eingebauten Browser.

## 1. AIDA-Preise (im eingebauten Browser)
1. `https://aida.de/finden/NO07270424/PREMIUM` öffnen (Cookie-Banner: nur notwendige).
2. Im Seitenkontext ausführen und Ergebnis merken:
```js
const out={cabins:[],tariffs:{}};
const base=a=>`/content/aida-search-and-booking/requests/detail.cruise.json/language=de/adults=${a}/juveniles=0/children=0/babies=0/JourneyIdentifier=NO07270424.json`;
const per={};
for (const a of [1,2,3,4]) {
  const j=await (await fetch(base(a))).json();
  for (const c of j.cabinItemsVariant) {
    per[c.cabinCode] ??= {code:c.cabinCode, prem:{}, ai:{}};
    const nf=t=>(c[t]?.prices||[]).find(x=>!x.flightIncluded)?.cabinAmount;
    if (nf('ind')!=null) per[c.cabinCode].prem[a]=nf('ind');
    if (nf('indAl')!=null) per[c.cabinCode].ai[a]=nf('indAl');
    out.tariffs.LIGHT ||= (c.lig?.prices||[]).length>0;
    out.tariffs.CLASSIC ||= (c.cla?.prices||[]).length>0 || (c.claAl?.prices||[]).length>0;
  }
}
out.tariffs.PREMIUM=true; out.tariffs.PREMIUM_AI=true;
out.cabins=Object.values(per);
JSON.stringify(out)
```

## 1b. Innenkabine zu dritt: Kategorie IA (ohne Pullman-Bett)
Die Gruppe will **keine Pullman-Betten**. Bei 3 Personen in der Innenkabine hat nur **IA (Bevorzugte Lage)** eine Bettcouch
statt Pullman (IB/IC: Pullman). Innen und Meerblick zu viert gehen gar nicht (4. Bett = Pullman) – dafür nichts abrufen.
Der IA-Preis steht nicht im JSON oben, sondern nur im Buchungsablauf (nichts buchen, keine Daten eingeben):
1. `https://aida.de/buchen/NO07270424/PREMIUM/meine-reise/reisende?adults=3&juveniles=0&children=0&babies=0&cabin=I` öffnen, ca. 5 s warten.
2. Element „PREMIUM auswählen“ anklicken (find), ca. 3 s warten.
3. Für PREMIUM: „Ich möchte ohne “PREMIUM ALL IN” fortfahren“ anklicken → Seitentext lesen: Zeile „Bevorzugte Lage (IA) … ab X €“ = `prem`.
4. Schritte 1–2 wiederholen, dann „“PREMIUM ALL IN” auswählen“ anklicken → „Bevorzugte Lage (IA) … ab Y €“ = `ai`.
5. Im Snapshot ergänzen: `"beds": {"I": {"3": {"sub": "IA", "prem": X, "ai": Y}}}`.
6. **Freie Kabinen zählen.** Auf der Kategorieliste (nach Schritt 3, PREMIUM ohne ALL IN) dieses Snippet per javascript_tool
   ausführen. Es wählt nacheinander die Kategorien, öffnet die Kabinenauswahl, zählt je Deck die angebotenen
   Kabinennummern und geht zurück. Es wird **nichts** ausgewählt oder gebucht. `CATS` je nach Durchgang setzen:
   - Durchgang **3 Personen** (Schritt 1 mit `adults=3`): `CATS=['IA']` → Snapshot `availability.IA3`
   - Durchgang **2 Personen** (Schritte 1–3 mit `adults=2` wiederholen): `CATS=['IC','IB','IA']` → Snapshot `availability.I2`
```js
const CATS=['IA'];   // bzw. ['IC','IB','IA'] im 2-Personen-Durchgang
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function back(){ const s=[...document.querySelectorAll('span')].find(e=>/^\s*Zurück zur Kabinenkategorie\s*$/.test(e.textContent)); if(s){ (s.closest('a,button')||s).click(); for(let i=0;i<20&&document.getElementById('cabin-picker-deck');i++) await sleep(500); await sleep(1200);} }
async function countCat(code){
  await back();
  const re=new RegExp('\\('+code+'\\)');
  const r=[...document.querySelectorAll('input[type=radio]')].find(x=>re.test(x.parentElement?.parentElement?.textContent||'')||re.test((x.closest('label')||x.parentElement).textContent));
  if(!r) return null; if(r.disabled) return 0;
  r.click(); await sleep(1200);
  const b=[...document.querySelectorAll('button')].find(b=>/Kabinenkategorie auswählen/.test(b.textContent)); if(!b) return null; b.click();
  let d=null; for(let i=0;i<30&&!(d=document.getElementById('cabin-picker-deck'));i++) await sleep(500);
  if(!d) return null;
  let n=0; for(const o of [...d.options].filter(o=>o.value!=='Deck')){ d.value=o.value; d.dispatchEvent(new Event('change',{bubbles:true})); await sleep(900); n+=[...document.getElementById('cabin-picker-cabin').options].filter(x=>x.value!=='Kabine').length; }
  return n;
}
const byCat={}; for(const c of CATS) byCat[c]=await countCat(c); await back();
JSON.stringify({byCat,total:Object.values(byCat).reduce((s,n)=>s+(n||0),0),failed:Object.keys(byCat).filter(k=>byCat[k]===null)})
```
   „Nicht verfügbar“ zählt als 0. Ist `failed` nicht leer, den betreffenden Durchgang im Snapshot weglassen (nicht raten).
   Hinweis: AIDA listet höchstens 100 Kabinen je Kategorie – 100 heißt „100 oder mehr“.
   Snapshot: `"availability": {"IA3": {"total": N, "byCat": {...}}, "I2": {"total": M, "byCat": {...}}}`.

## 2. Bahnpreise – NICHT automatisch
bahn.de erkennt automatisierte Abfragen als Bot (Fehler 751 / `OPS_BLOCKED`) und sperrt dann auch die normale Seite.
Bot-Erkennung wird nicht umgangen. Der Agent ruft bahn.de daher **nicht** auf.
Bahnpreise prüft Oliver bei Bedarf von Hand (oder bittet Claude in einer Sitzung um eine einzelne Prüfung);
dann `rail.hin`/`rail.rueck` und `rail.checked` in `site/data/prices.json` anpassen.
Zeitregeln der Gruppe: Ankunft Hamburg Hbf bis 12:30, Rückfahrt ab 11:00, max. 4:45 h, max. 1 Umstieg.

## 3. Zusammenführen und veröffentlichen
1. Das AIDA-Ergebnis als `snapshot.json` im Scratchpad speichern (`cabins`, `tariffs`, `beds`, `availability`).
   Schlägt der Abruf fehl, nichts speichern und Oliver informieren – nie Werte erfinden.
2. `python scripts/merge_prices.py <pfad>/snapshot.json`
3. `git add site/data/prices.json && git commit -m "Preise <Datum>" && git push`
   → GitHub Pages veröffentlicht die Seite automatisch neu.

## 4. Benachrichtigen
- Gibt das Skript `ALERT:`-Zeilen aus: Oliver per Push-Benachrichtigung informieren
  (Text: die ALERT-Zeilen + Link https://reise.bigbanker.de). Die Hinweise erscheinen
  automatisch oben auf der Webseite; Oliver teilt sie per WhatsApp-Button mit der Gruppe.
- Keine ALERT-Zeilen: keine Benachrichtigung.
- Schlägt ein Abruf fehl (403, Captcha, geänderte Seite): nichts erraten, Oliver kurz informieren.
  Niemals ein Captcha lösen.
