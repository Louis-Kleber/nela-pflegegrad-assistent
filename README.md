# Nela – Digitaler Assistent für pflegende Angehörige


## Das Problem

In Deutschland gibt es ca. 6 Mio. Pflegebedürftige; ihre Pflegeangehörigen
haben Anspruch auf umfangreiche finanzielle Entlastungsleistungen. Ein Großteil
dieser Mittel verfällt für die Angehörigen. Die Gründe hierfür sind die
fehlende Transparenz über bestehende Ansprüche und komplizierte bürokratische
Prozesse.

Genau diese Lücke möchte unsere Plattform schließen. Das Ziel ist es, mit
unserer Plattform der erste Ansprechpartner für Pflegeangehörige zu sein, die
bürokratischen Hürden radikal zu vereinfachen und den Nutzer Schritt für
Schritt bei der Hand zu nehmen und ganz intuitiv durch den Prozess des
Pflegeanspruchs zu führen.

**➡️ Live-Demo:** https://nela-pflegegrad.streamlit.app/

## Funktionsumfang

- **Schneller Leistungscheck** – Ein kurzer Fragebogen aus sieben Fragen,
  ohne Anmeldung direkt auf der Startseite nutzbar. Die Antworten werden nach
  dem Punktesystem des NBA gewichtet (Neues Begutachtungsassessment – das
  offizielle Verfahren, mit dem der Medizinische Dienst seit 2017 den
  Pflegegrad feststellt) und ergeben eine erste Einschätzung, welcher
  Pflegegrad in Frage kommt. So sieht der Nutzer nach zwei Minuten, ob Nela
  für ihn überhaupt relevant ist – ohne vorher Daten preiszugeben.

- **Detaillierter Pflegegrad-Rechner** – Innerhalb 7 Seiten werden dem Nutzer Fragen zur aktuellen Pflegesituation gestellt,
- die der Nutzer intuitiv beantworten kann.
  Daraus wird der Pflegegrad nach § 15 SGB XI ermittelt: sechs gewichtete
  Module ergeben insgesamt 100 Punkte, feste Schwellenwerte bestimmen den Grad.
  Zwei gesetzliche Sonderfälle sind berücksichtigt – die Mindestdauer von sechs
  Monaten (§ 14 I) und die besondere Bedarfskonstellation, die direkt zu
  Pflegegrad 5 führt (§ 15 IV). Anschließend zeigt die App, welche Leistungen
  bei diesem Pflegegrad zustehen, und rechnet den monatlichen Gesamtbetrag aus.

- **KI-Ablaufplan** – formuliert aus den Top-3-Empfehlungen einen zeitlich
  gegliederten Plan (Woche 1 / Woche 2–3 / danach) über Google Gemini.
  In der öffentlichen Demo ist bewusst kein API-Key hinterlegt, daher greift
  dort der Fallback (siehe unten) – die Anbindung selbst ist vollständig
  implementiert.

- **Nutzerkonten** – Registrierung und Login mit gehashten Passwörtern,
  persönliches Dashboard und die Möglichkeit, das Pflegegrad-Ergebnis im
  Profil zu speichern, statt den Fragebogen jedes Mal neu auszufüllen.

- **Rechtliches** – Datenschutzerklärung, AGB und eine Einwilligungsverwaltung
  direkt in der App, inklusive der Möglichkeit, das eigene Konto zu löschen.
## Technische Umsetzung

| Bereich | Umsetzung |
|---|---|
| Sprache | Python |
| Frontend | Streamlit (Single-File-Architektur, ca. 5.600 Zeilen) |
| Styling | eigenes CSS-Design-System statt HTML-Wrapper um Widgets |
| Persistenz | JSON-Datei, Passwörter über `hashlib`/`hmac` gehasht |
| KI | Google Gemini 2.5 Flash über die OpenAI-kompatible Schnittstelle |

**Bewusste Architekturentscheidungen:**

- **Kein Absturz durch die KI:** Der Gemini-Aufruf liegt vollständig in einem
  `try`/`except`. Fehlt der Key oder greift ein Rate-Limit, erscheint ein
  vorformulierter Ersatzplan – der Nutzer sieht nie eine Fehlermeldung.
  Die App bleibt dadurch unabhängig von einem externen Dienst voll benutzbar,
  was sich in der öffentlichen Demo direkt nachvollziehen lässt.
- **Ehrliche Kennzeichnung:** Ein Badge zeigt an, ob der Text von der KI oder
  aus dem Fallback stammt, inklusive Modellname.
- **Lazy Import:** Die `openai`-Bibliothek wird erst beim Klick geladen, damit
  die App auch ohne sie startet.
- **Deterministischer Kern:** Pflegegrad und Empfehlungen werden ausschließlich
  regelbasiert berechnet. Die KI formuliert nur die Reihenfolge – sie
  entscheidet nichts.

## Lokal starten

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Die App läuft damit vollständig – **ein API-Key ist nicht erforderlich.**

Wer den KI-Ablaufplan live sehen will, legt zusätzlich eine Datei
`.streamlit/secrets.toml` mit einem Google-Gemini-Key an:

```toml
GEMINI_KEY = "dein-key"
```

Fehlt der Key, erscheint statt des generierten Texts der hinterlegte
Ersatzplan – ohne Fehlermeldung. Genau dieser Fall ist in der öffentlichen
Demo aktiv.

## Kontext

Entstanden im Modul **Digital Business** an der Hochschule München als MVP
eines Teamprojekts (Team 34).
 
### Mein Anteil

- **Pflegegrad-Rechner und Leistungscheck** – Aufbau des Fragebogens, die
  Berechnungslogik und die Darstellung der Ergebnisse
- **Fachliche Grundlagen** – Punktesystem des NBA und die Leistungsbeträge
  erarbeitet und anhand der Originalquellen gegengeprüft
- **Visuelles Konzept** – Farben, Seitenaufbau und Gestaltung von Landingpage
  und App-Bereich
- **KI-Ablaufplan** – gemeinsam mit Christian (Schwerpunkt lag bei ihm) umgesetzt

Von Christian stammen Anmeldung, Registrierung und die rechtlichen Seiten.

### Hinweis
Nela ist ein Uniprojekt und ersetzt keine Pflegeberatung. Die Ergebnisse
sind Orientierungswerte ohne Rechtsanspruch. In der Live-Demo werden angelegte
Konten bei einem Neustart der Anwendung zurückgesetzt.

## Lokal starten

Voraussetzung: **Python 3.9 oder neuer**.

**1. Repository herunterladen**

```bash
git clone https://github.com/Louis-Kleber/nela-pflegegrad-assistent.git
cd nela-pflegegrad-assistent
```

Ohne Git geht es auch über den grünen Button *Code* → *Download ZIP*.

**2. Virtuelle Umgebung anlegen und aktivieren**

```bash
python -m venv venv
```

```bash
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS / Linux
```

**3. Abhängigkeiten installieren und App starten**

```bash
pip install -r requirements.txt
streamlit run app.py
```

Die App öffnet sich automatisch im Browser unter `http://localhost:8501`.
