# Täglicher Preis-Agent – Arbeitsanweisung

Ziel: Einmal täglich die Preise der AIDA-Reise NO07270424 (24.04.–01.05.2027, AIDAnova ab Hamburg)
und die Bahnpreise Hanau Hbf ⇄ Hamburg Hbf erfassen, in `site/data/prices.json` übernehmen,
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

## 2. Bahnpreise (im eingebauten Browser)
1. `https://www.bahn.de/buchung/start` öffnen.
2. Im Seitenkontext ausführen. Zeitregeln der Gruppe (Check-in 15 Uhr): Hinfahrt mit **Ankunft Hamburg Hbf spätestens 12:30** (Suche nach Ankunftszeit), Rückfahrt **ab 11:00** (Schiff legt 08:00 an). Nur 2 Personengruppen (5, 6) × 2 Klassen, mit 2 s Pause zwischen den Abfragen – bei zu vielen Abfragen sperrt bahn.de mit `OPS_BLOCKED` (403). Dann abbrechen, Bahn-Teil weglassen, nicht wiederholen.
```js
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const g=async s=>(await (await fetch('/web/api/reiseloesung/orte?suchbegriff='+encodeURIComponent(s)+'&typ=ALL&limit=1')).json())[0].id;
const H=await g('Hanau Hbf'), HH=await g('Hamburg Hbf');
async function q(from,to,t,n,kl,mode){await sleep(2000);const body={abfahrtsHalt:from,anfrageZeitpunkt:t,ankunftsHalt:to,ankunftSuche:mode,klasse:kl,produktgattungen:['ICE','EC_IC','IR','REGIONAL','SBAHN','BUS','SCHIFF','UBAHN','TRAM','ANRUFPFLICHTIG'],reisende:[{typ:'ERWACHSENER',ermaessigungen:[{art:'KEINE_ERMAESSIGUNG',klasse:'KLASSENLOS'}],alter:[],anzahl:n}],schnelleVerbindungen:true,sitzplatzOnly:false,bikeCarriage:false,reservierungsKontingenteVorhanden:false,nurDeutschlandTicketVerbindungen:false,deutschlandTicketVorhanden:false};
 const r=await fetch('/web/api/angebote/fahrplan',{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify(body)});
 if(!r.ok) throw new Error('bahn.de '+r.status+' '+(await r.text()).slice(0,120));
 const j=await r.json();
 return (j.verbindungen||[]).map(v=>{const a=v.verbindungsAbschnitte;const z=a.filter(x=>x.verkehrsmittel&&x.verkehrsmittel.typ!=='WALK').map(x=>x.verkehrsmittel.name);return {ab:(a[0].abfahrt?.sollzeit||'').slice(11,16),an:(a[a.length-1].ankunft?.sollzeit||'').slice(11,16),dauer:Math.round(v.verbindungsDauerInSeconds/60),umst:v.umstiegsAnzahl,zug:z.join(' → '),p:v.angebotsPreis?.betrag};});}
async function dir(from,to,t,mode){const rows={};for(const [n,kl] of [[6,'KLASSE_2'],[5,'KLASSE_2'],[6,'KLASSE_1'],[5,'KLASSE_1']]){for(const v of await q(from,to,t,n,kl,mode)){const r=rows[v.ab]??={ab:v.ab,an:v.an,dauer:v.dauer,umst:v.umst,zug:v.zug,k2:{},k1:{}};r[kl==='KLASSE_2'?'k2':'k1'][n]=v.p;}}return Object.values(rows).sort((a,b)=>a.ab.localeCompare(b.ab));}
JSON.stringify({rail:{hin:await dir(H,HH,'2027-04-24T12:30:00','ANKUNFT'),rueck:await dir(HH,H,'2027-05-01T11:00:00','ABFAHRT')}})
```

## 3. Zusammenführen und veröffentlichen
1. Beide Ergebnisse zu einer Datei `snapshot.json` im Scratchpad zusammenfügen (`cabins`, `tariffs`, `rail`).
   Fehlt ein Teil (Seite nicht erreichbar), den Teil weglassen – alte Werte bleiben erhalten.
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
