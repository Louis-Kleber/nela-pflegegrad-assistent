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

## Funktionsumfang

- **Pflegegrad-Rechner** – Fragebogen nach dem Punktesystem des NBA
  (Neues Begutachtungsassessment), ohne Anmeldung nutzbar
- **Leistungscheck** – zeigt auf Basis des ermittelten Pflegegrads die
  zustehenden Leistungen und rechnet den monatlichen Gesamtbetrag aus
- **KI-Ablaufplan** – formuliert aus den Top-3-Empfehlungen einen zeitlich
  gegliederten Plan (Woche 1 / Woche 2–3 / danach) über Google Gemini.
  In der öffentlichen Demo ist bewusst kein API-Key hinterlegt, daher greift
  dort der Fallback (siehe unten) – die Anbindung selbst ist vollständig
  implementiert
- **Nutzerkonten** – Registrierung und Login mit gehashten Passwörtern,
  persönliches Dashboard, Speichern des Pflegegrad-Ergebnisses im Profil
- **Rechtliches** – Datenschutzerklärung, AGB und Einwilligungsverwaltung
  direkt in der App

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
