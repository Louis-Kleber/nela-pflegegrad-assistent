"""
Single-File-Streamlit-App. Start über:  streamlit run app.py
================================================================

Architektur (klare Schichten, keine HTML-Wrapper um Streamlit-Widgets):
  1. Imports & Konstanten
  2. Design-System (CSS) - alle Styles über CSS-Klassen + Streamlit-Keys
  3. Persistenz (JSON-Nutzer-DB)
  4. Hilfsfunktionen (Session, Pflegegrad-Berechnung)
  5. Pflegegrad-Rechner (wiederverwendbar, anonym + eingeloggt)
  6. Authentifizierung (Login + Registrierung)
  7. Landingpage (Hero, Stats, Module, Vergleich, Rechner, CTA, Footer)
  8. App-Bereich (Sidebar, Dashboard, Profil, Leistung)
  9. Hauptprogramm
"""

# ============================================================
# 1) IMPORTS & KONSTANTEN
# ============================================================

import base64
import hashlib
import hmac
import html
import json
import os
import re
from datetime import datetime

import streamlit as st

# Dateipfade relativ zur App-Datei
APP_VERZEICHNIS = os.path.dirname(os.path.abspath(__file__))
NUTZER_DB_PFAD  = os.path.join(APP_VERZEICHNIS, "users_db.json")
LOGO_PFAD       = os.path.join(APP_VERZEICHNIS, "Nela-logo.jpeg")

# --- Markenfarben ---
PRIMAER        = "#2E7D32"   # Forestgrün
HG_HELLGRUEN   = "#E8F5E9"
HG_WARMWEISS   = "#FAFAF8"
HEADLINE_FARBE = "#1A2E0D"   # Tiefgrün
CTA_FARBE      = "#FFE5B4"   # CTA-Peach (Brand-Akzent)
PRIMAER_HELL   = "#43A047"
PRIMAER_DUNKEL = "#1B5E20"
TEXT_GRAU      = "#555555"
RAHMEN_GRAU    = "#E0E0E0"
AKZENT_HELL    = "#C8E6C9"

# --- Pflegegrad-Rechner: 7 Seiten, 16 Fragen (Etappe 1: nur Skelett) ---
#
# Antworten landen als String unter der Frage-ID in st.session_state["pg_answers"].
# Standardskala: "voll" / "meist" / "hilfe" / "nein".
# Sonderskalen für F4, F10, F11, F12 (gleiche Wert-Keys, andere Labels) und
# Ja/Nein für F15, F16. Es wird in Etappe 1 nichts berechnet — die Werte sind
# nur ordinale Antwort-Tokens.

PG_OPTIONEN_STANDARD = [  # Louis: Standard-Antwortmöglichkeiten. "label" = was auf dem Knopf steht, "wert" = interner Code zum Speichern/Rechnen
    {"wert": "voll",  "label": "Ja, vollständig"},
    {"wert": "meist", "label": "Meistens"},
    {"wert": "hilfe", "label": "Nur mit Hilfe"},
    {"wert": "nein",  "label": "Nein, gar nicht"},
]

PG_OPTIONEN_F4 = [
    {"wert": "voll",  "label": "Nie"},
    {"wert": "meist", "label": "Selten\n(1–3×/Monat)"},
    {"wert": "hilfe", "label": "Häufig\n(mehrmals/Woche)"},
    {"wert": "nein",  "label": "Täglich"},
]

PG_OPTIONEN_F10 = [
    {"wert": "voll",  "label": "Keine Probleme"},
    {"wert": "meist", "label": "Selten"},
    {"wert": "hilfe", "label": "Häufig\n(Blase ODER Stuhl)"},
    {"wert": "nein",  "label": "Ständig (beides)"},
]

PG_OPTIONEN_F11 = [
    {"wert": "voll",  "label": "Keine"},
    {"wert": "meist", "label": "1–3×"},
    {"wert": "hilfe", "label": "4–8×"},
    {"wert": "nein",  "label": "Mehr als 8×"},
]

PG_OPTIONEN_F12 = [
    {"wert": "voll",  "label": "Keine / selten"},
    {"wert": "meist", "label": "1×"},
    {"wert": "hilfe", "label": "2–3×"},
    {"wert": "nein",  "label": "Fast täglich"},
]

PG_OPTIONEN_JANEIN = [
    {"wert": "ja",   "label": "Ja"},
    {"wert": "nein", "label": "Nein"},
]

PG_SEITEN = [  # Louis: HIER stehen ALLE Fragen des Rechners (die "Daten"). Die Anzeige-Funktion sucht sie nicht selbst - sie bekommt sie von hier übergeben
    {                              # Louis: jede Seite = ein dict mit Nummer, Kategorie und einer Liste von Fragen
        "nummer":    1,
        "kategorie": "Mobilität",
        "fragen": [
            {"id": "F1",           # Louis: id = interner Name der Frage (wird zum Speichern der Antwort genutzt)
             "text": "Kann Ihre Mutter sich noch selbstständig im Wohnbereich "  # Louis: text = was als Frage angezeigt wird
                     "bewegen (auch mit Rollator)?",
             "optionen": PG_OPTIONEN_STANDARD},  # Louis: welche Antwortknöpfe -> verweist auf die Liste von oben
        ],
    },
    {
        "nummer":    2,
        "kategorie": "Kognition",
        "fragen": [
            {"id": "F2",
             "text": "Erkennt sie nahestehende Personen (Kinder, Enkel) "
                     "noch zuverlässig?",
             "optionen": PG_OPTIONEN_STANDARD},
            {"id": "F3",
             "text": "Versteht sie alltägliche Risiken (heiße Herdplatte, "
                     "offene Haustür, Medikamente)?",
             "optionen": PG_OPTIONEN_STANDARD},
        ],
    },
    {
        "nummer":    3,
        "kategorie": "Verhalten",
        "fragen": [
            {"id": "F4",
             "text": "Wie oft kommt es zu auffälligem Verhalten (nächtliche "
                     "Unruhe, Aggression, Abwehr bei Pflege, Ängste, "
                     "Antriebslosigkeit)?",
             "optionen": PG_OPTIONEN_F4},
        ],
    },
    {
        "nummer":    4,
        "kategorie": "Selbstversorgung",
        "fragen": [
            {"id": "F5",  "subheader": "Waschen & Duschen",
             "text": "Kann sie sich selbstständig waschen und duschen?",
             "optionen": PG_OPTIONEN_STANDARD},
            {"id": "F6",  "subheader": "An- und Auskleiden",
             "text": "Kann sie sich selbstständig an- und auskleiden?",
             "optionen": PG_OPTIONEN_STANDARD},
            {"id": "F7",  "subheader": "Essen",
             "text": "Kann sie selbstständig essen (Nahrung zerkleinern, "
                     "zum Mund führen)?",
             "optionen": PG_OPTIONEN_STANDARD},
            {"id": "F8",  "subheader": "Trinken",
             "text": "Kann sie selbstständig trinken?",
             "optionen": PG_OPTIONEN_STANDARD},
            {"id": "F9",  "subheader": "Toilettengang",
             "text": "Kann sie selbstständig zur Toilette gehen "
                     "(inkl. Hygiene)?",
             "optionen": PG_OPTIONEN_STANDARD},
            {"id": "F10", "subheader": "Kontinenz",
             "text": "Hat sie Probleme mit Blasen- oder Stuhlkontinenz?",
             "optionen": PG_OPTIONEN_F10},
        ],
    },
    {
        "nummer":    5,
        "kategorie": "Krankheit & Therapie",
        "fragen": [
            {"id": "F11",
             "text": "Wie viele Medikamente oder medizinische Hilfen täglich "
                     "(Tabletten, Spritzen, Inhalation, Verbände)?",
             "optionen": PG_OPTIONEN_F11},
            {"id": "F12",
             "text": "Wie viele Arztbesuche oder Therapien pro Woche?",
             "optionen": PG_OPTIONEN_F12},
        ],
    },
    {
        "nummer":    6,
        "kategorie": "Alltag & Soziales",
        "fragen": [
            {"id": "F13",
             "text": "Kann sie ihren Tagesablauf noch selbst gestalten "
                     "(aufstehen, Mahlzeiten planen, sich beschäftigen)?",
             "optionen": PG_OPTIONEN_STANDARD},
            {"id": "F14",
             "text": "Pflegt sie noch soziale Kontakte (Telefon, Besuche, "
                     "Spaziergänge)?",
             "optionen": PG_OPTIONEN_STANDARD},
        ],
    },
    {
        "nummer":    7,
        "kategorie": "Sonderfälle",
        "fragen": [
            {"id": "F15",
             "text": "Hat sie die Gebrauchsfähigkeit von beiden Armen UND "
                     "beiden Beinen vollständig verloren?",
             "optionen": PG_OPTIONEN_JANEIN},
            {"id": "F16",
             "text": "Besteht diese Pflegesituation seit mindestens 6 Monaten "
                     "oder wird sie voraussichtlich so lange bestehen?",
             "optionen": PG_OPTIONEN_JANEIN},
        ],
    },
]

PG_ANZAHL_SEITEN = len(PG_SEITEN)  # Louis: len() zählt die Seiten automatisch. So muss man die Gesamtzahl nicht von Hand pflegen



# ============================================================
# 1b) LEISTUNGSCHECK-KONSTANTEN (7 Fragen, NBA-Berechnung)
# ============================================================

# --- LEISTUNGSCHECK (Landing): 6 Lebensbereiche, 7 Fragen, echte NBA-Berechnung ---
LC_SEITEN = [
    {
        "lebensbereich": "Selbstversorgung",
        "fragen": [
            {
                "titel":        "Kann die pflegebedürftige Person sich selbständig waschen und duschen?",
                "beschreibung": "Körperpflege / Selbstversorgung",
                "schlüssel":   "sv_waschen",
            },
            {
                "titel":        "Kann die pflegebedürftige Person Mahlzeiten noch selbst zubereiten?",
                "beschreibung": "Selbstversorgung / Ernährung",
                "schlüssel":   "sv_mahlzeiten",
            },
        ],
    },
    {
        "lebensbereich": "Mobilität",
        "fragen": [
            {
                "titel":        "Kann die Person Treppen steigen und sich allein fortbewegen?",
                "beschreibung": "Mobilität / Fortbewegung",
                "schlüssel":   "mob_treppen",
            },
        ],
    },
    {
        "lebensbereich": "Kognitive Fähigkeiten",
        "fragen": [
            {
                "titel":        "Kann die Person Termine und den Alltag selbst organisieren?",
                "beschreibung": "Kognition / Alltag planen",
                "schlüssel":   "kog_termine",
            },
        ],
    },
    {
        "lebensbereich": "Verhalten & Psyche",
        "fragen": [
            {
                "titel":        "Zeigt die Person Verhaltensweisen wie Unruhe, Aggressionen oder Stimmungsschwankungen?",
                "beschreibung": "Verhaltensweisen / Psychische Stabilität",
                "schlüssel":   "verhalten_unruhe",
            },
        ],
    },
    {
        "lebensbereich": "Krankheitsbedingte Anforderungen",
        "fragen": [
            {
                "titel":        "Nimmt die Person Medikamente eigenständig zur richtigen Zeit?",
                "beschreibung": "Krankheitsbewältigung / Medikamente",
                "schlüssel":   "krank_medikamente",
            },
        ],
    },
    {
        "lebensbereich": "Soziale Bereiche",
        "fragen": [
            {
                "titel":        "Kann die Person selbständig Kontakte zu anderen Menschen pflegen?",
                "beschreibung": "Soziale Bereiche / Kontakte",
                "schlüssel":   "soz_kontakte",
            },
        ],
    },
]

# Antwortoptionen, Rohwerte 0..3 (max. 100 nach NBA-Gewichtung)
LC_ANTWORTOPTIONEN = [
    {"label": "Ja, vollständig", "untertitel": "Kein Hilfsbedarf",      "punkte": 0},
    {"label": "Meistens ja",      "untertitel": "Geringer Bedarf",       "punkte": 1},
    {"label": "Nur mit Hilfe",    "untertitel": "Regelmäßige Hilfe",   "punkte": 2},
    {"label": "Nein, gar nicht",  "untertitel": "Vollständiger Bedarf", "punkte": 3},
]

# NBA-konforme Modul-Gewichte pro Frage (Spec-IDs als Kommentar)
LC_GEWICHTE = {
    "sv_waschen":        20,  # q1_waschen      (Modul M4, Teil 1)
    "sv_mahlzeiten":     20,  # q2_essen        (Modul M4, Teil 2)
    "mob_treppen":       10,  # q3_mobilitaet   (Modul M1)
    "kog_termine":       15,  # q4_kognition    (Modul M2)
    "verhalten_unruhe":  15,  # q5_verhalten    (Modul M3, invertierte Skala)
    "krank_medikamente": 20,  # q6_medikamente  (Modul M5)
    "soz_kontakte":      15,  # q7_alltag       (Modul M6)
}
LC_INVERTIERT = {"verhalten_unruhe"}
LC_M23 = ("kog_termine", "verhalten_unruhe")
# ============================================================
# 2) DESIGN-SYSTEM (CSS)
# ============================================================
#
# WICHTIG zur Streamlit-DOM-Struktur:
#  Streamlit rendert jedes st.markdown() in einen eigenen Container.
#  Ein offener <div>-Tag in einem markdown() wird mit einem Auto-Close
#  vom Markdown-Parser versehen - das bricht jedes Wrapping über mehrere
#  Aufrufe hinweg. Konsequenz: Wir umschliessen niemals Streamlit-Widgets
#  mit HTML aus st.markdown(). Stattdessen styled CSS Buttons gezielt
#  per Selektor und der Hauptbereich wird über CSS auf Website-Breite
#  begrenzt.
#
# Architektur des Layouts:
#  - [data-testid="stMain"] .block-container ist auf max-width:1200px
#    begrenzt (typische Website-Breite). Auch im eingeloggten Bereich.
#  - "Full-bleed" Sections (Hero, Stats, CTA) brechen mit
#      margin-left: calc(-50vw + 50%); width: 100vw
#    aus diesem Container aus und nehmen die ganze Browser-Breite.
#  - Innerhalb der Sections kommt eine .nela-section-inner mit
#    max-width 1200px, die den Inhalt wieder zentriert.


def globales_css_injizieren(sidebar_anzeigen: bool) -> None:
    """Injiziert das gesamte Design-System.

    sidebar_anzeigen=False -> Landingpage: Sidebar komplett versteckt.
    sidebar_anzeigen=True  -> App-Bereich: Sidebar sichtbar.
    """

    # Sidebar-spezifisches CSS
    if sidebar_anzeigen:
        sidebar_block = """
        section[data-testid="stSidebar"] {
            display: block !important;
            background: #FAFAF8 !important;
            border-right: 1px solid #EDF2EE !important;
        }
        """
    else:
        sidebar_block = """
        section[data-testid="stSidebar"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        [data-testid="stSidebarNav"] { display: none !important; }
        [data-testid="stSidebarCollapsedControl"] { display: none !important; }
        """

    css = """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700;800&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">

    <style>
    /* ============ 1. SIDEBAR-MODUS ============ */
    """ + sidebar_block + """

    /* ============ 2. GLOBALE TYPOGRAFIE ============
     * UX: Montserrat (Display) + DM Sans (Body) – kontrastreiche, moderne
     *     Sans-Pairing für professionellen Pflege-Kontext.
     *     -webkit-font-smoothing für schärfere Darstellung.
     */
    html, body, [class*="css"] {
        font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: __HEADLINE__;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }
    /* Body bekommt explizit weißen Hintergrund, damit nach Transparenz
     * von stMain (siehe unten) keine ungewollten Farben durchscheinen. */
    body { background: #FFFFFF !important; }

    h1, h2, h3, h4, h5, h6 {  /* Louis: h1-h6 = die 6 HTML-Überschriften-Ebenen (wie Word Überschrift 1-6). Komma = eine Regel für ALLE auf einmal */
        font-family: 'Montserrat', 'DM Sans', sans-serif !important;  /* Louis: Schrift-Kette: erst Montserrat, falls nicht da DM Sans, sonst irgendeine sans-serif */
        color: __HEADLINE__ !important;  /* Louis: __HEADLINE__ = Platzhalter, wird unten per .replace() durch echte Farbe ersetzt */
        font-weight: 700 !important;
        letter-spacing: -0.02em;
        line-height: 1.18;
    }
    p {  /* Louis: p = Textabsatz (Fließtext), bekommt andere Schrift/Abstände als die Überschriften */
        color: __HEADLINE__;
        line-height: 1.65;
    }

    /* Streamlit-Chrome ausblenden */
    [data-testid="stHeader"] {
        background: transparent !important;
        height: 0 !important;
    }
    #MainMenu, footer, [data-testid="stToolbar"] {
        visibility: hidden !important;
        height: 0 !important;
    }

    /* ============ 3. HAUPT-CONTAINER ============
     * UX/Technik: stMain wird TRANSPARENT – damit injizierte Full-Bleed-
     * Hintergrund-Bänder (s. Abschnitt 20) hinter losen Button-Reihen
     * sichtbar werden können. body liefert Standardweiß.
     */
    [data-testid="stMain"] {
        background: transparent !important;
    }
    [data-testid="stMain"] .block-container {  /* Louis: spricht Streamlits Haupt-Inhaltsbereich an (data-testid = das "Namensschild", das Streamlit selbst vergibt) */
        max-width: 1200px !important;  /* Louis: HIER setzen WIR die Breite auf max. 1200px (unsere Wahl, nicht Streamlit-Standard). max-width = Obergrenze, schrumpft auf Handy mit */
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        padding-left: 32px !important;
        padding-right: 32px !important;
        background: transparent !important;
    }

    /* ============ 4. FULL-BLEED HELPER ============ */
    /*
     * .nela-fullbleed bricht aus dem 1200px-Container aus und nimmt die
     * volle Browser-Breite ein. Wird für Hero, Stats-Streifen, CTA und
     * Footer genutzt - klassisches Website-Pattern.
     */
    .nela-fullbleed {  /* Louis: "Full-Bleed" = bricht aus dem 1200px-Container aus und nimmt die VOLLE Browserbreite (für farbige Bänder: Hero, Stats, Footer) */
        position: relative;
        margin-left: calc(-50vw + 50%);   /* Louis: DER Trick. vw = Fensterbreite, % = Container-Breite. Die Differenz schiebt das Element bis zum echten Fensterrand */
        margin-right: calc(-50vw + 50%);
        width: 100vw;                      /* Louis: 100vw = volle Fensterbreite */
    }
    .nela-section-inner {  /* Louis: Gegenstück: holt den INHALT im Full-Bleed-Band wieder auf 1200px zurück und zentriert ihn (sonst klebt Text am Rand) */
        max-width: 1200px;
        margin: 0 auto;    /* Louis: margin: 0 auto = horizontal zentrieren */
        padding: 0 32px;
    }

    /* ============ 5. TOP-NAV ============ */
    .nela-brand {
        display: flex;
        align-items: center;
        gap: 12px;
        text-decoration: none;
        cursor: pointer;
    }
    .nela-brand-text { display: flex; flex-direction: column; line-height: 1; }
    .nela-brand-name {
        font-family: 'Montserrat', sans-serif;
        font-size: 22px;
        font-weight: 800;
        color: __PRIMAER__;
        letter-spacing: -0.01em;
    }
    .nela-brand-tagline {
        font-size: 11px;
        color: __TEXTGRAU__;
        margin-top: 2px;
    }
    /* Härtung: Streamlit-Auto-Anchors auf Überschriften ausblenden, damit kein
     * blaues Phantom-Link-Symbol neben Headlines/Brand auftaucht. */
    .stMarkdown a.anchor-link { display: none !important; }
    [data-testid="stHeaderActionElements"] { display: none !important; }
    /* Header-Zeile: Streamlit setzt um stMarkdown-Container und um <p>-Tags
     * Default-Margins. In Verbindung mit st.columns(vertical_alignment="center")
     * verschiebt das die optische Mitte von Logo und Nav-Links nach oben, sodass
     * die Auth-Buttons rechts tiefer wirken. Hier nivellieren — nur in den
     * Brand-/Nav-Spalten, ohne andere Markdown-Abstände anzufassen. */
    [data-testid="stMarkdownContainer"]:has(.nela-brand) p,
    [data-testid="stMarkdownContainer"]:has(.nela-topnav-links) p,
    [data-testid="stMarkdownContainer"]:has(.nela-brand),
    [data-testid="stMarkdownContainer"]:has(.nela-topnav-links) {
        margin: 0 !important;
        padding: 0 !important;
    }
    .nela-topnav-links {
        display: flex;
        gap: 28px;
        align-items: center;
    }
    /* UX: cursor:pointer + animierter Unterstrich-Hover statt nur Farbwechsel
     *     → klare Interaktivitäts-Signale, professioneller Eindruck. */
    .nela-topnav-links a {
        color: __HEADLINE__;
        font-size: 14px;
        font-weight: 600;
        text-decoration: none;
        transition: color 0.18s ease;
        cursor: pointer;
        position: relative;
        padding-bottom: 3px;
    }
    .nela-topnav-links a::after {
        content: "";
        position: absolute;
        bottom: -1px;
        left: 0;
        right: 0;
        height: 2px;
        background: __PRIMAER__;
        border-radius: 2px;
        transform: scaleX(0);
        transform-origin: left center;
        transition: transform 0.2s cubic-bezier(.4, 0, .2, 1);
    }
    .nela-topnav-links a:hover { color: __PRIMAER__; }
    .nela-topnav-links a:hover::after { transform: scaleX(1); }

    /* ============ 6. HERO ============ */
    .nela-hero {
        background:
            radial-gradient(ellipse 80% 60% at 80% 20%, rgba(46,125,50,0.10) 0%, transparent 60%),
            radial-gradient(ellipse 60% 50% at 10% 80%, rgba(200,230,201,0.40) 0%, transparent 60%),
            linear-gradient(180deg, __HG_WARM__ 0%, __HG_HELL__ 100%);
        padding: 88px 0 96px 0;
    }
    .nela-hero-grid {  /* Louis: teilt den Hero in 2 Spalten (links Text, rechts Bild/Karte) */
        display: grid;
        grid-template-columns: 1.15fr 1fr;  /* Louis: fr = Anteil. 1.15:1 -> linke Spalte etwas breiter */
        gap: 64px;
        align-items: center;
    }
    .nela-eyebrow {  /* Louis: "Eyebrow" = kleines Label ÜBER der Hauptüberschrift (die grüne Pille, z.B. "PFLEGE NEU GEDACHT") */
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(46, 125, 50, 0.10);
        color: __PRIMAER__;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        padding: 7px 14px;
        border-radius: 999px;
        margin-bottom: 22px;
    }
    .nela-eyebrow::before {  /* Louis: ::before = Pseudo-Element, fügt per CSS Inhalt EIN (hier der kleine grüne Punkt vor dem Text), steht NICHT im HTML */
        content: "";
        width: 6px; height: 6px;
        background: __PRIMAER__;
        border-radius: 50%;  /* Louis: 50% = perfekter Kreis */
    }
    .nela-hero-headline {
        font-family: 'Montserrat', sans-serif !important;
        font-size: clamp(34px, 4.6vw, 56px);
        font-weight: 800;
        line-height: 1.04;
        color: __HEADLINE__;
        margin: 0 0 20px 0;
        letter-spacing: -0.025em;
    }
    .nela-hero-headline .akzent {
        color: __PRIMAER__;
        position: relative;
        display: inline-block;
    }
    .nela-hero-headline .akzent::after {
        content: "";
        position: absolute;
        left: 0; right: 0;
        bottom: 0.06em;
        height: 0.16em;
        background: rgba(255, 229, 180, 0.55);
        z-index: -1;
        border-radius: 4px;
    }
    .nela-hero-sub {
        font-size: 18px;
        line-height: 1.6;
        color: #3a4a2e;
        margin: 0 0 12px 0;
        max-width: 560px;
    }
    .nela-hero-trust {
        display: flex; gap: 22px;
        margin-top: 28px;
        font-size: 13px;
        color: __TEXTGRAU__;
        flex-wrap: wrap;
    }
    .nela-hero-trust span {
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }
    .nela-hero-check {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 16px; height: 16px;
        background: __PRIMAER__;
        color: #FFFFFF;
        border-radius: 50%;
        font-size: 10px;
        font-weight: 800;
    }

    /* Hero-Card (rechte Spalte) */
    .nela-hero-visual { position: relative; display: flex; justify-content: center; }
    .nela-hero-card {
        background: #FFFFFF;
        border-radius: 24px;
        padding: 32px;
        box-shadow:
            0 25px 50px -12px rgba(46, 125, 50, 0.18),
            0 0 0 1px rgba(46, 125, 50, 0.05);
        max-width: 420px;
        width: 100%;
        position: relative;
        z-index: 2;
    }
    .nela-hero-card-label {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: __PRIMAER__;
        margin-bottom: 8px;
    }
    .nela-hero-card-headline {
        font-family: 'Montserrat', sans-serif;
        font-size: 19px;
        font-weight: 700;
        color: __HEADLINE__;
        margin: 0 0 18px 0;
        line-height: 1.3;
    }
    .nela-hero-amount {
        font-family: 'Montserrat', sans-serif;
        font-size: 56px;
        font-weight: 800;
        color: __PRIMAER__;
        line-height: 1;
        margin: 12px 0 6px 0;
        letter-spacing: -0.03em;
    }
    .nela-hero-amount-sub {
        font-size: 14px;
        color: __TEXTGRAU__;
        margin-bottom: 22px;
    }
    .nela-hero-step {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 0;
        border-top: 1px solid #F1F3F0;
        font-size: 13px;
        color: __HEADLINE__;
    }

    /* ============ 7. STATS-STREIFEN ============ */
    .nela-stats {
        background: __HEADLINE__;
        padding: 56px 0;
    }
    .nela-stats-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 32px;
    }
    .nela-stat {
        color: #FFFFFF;
        border-left: 3px solid __PRIMAER_HELL__;
        padding-left: 18px;
    }
    .nela-stat-zahl {
        font-family: 'Montserrat', sans-serif;
        font-size: 36px;
        font-weight: 800;
        color: #FFFFFF;
        line-height: 1;
        margin-bottom: 8px;
        letter-spacing: -0.02em;
    }
    .nela-stat-label {
        font-size: 13px;
        color: __AKZENT_HELL__;
        line-height: 1.45;
    }

    /* ============ 8. SECTIONS allgemein ============ */
    .nela-section {
        padding: 88px 0;
    }
    .nela-section-warm { background: __HG_WARM__; }
    .nela-section-soft { background: __HG_HELL__; }

    .nela-section-head {
        text-align: center;
        max-width: 720px;
        margin: 0 auto 56px auto;
    }
    .nela-section-eyebrow {
        display: inline-block;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: __PRIMAER__;
        margin-bottom: 12px;
    }
    .nela-section-title {
        font-family: 'Montserrat', sans-serif;
        font-size: clamp(28px, 3.4vw, 40px);
        font-weight: 700;
        color: __HEADLINE__;
        margin: 0 0 16px 0;
        line-height: 1.15;
        letter-spacing: -0.02em;
    }
    .nela-section-sub {
        font-size: 17px;
        color: __TEXTGRAU__;
        line-height: 1.6;
    }

    /* ============ 9. MODUL-KARTEN ============ */
    .nela-modul-grid {  /* Louis: Raster für die 4 Modul-Karten */
        display: grid;
        grid-template-columns: repeat(4, 1fr);  /* Louis: repeat(4, 1fr) = 4 gleich breite Spalten nebeneinander */
        gap: 22px;
    }
    .nela-modul {  /* Louis: eine einzelne Karte (weiße Box mit Rahmen und runden Ecken) */
        background: #FFFFFF;
        border: 1px solid #EDF2EE;
        border-radius: 18px;
        padding: 28px 24px;
        transition: all 0.25s cubic-bezier(.4, 0, .2, 1);  /* Louis: transition = Änderungen sanft animieren (0.25s), statt ruckartig */
        position: relative;  /* Louis: nötig, damit die Nummer (unten, position:absolute) sich AN DIESER Karte ausrichtet */
    }
    .nela-modul:hover {  /* Louis: :hover = wenn Maus drüber. Reine CSS-Optik, kein Klick! */
        transform: translateY(-4px);  /* Louis: Karte 4px nach oben "anheben" */
        box-shadow: 0 20px 40px -16px rgba(46, 125, 50, 0.18);  /* Louis: + Schatten -> wirkt lebendig/anklickbar */
        border-color: __AKZENT_HELL__;
    }
    .nela-modul-icon {
        width: 50px; height: 50px;
        background: __HG_HELL__;
        border-radius: 14px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 18px;
        color: __PRIMAER__;
    }
    .nela-modul-nr {  /* Louis: die kleine Nummer (01-04) oben rechts in der Karte */
        position: absolute;   /* Louis: absolute = frei platzieren, bezogen auf die Karte (die hat ja position:relative) */
        top: 22px; right: 22px;  /* Louis: 22px von oben und rechts -> obere rechte Ecke */
        font-family: 'Montserrat', sans-serif;
        font-size: 12px;
        font-weight: 800;
        color: __AKZENT_HELL__;
        letter-spacing: 1px;
    }
    .nela-modul h3 {
        font-family: 'Montserrat', sans-serif;
        font-size: 19px;
        font-weight: 700;
        color: __HEADLINE__;
        margin: 0 0 10px 0;
        line-height: 1.25;
    }
    .nela-modul p {
        font-size: 14px;
        color: __TEXTGRAU__;
        line-height: 1.6;
        margin: 0;
    }

    /* ============ 10. VERGLEICHSTABELLE ============ */
    .nela-vergleich-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }  /* Louis: Hülle um die Tabelle. overflow-x:auto = auf schmalem Handy seitlich scrollbar, statt die Tabelle zu quetschen */
    .nela-vergleich {
        width: 100%;
        min-width: 600px;
        background: #FFFFFF;
        border-radius: 18px;
        overflow: hidden;
        box-shadow: 0 4px 20px -8px rgba(0,0,0,0.06);
        border-collapse: collapse;
    }
    .nela-vergleich thead th {
        background: __HEADLINE__;
        color: #FFFFFF;
        font-family: 'Montserrat', sans-serif;
        font-size: 14px;
        font-weight: 700;
        text-align: center;
        padding: 18px 14px;
    }
    .nela-vergleich thead th:first-child { text-align: left; }
    .nela-vergleich thead th.nela-spalte {
        background: __PRIMAER__;
        position: relative;
    }
    .nela-vergleich thead th.nela-spalte::after {  /* Louis: ::after hängt das kleine "Wir"-Label an unsere Nela-Spalte (lenkt den Blick auf die eigene Spalte) */
        content: "Wir";
        position: absolute;
        top: 6px; right: 10px;
        font-size: 10px;
        background: __CTA__;
        color: #0D2B0F;
        padding: 2px 8px;
        border-radius: 999px;
        letter-spacing: 1px;
        font-weight: 700;
    }
    .nela-vergleich tbody td {
        padding: 14px;
        text-align: center;
        font-size: 14px;
        color: __HEADLINE__;
        border-bottom: 1px solid #F0F4F0;
    }
    .nela-vergleich tbody td:first-child {
        text-align: left;
        font-weight: 600;
    }
    .nela-vergleich tbody tr:last-child td { border-bottom: none; }
    .nela-vergleich td.yes { color: __PRIMAER__; font-weight: 800; font-size: 18px; }  /* Louis: td.yes (ohne Leerzeichen!) = eine Zelle MIT Klasse "yes" -> grünes Häkchen */
    .nela-vergleich td.no  { color: #CCCCCC; font-weight: 800; font-size: 18px; }      /* Louis: "no" -> graues Kreuz (dezent) */
    .nela-vergleich td.partial { color: __CTA__; font-weight: 800; font-size: 14px; }  /* Louis: "partial" -> "teilw." in Akzentfarbe */
    .nela-vergleich td.col-us { background: rgba(46,125,50,0.04); }  /* Louis: col-us = alle Nela-Zellen leicht grün hinterlegt, damit die Spalte zusammenhängt */

    /* ============ 11. PFLEGEGRAD-RECHNER CARD ============ */
    .nela-rechner-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 14px;
    }
    .nela-rechner-step {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: __PRIMAER__;
    }
    .nela-rechner-bereich {
        font-size: 13px;
        color: __TEXTGRAU__;
        font-weight: 600;
    }
    .nela-frage h3 {
        font-family: 'Montserrat', sans-serif !important;
        font-size: 21px !important;
        font-weight: 700 !important;
        color: __HEADLINE__ !important;
        margin: 12px 0 6px 0;
        line-height: 1.3;
    }
    .nela-frage-beschreibung {
        color: __TEXTGRAU__;
        font-size: 13px;
        margin: 0 0 16px 0;
        letter-spacing: 0.3px;
    }

    /* Ergebnis-Karte */
    .nela-ergebnis {
        background: linear-gradient(135deg, __PRIMAER__ 0%, __PRIMAER_DUNKEL__ 100%);
        color: #FFFFFF;
        padding: 36px 28px;
        border-radius: 18px;
        text-align: center;
        margin: 24px 0 16px 0;
        box-shadow: 0 12px 36px -14px rgba(46, 125, 50, 0.40);
        position: relative;
        overflow: hidden;
    }
    .nela-ergebnis-eyebrow {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
        opacity: 0.85;
        margin-bottom: 12px;
    }
    .nela-ergebnis-headline {
        font-family: 'Montserrat', sans-serif;
        font-size: clamp(22px, 3vw, 30px);
        font-weight: 800;
        margin: 0 0 8px 0;
        color: #FFFFFF !important;
    }
    .nela-ergebnis-sub {
        font-size: 14px;
        opacity: 0.92;
    }

    /* Leistungs-Übersicht (PG1) - Apple-clean Minimalismus */
    .nela-lst-titel {
        font-size: 18px;
        font-weight: 500;
        color: __HEADLINE__;
        margin: 28px 0 4px 0;
        letter-spacing: -0.2px;
    }
    .nela-lst-subtitel {
        font-size: 14px;
        color: __TEXTGRAU__;
        margin: 0 0 16px 0;
    }
    .nela-lst-hinweis {
        background: #F7F7F4;
        border-radius: 10px;
        padding: 12px 16px;
        font-size: 13px;
        color: __HEADLINE__;
        margin: 0 0 14px 0;
        line-height: 1.45;
    }
    .nela-lst-karte {
        background: #FFFFFF;
        border: 0.5px solid #E5E5E5;
        border-radius: 12px;
        padding: 4px 0;
        overflow: hidden;
    }
    .nela-lst-row {
        display: flex;
        align-items: center;
        padding: 14px 20px;
        border-bottom: 0.5px solid #F0F0F0;
        gap: 12px;
    }
    .nela-lst-row:last-child {
        border-bottom: none;
    }
    .nela-lst-col-name {
        flex: 0 0 60%;
        max-width: 60%;
    }
    .nela-lst-col-betrag {
        flex: 0 0 25%;
        max-width: 25%;
        text-align: right;
    }
    .nela-lst-col-tag {
        flex: 0 0 15%;
        max-width: 15%;
        text-align: right;
    }
    .nela-lst-name {
        font-size: 15px;
        font-weight: 600;
        color: __HEADLINE__;
        line-height: 1.3;
    }
    .nela-lst-info {
        font-size: 13px;
        color: __TEXTGRAU__;
        margin-top: 2px;
        line-height: 1.4;
    }
    .nela-lst-betrag {
        font-size: 15px;
        font-weight: 600;
        color: __HEADLINE__;
        line-height: 1.3;
    }
    .nela-lst-periode {
        font-size: 12px;
        color: __TEXTGRAU__;
        margin-top: 2px;
    }
    .nela-lst-tag {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.2px;
    }
    .nela-lst-tag-guthaben { background: #E6F1FB; color: #0C447C; }
    .nela-lst-tag-antrag   { background: #F5EBC8; color: #633806; }
    .nela-lst-tag-service  { background: #F1EFE8; color: #444441; }
    .nela-lst-tag-konto    { background: #EAF3DE; color: #27500A; }
    .nela-lst-tag-indirekt { background: #EEEDFE; color: #3C3489; }
    .nela-lst-tag-steuer   { background: #EEEDFE; color: #3C3489; }
    .nela-lst-legende {
        display: flex;
        justify-content: center;
        gap: 22px;
        margin: 14px 0 4px 0;
        flex-wrap: wrap;
    }
    .nela-lst-legende-item {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        color: __TEXTGRAU__;
    }
    .nela-lst-legende-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
    }
    .nela-lst-legende-dot-guthaben       { background: #0C447C; }
    .nela-lst-legende-dot-antrag         { background: #C97A1B; }
    .nela-lst-legende-dot-service        { background: #888685; }
    .nela-lst-legende-dot-konto          { background: #27500A; }
    .nela-lst-legende-dot-indirekt-steuer { background: #3C3489; }

    /* Jahres-Summen-Block am Ende der Leistungstabelle */
    .nela-lst-summe {
        background: __HG_HELL__;
        border: 0.5px solid __AKZENT_HELL__;
        border-radius: 14px;
        padding: 22px 24px;
        margin: 18px 0 6px 0;
        text-align: center;
    }
    .nela-lst-summe-label {
        font-size: 12px;
        font-weight: 600;
        color: __HEADLINE__;
        letter-spacing: 1px;
        text-transform: uppercase;
        opacity: 0.75;
    }
    .nela-lst-summe-betrag {
        font-family: 'Montserrat', sans-serif;
        font-size: clamp(28px, 4vw, 38px);
        font-weight: 700;
        color: __PRIMAER_DUNKEL__;
        line-height: 1.1;
        margin: 6px 0 10px 0;
        letter-spacing: -0.5px;
    }
    .nela-lst-summe-cta {
        font-size: 14px;
        color: __TEXTGRAU__;
        max-width: 460px;
        margin: 0 auto;
        line-height: 1.45;
    }

    /* Conversion-Box nach Rechner-Ergebnis (nur für anonyme Nutzer)
     * UX: Türkis-Akzent statt Amber → einheitliche CTA-Farbe. */
    .nela-conversion {
        background: linear-gradient(135deg, #E6FAFB 0%, #F0FEFF 100%);
        border: 2px dashed __CTA__;
        border-radius: 16px;
        padding: 24px 26px;
        margin: 24px 0 16px 0;
    }
    .nela-conversion-headline {
        font-family: 'Montserrat', sans-serif;
        font-size: 19px;
        font-weight: 700;
        color: __HEADLINE__;
        margin: 0 0 8px 0;
    }
    .nela-conversion-text {
        font-size: 14px;
        color: __TEXTGRAU__;
        line-height: 1.6;
        margin: 0;
    }

    /* ============ 12. LEISTUNGSLÜCKEN-VORSCHAU ============ */
    .nela-vorschau {
        background: linear-gradient(135deg, __HG_WARM__ 0%, __HG_HELL__ 100%);
        border-radius: 22px;
        padding: 44px 36px;
        max-width: 820px;
        margin: 0 auto;
        position: relative;
    }
    .nela-vorschau-badge {
        position: absolute;
        top: 18px; right: 22px;
        background: #FFFFFF;
        color: __PRIMAER__;
        border: 1px solid __PRIMAER__;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        padding: 6px 12px;
        border-radius: 999px;
    }
    .nela-vorschau-eyebrow {
        text-align: center;
        color: __TEXTGRAU__;
        font-size: 12px;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        font-weight: 700;
    }
    .nela-vorschau-amount {
        font-family: 'Montserrat', sans-serif;
        font-size: clamp(48px, 7vw, 78px);
        font-weight: 800;
        color: __PRIMAER__;
        line-height: 1;
        text-align: center;
        margin: 12px 0 6px 0;
        letter-spacing: -0.04em;
    }
    .nela-vorschau-label {
        text-align: center;
        color: __HEADLINE__;
        font-size: 16px;
        margin-bottom: 28px;
    }
    .nela-vorschau-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
    }
    .nela-vorschau-item {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 16px 18px;
        border-left: 3px solid __PRIMAER__;
    }
    .nela-vorschau-item-label {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: __TEXTGRAU__;
        margin-bottom: 4px;
    }
    .nela-vorschau-item-value {
        font-family: 'Montserrat', sans-serif;
        font-size: 20px;
        font-weight: 700;
        color: __HEADLINE__;
    }
    .nela-vorschau-hint {
        text-align: center;
        margin-top: 26px;
        font-size: 13px;
        color: __TEXTGRAU__;
        font-style: italic;
    }
    /* ============ 13. CTA-SECTION ============ */
    .nela-cta {
        background: linear-gradient(135deg, __HEADLINE__ 0%, #243d12 100%);
        padding: 80px 0;
        text-align: center;
    }
    .nela-cta-headline {
        font-family: 'Montserrat', sans-serif !important;
        font-size: clamp(28px, 4vw, 44px);
        font-weight: 800;
        color: #FFFFFF !important;
        margin: 0 0 18px 0;
        line-height: 1.15;
    }
    .nela-cta-sub {
        font-size: 17px;
        color: __AKZENT_HELL__;
        line-height: 1.55;
        margin: 0 auto 0 auto;
        text-align: center;
        max-width: 580px;
    }

    /* ============ 14. FOOTER ============ */
    .nela-footer {  /* Louis: Footer = Fußzeile ganz unten (dunkelgrün). Eigenes HTML-Tag <footer>, semantisch = "hier ist der Fußbereich" */
        background: #0F1A06;
        color: #A5C9A8;
        padding: 56px 0 28px 0;
    }
    .nela-footer-cols {  /* Louis: die 4 Spalten des Footers: Marke | Produkt | Unternehmen | Rechtliches */
        display: grid;
        grid-template-columns: 2fr 1fr 1fr 1fr;  /* Louis: erste Spalte (Marke) doppelt so breit wie die Link-Spalten */
        gap: 48px;
        margin-bottom: 42px;
    }
    .nela-footer-brand {
        font-family: 'Montserrat', sans-serif;
        font-size: 22px;
        font-weight: 800;
        color: #FFFFFF;
        margin-bottom: 6px;
    }
    .nela-footer-tagline {
        font-size: 14px;
        color: __AKZENT_HELL__;
        font-style: italic;
        margin-bottom: 14px;
    }
    .nela-footer-text {
        font-size: 13px;
        line-height: 1.6;
        color: #82A485;
        max-width: 320px;
    }
    .nela-footer-col-title {
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: #FFFFFF;
        margin-bottom: 14px;
    }
    .nela-footer-link {
        display: block;
        font-size: 14px;
        color: #A5C9A8;
        text-decoration: none;
        margin-bottom: 9px;
        transition: color 0.15s ease;
        cursor: pointer;
    }
    .nela-footer-link:hover { color: #FFFFFF; }
    .nela-footer-bottom {
        border-top: 1px solid #1F3414;
        padding-top: 22px;
        font-size: 12px;
        color: #678869;
        display: flex;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 10px;
    }

    /* UX: Band-Variante für Footer-Legal-Buttons – dunkler Footer-Hintergrund
     * wird nach unten verlängert, damit die Streamlit-Buttons darunter
     * (Datenschutz / AGB / Impressum) optisch zum Footer gehören.
     *
     * Beim Footer ziehen wir die Buttons besonders aggressiv hoch, damit
     * sie wirklich IM Footer (über der Copyright-Zeile) erscheinen statt
     * mit großem Abstand darunter.
     */
    .nela-band-footer {
        background: #0F1A06;
    }
    /* Spezifischer Override: stärkerer Pull-up für die Footer-Buttons.
     * Mit Bandhöhe 150 und margin -260 starten die Buttons 110px ÜBER
     * dem Band-Anfang (= 110px im Footer-Inhalt). */
    [data-testid="stElementContainer"]:has(.nela-band-footer) {
        margin-bottom: -260px !important;
    }
    /* Datenschutz/AGB/Impressum-Buttons in der Footer-Legal-Row:
     * unauffällige helle Text-Links auf dunklem Footer-Grund. */
    div[data-testid="stButton"] > button[aria-label="Datenschutz"],
    div[data-testid="stButton"] > button[aria-label="AGB"],
    div[data-testid="stButton"] > button[aria-label="Impressum"] {
        background: transparent !important;
        color: #A5C9A8 !important;
        border: 1px solid transparent !important;
        font-weight: 500 !important;
        font-size: 13px !important;
        padding: 6px 12px !important;
        box-shadow: none !important;
    }
    div[data-testid="stButton"] > button[aria-label="Datenschutz"]:hover,
    div[data-testid="stButton"] > button[aria-label="AGB"]:hover,
    div[data-testid="stButton"] > button[aria-label="Impressum"]:hover {
        background: rgba(255,255,255,0.06) !important;
        color: #FFFFFF !important;
        border-color: transparent !important;
    }

    /* ============ 15. STREAMLIT-BUTTONS (global) ============
     * UX: cursor:pointer auf ALLE Buttons – fundamentale UX-Erwartung.
     *     Buttons kompakter dimensioniert (9px/18px statt 11px/22px) –
     *     ruhigeres, professionelleres Erscheinungsbild.
     */
    div[data-testid="stButton"] > button {  /* Louis: Grundstil für ALLE Streamlit-Buttons. div[...]=Streamlits Button-Hülle, ">"=das button DIREKT darin. Wir geben dem Standard-Button unser Aussehen */
        border-radius: 9px !important;       /* Louis: !important überall, weil wir Streamlits eigenes Standard-CSS überschreiben müssen */
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        padding: 9px 20px !important;
        border: 1.5px solid __PRIMAER__ !important;  /* Louis: grüner Rahmen... */
        background: #FFFFFF !important;              /* Louis: ...auf weiß... */
        color: __PRIMAER__ !important;              /* Louis: ...mit grüner Schrift */
        transition: all 0.18s ease !important;
        box-shadow: none !important;
        cursor: pointer !important;  /* Louis: Hand-Symbol bei Maus drüber */
        letter-spacing: 0.01em !important;
    }
    div[data-testid="stButton"] > button:hover {  /* Louis: eigener Hover für die Buttons (gilt NUR für sie, nicht für Karten/Links) */
        background: __HG_HELL__ !important;
        color: __PRIMAER_DUNKEL__ !important;
        border-color: __PRIMAER_DUNKEL__ !important;
        cursor: pointer !important;
    }
    div[data-testid="stButton"] > button[kind="primary"],  /* Louis: [kind="primary"] = die wichtigen Buttons (in Python: type="primary"). Bekommen Akzentfarbe (Peach) und stechen heraus */
    div[data-testid="stFormSubmitButton"] > button[kind="primary"] {
        background: __CTA__ !important;
        color: #1A2E0D !important;
        border-color: #E8B877 !important;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover,
    div[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {
        background: #FFD89A !important;
        border-color: #DBA85F !important;
        color: #1A2E0D !important;
        cursor: pointer !important;
    }
    div[data-testid="stButton"] > button:disabled {
        opacity: 0.45 !important;
        cursor: not-allowed !important;
    }

    /* UX: Top-CTA-Buttons (Konversionspunkte) erhalten zusätzlich Box-Shadow
     * und Font-Weight 700. Farben kommen bereits aus der globalen
     * primary-Regel (Peach #FFE5B4 / Text #1A2E0D / Hover #FFD89A mit
     * Rahmen #E8B877, damit der helle Button auf Warmweiß nicht ausläuft). */
    div[data-testid="stButton"] > button[aria-label="Kostenloses Konto erstellen"][kind="primary"],
    div[data-testid="stButton"] > button[aria-label="Konto erstellen"][kind="primary"],
    div[data-testid="stButton"] > button[aria-label="Anmelden"][kind="primary"],
    div[data-testid="stButton"] > button[aria-label="Registrieren"][kind="primary"],
    div[data-testid="stFormSubmitButton"] > button[kind="primary"] {
        background: __CTA__ !important;
        color: #1A2E0D !important;
        border-color: #E8B877 !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 14px -4px rgba(232, 184, 119, 0.45) !important;
        cursor: pointer !important;
    }
    div[data-testid="stButton"] > button[aria-label="Kostenloses Konto erstellen"][kind="primary"]:hover,  /* Louis: feinste Stufe: NUR der Hover-Moment dieser bestimmten Buttons. aria-label = der Button-TEXT (vergibt Streamlit automatisch aus st.button("...")). Komma = mehrere Selektoren, gleicher Style */
    div[data-testid="stButton"] > button[aria-label="Konto erstellen"][kind="primary"]:hover,
    div[data-testid="stButton"] > button[aria-label="Anmelden"][kind="primary"]:hover,
    div[data-testid="stButton"] > button[aria-label="Registrieren"][kind="primary"]:hover,
    div[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {
        background: #FFD89A !important;  /* Louis: helleres Peach beim Drüberfahren (passt zum Peach-Button, statt grünem Standard-Hover) */
        border-color: #DBA85F !important;
        color: #1A2E0D !important;
        cursor: pointer !important;
    }

    /* ============ 16. ANTWORT-BUTTONS RECHNER ============
     * UX: Buttons kompakter (76px statt 100px) – weniger visuelles Rauschen,
     *     Antworten bleiben klar lesbar. cursor: pointer ergänzt.
     */
    [data-testid="stHorizontalBlock"] div[data-testid="stButton"] > button {
        height: 76px !important;
        border-radius: 10px !important;
        white-space: pre-line !important;
        line-height: 1.35 !important;
        border: 1.5px solid __AKZENT_HELL__ !important;
        font-size: 12.5px !important;
        font-weight: 500 !important;
        color: __TEXTGRAU__ !important;
        background: #FFFFFF !important;
        padding: 8px 10px !important;
        text-align: center !important;
        cursor: pointer !important;
    }
    [data-testid="stHorizontalBlock"] div[data-testid="stButton"] > button::first-line {
        font-size: 14px !important;
        font-weight: 700 !important;
        color: __HEADLINE__ !important;
    }
    [data-testid="stHorizontalBlock"] div[data-testid="stButton"] > button:hover {
        background: __HG_HELL__ !important;
        border-color: __PRIMAER__ !important;
        color: __HEADLINE__ !important;
        cursor: pointer !important;
    }
    [data-testid="stHorizontalBlock"] div[data-testid="stButton"] > button[kind="primary"] {
        background: __CTA__ !important;
        border-color: #E8B877 !important;
        color: #1A2E0D !important;
    }
    [data-testid="stHorizontalBlock"] div[data-testid="stButton"] > button[kind="primary"]::first-line {
        color: #1A2E0D !important;
    }

    /* ============ 16b. ANTWORT-BUTTONS RECHNER/LEISTUNGSCHECK - HELLGRUEN-OVERRIDE ============
     * UX: Im Pflegegrad-Rechner (Keys pg_btn_*) und Leistungscheck (Keys lc_*)
     *     sollen Antwort-Buttons NICHT in Peach (globale primary-Regel) gerendert
     *     werden, sondern in einem zarten Hellgruen (ausgewaehlt) bzw. Weiss mit
     *     dezentem grau-gruenen Rahmen (nicht ausgewaehlt). Der Weiter-Button
     *     (Key pg_weiter_*) faellt NICHT in dieses Scope und bleibt Peach.
     */

    /* Antwort-Buttons Pflegegrad-Rechner + Leistungscheck:
       AUSGEWAEHLT (primary) = zartes Hellgruen, NICHT Peach. */
    div[class*="st-key-pg_btn_"] div[data-testid="stButton"] > button[kind="primary"],
    div[class*="st-key-lc_"] div[data-testid="stButton"] > button[kind="primary"] {
        background: #E8F5E9 !important;
        border: 2px solid #2E7D32 !important;
        color: #1A2E0D !important;
        box-shadow: none !important;
    }
    div[class*="st-key-pg_btn_"] div[data-testid="stButton"] > button[kind="primary"]:hover,
    div[class*="st-key-lc_"] div[data-testid="stButton"] > button[kind="primary"]:hover {
        background: #DCEEDD !important;
        border-color: #2E7D32 !important;
        color: #1A2E0D !important;
    }
    div[class*="st-key-pg_btn_"] div[data-testid="stButton"] > button[kind="primary"] *,
    div[class*="st-key-lc_"] div[data-testid="stButton"] > button[kind="primary"] * {
        color: #1A2E0D !important;
    }

    /* NICHT-AUSGEWAEHLT (secondary) = weiss + dezenter grau-gruener Rahmen. */
    div[class*="st-key-pg_btn_"] div[data-testid="stButton"] > button[kind="secondary"],
    div[class*="st-key-lc_"] div[data-testid="stButton"] > button[kind="secondary"] {
        background: #FFFFFF !important;
        border: 1px solid #D5DED2 !important;
        color: #1A2E0D !important;
        box-shadow: none !important;
    }
    div[class*="st-key-pg_btn_"] div[data-testid="stButton"] > button[kind="secondary"]:hover,
    div[class*="st-key-lc_"] div[data-testid="stButton"] > button[kind="secondary"]:hover {
        background: #F4F9F2 !important;
        border-color: #2E7D32 !important;
        color: #1A2E0D !important;
    }
    div[class*="st-key-pg_btn_"] div[data-testid="stButton"] > button[kind="secondary"] *,
    div[class*="st-key-lc_"] div[data-testid="stButton"] > button[kind="secondary"] * {
        color: #1A2E0D !important;
    }

    /* ============ 16c. WEITER-BUTTON PEACH (Pflegegrad-Rechner + Leistungscheck) ============
     * UX: Der "Weiter"-Button im Pflegegrad-Rechner (Keys pg_weiter_*) und im
     *     Leistungscheck (Keys lc_weiter_*) bleibt Peach. Diese Regel kommt nach 16b
     *     und ueberschreibt damit das Hellgruen-Override fuer alle Keys, die mit
     *     "lc_weiter_" beginnen (sie wuerden sonst durch das breitere "st-key-lc_"-
     *     Match faelschlich hellgruen).
     */
    div[class*="st-key-pg_weiter_"] div[data-testid="stButton"] > button[kind="primary"],
    div[class*="st-key-lc_weiter_"] div[data-testid="stButton"] > button[kind="primary"] {
        background: #FFE5B4 !important;
        border: 1.5px solid #E8B877 !important;
        color: #1A2E0D !important;
        box-shadow: none !important;
    }
    div[class*="st-key-pg_weiter_"] div[data-testid="stButton"] > button[kind="primary"]:hover,
    div[class*="st-key-lc_weiter_"] div[data-testid="stButton"] > button[kind="primary"]:hover {
        background: #FFD89A !important;
        border-color: #DBA85F !important;
        color: #1A2E0D !important;
    }
    div[class*="st-key-pg_weiter_"] div[data-testid="stButton"] > button[kind="primary"] *,
    div[class*="st-key-lc_weiter_"] div[data-testid="stButton"] > button[kind="primary"] * {
        color: #1A2E0D !important;
    }

    /* ============ 17. INPUTS / FORMS ============ */
    [data-testid="stTextInput"] input,
    [data-testid="stPasswordInput"] input,
    input[type="text"], input[type="password"] {
        border-radius: 10px !important;
        border: 2px solid #E5E9E4 !important;
        padding: 11px 14px !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 14px !important;
        background: #FFFFFF !important;
    }
    [data-testid="stTextInput"] input:focus,
    [data-testid="stPasswordInput"] input:focus,
    input[type="text"]:focus, input[type="password"]:focus {
        border-color: __PRIMAER__ !important;
        box-shadow: 0 0 0 3px rgba(46,125,50,0.12) !important;
        outline: none !important;
    }
    [data-testid="stTextInput"] label,
    [data-testid="stPasswordInput"] label {
        font-size: 13px !important;
        font-weight: 600 !important;
        color: __HEADLINE__ !important;
    }
    [data-testid="stCheckbox"] label p {
        font-size: 13px !important;
        color: __TEXTGRAU__ !important;
    }

    /* Progress-Bar */
    [data-testid="stProgress"] > div > div > div {
        background-color: __PRIMAER__ !important;
        border-radius: 999px;
    }
    [data-testid="stProgress"] > div > div {
        background-color: #EDF2EE !important;
        border-radius: 999px;
    }

    /* ============ 18. SIDEBAR (eingeloggt) ============
     * UX: cursor:pointer auf alle Sidebar-Buttons. Aktiver Zustand mit
     *     linker Akzentlinie statt voller Hintergrundfarbe – ruhigerer Look. */
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: __HEADLINE__ !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 1.5px;
        margin: 22px 0 8px 0 !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button {
        text-align: left !important;
        justify-content: flex-start !important;
        font-weight: 600 !important;
        padding: 9px 14px !important;
        border: 1px solid transparent !important;
        background: transparent !important;
        color: __HEADLINE__ !important;
        cursor: pointer !important;
        border-radius: 8px !important;
        transition: all 0.15s ease !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
        background: __HG_HELL__ !important;
        color: __PRIMAER__ !important;
        border-color: transparent !important;
        cursor: pointer !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="primary"] {
        background: rgba(255,229,180,0.25) !important;
        border-color: transparent !important;
        border-left: 3px solid #E8B877 !important;
        color: #1A2E0D !important;
        font-weight: 700 !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="primary"]:hover {
        background: rgba(255,229,180,0.40) !important;
        cursor: pointer !important;
    }

    /* ============ 19. APP-BEREICH ============ */
    .nela-app-heading {
        margin: 8px 0 28px 0;
    }
    .nela-app-heading h1 {
        font-family: 'Montserrat', sans-serif !important;
        font-size: clamp(26px, 3.6vw, 36px) !important;
        font-weight: 800 !important;
        color: __HEADLINE__ !important;
        margin: 6px 0 6px 0 !important;
        letter-spacing: -0.02em;
    }
    .nela-app-heading p {
        color: __TEXTGRAU__;
        font-size: 15px;
        max-width: 700px;
    }
    .nela-tile {
        background: #FFFFFF;
        border: 1px solid #EDF2EE;
        border-left: 4px solid __PRIMAER__;
        border-radius: 14px;
        padding: 22px 24px;
        height: 100%;
        margin-bottom: 8px;
    }
    .nela-tile-label {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: __PRIMAER__;
        margin-bottom: 6px;
    }
    .nela-tile-value {
        font-family: 'Montserrat', sans-serif;
        font-size: 20px;
        font-weight: 700;
        color: __HEADLINE__;
        line-height: 1.25;
    }
    .nela-tile-sub {
        font-size: 12px;
        color: __TEXTGRAU__;
        margin-top: 6px;
    }

    /* Profil-Felder */
    .nela-profil-feld { margin-bottom: 14px; }
    .nela-profil-label {
        font-size: 11px;
        color: __TEXTGRAU__;
        letter-spacing: 1px;
        text-transform: uppercase;
        margin-bottom: 2px;
    }
    .nela-profil-value {
        font-size: 15px;
        color: __HEADLINE__;
        font-weight: 600;
    }

    /* Alerts in Markenfarbe */
    [data-testid="stAlert"] { border-radius: 12px !important; }

    /* ============ 20. SECTION-BLENDING-BÄNDER ============
     *
     * Streamlit-Beschränkung: Buttons sind eigene DOM-Container und können
     * NICHT in HTML-Sections eingebettet werden. Lösung: vor jeder losen
     * Button-Reihe wird ein Full-Bleed-Band injiziert, das die Farbe der
     * darüberliegenden Section nach unten verlängert. Über negative
     * margin-bottom wird die folgende Button-Reihe optisch in dieses Band
     * "hineingezogen", sodass die Buttons wie Teil der Section wirken.
     *
     * Das funktioniert sauber, weil:
     *   1. stMain ist transparent (s. Abschnitt 3) → das Band ist sichtbar
     *      auch hinter der zentrierten 1200px-Container-Zone.
     *   2. Die Buttons selbst haben definierte eigene Hintergründe
     *      (Primärgrün / CTA-Peach), heben sich also klar vom Band ab.
     *   3. Die nachfolgende Full-Bleed-Section deckt das Band sauber
     *      nach unten ab.
     */
    /* ============ 20. SECTION-BLENDING-BÄNDER ============
     *
     * Streamlit-Beschränkung: Buttons sind eigene DOM-Container und können
     * NICHT in HTML-Sections eingebettet werden. Lösung: vor jeder losen
     * Button-Reihe wird ein Full-Bleed-Band injiziert, das die Farbe der
     * darüberliegenden Section nach unten verlängert.
     *
     * WICHTIG zur Streamlit-DOM-Mechanik:
     *  Jeder st.markdown-Aufruf wird in einen stElementContainer +
     *  stMarkdown-Wrapper gepackt. Eine negative margin-bottom auf dem
     *  INNEREN .nela-band-div propagiert nicht zuverlässig durch diese
     *  Wrapper hindurch zum nachfolgenden Sibling (stHorizontalBlock mit
     *  den Buttons). Konsequenz: die Buttons würden visuell UNTER dem
     *  Band landen statt darin.
     *
     *  Fix: wir setzen die negative margin-bottom auf den ÄUSSEREN
     *  stElementContainer, der das Band enthält — per :has()-Selektor.
     *  Damit wird der nachfolgende Sibling (= die Button-Spalten) wirklich
     *  hochgezogen.
     */
    .nela-band {
        margin-left: calc(-50vw + 50%);
        margin-right: calc(-50vw + 50%);
        width: 100vw;
        height: 150px;            /* großzügige Bandhöhe für klare Section-Verlängerung */
        position: relative;
        pointer-events: none;     /* Band ist rein dekorativ, blockiert keine Klicks */
        z-index: 0;
    }
    /* UX: Aggressive negative Margin auf dem äußeren Container.
     * effektiver Flow-Verbrauch = height + margin = 150 - 175 = -25px
     * → Die Button-Reihe wird 25px IN die Section darüber hineingezogen.
     * Die Buttons sitzen damit zu ca. 70% in der eigentlichen Section
     * (Hero/CTA/Soft) und nur noch knapp im Band — exakt das gewünschte
     * "weiter hoch"-Verhalten. */
    [data-testid="stElementContainer"]:has(> div > .nela-band),
    [data-testid="stElementContainer"]:has(.nela-band) {
        margin-bottom: -175px !important;
        position: relative;
        z-index: 0;
    }
    /* Die folgende Button-Reihe muss visuell ÜBER dem Band liegen */
    [data-testid="stElementContainer"]:has(.nela-band) + [data-testid="stHorizontalBlock"],
    [data-testid="stElementContainer"]:has(.nela-band) + div [data-testid="stHorizontalBlock"] {
        position: relative;
        z-index: 2;
    }

    /* Band-Farbe = Endfarbe der darüberliegenden Section */
    .nela-band-hero {
        background: __HG_HELL__;   /* Hero endet in HG_HELL */
    }
    .nela-band-soft {
        background: __HG_HELL__;   /* section-soft-Hintergrund */
    }
    .nela-band-cta {
        background: linear-gradient(135deg, __HEADLINE__ 0%, #243d12 100%);
    }

    /* ============ 21. SPEZIFISCHE BUTTON-STYLES =========
     * UX: Nav-Buttons kompakter (weniger dominant), Hero-CTA etwas größer
     *     (klare visuelle Priorität als Hauptkonversionspunkt). */
    /* Header-Buttons: kompakt, beide identische Höhe.
     * UX: Scope per :has(.nela-topnav-marker) auf den Header-stHorizontalBlock.
     *     Selektor verzichtet bewusst auf [aria-label="..."], weil Streamlit
     *     je nach Version kein aria-label am Button setzt — die Marker-Scope
     *     reicht, weil im Header genau die zwei Buttons leben.
     *     Bewusst NUR min-height (kein fixes height) und KEIN ::first-line-
     *     Override, weil beides in Chrome zu Click-Aussetzern führen kann. */
    [data-testid="stHorizontalBlock"]:has(.nela-topnav-marker) [data-testid="stButton"] > button {
        padding-top: 2px !important;
        padding-bottom: 2px !important;
        padding-left: 14px !important;
        padding-right: 14px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        line-height: 1 !important;
        min-height: 0 !important;
        border-radius: 8px !important;
        box-sizing: border-box !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    [data-testid="stHorizontalBlock"]:has(.nela-topnav-marker) [data-testid="stButton"] > button p {
        font-size: 13px !important;
        font-weight: 600 !important;
        line-height: 1 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    /* Header-Registrieren: gefülltes Grün statt Peach.
     * UX: Peach bleibt den Top-Conversion-CTAs (Hero "In 5 Minuten
     *     herausfinden", "Kostenloses Konto erstellen") vorbehalten —
     *     normale Header-Aktion wird grün, damit der Hero-CTA weiter
     *     visuell dominiert. Scope per Marker, damit andere primary-
     *     Buttons (Hero, Section-CTAs) unverändert Peach bleiben. */
    [data-testid="stHorizontalBlock"]:has(.nela-topnav-marker) [data-testid="stButton"] > button[kind="primary"] {
        background: __PRIMAER__ !important;
        color: #FFFFFF !important;
        border: 1px solid __PRIMAER__ !important;
        box-shadow: none !important;
    }
    [data-testid="stHorizontalBlock"]:has(.nela-topnav-marker) [data-testid="stButton"] > button[kind="primary"] p {
        color: #FFFFFF !important;
    }
    [data-testid="stHorizontalBlock"]:has(.nela-topnav-marker) [data-testid="stButton"] > button[kind="primary"]:hover {
        background: #25671F !important;
        border-color: #25671F !important;
        color: #FFFFFF !important;
    }
    /* Header-Anmelden: Ghost — transparenter Hintergrund, gruener Rahmen + Text. */
    [data-testid="stHorizontalBlock"]:has(.nela-topnav-marker) [data-testid="stButton"] > button[kind="secondary"] {
        background: transparent !important;
        color: __PRIMAER__ !important;
        border: 1px solid __PRIMAER__ !important;
        box-shadow: none !important;
    }
    [data-testid="stHorizontalBlock"]:has(.nela-topnav-marker) [data-testid="stButton"] > button[kind="secondary"] p {
        color: __PRIMAER__ !important;
    }
    [data-testid="stHorizontalBlock"]:has(.nela-topnav-marker) [data-testid="stButton"] > button[kind="secondary"]:hover {
        background: rgba(46, 125, 50, 0.06) !important;
        border-color: __PRIMAER__ !important;
        color: __PRIMAER__ !important;
    }
    /* Haupt-CTA im Hero etwas prominenter */
    div[data-testid="stButton"] > button[aria-label="Kostenloses Konto erstellen"] {
        padding: 12px 24px !important;
        font-size: 15px !important;
        border-radius: 9px !important;
    }
    /* UX: Sekundärer CTA-Section-Button "Bereits Konto - Anmelden" sitzt
     * auf dunklem Band (nela-band-cta). Wir geben ihm hellen Stil für
     * ausreichenden Kontrast auf dunklem Untergrund. */
    div[data-testid="stButton"] > button[aria-label="Bereits Konto - Anmelden"] {
        background: transparent !important;
        color: #FFFFFF !important;
        border-color: rgba(255,255,255,0.55) !important;
        font-weight: 600 !important;
    }
    div[data-testid="stButton"] > button[aria-label="Bereits Konto - Anmelden"]:hover {
        background: rgba(255,255,255,0.10) !important;
        border-color: #FFFFFF !important;
        color: #FFFFFF !important;
    }
    </style>
    """

    # Farb-Konstanten ersetzen (statt f-string, weil das gesamte CSS dann
    # frei von { und } im Bereich von Format-Spezifiern bleibt).
    css = (css                              # Louis: jetzt die Platzhalter im CSS-Text durch die echten Farbwerte ersetzen
        .replace("__PRIMAER__",        PRIMAER)   # Louis: .replace("Suchen", "Ersetzen") - tauscht jedes "__PRIMAER__" gegen die echte Farbe. So sind alle Farben zentral oben definiert
        .replace("__PRIMAER_HELL__",   PRIMAER_HELL)
        .replace("__PRIMAER_DUNKEL__", PRIMAER_DUNKEL)
        .replace("__HG_HELL__",        HG_HELLGRUEN)
        .replace("__HG_WARM__",        HG_WARMWEISS)
        .replace("__HEADLINE__",       HEADLINE_FARBE)
        .replace("__CTA__",            CTA_FARBE)
        .replace("__TEXTGRAU__",       TEXT_GRAU)
        .replace("__AKZENT_HELL__",    AKZENT_HELL)
    )

    st.markdown(css, unsafe_allow_html=True)  # Louis: WICHTIGSTE Design-Zeile! Spielt das ganze Stylesheet in die Seite ein. unsafe_allow_html=True = "behandle den Text als echtes HTML/CSS, nicht als Buchstaben". Ohne diese Zeile wäre alles ungestylt


def logo_als_data_uri() -> str:
    """Lest das Logo als Base64-Data-URI ein (für Inline-Einbettung)."""
    if not os.path.exists(LOGO_PFAD):
        return ""
    with open(LOGO_PFAD, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("ascii")


# ============================================================
# 3) PERSISTENZ
# ============================================================
#wichtige Info am Anfang: Was ist die JSON Datei? Eine Textdatei zum speichern von Daten. 
#Später, wenn Nela eine richtige App wäre, würde man eine gescheite Datenbank hernehmen. 
#Kann man vergleichen mit einer Excel Tabelle

# was bedeutet def allgemein? 
    # Ich mache jetzt eine Funktion mit dem Namen, merk dir das, die wird noch gebraucht 
#true and false: läuft alles im Hintergrund, sind sozusagen interne Signale 

def _nutzer_db_laden() -> dict:
    # JSON Datei wird geöffnet 
    # alle gespeicherten Nutzer werden als Art Wörterbuch angezeigt
    """Lest die JSON-Nutzerdatenbank vom Dateisystem.

    Migriert dabei einmalig alte Pflegegrad-Einträge: vor dem Umbau auf
    NBA-Gewichtung wurden Punkte als `int` 0-21 gespeichert. Solche Profile
    werden zurückgesetzt, damit alte Werte nicht fälschlich als „5.0 / 100"
    erscheinen — der Nutzer muss den Rechner einmal neu durchlaufen.
    """
    if not os.path.exists(NUTZER_DB_PFAD):
     #Falls die Datei noch nicht existiert, dann gib eine leere Nutzerliste bitte an     
     return {"users": {}}
    #Die leere Klammer ist die leere Nutzerliste 
    try:
        with open(NUTZER_DB_PFAD, "r", encoding="utf-8") as f:
            db = json.load(f)
    except (json.JSONDecodeError, OSError):
        st.error("Nutzerdatenbank ist beschädigt; arbeite mit leerer DB.")
        return {"users": {}}
 #Grundprinzip von try/except 
 #"Versuch das hier und falls da was schiefgeht, mach das
 #Versuch die JSON-Datei zu öffen und zu lesen 
 #"r" = read 
 #encoding="utf-8" = Damit Umlaute gecheckt werden 
 #json.load f = damit der Text in ein Python Objekt umgewandelt wird 
 #except...= Falls beim Lesen ein Fehler passiert, zeig eine Fehlermeldung -> Datenbank gilt als leer 
     #1. Fehler: Datei ist da, Inhalt aber ungültig 
     #2. Fehler: Man hat zb keine Leserechte 
 #try/except ist richtig wichtig, mit dem Code läuft die App einfach weiter, nur ohne Datenbank 
 #Das bedeutet, wenn ein Nutzer registriert ist, muss er sich für den Moment nochmal registrieren, weil alles weg ist 
   
    if _pflegegrad_altprofile_migrieren(db):
     # Ruft Datenbank auf: Hat der Nutzer alte Pflegegrad-Daten irgendwie falsch? 
      #If bedeutet, mach nur weiter wenn es Änderungen gab, ansonsten überspring den Teil 
        try:
            _nutzer_db_speichern(db)
     #try: versuch die korrigierte Datenbank jetzt zu speichern 
     #sehr wichtig, sonst wär beim nächsten Start wieder alles weg 
        except OSError as fehler:
            print(f"Profil-Migration konnte nicht persistiert werden: {fehler}")
 #except: Falls das Speichern nicht klappt, gib eine Meldung in der Konsole aus - und einfach weiter 
 #OSError = Fehler der auftritt (keine Schreibrechte)
 #as fehler = genauer Fehlertext 
 #fehler = speichern, damit man ihn in der Meldung anzeigen kann. 
     #man versteht gleich, was falsch gelaufen ist 
 
# Allgemein für "if_pflegegrad...": Prüf ob alte Profile aktualisert werden müssen 
    #wenn ja, dann speicher die korrigierte Datenbank 
    #wenn Speichern nicht klappt, lass es 

    # NEU: Migration der Einwilligungs-Felder für Bestandsnutzer    
    if _einwilligungen_migrieren(db):
     #Fehlen bei dem User die Datenschutz- und AGB Felder? 
        try:
            _nutzer_db_speichern(db)
        except OSError as fehler:
            print(f"Einwilligungs-Migration konnte nicht persistiert werden: {fehler}")
    #System gleich wie im Block davor
    #Versuch zu speichern, wenn nicht dann zeig die Meldung in der Konsole 
    return db
#"return db" Abschluss der Funktion "def _nutzer_db_laden"
#alle Prüfungen und Korrekturen sind fertig, die Datenbank kann zurückgegeben werden
    #damit die App weiterlaufen kann

def _pflegegrad_altprofile_migrieren(db: dict) -> bool:
    #Bool = True or False 
    #Funktion bekommt die Datenbank
    """Setzt alte Pflegegrad-Felder (int-Punkte vor NBA-Umstellung) zurück.

    Rückgabe: True wenn mindestens ein Profil migriert wurde.
    """
    geaendert = False
    #=ein Merker 
    #startet auf false und wird zu true wenn etwas korrigiert wurde 
    for nutzer in db.get("users", {}).values():
    #geht einzelne Nutzer in der DB durch 
    #"get("users",())= Hol mir die Liste und wenn nicht nimm ne leere 
        #Art Sicherheit, damit das System nicht so schnell abstürzt 
        pkt = nutzer.get("pflegegrad_punkte")
    #Schaut die gespeicherten Daten zum Pflgegegrad an und speichert sie schnell zwischen 
        if pkt is not None and not isinstance(pkt, float):
     #Eigentliche Prüfung 
     #"pkt is not None" = Es gibt einen gespeicherten Wert
     #"not isinstance(pkt, float): aber der Wert ist keine Kommazahl 
     # durch "and" wird gezeigt, dass beide wahr sein müssen 
     #Ganzzahl ist kein float        
            nutzer["pflegegrad"]        = None
            nutzer["pflegegrad_punkte"] = None
            nutzer["pflegegrad_datum"]  = None
            geaendert = True
    #Alle drei Pflegegrad-Felder werden auf leer gesetzt (None=Leer)
    #"geändert=true" macht man, damit die App weiß, dass die Datenbank neu gespeichert werden muss 
    return geaendert
#gleiches Prinzip wie bei der Pflegegrad-Migration 

def _einwilligungen_migrieren(db: dict) -> bool:
    """Ergänzt fehlende Einwilligungs-Felder bei Bestandsnutzern.

    Bestandsnutzer haben bei der Registrierung bereits zugestimmt, daher
    werden die Felder auf True gesetzt. Rückgabe: True wenn geändert.
    """
    geaendert = False
    #siehe oben, es startet bei false und wird dann auf true gesetzt
    for nutzer in db.get("users", {}).values():
    #jeder einzelne Nutzer wird einzeln durchgegangen 
        if "einwilligung_datenschutz" not in nutzer:
            nutzer["einwilligung_datenschutz"] = True
            geaendert = True
    #"einwilligung_datenschutz": schaut, ob es beim aktuellen Nutzer überhaupt existiert 
    # fehlt es wird es auf true gesetzt 
        #er hat damals zugestimmt, nur das Feld gab es noch nicht
        #Merker wird wieder gesetzt
        if "einwilligung_agb" not in nutzer:
            nutzer["einwilligung_agb"] = True
            geaendert = True
    #Wieder das Gleiche, nur für AGB 
    #Beide Felder werden seperat geprüft
        #"einwilligung_datenschutz"= Hat der Nutzer zugestimmt? 
        #"einwilligung_agb" = Hat der Nutzer den AGB zugestimmt?
    return geaendert
    #Gibt den Merker zurück
    #true wenn ein feld ergänzt wurde, false, wenn bei allen nutzern schon alles vorhanden ist 

#Allgemein: Die Funktion speichert die Nutzerdatenbank erst in einer Hilfsdatei
    #Damit bei einem Absturz nichts verloren geht
def _nutzer_db_speichern(daten: dict) -> None:
    #Die Funktion bekommt die Datenbank, gibt aber nichts zurück (None)
    """Speichert die Nutzerdatenbank atomar als JSON."""
    temp = NUTZER_DB_PFAD + ".tmp"
    #Erstellt einen temporären Dateinamen. Dann wird quasi in die Hilfsdatei geschrieben und nicht in die Echte 
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=2)
    #öffnet die Hilfsdatei 
    #"w" = write -> schreibt die Datenbank in die Hilfsdatei 
    #encoding="utf-8" = Umlaute werden richtig gespeichert 
    #ensure_ascii=False= 2. Umlautschutz, aber speziell für jason.dump
        #Python würde das "ä" in eine ganz komischen Code umwandeln
        #deshalb geben wir gleich an, dass es so gespeichert werden soll 
    #indent=2 = extra für die JSON Datei, damit alles lesbar formatiert wird 
    os.replace(temp, NUTZER_DB_PFAD)
    #Hilfsdatei wird in die echte umbenannt 
    #Warum verwenden wir eine Hilfsdatei?
    #Entweder ist die alte Datei noch da oder die fertige, aber nie eine halbfertige Datei 

#Allgemein: Die Funktion nimmt ein Passwort und verwandelt es in einem unlesbaren Code. 
    #Dieser Code wird in einer Datenbank gespeichert 
    #Das echte Passwort wird niemals gespeichert 
def passwort_hashen(passwort: str) -> str:
    """SHA-256-Hash eines Passworts."""
    #Funktion bekommt ein Passwort als Text und gibt danach den Text auch wieder 
    #deswegen string zu string 
    #nur kommt am Ende eben dieser unlesbare Code zurück 
    return hashlib.sha256(passwort.encode("utf-8")).hexdigest()
    #Dieser Return ist bisschen kompliziert finde ich deshalb wird er genau aufgeteilt 
    #passwort.encode("utf-8) = wandelt Text in Bytes um 
        #Computer rechnet innen drin mit Bytes und nicht mit Buchstaben 
    #hashlib.sha256(...) Mathematisches Verfahren (Algorithmus)
        # Macht aus einem beliebigen Text immer einen 64-Zeilen langen Code 
   #hexdigest() = wandelt das Ergebnis in lesbaren Text um (Zahlen und Buchstaben von a bis f)
       #der Text kann dann in der Datenbank gespeichert werden 

#Die Funktion schaut sich das eingegebene Passwort an und bewertet es, wie sicher es ist. 
#Dazu gehört auch, dass die Passwortstärke in einem Balken unter dem Passwortfeld angezeigt wird 
def _passwort_staerke_bewerten(passwort: str) -> dict:
#Die Funktion gekommt ein eingetipptes Passwort übergeben
#Gibt am Ende ein "dict" zurück, also ein Wörterbuch mit mehreren Infos auf einmal 
    """Bewertet die Passwortstärke nach 5 Kriterien (Score 0–5).

    Kriterien:
      - mind. 8 Zeichen
      - mind. 12 Zeichen (Bonus)
      - mind. 1 Kleinbuchstabe + 1 Großbuchstabe
      - mind. 1 Ziffer
      - mind. 1 Sonderzeichen

    Rückgabe: dict mit score, label, farbe, fehlende_kriterien
    """
    if not passwort:
        return {
            "score": 0, "label": "", "farbe": "#E0E0E0",
            "fehlende_kriterien": [],
        }
# zum If: Sonderfall 
#Eingabefeld ist noch leer, dann wird sofort abgebrochen 
#kein Balken anzeigen, bzw keinen Score berechnen 
    score = 0
    fehlend = []
#2 "Starter Werte"
#Score = der Punktezähler startet bei 0 
#fehlend = eine leere Liste, die später mit Anmerkungen gefühllt wird was noch fehlt 

    if len(passwort) >= 8:
        score += 1
    else:
        fehlend.append("mind. 8 Zeichen")
    #Erste Prüfung 
    #Hat das Passwort mindestens 8 Zeichen? 
    #len() zählt die Zeichen 
    #Falls ja, dann score + 1, falls nein, dann kommt der Tipp zur Liste 
    
    if len(passwort) >= 12:
        score += 1
    #Zweite Prüfung 
    #Hat das Passwort üner 12 Zeichen? 
    #Dann gibt es einen Bonuspunkt, deswegen score+1
    #else gibts hier nicht, da es ja nur ein Bonus ist, hat es unter 12 Zeichen, passiert nichts 
    
    if re.search(r"[a-z]", passwort) and re.search(r"[A-Z]", passwort):
        score += 1
    else:
        fehlend.append("Groß- und Kleinbuchstaben")
    #Dritte Prüfung 
    #Hat das Passwort eine Groß-und Kleinschreibung? 
    #re.search sucht nach den Buchstaben 
    #"and" heißt beides muss da sein 
    #wenn da, dann score + 1
    #else: wenn nicht wird ein Tipp gegeben 
    
    if re.search(r"\d", passwort):
        score += 1
    else:
        fehlend.append("mind. eine Zahl")
    #Vierte Prüfung 
    #Hat das Passwort eine Zahl?
    #\d steht für beliebige Ziffer (0-9)
    #wenn da, dann score + 1
    #else: wenn nicht wird ein Tipp gegeben
    
    if re.search(r"[^A-Za-z0-9]", passwort):
        score += 1
    else:
        fehlend.append("mind. ein Sonderzeichen")
    #Fünfte Prüfung 
    #Hat das Passwort ein Sonderzeichen? 
    #[^A-Za-z0-9] = kein Buchstabe und keine Zahl
    #wenn da, dann score + 1
    #wenn nicht, dann wird wieder ein Tipp gegeben 

    labels = {
        0: "Sehr schwach", 1: "Schwach", 2: "Ausreichend",
        3: "Gut", 4: "Stark", 5: "Sehr stark",
    }
    #Art Wörterbuch, dass jedem Score einen Text zuordnet
   
    # Farb-Stufung: rot → orange → gelb → hellgrün → grün
    farben = {
        0: "#D32F2F", 1: "#D32F2F", 2: "#F57C00",
        3: "#FBC02D", 4: "#7CB342", 5: "#2E7D32",
    }
    return {
        "score": score,
        "label": labels[score],
        "farbe": farben[score],
        "fehlende_kriterien": fehlend,
    }
    # Am Ende wird alles zusammen zurückgegeben 
    #Der Punktestand, der passende Text, die passende Farbe und die Tipps 
    #Die nächste Funktion nimmt Ergebnis

#Allgemein: Die Funktion nimmt das Ergebnis von vorher und baut daraus den Balken 
def _passwort_staerke_indikator_html(bewertung: dict) -> str:
    #Die Funktion bekommt das dict von der vorherigen Funktion 
    #Am Ende gibt es am Ende einen fertigen HTML-Code (str)
    #Was sit HTML Code: Grundlegende Programmiersprache, mit der Webseiten im Internet strukturiert und aufgebaut werden
    #der return von oben (diese 4 Einträge) sind das dict 
    """Rendert den visuellen Stärke-Indikator als HTML."""
    score = bewertung["score"]
    farbe = bewertung["farbe"]
    label = bewertung["label"]
    fehlend = bewertung["fehlende_kriterien"]
    #die vier Werte von oben werden in eigene Variablen eingepackt 
    #damit man sie später einfach nutzen kann, ohne jedes mal "bewertung [score] schreiben zu müssen 
    
    if not label:
        return ""
    #Falls kein Label vorhanden ist (=Eingabefeld noch leer), dann sofort abbrechen
    #nichts zurückgeben -> kein leerer Balken anzeigen 

    # Balken-Segmente (5 Stück)
    segmente = ""
    for i in range(5):
        gefuellt = i < score
        bg = farbe if gefuellt else "#E5E9E4"
        segmente += (
            f'<div style="flex:1; height:6px; background:{bg}; '
            'border-radius:3px; transition:background 0.2s ease;"></div>'
        )
 #Hier wird gebaut, eines nach dem anderen in einer Schleife 
 #range (5) = zählt von 0 bis 4, also genau 5 Durchläufe 
 #gefuellt = i < score -> ist dieses Segment farbig? 
 #Beispiel: Score 3: Segmente 0,1,2 sind farbig, 3 und 4 sind grau 
 #bg = farbe if gefuellt else "#E5E9E4" = farbig oder grau, je nachdem ob gefüllt 
 #segmente += jedes neue Segment wird an den bisherigen Text angehängt 
 #Das grüne ist der HTML Code
     #Ein div ist wie eine unsichtbare Box. Mit style= gibt man ihr ein Aussehen.
    
    tipps_html = ""
    if fehlend:
        tipps_text = html.escape(", ".join(fehlend))
        tipps_html = (
            f'<div style="font-size:11px; color:{TEXT_GRAU}; '
            f'margin-top:6px; line-height:1.4;">'
            f'Empfohlen: {tipps_text}</div>'
        )
        #Falls es noch fehlende Kriterien gibt, wird ein Tipp-Text gebaut 
        #", ".join(fehlend) = verbindet alle Tipps mit Komma 
        #html.escape() = Sicherheitsmaßnahme damit kein schädlicher Code eingeschleust werden kann 
        #Falls fehlend leer ist → kein Tipp anzeigen, tipps_html bleibt leer
        #Das Grüne ist wieder der HTML Code 
        
    return (
        '<div style="margin:8px 0 6px 0;">'
        '<div style="display:flex; gap:4px; margin-bottom:6px;">'
        f'{segmente}'
        '</div>'
        f'<div style="font-size:12px; font-weight:600; '
        f'color:{farbe};">Passwortstärke: {html.escape(label)}</div>'
        f'{tipps_html}'
        '</div>'
    )
     #Alles wird in einem fertigen HTML-Baustein zusammengesetzt und zurückgegeben 
         #Äußerer div → Abstand nach oben und unten
         #Innerer div mit display:flex → die 5 Segmente nebeneinander
         #f'{segmente}' → die 5 Balken die vorhin gebaut wurden
         #Passwortstärke: {label} → z.B. "Passwortstärke: Gut" in der passenden Farbe
         #{tipps_html} → die Tipps darunter, falls vorhanden

#Allgemein: Die Funktion legt einen neuen Nutzer in der Datenbank an.
#Also was passiert alles, wenn man auf "Konto erstellen" klickt?
def nutzer_anlegen(vorname: str, nachname: str, email: str,
                    passwort: str) -> bool:
    #Die Funktion bekommt vier Angaben 
    #die Funktion bekommt true oder false (wegen bool) je nachdem ob das Anlegen geklappt hat 
    """Legt einen neuen Nutzer an. False falls E-Mail bereits vergeben."""
    db = _nutzer_db_laden()
    #Zuerst wird die Datenbank geladen, damit wir wissen, wer schon alles registriert ist 
    email = email.lower()
    #die email wird in Kleinbuchstaben umgewandelt 
    #damit nina.kressierer@... das Gleiche ist wie Nina.kressierer@...
    if email in db["users"]:
        return False
    #prüft, ob die Email schon in der Datenbank registriert ist 
    #falls ja, dann sofort abbrechen (passiert durch false)
    #Es wird dann angezeigt: "Diese E-Mail ist bereits registriert"
    db["users"][email] = {
        #Falls die Email noch nicht vergeben ist 
        #Neuer Eintrag in der Datenbank 
        #Die Email wird als Schlüssel benutzt, damit man später schnell nachschauen kann 
        "vorname":                  vorname,
        "nachname":                 nachname,
        "email":                    email,
        #Die eingegebenen Daten werden sofort gespeichert 
        "password_hash":            passwort_hashen(passwort),
        #Passwort wird gespeichert, aber als den Code, denn wir vorhin umgewandelt haben 
        "created_at":               datetime.now().isoformat(),
        #der genaue Zeitpunkt der Registrierung wird gespeichert 
        #datetime.now() = genaue Uhrzeit 
        #.isoformat() = lesbarer Text 
        "pflegegrad":               None,
        "pflegegrad_punkte":        None,
        "pflegegrad_datum":         None,
        #Alle drei Felder starten leer 
        "genutzte_leistungen":      [],
        #Noch keine Leistungen markiert - leere Liste als Startwert 
        "einwilligung_datenschutz": True,
        "einwilligung_agb":         True,
        # Einwilligungen (Pflicht bei Registrierung; im Profil widerrufbar)
        #deshalb wird direkt auf true gesetzt 
    }
    _nutzer_db_speichern(db)
    return True
    #Der neue Nutzer wird sofort in der Datei gespeichert 
    #True wird zurückgegeben, damit das Registrierungsformular weiß, dass alles geklappt hat 
    #Nutzer wird automatisch eingelogt 

#Allgemein: Die Funktion braucht man, wenn ein Nutzer in seinem Profil den Haken bei der Datenschutzerklärung oder den AGBs entfernt oder wiedersetzt hat 
#Einwilligung ändert sich 
def nutzer_einwilligungen_aktualisieren(email: str, datenschutz: bool,
                                         agb: bool) -> None:
    #Funktion bekommmt 3 Angaben 
    #Email, zwei true/false Werte 
        # Einmal Datenschutz und einmal AGB 
    #Funktion gibt aber nichts zurück, deswegen none 
    db = _nutzer_db_laden()
    #Datenbank wird geladen 
    email = email.lower()
    #Email wieder in Kleinbuchstaben 
    if email in db["users"]:
    #prüft, ob der Nutzer überhaupt existiert 
    #falls nicht, dann einfach nichts machen
        db["users"][email]["einwilligung_datenschutz"] = bool(datenschutz)
        db["users"][email]["einwilligung_agb"]         = bool(agb)
    #Die beiden Felder werden mit neuen Werten überschrieben 
    #bool() als Sicherheitsmaßnahme (damit nichts anderes wie true/false benutzt wird)
        _nutzer_db_speichern(db)
    #Änderung wird sofort gespeichert 
    #Sonst passiert aber nichts, Nutzer kann weiterhin was in der App machen 
    #Konsequenz kommt später noch 

#Funktion speichert, welche Pflegeleistungen ein Nutzer bereits nutzt 
#Damit der Leistungscheck diese ausblendet und nur noch die ungenutzten angezeigt werden 
def nutzer_genutzte_leistungen_speichern(email: str, leistungen: list) -> None:
    #Funktion bekommt email und eine Liste von Leistungen 
    #Sie speichert nur, deswegen none 
    erlaubt = set(NELA_LEISTUNGEN_ALLE)
    #NELA_LEISTUNGEN_ALLE = Liste mit allen offizielen Leistungsnahmen die Nela kennt (zb Pflegegeld)
    #set() wandelt Liste in eine Menge  um 
      #Macht die spätere Prüfung schneller 
      #Nur was auf der Liste steht kommt rein 
    bereinigt = sorted(
        {str(x) for x in (leistungen or []) if str(x) in erlaubt}
    )
    #wichtigste Zeile 
    #leistungen or [] -> falls keine Leistungen übergeben wurden, nimm eine leere Liste
    #if str(x) in erlaubt -> nur Leistungen behalten die auf der Liste stehen — fremde oder falsche Einträge werden ignoriert
    #{...} -> geschweifte Klammern entfernen automatisch Duplikate
    #sorted() -> alphabetisch sortieren damit die Reihenfolge immer gleich ist
    db = _nutzer_db_laden()
    email = email.lower()
    #Datenbank laden und Email kleinschreiben wie immer 
    if email in db["users"]:
        db["users"][email]["genutzte_leistungen"] = bereinigt
        _nutzer_db_speichern(db)
    #Falls der Nutzer existiert, die bereinigte Liste speichern und sofort in die Datei schreiben 
    
#Die Funktion löscht einen Nutzer dauerhaft aus der Datenbank     
def nutzer_loeschen(email: str) -> bool:
    #Die Funktion sucht die Email des zu löschenden Nutzers bzw gibt sie wieder 
    #True/Flase, je nachdem ob überhaupt jemand gefunden wurde 
    email = email.lower()
    db = _nutzer_db_laden()
    #Email und Datenbank wie immer 
    if email not in db["users"]:
        return False
    #Prüft ob Nutzer existiert 
    #not in = "nicht vorhanden" 
    # sofort abbrechen und false zurückgeben 
    del db["users"][email]
    #del = delete 
    #löscht den KOMPLETTEN Nutzereintrag 
    _nutzer_db_speichern(db)
    return True
    # Veränderte Datenbank wird gespeichert 
    #true = damit App weiß, dass ds Löschen gklappt hat 

#Allgemein: Funktion prüft, ob beim Login Email und Passwort richtig sind 
#Timing-sicher 
def anmeldung_pruefen(email: str, passwort: str):
    #Funktion bekommt Email und Passwort 
    #Entweder bekommt man komplettes Nutzerprofil oder None wenn was falsch ist 
    db = _nutzer_db_laden()
    email = email.lower()
    #Datenbank und Email wie immmer 
    if email not in db["users"]:
        return None
    #Prüft ob Email registriert ist 
    #Falls nicht, dann none 
    #Anzeige: Email oder Passwort falsch 
    nutzer = db["users"][email]
    #Nutzereintrag wird in eine eigene Variable gespeichert 
    if hmac.compare_digest(nutzer["password_hash"], passwort_hashen(passwort)):
        return nutzer
    return None
    #hier ist die wahre Passwort-Prüfung 
    #passwort_hashen(passwort) -> das eingetippte Passwort wird gehash, wie oben 
    #hmac.compare_digest(...) -> vergleicht den gespeicherten Hash mit dem neuen Hash
    #Falls beide gleich sind, dann ist das Passwort richtig 
    #Falls nicht, dann none 
#Besonderheit hier für Hacker 
    #hmac.compare_digest = Macht den Abgleich gleich lang 
    #Sonst dauert der Abgleich mit einer registrierten Email länger (das ist wichtig gegen Hacker)

#Holt Profil eines Nutzers aus der Datenbank 
def nutzer_holen(email: str):
    #Funktion bekommt Email
    #Funktion gibt dann das dazugehörige Nutzerprofil zurück 
    #Oder none falls nicht gefunden 
    db = _nutzer_db_laden()
    #Datenbank
    return db["users"].get(email.lower())
    #email.lower() = Kleinschreibung 
    #get() Nutzerprofil aus dem Wörterbuch holen 
    #falls email nicht existiert, dann gibt get () einfach none zurück statt abzustürzen 

#Funktion speichert das Ergebnis des Pflegegrad-Rechners im Nutzerprofil
def pflegegrad_im_profil_speichern(email: str, ergebnis_text: str,
                                    punkte: float) -> None:
    #Funktion bekommt drei Angaben 
        #Email 
        #Ergebnis_Text (welcher Pflegegrad)
        #punkte, float, da Kommazahl 
    #none, da sie nur speichert 
    db = _nutzer_db_laden()
    email = email.lower()
    #Datenbank und email wie immer 
    if email in db["users"]:
    #Sicherheit, nur speichern wenn es Nutzer auch wirklich gibt 
        db["users"][email]["pflegegrad"]        = ergebnis_text
        db["users"][email]["pflegegrad_punkte"] = punkte
        db["users"][email]["pflegegrad_datum"]  = datetime.now().isoformat()
     #alle drei Felder werden gleichzeitig aktualisiert 
     #Pflegegrad, Punkte und Datum, also wann der Rechner durchgeführt wurde 
        _nutzer_db_speichern(db)
        #Speichern wie immer 
    #Diese Funktion gilt dann quasi als Bindeglied zwischen Rechner und Datenbank

    #Ende Nina Teil 1 
# ============================================================
# 4) HILFSFUNKTIONEN
# ============================================================

# --- Leistungscheck: NBA-Berechnung (0-100, M2/M3-Max, Q5 invertiert) ---

def lc_aus_punkten(gesamtpunkte: float) -> str:
    """Erste Einschätzung des Pflegegrads aus NBA-gewichteten Punkten (0-100).

    Schwellen nach SGB XI § 15 Abs. 3 — untere Grenze inklusiv, obere exklusiv,
    ausser PG5 (90-100, beidseitig inklusiv). Werte ausserhalb liefern einen
    defensiven Fallback-Text, niemals None.
    """
    p = float(gesamtpunkte)
    if p < 12.5:
        return "Erste Einschätzung: Kein Pflegegrad"
    if p < 27.0:
        return "Erste Einschätzung: Pflegegrad 1"
    if p < 47.5:
        return "Erste Einschätzung: Pflegegrad 2"
    if p < 70.0:
        return "Erste Einschätzung: Pflegegrad 3"
    if p < 90.0:
        return "Erste Einschätzung: Pflegegrad 4"
    if p <= 100.0:
        return "Erste Einschätzung: Pflegegrad 5"
    return "Erste Einschätzung: Nicht klassifizierbar"


def lc_punkte_berechnen(antworten: dict) -> float:
    """Berechnet die gewichtete Gesamtpunktzahl (0-100) nach NBA-Logik.

    Pro Frage: `(rohwert / 3) * gewicht`. Die Frage `verhalten_unruhe` wird
    invertiert (`roh = 3 - roh`). Aus den Modulen M2/M3 zählt nur das
    Maximum, nicht die Summe. Rückgabe auf eine Nachkommastelle gerundet.

    Nicht beantwortete Fragen (Schlüssel fehlt im Dict) liefern Beitrag 0 —
    auch für invertierte Fragen. So entsteht aus leerem Dict 0.0 (statt 15.0
    durch versehentliche Default-Inversion).
    """
    gewichtet: dict = {}
    for fid, gewicht in LC_GEWICHTE.items():
        if fid not in antworten:
            gewichtet[fid] = 0.0
            continue
        roh = int(antworten[fid])
        if fid in LC_INVERTIERT:
            roh = 3 - roh
        gewichtet[fid] = (roh / 3) * gewicht
    m23 = max(gewichtet[k] for k in LC_M23)
    gesamt = (gewichtet["sv_waschen"] + gewichtet["sv_mahlzeiten"]
              + gewichtet["mob_treppen"] + m23
              + gewichtet["krank_medikamente"] + gewichtet["soz_kontakte"])
    return round(gesamt, 1)


# --- Detail-Rechner (16 Fragen): Pflegegrad-Berechnung nach NBA-Logik ---
#
# Eingabe: das pg_answers-Dict aus dem Session-State. Werte sind die
# String-Tokens aus den PG_OPTIONEN_*-Listen ("voll"/"meist"/"hilfe"/
# "nein" für die 14 ordinalen Fragen, "ja"/"nein" für F15/F16).
# Rückgabe: Ergebnis-Dict mit pg/punkte/reason/module.

def calc_pflegegrad(answers: dict) -> dict:  # Louis: HERZSTÜCK. Kriegt alle Antworten ("answers") rein, gibt das Ergebnis als dict raus (pg/punkte/...)
    """Berechnet Pflegegrad-Schätzung nach NBA-Logik (vereinfacht für MVP).

    Respektiert: Modul-Gewichtungen, max(M2,M3)-Regel, strikte
    <-Schwellen, PG5-Override (§15 IV), 6-Monats-Eligibility (§14 I).
    """
    # === STEP 1: Eligibility (§14 I SGB XI) ===
    if answers.get("F16") == "nein":  # Frage 16 = "dauert die Pflege mind. 6 Monate?" -> wenn NEIN gibt's per Gesetz GAR keinen Pflegegrad
        return {                       # dann sofort raus (return = Funktion hier beenden), pg = None (= "nicht feststellbar")
            "pg":     None,
            "punkte": 0,
            "reason": "Pflegebedürftigkeit muss laut §14 I SGB XI mind. "
                      "6 Monate andauern.",
            "module": {},
        }

    # === STEP 2: PG-5-Override (§15 IV, BSG B 3 P 1/22 R) ===
    if answers.get("F15") == "ja":  # Frage 15 = krasser Spezialfall (kann nichts mehr greifen/stehen/gehen) -> direkt PG5, OHNE zu rechnen (Abkürzung lt. Gesetz)
        return {
            "pg":     5,             # höchster Pflegegrad sofort, 100 Punkte gesetzt
            "punkte": 100,
            "reason": "Besondere Bedarfskonstellation (§15 IV SGB XI): "
                      "vollständiger Verlust von Greif-, Steh- und "
                      "Gehfunktionen.",
            "module": {"override": True},  # "override" = Marker, dass hier abgekürzt wurde (Ergebnis-Screen zeigt das anders an)
        }

    # === STEP 3: Mapping ===
    # Im pg_answers landen die Wert-Tokens ("voll"/"meist"/"hilfe"/"nein"),
    # nicht die Labels. Alle ordinalen Fragen (F1-F14) nutzen daher dieselbe
    # Skala — die Sonder-Maps der Spec (F4_MAP/F10_MAP/F11_MAP/F12_MAP) sind
    # damit überflüssig.
    SKALA = {"voll": 0.0, "meist": 0.33, "hilfe": 0.67, "nein": 1.0}  # übersetzt die Antwort-Codes in Zahlen. 0.0 = selbstständig, 1.0 = gar nicht -> je höher, desto mehr Pflegebedarf

    # === STEP 4: Modul-Scores (gewichtete Punkte, diskrete NBA-Werte) ===

    # MODUL 1 — Mobilität (10%, max 10 Pkte)
    m1_map = {0.0: 0, 0.33: 2.5, 0.67: 5, 1.0: 10}  # Punkte-Tabelle für Modul 1. Die 10 = Maximalpunkte (Modul zählt 10%). "map" = Zuordnung Wert->Punkte
    m1 = m1_map[SKALA[answers["F1"]]]                # von innen lesen: Antwort F1 -> SKALA-Zahl -> in m1_map nachschlagen = Punkte für Modul 1

    # MODUL 2 — Kognition (15%, gemeinsam mit M3)
    m2_avg = (SKALA[answers["F2"]] + SKALA[answers["F3"]]) / 2  # hier 2 Fragen -> Durchschnitt bilden (avg = average)
    if   m2_avg < 0.15: m2 = 0       # Durchschnitt in Punkte umrechnen über Schwellen. Wenig Einschränkung = wenig Punkte
    elif m2_avg < 0.4:  m2 = 3.75
    elif m2_avg < 0.6:  m2 = 7.5
    elif m2_avg < 0.85: m2 = 11.25
    else:               m2 = 15      # max 15 Punkte (Modul zählt 15%)

    # MODUL 3 — Verhalten (15%, gemeinsam mit M2)
    m3_map = {0.0: 0, 0.33: 3.75, 0.67: 7.5, 1.0: 15}  # gleiche Idee wie m1_map, nur max 15 Punkte
    m3 = m3_map[SKALA[answers["F4"]]]

    # MODUL 2/3: nur höherer Wert zählt (§15 III SGB XI)
    m2_m3 = max(m2, m3)  # WICHTIG (Gesetz): von Modul 2 und 3 zählt nur der GRÖSSERE Wert, nicht beide. max() = das Größere von beidem

    # MODUL 4 — Selbstversorgung (40%, max 40 Pkte) — Pitch-relevant!
    m4_avg = (SKALA[answers["F5"]] + SKALA[answers["F6"]]   # Modul 4 hat 6 Fragen (F5-F10) -> alle addieren und /6 = Durchschnitt
              + SKALA[answers["F7"]] + SKALA[answers["F8"]]
              + SKALA[answers["F9"]] + SKALA[answers["F10"]]) / 6
    if   m4_avg < 0.1:  m4 = 0
    elif m4_avg < 0.3:  m4 = 10
    elif m4_avg < 0.55: m4 = 20
    elif m4_avg < 0.8:  m4 = 30
    else:               m4 = 40      # wichtigstes Modul, max 40 Punkte (40% Gewicht!)

    # MODUL 5 — Krankheits-/Therapieanforderungen (20%, max 20 Pkte)
    m5_avg = (SKALA[answers["F11"]] + SKALA[answers["F12"]]) / 2  # 2 Fragen -> Durchschnitt
    if   m5_avg < 0.15: m5 = 0
    elif m5_avg < 0.4:  m5 = 5
    elif m5_avg < 0.6:  m5 = 10
    elif m5_avg < 0.85: m5 = 15
    else:               m5 = 20      # max 20 Punkte (20% Gewicht)

    # MODUL 6 — Alltagsgestaltung/soziale Kontakte (15%, max 15 Pkte)
    m6_avg = (SKALA[answers["F13"]] + SKALA[answers["F14"]]) / 2  # 2 Fragen -> Durchschnitt
    if   m6_avg < 0.15: m6 = 0
    elif m6_avg < 0.4:  m6 = 3.75
    elif m6_avg < 0.6:  m6 = 7.5
    elif m6_avg < 0.85: m6 = 11.25
    else:               m6 = 15      # max 15 Punkte (15% Gewicht). Summe aller Module-Maxima = 10+15+40+20+15 = 100

    # === STEP 5: Summe ===
    total = m1 + m2_m3 + m4 + m5 + m6  # alle Modul-Punkte zusammenzählen = Gesamtpunktzahl (0 bis 100)

    # === STEP 6: Schwellen STRIKT < (nicht <=!) §15 III SGB XI ===
    if   total < 12.5: pg = 0   # kein PG   # aus den Gesamtpunkten wird der Pflegegrad. Mehr Punkte = höherer Grad
    elif total < 27:   pg = 1               # das sind die offiziellen NBA-Grenzwerte (z.B. ab 27 Punkten -> PG2)
    elif total < 47.5: pg = 2
    elif total < 70:   pg = 3
    elif total < 90:   pg = 4
    else:              pg = 5               # 90+ Punkte -> PG5

    return {                                # Ergebnis als dict zurückgeben - dieses dict nutzt nachher der Ergebnis-Screen
        "pg":     pg,                       # der ermittelte Pflegegrad (0-5)
        "punkte": round(total, 2),          # round(...,2) = auf 2 Nachkommastellen runden
        "reason": f"Gewichtete Gesamtpunkte: {round(total, 2)} von 100",
        "module": {                         # Einzelpunkte pro Modul - damit der "Wie kommt das zustande?"-Aufklapp-Bereich die Aufschlüsselung zeigen kann
            "M1_Mobilitaet":       m1,
            "M2_Kognition":        m2,
            "M3_Verhalten":        m3,
            "M2_M3_gewertet":      m2_m3,
            "M4_Selbstversorgung": m4,
            "M5_Krankheit":        m5,
            "M6_Alltag":           m6,
        },
    }


def session_init() -> None:  # richtet beim ALLERERSTEN Start das "Gedächtnis" (session_state) ein - mit Startwerten
    """Initialisiert Session-State-Variablen mit Defaults."""
    defaults = {                            # Vorlage: ALLE Dinge, die die App sich merken muss, jeweils mit Startwert
        "anmeldung_eingeloggt":     False,  # am Anfang ist niemand eingeloggt
        "anmeldung_email":          "",
        "aktuelle_seite":           "landing",  # App startet auf der Landing-Page
        # 16-Fragen-Detail-Rechner (App-Bereich)
        "pg_page":                  1,   # auf welcher Seite des Rechners man gerade ist (startet bei 1)
        "pg_answers":               {},  # hier landen alle gegebenen Antworten (leer = noch nichts beantwortet)
        # 7-Fragen-Leistungscheck (Landing + Conversion-Quiz)
        "lc_seite_index":           0,
        "lc_antworten":             {},
        "lc_abgeschlossen":         False,
        "lc_letzter_klick_idx":     -1,
        "lc_ergebnis_text":         "",
        "lc_ergebnis_punkte":       0.0,
        "lc_im_profil_gespeichert": False,
        "auth_modus":               None,
        # Sicherheits-/Datenschutz-Bestätigungen (zweistufig)
        "logout_bestaetigen":       False,
        "account_loeschen_bestaetigen": False,
        # 2-Schritt-Logout direkt vom Dashboard (US2 zentral sichtbar)
        "dash_logout_bestaetigen":  False,
        # Detail-Rechner-Ergebnis nur einmal pro Lauf ins Profil schreiben
        "pg_detail_im_profil_gespeichert": False,
    }
    for k, v in defaults.items():        # jeden Eintrag der Vorlage durchgehen. k = Name, v = Startwert
        if k not in st.session_state:    # NUR setzen, wenn's die Variable noch NICHT gibt (= nur beim 1. Mal)...
            st.session_state[k] = v      # ...sonst würde Streamlit bei jedem Klick alles zurücksetzen (z.B. ständig ausloggen)


def _app_zurueck_dashboard_button() -> None:
    """Rendert einen "Zurück zum Dashboard"-Button am Anfang einer
    App-Sub-Seite (US: aus jeder Seite jederzeit zurück zum Dashboard).

    Setzt zusätzlich alle Bestätigungs-States zurück, damit sich keine
    halbfertigen Logout/Lösch-Dialoge mitnehmen.
    """
    col_zb, _ = st.columns([1, 4])  # 2 Spalten im Verhältnis 1:4. col_zb = schmale linke. Das "_" = breite rechte, die ich NICHT brauche (nur Platzhalter, damit Button schmal links bleibt)
    with col_zb:                    # alles hierdrin kommt in die schmale linke Spalte
        if st.button("← Zurück zum Dashboard",   # if st.button(...) = wird True, SOBALD man klickt
                     key="app_zurueck_dashboard",
                     use_container_width=True):
            st.session_state["aktuelle_seite"] = "dashboard"  # beim Klick -> Seite auf "dashboard" umstellen
            st.session_state["logout_bestaetigen"]          = False  # offene Sicherheits-Dialoge zurücksetzen, damit nichts halbfertig "mitwandert"
            st.session_state["account_loeschen_bestaetigen"] = False
            st.session_state["dash_logout_bestaetigen"]     = False
            st.rerun()              # Seite sofort neu laden, damit der Seitenwechsel sichtbar wird
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)  # leerer Kasten = nur Abstand nach unten


def session_logout() -> None:  # Logout = komplettes Gedächtnis leeren und neu aufsetzen
    """Leert die Session und setzt auf Landingpage zurück."""
    for key in list(st.session_state.keys()):  # alle gemerkten Variablen durchgehen...
        del st.session_state[key]               # ...und löschen (del = delete)
    session_init()                              # danach Startwerte neu setzen -> App ist wie frisch gestartet


def pg_reset() -> None:  # setzt NUR den Pflegegrad-Rechner zurück (nicht das ganze Login)
    """Setzt den Pflegegrad-Detail-Fragebogen zurück (Seite 1, keine Antworten)."""
    st.session_state["pg_page"] = 1      # zurück auf Seite 1
    st.session_state["pg_answers"] = {}  # alle Antworten löschen (leeres dict)
    # Damit das Speichern beim nächsten Abschluss wieder ausgelöst wird
    st.session_state["pg_detail_im_profil_gespeichert"] = False  # Speicher-Sperre lösen, damit das nächste Ergebnis wieder ins Profil darf


def lc_reset() -> None:
    """Setzt den 7-Fragen-Leistungscheck zurück."""
    st.session_state["lc_seite_index"] = 0
    st.session_state["lc_antworten"] = {}
    st.session_state["lc_abgeschlossen"] = False
    st.session_state["lc_letzter_klick_idx"] = -1
    st.session_state["lc_im_profil_gespeichert"] = False


# ============================================================
# 5) PFLEGEGRAD-RECHNER (wiederverwendbar)
# ============================================================

def _pg_press_animation_unterdruecken() -> None:  # NUR Optik/Feinschliff! Schaltet das kleine "Zucken" der Buttons beim Klick ab. Falls Dozent fragt: rein kosmetisch, App geht auch ohne
    """Unterdrückt die Streamlit-Button-Press-Animation."""
    from streamlit.components.v1 import html as komp_html  # dieses Werkzeug kann (anders als st.markdown) echtes JavaScript einbetten
    komp_html(                                             # ab hier folgt JavaScript (4. "Sprache" neben Python/HTML/CSS) - musste so, weil CSS das hier nicht zuverlässig konnte
        """
        <script>
        (function() {
            const w = window.parent;
            if (w.__nelaPressFixed) return;
            w.__nelaPressFixed = true;
            const doc = w.document;
            const sel = '[data-testid="stHorizontalBlock"] div[data-testid="stButton"] > button';
            const fix = (el) => {
                el.style.setProperty('transform', 'none', 'important');
                el.style.setProperty('scale', '1', 'important');
            };
            const fixAll = () => doc.querySelectorAll(sel).forEach(fix);
            fixAll();
            new MutationObserver(fixAll).observe(doc.body, {childList:true, subtree:true});
            ['mousedown','mouseup','click','pointerdown','pointerup'].forEach(evt => {
                doc.addEventListener(evt, (e) => {
                    const btn = e.target && e.target.closest && e.target.closest(sel);
                    if (btn) fix(btn);
                }, true);
            });
        })();
        </script>
        """,
        height=0,  # height=0 = das Ganze ist unsichtbar, läuft nur im Hintergrund
    )


def _pg_frage_rendern(frage: dict) -> None:  # ZEIGT eine einzelne Frage an. Sie kriegt die Frage ÜBERGEBEN (Parameter "frage"), sucht sie nicht selbst! Die Fragen stehen oben in PG_SEITEN (ab Zeile 97)
    """Rendert eine einzelne Frage: optionaler Subheader, Fragetext, Antwort-Buttons.

    Klick auf einen Button speichert den `wert` der Option unter `frage["id"]`
    in st.session_state["pg_answers"] und löst ein Rerun aus. Ein bereits
    gewählter Button bekommt ein "✓ "-Präfix und den primary-Style.
    """
    if "subheader" in frage:  # NUR falls die Frage einen kleinen Zwischentitel hat -> anzeigen (sonst überspringen)
        st.markdown(
            '<div style="font-size:12px; font-weight:700; letter-spacing:1.5px; '
            'text-transform:uppercase; color:' + TEXT_GRAU + '; '
            'margin: 22px 0 6px 0;">'
            + html.escape(frage["subheader"]) +
            '</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        '<h3 style="font-family:Montserrat, DM Sans, sans-serif; font-size:22px; '
        'font-weight:700; color:' + HEADLINE_FARBE + '; '
        'margin: 6px 0 20px 0; line-height:1.35; letter-spacing:-0.01em;">'
        + html.escape(frage["text"]) +  # der eigentliche Fragetext, geholt aus dem Frage-Päckchen. html.escape() = Sonderzeichen entschärfen (Sicherheit)
        '</h3>',
        unsafe_allow_html=True,
    )

    aktuell = st.session_state["pg_answers"].get(frage["id"])  # wurde diese Frage schon beantwortet? .get() gibt None, falls noch nicht
    optionen = frage["optionen"]      # die Antwortmöglichkeiten dieser Frage (Liste)
    cols = st.columns(len(optionen))  # so viele Spalten wie es Antworten gibt -> Buttons stehen nebeneinander. len() = Anzahl
    for i, opt in enumerate(optionen):  # jede Antwort durchgehen. i = Nummer (0,1,2,3), opt = die Antwort selbst
        gewaehlt = aktuell == opt["wert"]  # ist DIESE Antwort die gerade gewählte? -> True/False
        beschriftung = ("✓ " if gewaehlt else "") + opt["label"]  # wenn gewählt -> Häkchen davor, sonst nur der Text
        with cols[i]:  # diesen Button in Spalte Nr. i setzen
            if st.button(
                beschriftung,
                key="pg_btn_" + frage["id"] + "_" + opt["wert"],  # JEDER Button braucht einen EINDEUTIGEN key (z.B. pg_btn_F1_voll), sonst Fehler
                type="primary" if gewaehlt else "secondary",      # gewählter Button wird farbig (primary), Rest normal (secondary)
                use_container_width=True,
            ):
                st.session_state["pg_answers"][frage["id"]] = opt["wert"]  # beim Klick -> Antwort ins Gedächtnis speichern (Frage-ID -> gewählter Wert)
                st.rerun()  # neu laden, damit Häkchen + Farbe sofort erscheinen


PG_EINORDNUNG = {  # Nachschlage-Tabelle: zu jedem Pflegegrad (0-5 und None) der passende Erklärtext fürs Ergebnis
    0:    "Nach Ihren Angaben besteht aktuell kein gesetzlicher Pflegebedarf.",
    1:    "Geringe Beeinträchtigung der Selbstständigkeit. Ihre Mutter "
          "hat Anspruch auf 131 € Entlastungsbetrag pro Monat.",
    2:    "Erhebliche Beeinträchtigung. Anspruch auf bis zu 5.111 € pro "
          "Jahr an Pflegeleistungen — laut Studien werden davon im "
          "Schnitt 60% nicht abgerufen.",
    3:    "Schwere Beeinträchtigung. Anspruch auf bis zu 8.500 € pro Jahr.",
    4:    "Schwerste Beeinträchtigung. Anspruch auf bis zu 11.000 € pro Jahr.",
    5:    "Schwerste Beeinträchtigung mit besonderen Anforderungen. "
          "Anspruch auf bis zu 13.000 € pro Jahr.",
    None: "Die Pflegebedürftigkeit muss laut §14 I SGB XI mindestens "
          "6 Monate andauern, um einen Pflegegrad zu beantragen. Wenn "
          "sich die Situation ändert, können Sie den Check erneut "
          "durchführen.",
}


def _pg_platzhalter_zeigen() -> None:
    """Apple-Style Ergebnis-Screen nach Seite 7.

    Ruft calc_pflegegrad auf und rendert das Ergebnis als zentrierte
    Karte: Progress 100 %, Kategorie-Label, Headline, Punkte, kurze
    Einordnung, Expander mit Modul-Breakdown, Disclaimer, CTA-Button
    (Leistungslücken oder Reset), Sekundär-Link zum Antworten-Prüfen.
    """
    ergebnis = calc_pflegegrad(st.session_state["pg_answers"])  # HIER wird gerechnet! Alle gespeicherten Antworten an die Rechen-Funktion geben -> Ergebnis-dict
    pg      = ergebnis["pg"]      # aus dem dict die einzelnen Werte rausholen, um sie unten anzuzeigen
    punkte  = ergebnis["punkte"]
    module  = ergebnis.get("module", {})       # die Einzelpunkte pro Modul (für den Aufklapp-Bereich)
    override = bool(module.get("override"))     # True, falls oben der PG5-Spezialfall griff (dann gab's keine normale Rechnung)

    # NEU: Ergebnis ins Profil speichern, sobald der Rechner durchgelaufen
    # ist (idempotent über Session-Flag, wird in pg_reset() zurückgesetzt).
    # Speichert nur, wenn ein gültiger Pflegegrad ermittelt wurde.
    if pg in (1, 2, 3, 4, 5) and st.session_state.get("anmeldung_eingeloggt"):  # nur speichern, wenn gültiger PG rauskam UND man eingeloggt ist
        email = st.session_state.get("anmeldung_email", "")
        if email and not st.session_state.get("pg_detail_im_profil_gespeichert"):  # und nur EINMAL pro Durchlauf (sonst doppelt speichern bei jedem Rerun)
            pflegegrad_im_profil_speichern(
                email, f"Pflegegrad {pg}", float(punkte),
            )
            st.session_state["pg_detail_im_profil_gespeichert"] = True

    # Genutzte Leistungen aus dem Profil holen (für Filter im Leistungs-Block).
    # Nur eingeloggte Nutzer; anonyme sehen die volle Liste.
    genutzte_namen = set()
    if st.session_state.get("anmeldung_eingeloggt"):
        email_n = st.session_state.get("anmeldung_email", "")
        if email_n:
            n_data = nutzer_holen(email_n)
            if n_data:
                genutzte_namen = set(n_data.get("genutzte_leistungen") or [])

    # 1. Progress bei 100 %, kein Label
    st.progress(1.0)  # Fortschrittsbalken auf 100% (Rechner ist ja fertig)

    # Inhalt in einer max-700-Spalte zentrieren
    sp_l, mid, sp_r = st.columns([1, 6, 1])  # 3 Spalten 1:6:1 -> äußere als Rand, Inhalt kommt in die breite Mitte = zentriert
    with mid:
        # 2. Kategorie-Label
        st.markdown(
            '<div style="text-align:center; font-size:12px; '
            'font-weight:700; letter-spacing:2px; text-transform:uppercase; '
            'color:' + PRIMAER + '; margin: 36px 0 12px 0;">'
            'IHR ERGEBNIS'
            '</div>',
            unsafe_allow_html=True,
        )

        # 3. Headline
        if pg in (1, 2, 3, 4, 5):  # je nach Ergebnis eine andere Überschrift wählen
            headline = f"Geschätzter Pflegegrad: {pg}"  # f"...{pg}..." = Wert von pg direkt in den Text einsetzen
        elif pg == 0:
            headline = "Kein Pflegegrad erkennbar"
        else:                       # else greift bei pg = None (der 6-Monats-Fall)
            headline = "Pflegegrad nicht feststellbar"
        st.markdown(
            '<h1 style="font-family:Montserrat, DM Sans, sans-serif; '
            'font-size:clamp(32px, 5vw, 48px); font-weight:800; '
            'color:' + HEADLINE_FARBE + '; text-align:center; '
            'margin: 0 0 14px 0; line-height:1.15; letter-spacing:-0.02em;">'
            + html.escape(headline) +
            '</h1>',
            unsafe_allow_html=True,
        )

        # 4. Punkte-Anzeige (nur wenn pg is not None)
        if pg is not None:
            st.markdown(
                '<div style="text-align:center; font-size:18px; '
                'color:' + TEXT_GRAU + '; margin: 0 0 30px 0;">'
                f'{punkte:g} von 100 möglichen Punkten'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown("<div style='height:18px'></div>",
                        unsafe_allow_html=True)

        # 5. Einordnung
        einordnung = PG_EINORDNUNG.get(pg, "")  # passenden Erklärtext zum Pflegegrad aus der Tabelle oben holen
        st.markdown(
            '<div style="text-align:center; font-size:16px; '
            'color:' + HEADLINE_FARBE + '; max-width:600px; '
            'margin: 0 auto 32px auto; line-height:1.55;">'
            + html.escape(einordnung) +
            '</div>',
            unsafe_allow_html=True,
        )

        # 5b. Vollständige Leistungs-Tabelle (wiederverwendet aus
        # Leistungscheck). Nur für pg 1..5 — bei pg=0 oder None gibt es
        # keinen Anspruch und damit nichts anzuzeigen.
        # Genutzte Leistungen werden im Profil verwaltet und hier
        # ausgeblendet (User Story 2/3).
        if pg == 1:
            _lc1_leistungen_zeigen(genutzte_namen)  # passende Leistungs-Liste anzeigen (bei PG1 eine andere als bei 2-5)
        elif pg in (2, 3, 4, 5):
            _lc_leistungen_zeigen(pg, genutzte_namen)

        # 6. Expander mit Modul-Breakdown
        with st.expander("Wie kommt dieses Ergebnis zustande?"):  # st.expander = aufklappbarer Bereich. Zeigt die Punkte-Aufschlüsselung pro Modul
            if override:
                st.markdown(
                    "**Direktzuordnung PG 5 nach §15 IV SGB XI.**\n\n"
                    "Bei vollständigem Verlust der Greif-, Steh- und "
                    "Gehfunktionen entfällt die Modul-Berechnung — der "
                    "Pflegegrad 5 wird unmittelbar zuerkannt."
                )
            elif pg is None:
                st.markdown(
                    "Die Berechnung wurde übersprungen, weil die "
                    "Pflegesituation laut Ihren Angaben weniger als "
                    "6 Monate andauert (§14 I SGB XI)."
                )
            else:
                zeilen = [
                    ("M1 Mobilität",
                     module.get("M1_Mobilitaet", 0), 10),
                    ("M2/M3 Kognition+Verhalten (höherer Wert zählt)",
                     module.get("M2_M3_gewertet", 0), 15),
                    ("M4 Selbstversorgung",
                     module.get("M4_Selbstversorgung", 0), 40),
                    ("M5 Krankheit/Therapie",
                     module.get("M5_Krankheit", 0), 20),
                    ("M6 Alltag/Soziales",
                     module.get("M6_Alltag", 0), 15),
                ]
                tabellen_html = (
                    '<table style="width:100%; border-collapse:collapse; '
                    'font-size:14px;">'
                )
                for name, wert, max_wert in zeilen:
                    tabellen_html += (
                        '<tr>'
                        '<td style="padding:6px 0; color:' + HEADLINE_FARBE + ';">'
                        + html.escape(name) +
                        '</td>'
                        '<td style="padding:6px 0; text-align:right; '
                        'color:' + HEADLINE_FARBE + '; font-variant-numeric:'
                        'tabular-nums;">'
                        f'{wert:g} / {max_wert}'
                        '</td>'
                        '</tr>'
                    )
                tabellen_html += (
                    '<tr><td colspan="2" style="border-top:1px solid '
                    + RAHMEN_GRAU + '; padding-top:8px;"></td></tr>'
                    '<tr>'
                    '<td style="padding:6px 0; font-weight:700; '
                    'color:' + HEADLINE_FARBE + ';">Gesamt</td>'
                    '<td style="padding:6px 0; text-align:right; '
                    'font-weight:700; color:' + HEADLINE_FARBE + '; '
                    'font-variant-numeric:tabular-nums;">'
                    f'{punkte:g} / 100'
                    '</td>'
                    '</tr>'
                    '</table>'
                )
                st.markdown(tabellen_html, unsafe_allow_html=True)

        st.markdown("<div style='height:24px'></div>",
                    unsafe_allow_html=True)

        # 7. Disclaimer
        st.markdown(
            '<div style="text-align:center; font-style:italic; '
            'font-size:13px; color:' + TEXT_GRAU + '; '
            'max-width:600px; margin: 0 auto 28px auto; line-height:1.55;">'
            'Diese Schätzung ersetzt keine offizielle Begutachtung durch '
            'den Medizinischen Dienst (MD). Sie haben Anspruch auf eine '
            'kostenfreie Pflegeberatung nach §7a SGB XI.'
            '</div>',
            unsafe_allow_html=True,
        )

        # 8. CTA-Button
        if pg in (1, 2, 3, 4, 5):  # bei gültigem PG -> Button, der zum nächsten Modul (Leistungslücken) führt
            if st.button("→ Jetzt prüfen: Wie viel Geld lassen Sie ungenutzt?",
                         key="pg_cta_leistungsluecken",
                         type="primary",
                         use_container_width=True):
                st.session_state["next_module"] = "leistungsluecken"  # merken, dass als Nächstes das Leistungslücken-Modul kommt
                st.rerun()
        else:  # bei pg=0 oder None -> stattdessen Button zum Neu-Starten
            if st.button("Check erneut durchführen",
                         key="pg_cta_neu",
                         type="primary",
                         use_container_width=True):
                pg_reset()  # Rechner zurücksetzen (Seite 1, keine Antworten)
                st.rerun()

        # 9. Sekundär-Link
        st.markdown("<div style='height:8px'></div>",
                    unsafe_allow_html=True)
        col_a, col_b, col_c = st.columns([1, 2, 1])  # wieder 3 Spalten zum Zentrieren des Buttons in der Mitte
        with col_b:
            if st.button("Antworten überprüfen",
                         key="pg_antworten_pruefen",
                         use_container_width=True):
                st.session_state["pg_page"] = 1  # zurück auf Seite 1, ABER Antworten bleiben erhalten (nur pg_page ändern, nicht pg_answers leeren)
                st.rerun()


def pflegegrad_rechner_anzeigen() -> None:
    """Rendert die aktuelle Seite des 7-stufigen Pflegegrad-Fragebogens.

    Etappe 1: nur Navigation und Antwort-Speicherung — es wird nichts berechnet.
    Antworten landen in st.session_state["pg_answers"] (Frage-ID -> Wert),
    die aktuelle Seite in st.session_state["pg_page"] (1..7). Nach Seite 7
    erscheint ein Platzhalter.
    """
    # Etappe-3-Platzhalter für das geplante Leistungslücken-Modul.
    # Der CTA-Button im Ergebnis-Screen setzt dieses Flag; der echte
    # Rechner kommt in Etappe 4.
    if st.session_state.get("next_module") == "leistungsluecken":  # Platzhalter - falls der CTA-Button "Leistungslücken" gesetzt hat, zeig "kommt bald"
        st.subheader("Leistungslücken-Rechner")
        st.info("Kommt bald.")
        if st.button("Zurück zum Pflegegrad-Ergebnis",
                     key="next_module_zurueck"):
            st.session_state.pop("next_module", None)  # pop = Eintrag wieder entfernen -> zurück zum Ergebnis
            st.rerun()
        return  # hier raus, der Rest der Funktion läuft dann nicht

    _pg_press_animation_unterdruecken()  # die kosmetische JS-Funktion von oben einbinden

    page = int(st.session_state.get("pg_page", 1))  # aktuelle Seite aus dem Gedächtnis holen (Standard 1). int() = sicher als ganze Zahl

    if page > PG_ANZAHL_SEITEN:        # wenn man hinter die letzte Frage-Seite kommt...
        _pg_platzhalter_zeigen()       # ...dann das Ergebnis anzeigen (statt einer Frage)
        return

    seite = PG_SEITEN[page - 1]  # die aktuelle Seite aus der Fragen-Liste holen. -1, weil Listen bei 0 anfangen (Seite 1 = Index 0)

    # Fortschrittsbalken über der Seite
    st.progress((page - 1) / PG_ANZAHL_SEITEN)

    # Kategorie-Label + Schritt-Zähler (zwei kleine Zeilen)
    st.markdown(
        '<div style="display:flex; justify-content:space-between; '
        'align-items:center; margin: 18px 0 6px 0;">'
        '<span style="font-size:12px; font-weight:700; letter-spacing:2px; '
        'text-transform:uppercase; color:' + PRIMAER + ';">'
        + html.escape(seite["kategorie"].upper()) +
        '</span>'
        '<span style="font-size:12px; color:' + TEXT_GRAU + '; '
        'font-weight:600; letter-spacing:0.4px;">Schritt ' + str(page)
        + ' von ' + str(PG_ANZAHL_SEITEN) + '</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Fragen der aktuellen Seite (mit Trennlinien zwischen Fragen)
    for k, frage in enumerate(seite["fragen"]):  # jede Frage dieser Seite durchgehen (manche Seiten haben mehrere)
        _pg_frage_rendern(frage)                  # HIER wird die Frage übergeben! Aufrufer reicht -> Funktion empfängt und zeigt an
        if k < len(seite["fragen"]) - 1:          # zwischen den Fragen (aber nicht nach der letzten) eine Trennlinie
            st.markdown(
                '<hr style="border:none; border-top:1px solid #EDF2EE; '
                'margin: 30px 0 6px 0;">',
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:36px'></div>", unsafe_allow_html=True)

    alle_beantwortet = all(  # True nur, wenn ALLE Fragen dieser Seite beantwortet sind. all() = "trifft auf alle zu?"
        f["id"] in st.session_state["pg_answers"]  # prüft pro Frage, ob ihre ID schon im Antworten-Gedächtnis steht
        for f in seite["fragen"]
    )
    letzter = page == PG_ANZAHL_SEITEN  # sind wir auf der letzten Seite? (== prüft auf Gleichheit, ist KEINE Zuweisung)

    # Zurück- und Weiter-Buttons unten
    col_z, col_spacer, col_w = st.columns([1, 0.3, 1])  # Zurück links, kleiner Abstand, Weiter rechts
    with col_z:
        if page > 1:  # "Zurück" nur zeigen, wenn man nicht auf Seite 1 ist
            if st.button("Zurück",
                         key="pg_zurueck_" + str(page),  # key mit Seitennummer, damit jeder Button eindeutig ist
                         use_container_width=True):
                st.session_state["pg_page"] = page - 1  # eine Seite zurück
                st.rerun()
    with col_w:
        label = "Auswertung anzeigen" if letzter else "Weiter"  # auf der letzten Seite heißt der Button anders
        if st.button(label,
                     key="pg_weiter_" + str(page),
                     type="primary",
                     disabled=not alle_beantwortet,  # Button ausgegraut/gesperrt, solange NICHT alle Fragen beantwortet sind
                     use_container_width=True):
            st.session_state["pg_page"] = page + 1  # Louis: eine Seite weiter (oder hinter die letzte -> löst den Ergebnis-Screen aus)
            st.rerun()

    if not alle_beantwortet:
        st.markdown(
            '<p style="font-size:12px; color:#888; text-align:center; '
            'margin-top:12px;">Bitte beantworten Sie alle Fragen, '
            'um fortzufahren.</p>',
            unsafe_allow_html=True,
        )


# ============================================================

# ------------------------------------------------------------
# LEISTUNGSCHECK-UI (alter 7-Fragen-Rechner, anonym auf Landing)
# ------------------------------------------------------------

def _lc_einzelne_frage(frage: dict) -> None:
    """Eine Frage mit Titel, Beschreibung und 4 Antwort-Buttons."""
    # Ist nur intern gedacht deshalb _ vor dem lc. "frage" ist der Name der variable. Dict steht für Datenpaket mit Schlüsselwert-Paare.
    # None gibt nichts zurück sondern zeigt nur etwas auf dem Bildschirm an
    # markdown zeigt Text an. Bei nela-frage wird html Container mit der Klasse nela-frage geöffnet.
    # f steht für f-string und ermöglicht es variablen direkt in eine Zeichenkette einzufügen. "frage titel" wird dann mit dem hinterlegten Text aus dict ersetzt. 
    # Fragenbeschreibung wird geöffnet und eine Beschreibung unter dem Text hinzugefügt. 
    # '</div' schließt den Container. Durch unsafe allow html = true darf streamlit echte HTML anzegen und keine HTML-Tags
    st.markdown(
        '<div class="nela-frage">'
        f'<h3>{frage["titel"]}</h3>'
        f'<p class="nela-frage-beschreibung">{frage["beschreibung"]}</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    aktuelle = st.session_state.lc_antworten.get(frage["schlüssel"])
    # Es wird geprüft ob der Nutzer die Fragen schon beantwortet hat. 
    # get sucht den Frageschlüssel und gibt ggf. die gespeicherte Punktezahl zurück. Es wird in "aktuelle" gespeichert"
    cols = st.columns(4)
    # Bildschirm wird in 4 gleich große Spalten geteilt

    for i, opt in enumerate(LC_ANTWORTOPTIONEN):
        gewaehlt = aktuelle == opt["punkte"]
        with cols[i]:
            # enumerate liefert den Index (Zählnummer beginnt mit 0,1,2,3) sowie die Antwortmöglichkeiten z.B. "ja vollständig". läuft vier mal durch.
            # Es wird geprüft ob gewählt Antwortmöglichkeit mit der Punktezahl übereinstimmt. Bei allen vier durchläufen.
            # Cols betrettet die i-te Spalte
            # opt ist Antwortmöglichkeit + Zeilenumbruch + Untertitel
            # key baut einzigartigen Namen zusammmen 
            # gewählter button ist primary (grün) der secondary button wird grau
            # durch width füllt der Button die gesamte Spaltenbreite aus
            # antworten werden im Arbeitsspeicher gesichert. Seite wird neu geladen.
            if st.button(
                opt["label"] + "\n(" + opt["untertitel"] + ")",
                key="lc_" + frage["schlüssel"] + "_opt" + str(i),
                type="primary" if gewaehlt else "secondary",
                use_container_width=True,
            ):
                st.session_state.lc_antworten[frage["schlüssel"]] = opt["punkte"]
                st.rerun()


def _lc_monatsbetrag(betrag_str: str, periode: str) -> float:
    """Konvertiert einen Anzeige-Betrag ('347 €', 'kostenlos', 'bis 4.180 €')
    in Euro pro Monat. 'bis ...' und 'kostenlos' liefern 0.
    Jährliche Beträge werden durch 12 geteilt.
    """
    if betrag_str.startswith("bis ") or betrag_str == "kostenlos":
        return 0.0
    zahl = int(betrag_str.replace(" €", "").replace(".", ""))
    return float(zahl) if periode == "monatlich" else zahl / 12.0 
    # Die Funktion erhält string und gibt float zurück
    # bei "bis" und "kostenlos" wird 0 ausgegeben. Funktion wird abgebrochen
    # zahl wird von "1.111 €" zu 1112 umgewandelt
    # wenn monatlich dann wird die Zahl/float direkt angegeben ansonsten erst noch durch 12 geteilt 


def _lc_summen_html(summe_eur: int) -> str:
    """Erzeugt den HTML-Block für die Monats-Summe am Ende der Leistungstabelle."""
    betrag_fmt = f"{summe_eur:,.0f}".replace(",", ".") + " €"
    return (
        '<div class="nela-lst-summe">'
            '<div class="nela-lst-summe-label">Pro Monat stehen Ihnen bis zu:</div>'
            f'<div class="nela-lst-summe-betrag">{betrag_fmt}</div>'
            '<div class="nela-lst-summe-cta">'
                'Wir helfen Ihnen, das Geld zu erhalten und einzusetzen.'
            '</div>'
        '</div>'
    )
    #int wird zu str umgewandelt. Komma wird zu Punkt umgewandelt. Text für Kunde wird zusammengestellt.
    

def _lc1_leistungen_zeigen(genutzte_namen: set = None) -> None:
    """Minimalistische Leistungs-Übersicht für Pflegegrad 1.

    Hardcoded PG1-Beträge (ab 2026). Wird nur aufgerufen, wenn die
    Einschätzung exakt Pflegegrad 1 ergibt.

    Optional `genutzte_namen`: Set von Leistungs-Namen, die der Nutzer
    laut Profil bereits beansprucht — diese werden aus der Liste UND
    aus der Monatssumme entfernt (User Story: Rechner zeigt nur die
    tatsächlich ungenutzten Beträge).
    """
    if genutzte_namen is None:
        genutzte_namen = set()

    leistungen = [
        {
            "name":    "Entlastungsbetrag",
            "info":    "Für Alltagshelfer, Haushaltshilfe oder Betreuungsangebote anerkannter Anbieter.",
            "betrag":  "131 €",
            "periode": "monatlich",
            "tag":     "Guthaben",
        },
        {
            "name":    "Pflegehilfsmittel",
            "info":    "Handschuhe, Desinfektion, Bettschutzeinlagen. Werden monatlich geliefert.",
            "betrag":  "42 €",
            "periode": "monatlich",
            "tag":     "Guthaben",
        },
        {
            "name":    "Hausnotruf",
            "info":    "Notrufknopf für den Fall, dass schnell Hilfe gebraucht wird.",
            "betrag":  "27 €",
            "periode": "monatlich",
            "tag":     "Guthaben",
        },
        {
            "name":    "Pflegeberatung",
            "info":    "Kostenlose Beratung durch Pflegekasse oder Pflegestützpunkt.",
            "betrag":  "kostenlos",
            "periode": "nach Bedarf",
            "tag":     "Service",
        },
        {
            "name":    "Wohnumfeldverbesserung",
            "info":    "Für Badumbau, Treppenlift oder Türverbreiterung. Antrag vor dem Umbau!",
            "betrag":  "bis 4.180 €",
            "periode": "einmalig",
            "tag":     "Antrag",
        },
    ]

    # wenn kein genutzter Name übergeben wurde (None) dann wird ein leeres Set/Liste erstellt (set())
    # wenn e nicht im set "genutze_namen" aufzufinden ist wird e behalten. genutzte Leistungen werden somit rausgefiltert. Lückenrechner
    leistungen_gefiltert = [e for e in leistungen
                             if e["name"] not in genutzte_namen]

    # Sonderfall: alle Leistungen bereits genutzt.
    if not leistungen_gefiltert:
        st.markdown(
            '<div class="nela-lst-titel">Alles erfasst</div>'
            '<div class="nela-lst-subtitel">'
            'Sie nutzen laut Ihrem Profil bereits alle für Pflegegrad 1 '
            'verfügbaren Leistungen.'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    tag_klassen = {
        "Guthaben": "nela-lst-tag-guthaben",
        "Antrag":   "nela-lst-tag-antrag",
        "Service":  "nela-lst-tag-service",
    }

    # alle gefilterten/ungenutzten Leistungen werden zusammen addiert. Wohnfeldverb. wird ausgeschlossen da nicht monatlich.
    summe_eur = round(sum(
        _lc_monatsbetrag(e["betrag"], e["periode"])
        for e in leistungen_gefiltert
        if e["name"] != "Wohnumfeldverbesserung"
    ))

    # Leere Liste wird erstellt um alle html Texte zu sammeln. Escape wandelt für die Tabelle alle < und > um
    # append fügt die fertige Zeile in die Liste hinzu. 
    zeilen_html = []
    for eintrag in leistungen_gefiltert:
        name    = html.escape(eintrag["name"])
        info    = html.escape(eintrag["info"])
        betrag  = html.escape(eintrag["betrag"])
        periode = html.escape(eintrag["periode"])
        tag     = eintrag["tag"]
        tag_cls = tag_klassen[tag]
        zeilen_html.append(
            '<div class="nela-lst-row">'
                '<div class="nela-lst-col-name">'
                    f'<div class="nela-lst-name">{name}</div>'
                    f'<div class="nela-lst-info">{info}</div>'
                '</div>'
                '<div class="nela-lst-col-betrag">'
                    f'<div class="nela-lst-betrag">{betrag}</div>'
                    f'<div class="nela-lst-periode">{periode}</div>'
                '</div>'
                '<div class="nela-lst-col-tag">'
                    f'<span class="nela-lst-tag {tag_cls}">{tag}</span>'
                '</div>'
            '</div>'
        )

    # Text wird je nach Filter-Zustand angepasst. len gibt Anzahl der Elemente zurück.
    # join verbindet alle html zeilen der Liste
    # Summe wird hinten dran gehängt
    # markdown zeigt den gesamten hmtl block auf Bildschirm des Kunden an
    if genutzte_namen and any(e["name"] in genutzte_namen for e in leistungen):
        n_gezeigt = len(leistungen_gefiltert)
        n_gesamt  = len(leistungen)
        subtitel = (f'Bei Pflegegrad 1 — Ihre noch ungenutzten Leistungen '
                    f'({n_gezeigt} von {n_gesamt})')
    else:
        subtitel = 'Bei Pflegegrad 1 — alle Leistungen im Überblick'

    html_block = (
        '<div class="nela-lst-titel">Das steht Ihnen zu</div>'
        f'<div class="nela-lst-subtitel">{html.escape(subtitel)}</div>'
        '<div class="nela-lst-hinweis">'
            'Bei Pflegegrad 1 gibt es noch kein Pflegegeld und keine Pflegesachleistung. '
            'Die wichtigsten Leistungen sind Entlastungsbetrag und Hilfsmittel.'
        '</div>'
        '<div class="nela-lst-karte">'
        + ''.join(zeilen_html) +
        '</div>'
        '<div class="nela-lst-legende">'
            '<span class="nela-lst-legende-item">'
                '<span class="nela-lst-legende-dot nela-lst-legende-dot-guthaben"></span>'
                'Guthaben — für bestimmte Zwecke'
            '</span>'
            '<span class="nela-lst-legende-item">'
                '<span class="nela-lst-legende-dot nela-lst-legende-dot-antrag"></span>'
                'Antrag — vorher beantragen'
            '</span>'
            '<span class="nela-lst-legende-item">'
                '<span class="nela-lst-legende-dot nela-lst-legende-dot-service"></span>'
                'Service — kostenlose Leistung'
            '</span>'
        '</div>'
        + _lc_summen_html(summe_eur)
    )

    st.markdown(html_block, unsafe_allow_html=True)


# Alle Leistungen für Pflegegrad 2 bis 5 
NELA_LEISTUNGEN_ALLE = [
    "Pflegegeld",
    "Pflegesachleistung",
    "Entlastungsbetrag",
    "Entlastungsbudget",
    "Pflegehilfsmittel",
    "Tages-/Nachtpflege",
    "Hausnotruf",
    "Pflegeberatung",
    "Wohnumfeldverbesserung",
    "Rentenbeiträge",
    "Pflege-Pauschbetrag",
]


LC_LEISTUNGEN_2_BIS_5 = [
    {
        "name":     "Pflegegeld",
        "info":     "Frei verfügbares Geld für die Pflege durch Angehörige. Keine Belege nötig.",
        "periode":  "monatlich",
        "tag":      "Konto",
        "betraege": {2: "347 €", 3: "599 €", 4: "800 €", 5: "990 €"},
    },
    {
        "name":     "Pflegesachleistung",
        "info":     "Budget für einen ambulanten Pflegedienst. Wird direkt mit der Kasse abgerechnet.",
        "periode":  "monatlich",
        "tag":      "Guthaben",
        "betraege": {2: "796 €", 3: "1.497 €", 4: "1.859 €", 5: "2.299 €"},
    },
    {
        "name":     "Entlastungsbetrag",
        "info":     "Für Alltagshelfer, Haushaltshilfe oder Betreuungsangebote anerkannter Anbieter.",
        "periode":  "monatlich",
        "tag":      "Guthaben",
        "betraege": {2: "131 €", 3: "131 €", 4: "131 €", 5: "131 €"},
    },
    {
        "name":     "Pflegehilfsmittel",
        "info":     "Handschuhe, Desinfektion, Bettschutzeinlagen. Werden monatlich geliefert.",
        "periode":  "monatlich",
        "tag":      "Guthaben",
        "betraege": {2: "42 €", 3: "42 €", 4: "42 €", 5: "42 €"},
    },
    {
        "name":     "Entlastungsbudget",
        "info":     "Für Verhinderungs- und Kurzzeitpflege, wenn die Hauptpflegeperson ausfällt.",
        "periode":  "jährlich",
        "tag":      "Guthaben",
        "betraege": {2: "3.539 €", 3: "3.539 €", 4: "3.539 €", 5: "3.539 €"},
    },
    {
        "name":     "Tages-/Nachtpflege",
        "info":     "Tagsüber oder nachts wird sie in einer Einrichtung betreut.",
        "periode":  "monatlich",
        "tag":      "Guthaben",
        "betraege": {2: "721 €", 3: "1.357 €", 4: "1.685 €", 5: "2.085 €"},
    },
    {
        "name":     "Hausnotruf",
        "info":     "Notrufknopf für den Fall, dass schnell Hilfe gebraucht wird.",
        "periode":  "monatlich",
        "tag":      "Guthaben",
        "betraege": {2: "27 €", 3: "27 €", 4: "27 €", 5: "27 €"},
    },
    {
        "name":     "Rentenbeiträge",
        "info":     "Die Pflegekasse zahlt in Ihre Rente ein, wenn Sie mind. 10h/Woche pflegen.",
        "periode":  "monatlich",
        "tag":      "Indirekt",
        "betraege": {2: "199 €", 3: "316 €", 4: "515 €", 5: "736 €"},
    },
    {
        "name":     "Pflege-Pauschbetrag",
        "info":     "Steuerersparnis bei unentgeltlicher Pflege. In Steuererklärung angeben.",
        "periode":  "jährlich",
        "tag":      "Steuer",
        "betraege": {2: "600 €", 3: "1.100 €", 4: "1.800 €", 5: "1.800 €"},
    },
    {
        "name":     "Wohnumfeldverbesserung",
        "info":     "Für Badumbau, Treppenlift oder Türverbreiterung. Antrag vor dem Umbau!",
        "periode":  "einmalig",
        "tag":      "Antrag",
        "betraege": {2: "bis 4.180 €", 3: "bis 4.180 €", 4: "bis 4.180 €", 5: "bis 4.180 €"},
    },
]


     # pflegegradnummer als int (2-5), set optional
     # wenn kein genutzer Name verwendet wurde dann leeres set
def _lc_leistungen_zeigen(pg_nummer: int,
                            genutzte_namen: set = None) -> None:
    """Minimalistische Leistungs-Übersicht für Pflegegrad 2-5.

    Struktur (Töpfe, Beschreibungen, Tags, Legende) ist für PG2-5 identisch;
    nur einzelne Beträge variieren. PG1 hat eine eigene Funktion mit anderem
    Tag-Satz und Hinweis-Box.

    Optional `genutzte_namen`: Set von Leistungs-Namen, die der Nutzer
    laut Profil bereits beansprucht — diese werden ausgeblendet und
    fließen nicht in die Monatssumme ein.
    """
    if genutzte_namen is None:
        genutzte_namen = set()

    # Filter genutzte Leistungen heraus
    leistungen_gefiltert = [e for e in LC_LEISTUNGEN_2_BIS_5
                             if e["name"] not in genutzte_namen]

    # Sonderfall: alle Leistungen bereits erfasst
    if not leistungen_gefiltert:
        st.markdown(
            '<div class="nela-lst-titel">Alles erfasst</div>'
            '<div class="nela-lst-subtitel">'
            f'Sie nutzen laut Ihrem Profil bereits alle für Pflegegrad '
            f'{pg_nummer} verfügbaren Leistungen.'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    tag_klassen = {
        "Konto":    "nela-lst-tag-konto",
        "Guthaben": "nela-lst-tag-guthaben",
        "Antrag":   "nela-lst-tag-antrag",
        "Indirekt": "nela-lst-tag-indirekt",
        "Steuer":   "nela-lst-tag-steuer",
    }

    # Leistungen werden addiert und gerundet. Wohnumfeldverbesserung wird ausgelassen, da einmalige Zahlung
    summe_eur = round(sum(
        _lc_monatsbetrag(e["betraege"][pg_nummer], e["periode"])
        for e in leistungen_gefiltert
        if e["name"] != "Wohnumfeldverbesserung"
    ))

    zeilen_html = []
    for eintrag in leistungen_gefiltert:
        name    = html.escape(eintrag["name"])
        info    = html.escape(eintrag["info"])
        betrag  = html.escape(eintrag["betraege"][pg_nummer])
        periode = html.escape(eintrag["periode"])
        tag     = eintrag["tag"]
        tag_cls = tag_klassen[tag]
        zeilen_html.append(
            '<div class="nela-lst-row">'
                '<div class="nela-lst-col-name">'
                    f'<div class="nela-lst-name">{name}</div>'
                    f'<div class="nela-lst-info">{info}</div>'
                '</div>'
                '<div class="nela-lst-col-betrag">'
                    f'<div class="nela-lst-betrag">{betrag}</div>'
                    f'<div class="nela-lst-periode">{periode}</div>'
                '</div>'
                '<div class="nela-lst-col-tag">'
                    f'<span class="nela-lst-tag {tag_cls}">{tag}</span>'
                '</div>'
            '</div>'
        )

    # Text je nach Filter-Zustand anpassen
    if genutzte_namen and any(e["name"] in genutzte_namen
                                for e in LC_LEISTUNGEN_2_BIS_5):
        n_gezeigt = len(leistungen_gefiltert)
        n_gesamt  = len(LC_LEISTUNGEN_2_BIS_5)
        subtitel = (f'Bei Pflegegrad {pg_nummer} — Ihre noch ungenutzten '
                    f'Leistungen ({n_gezeigt} von {n_gesamt})')
    else:
        subtitel = f'Bei Pflegegrad {pg_nummer} — alle Leistungen im Überblick'

    html_block = (
        '<div class="nela-lst-titel">Das steht Ihnen zu</div>'
        f'<div class="nela-lst-subtitel">{html.escape(subtitel)}</div>'
        '<div class="nela-lst-karte">'
        + ''.join(zeilen_html) +
        '</div>'
        '<div class="nela-lst-legende">'
            '<span class="nela-lst-legende-item">'
                '<span class="nela-lst-legende-dot nela-lst-legende-dot-konto"></span>'
                'Konto — direkt aufs Bankkonto'
            '</span>'
            '<span class="nela-lst-legende-item">'
                '<span class="nela-lst-legende-dot nela-lst-legende-dot-guthaben"></span>'
                'Guthaben — für bestimmte Zwecke'
            '</span>'
            '<span class="nela-lst-legende-item">'
                '<span class="nela-lst-legende-dot nela-lst-legende-dot-antrag"></span>'
                'Antrag — vorher beantragen'
            '</span>'
            '<span class="nela-lst-legende-item">'
                '<span class="nela-lst-legende-dot nela-lst-legende-dot-indirekt-steuer"></span>'
                'Indirekt / Steuer — wirkt über Rente oder Steuer'
            '</span>'
        '</div>'
        + _lc_summen_html(summe_eur)
    )

    st.markdown(html_block, unsafe_allow_html=True)


     # eingeloggt -> true oder false. Je nachdem verschiedene Möglichkeiten
     # pkt ruft eine wo anders gespeicherte Funktion auf, gewichtet die Antworten und berechnet Gesamtpunktzahl 0 bis 100
     # text wandelt die gesamtpunktzahl in eine Pflegegradempfehlung um
     # text und pkt werden im Arbeitsspeicher gesichert
def _lc_ergebnis_zeigen(eingeloggt: bool) -> None:
    """Ergebnis-Karte + nächste Schritte (CTA oder Weiter)."""
    pkt   = lc_punkte_berechnen(st.session_state.lc_antworten)
    text  = lc_aus_punkten(pkt)

    st.session_state.lc_ergebnis_text   = text
    st.session_state.lc_ergebnis_punkte = pkt

    # Ergebnis Text für Kunden. "Ihr Ergebnis + Pflegegrad + Punktzahl
    st.markdown(
        '<div class="nela-ergebnis">'
        '<div class="nela-ergebnis-eyebrow">Ihr Ergebnis</div>'
        f'<div class="nela-ergebnis-headline">{text}</div>'
        f'<div class="nela-ergebnis-sub">{pkt:.1f} von 100 möglichen Punkten</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Genutzte Leistungen aus dem Profil/Datenbank holen (nur für eingeloggte Nutzer).
    # wenn eingeloggt dann gespeicherte email holen sonst leeres string
    # wenn email gefunden dann werden Nutzerdaten aus Json-Datenbank geholt
    # wenn Nutzer gefunden wurde dann gespeicherte Leistungen anzeigen, sonst leere.
    # Liste wird in set umgewandelt (schnelles nachschlagen möglich)
    genutzte_namen = set()
    if eingeloggt:
        email_n = st.session_state.get("anmeldung_email", "")
        if email_n:
            n_data = nutzer_holen(email_n)
            if n_data:
                genutzte_namen = set(n_data.get("genutzte_leistungen") or [])

    if text == "Erste Einschätzung: Pflegegrad 1":
        _lc1_leistungen_zeigen(genutzte_namen)
    elif text == "Erste Einschätzung: Pflegegrad 2":
        _lc_leistungen_zeigen(2, genutzte_namen)
    elif text == "Erste Einschätzung: Pflegegrad 3":
        _lc_leistungen_zeigen(3, genutzte_namen)
    elif text == "Erste Einschätzung: Pflegegrad 4":
        _lc_leistungen_zeigen(4, genutzte_namen)
    elif text == "Erste Einschätzung: Pflegegrad 5":
        _lc_leistungen_zeigen(5, genutzte_namen)

    st.info(
        "**Hinweis:** Dies ist eine erste Einschätzung und ersetzt keine "
        "offizielle Begutachtung durch den Medizinischen Dienst (MD)."
    )

    # pflegegrad soll nur einmal im Profil und nicht nach jedem klick gespeichert werden
    # beim ersten durchlauf gibt es noch keine Speicherung -> get = None -> Not None = True -> Speicherung
    # bei den folgenden Durchläufen war es schon gespeichert -> True -> Not True = False -> keine Speicherung
    # success zeigt grünen Bestätigungskasten
    # markdown 12px ist unsichtbarer Abstand
    if eingeloggt:
        email = st.session_state.get("anmeldung_email", "")
        if email and not st.session_state.get("lc_im_profil_gespeichert"):
            pflegegrad_im_profil_speichern(email, text, pkt)
            st.session_state["lc_im_profil_gespeichert"] = True
        if st.session_state.get("lc_im_profil_gespeichert"):
            st.success("Ihr Ergebnis wurde in Ihrem Profil gespeichert.")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # button 1 und 2 sind im verhältnis 3:1 groß
    # use container width = true bedeutet dass der angedrückte Button die gesamte Seite einnimmt
    # primary = Leistung wird angezeigt
    # rerun = neu laden / reset = setzt alles zurück 
    if eingeloggt:
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("Weiter zum Leistungslücken-Rechner",
                         key="lc_weiter_leistung",
                         type="primary",
                         use_container_width=True):
                st.session_state["aktuelle_seite"] = "leistung"
                st.rerun()
        with col2:
            if st.button("Neu starten", key="lc_neu_start",
                         use_container_width=True):
                lc_reset()
                st.rerun()
    else:
        # Conversion-Box für anonyme Nutzer = Ergebnis für nicht eingeloggt Nutzer wird nicht gespeichert
        # button 1, 2 und 3 snd im Verhältnis 2:2:1 groß
        # use container width = angedrückter Button nimmt gesamte Fläche ein
        # primary = Leistung wird angezeigt, rerun = neu laden, reset = zurücksetzen
        # auth_modus register/login zeigt das Registrierungs/Login Formular an
        st.markdown(
            '<div class="nela-conversion">'
            '<div class="nela-conversion-headline">Sichern Sie Ihr Ergebnis dauerhaft</div>'
            '<p class="nela-conversion-text">'
            'Mit einem kostenlosen Nela-Konto wird Ihr Ergebnis automatisch in '
            'Ihrem Profil gespeichert. Im nächsten Schritt zeigen wir Ihnen, '
            'wieviel Euro Ihnen pro Jahr zustehen.'
            '</p></div>',
            unsafe_allow_html=True,
        )

        col_a, col_b, col_c = st.columns([2, 2, 1])
        with col_a:
            if st.button("Kostenloses Konto erstellen",
                         key="lc_cta_register",
                         type="primary",
                         use_container_width=True):
                st.session_state["auth_modus"] = "register"
                st.rerun()
        with col_b:
            if st.button("Bereits Konto - Anmelden",
                         key="lc_cta_login",
                         use_container_width=True):
                st.session_state["auth_modus"] = "login"
                st.rerun()
        with col_c:
            if st.button("Neu",
                         key="lc_cta_neu",
                         use_container_width=True):
                lc_reset()
                st.rerun()


     # wenn ein button gedrück wird flackert es kurz (aufgrund von streamlit), wird durch pg press animation unterdruecken untertrückt
     # idx ist der Seitenindex (0-5 für 6 seiten)
     # sd sind die Seitendaten zB überschriften
     # len ist gesamtzahl der Seiten = 6
def leistungscheck_anzeigen(eingeloggt: bool) -> None:
    """Rendert den kompletten Rechner. Falls abgeschlossen, das Ergebnis."""
    _pg_press_animation_unterdruecken()

    if st.session_state.lc_abgeschlossen:
        _lc_ergebnis_zeigen(eingeloggt)
        return

    idx  = st.session_state.lc_seite_index
    sd   = LC_SEITEN[idx]
    n    = len(LC_SEITEN)

    # Seitenzahl anzeigen 1 von 6. Lebensbereich anzeigen
    # progress ist der Fortschrittsbalken 2/6 -> 33% sind grün
    # markdown 24px ist unsichtbarer abstand
    st.markdown(
        '<div class="nela-rechner-meta">'
        f'<span class="nela-rechner-step">Schritt {idx + 1} von {n}</span>'
        f'<span class="nela-rechner-bereich">{sd["lebensbereich"]}</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.progress((idx + 1) / n)
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    # alle Fragen der jeweiligen Seite werden durchgegangen
    # wenn es nicht die letzte Frage auf der Seite ist dann wird dünne Trennlinie (<hr>) 
    # -1 weil nach der letzten Frage keine Trennlinie erscheinen soll sondern ein weiter button
    # alle prüft ob alle fragen auf der seite beantwortet wurden (schlüssel wird in Datenbank gefunden, falls die Seite beantwortet wurde)
    # letzter prüft ob es sich um die letzte Seite handelt (n-1= letzte seite)
    for k, frage in enumerate(sd["fragen"]):
        _lc_einzelne_frage(frage)
        if k < len(sd["fragen"]) - 1:
            st.markdown(
                "<hr style='border:none; border-top:1px solid #EDF2EE; "
                "margin:22px 0;'>",
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    alle = all(f["schlüssel"] in st.session_state.lc_antworten
               for f in sd["fragen"])
    letzter = idx == n - 1

    # Wenn idx>0 (ab seite 2) gibt es zwei buttons im Verhältnis 1:3
    # session state lc seite index -= 1 springt eine Seite zurück
    # Ansonsten (Seite 1) gibt es faktisch nur den button weiter
    # 0,0001 ist unsichtbar, bleibt aber erhalten damit weiter button auf der gleichen position stehen bleiben kann
    # auf letzter Seite steht Ergebnis anzeigen statt weiter
    # disabled = not alle -> wenn False dann nicht alle Fragen beantwortet (weiter button ausgegraut), bei True sind alle Fragen beantwortet (button aktiviert)
    # stop unterbindet doppelklicks
    # Letzter klick idx merkt sich welche Seite soeben geklickt wurde um doppelklicks zu erkennen
    # wenn letzte Seite bearbeitet dann ergebnis anzeigen, sonst eine seite weiter
    if idx > 0:
        col_z, col_w = st.columns([1, 3])
        with col_z:
            if st.button("Zurück",
                         key="lc_zurueck_" + str(idx),
                         use_container_width=True):
                st.session_state.lc_seite_index -= 1
                st.rerun()
    else:
        col_z, col_w = st.columns([0.001, 1])

    with col_w:
        label = "Ergebnis anzeigen" if letzter else "Weiter"
        if st.button(label,
                     key="lc_weiter_" + str(idx),
                     disabled=not alle,
                     type="primary",
                     use_container_width=True):
            if st.session_state.get("lc_letzter_klick_idx") == idx:
                st.stop()
            st.session_state.lc_letzter_klick_idx = idx
            if letzter:
                st.session_state.lc_abgeschlossen = True
            else:
                st.session_state.lc_seite_index += 1
            st.rerun()

    if not alle:
        st.markdown(
            "<p style='font-size:12px; color:#888; text-align:center; "
            "margin-top:10px;'>Bitte beantworten Sie alle Fragen, "
            "um fortzufahren.</p>",
            unsafe_allow_html=True,
        )

# 6) AUTHENTIFIZIERUNG #Nina 
# ============================================================

#Jemand macht Leistungscheck ohne eingeloggt zu sein
#meldet sich danach an, aber Ergebnis soll nicht gelöscht sein, sondern automatisch ins Profil gehen 
def _auth_leistungscheck_uebernehmen() -> None:
    #Funktion bekommt nichts übergeben und gibt auch nichts, deswegen none 
    #"rettet" nur das anyonyme Ereignis ins Profil
    if (st.session_state.get("lc_abgeschlossen") and
            st.session_state.get("lc_ergebnis_text")):
    #and = Zwei Bedingungen müssen gleichzetig erfüllt werden 
    #Ist der Leistungscheck abgeschlossen?
    #Gibt es auch ein Ergebnis, dass "gerettet" werden kann 
    #Ist eins nicht erfüllt, dann einfach nichts tun 
        email = st.session_state.get("anmeldung_email", "")
        text = st.session_state.get("lc_ergebnis_text", "")
        pkt = st.session_state.get("lc_ergebnis_punkte", 0)
    #3 Werte werden aus dem Kurzzeitgedächnis geholt 
    #Email, Pflegegrad und die Punktzahl
        #falls die Punktzahl nicht vorhanden ist, startet sie bei 0 
        if email and text:
    #Nochmal Sicherheitsprüfung
    #Nur weitermachen wenn Email und Text da ist 
    #damit will man einen Absturz verhindern, falls doch was leer ist 
            pflegegrad_im_profil_speichern(email, text, pkt)
    #Das Ergebnis wird jetzt dauerhaft gespeichert 
            st.session_state["lc_im_profil_gespeichert"] = True
    #Merker wird gesetzt 
    #Das Ergebnis wurde gerettet -> Erfolgsmeldung 

#Zeigt Login-Formular an, das Nutzer sehen, wenn sie sich anmelden wollen 
#Mit Email-Feld, Passwort und Anmelde-Knopf
def auth_form_anmelden() -> None:
    #Funktion zeigt nur das Formular an
    #gibt nichts zurück, deswegen none 
    st.markdown("<div style='height:48px'></div>", unsafe_allow_html=True)
    #gibt nur den Abstand nach oben an 
    st.markdown(
        '<div style="text-align:center;">'
        '<span class="nela-eyebrow">Willkommen zurück</span>'
        '<h1 style="font-family:Montserrat, sans-serif; '
        'font-size:clamp(26px, 3.6vw, 36px); font-weight:800; '
        f'color:{HEADLINE_FARBE}; margin:12px 0 8px 0;">Anmelden bei Nela</h1>'
        f'<p style="color:{TEXT_GRAU}; font-size:15px; max-width:480px; '
        'margin:0 auto 28px auto;">'
        'Melden Sie sich an, um Ihre Pflegesituation zu verwalten und '
        'gespeicherte Ergebnisse einzusehen.'
        '</p></div>',
        unsafe_allow_html=True,
    )
    #Eigentlich nur Design Sachen 
    #"Willkommen zurück" -> kleiner Text über der Überschrift
    #"Anmelden bei Nela" -> große Hauptüberschrift in Nelas Farbe
    #<p> -> grauer Erklärungstext darunter

    cols = st.columns([1, 2, 1])
    with cols[1]:
    #Macht 3 Spalte, aber die mittlere ist doppelt so breit wie die zwei anderen 
    #So ist das Formular zentriert     
        
        with st.form("form_login", clear_on_submit=False):
    #Streamlit Formular
    #Gruppiert alle Eingabefelder zusammen damit sie auf einmal abgeschickt werden 
    #clear_on_submit=False = Felder werden nach dem Abschicken nicht geleert 
            email = st.text_input("E-Mail-Adresse",
                                   key="login_email",
                                   placeholder="ihre.adresse@example.de")
    #Texteingabefeld für die E-Mail 
    #placeholder = ist der graue Hinweistext
        #verschwindet aber, sobald man anfängt zu tippen
            pw = st.text_input("Passwort", type="password",
                                key="login_passwort")
    #Passwortfeld 
    #type="password" = Punkte werden statt Buchstaben angezeigt 
            ok = st.form_submit_button("Anmelden",
                                       type="primary",
                                        use_container_width=True)
    #st.form_submit_button = Absende-Knopf des Formulars
    #schickt ein Formular ab
    #wenn der Knopf gedrückt wurde true, sonst false 
        if ok:
            e = (email or "").strip().lower()
            if not e or not pw:
                st.error("Bitte geben Sie E-Mail und Passwort ein.")
    #Wenn der Knopf gedrückt wurde, wird zuerst überprüft ob überhaupt was eingegeben wurde 
    #strip() = entfernt Leerzeichen am Anfang/Ende 
    #Falls ein Feld leer ist -> Fehlermeldung und Text 
            else:
                n = anmeldung_pruefen(e, pw)
                if n is None:
                    st.error("E-Mail oder Passwort ist nicht korrekt.")
    #Falls beide Felder ausgefüllt worden sind, wird geprüft 
    #anmeldung_pruefen = Ob Email/Passwort passt 
    #Falls none, dann gibts Fehlermeldung 
                else:
                    st.session_state["anmeldung_eingeloggt"] = True
                    st.session_state["anmeldung_email"]     = e
                    _auth_leistungscheck_uebernehmen()
                    st.session_state["aktuelle_seite"] = "dashboard"
                    st.session_state["auth_modus"]    = None
                    st.rerun()
    #Login war erfolgreich 
        #Eingeloggt Merker wird auf true gesetzt
        #Email wird im Kurzzeitgedächnis gespeichert 
        #Leistungscheckergebnis wurde gerettet 
        #Weiterleiten zum Dashboard
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Noch kein Konto? Registrieren",
                         key="login_zu_register",
                         use_container_width=True):
                st.session_state["auth_modus"] = "register"
                st.rerun()
        with c2:
            if st.button("Zurück zur Startseite",
                         key="login_zurueck",
                         use_container_width=True):
                st.session_state["auth_modus"] = None
                st.rerun()
    #Zwei Knöpfe untereinander unter dem Formular 
    #deswegen auch wieder c1 und c2
    #links = wechselt zum Registrierungsformular 
    #rechts = zurück zur Startseite 

#Allgemein: Funktion zeigt das Registrierungsformular an 
#Alles was passiert wenn jemand ein neues Konto erstellt 

def auth_form_registrieren() -> None:
    #Zeigt nur das Formular an -> gibt nichts, deswegen none 
    st.markdown("<div style='height:48px'></div>", unsafe_allow_html=True)
    #Abstandhalter, damit das Formular nicht firekt ganz oben ist, sondern bissl schwebt 
    st.markdown(
        '<div style="text-align:center;">'
        '<span class="nela-eyebrow">Kostenlos starten</span>'
        '<h1 style="font-family:Montserrat, sans-serif; '
        'font-size:clamp(26px, 3.6vw, 36px); font-weight:800; '
        f'color:{HEADLINE_FARBE}; margin:12px 0 8px 0;">Konto bei Nela erstellen</h1>'
        f'<p style="color:{TEXT_GRAU}; font-size:15px; max-width:520px; '
        'margin:0 auto 28px auto;">'
        'In 60 Sekunden registriert. Ihre Daten bleiben bei Ihnen. '
        'Erinnerung an Fristen, gespeichertes Ergebnis und unsere '
        'Leistungsanträge - kostenlos und ohne Abo.'
        '</p></div>',
        unsafe_allow_html=True,
    )
    #wieder die Streamlit Funktion, damit alles angezeigt wird 
    #"Kostenlos starten" -> kleiner Text über der Überschrift
    #"Konto bei Nela erstellen" -> große Hauptüberschrift
    #<p> -> grauer Werbetext darunter mit den drei Vorteilen
    
    cols = st.columns([1, 2, 1])
    with cols[1]:
        #Drei Spalten und die in der Mitte ist wieder doppelt so breit 
        #macht man, damit alles zentriert ist 

        col_v, col_n = st.columns(2)
        with col_v:
            vor = st.text_input("Vorname", key="reg_vorname",
                                 placeholder="Anna")
        with col_n:
            nach = st.text_input("Nachname", key="reg_nachname",
                                  placeholder="Müller")
    #Vorname und Nachname nebeneinander 
        #auch in 2 gleich breiten Spalten 
    #placeholder ist der graue Hinweistext der verschwindet sobald man tippt
        email = st.text_input("E-Mail-Adresse", key="reg_email",
                               placeholder="anna.müller@example.de")
    #Eingabefeld für die Email 
        #ein Feld, nicht wie oben drüber bei den Namen 
        pw1 = st.text_input("Passwort (mind. 8 Zeichen)",
                             type="password", key="reg_pw1")
    #Erstes Passwortfeld 
    #Zeigt Punkte anstelle von Buchstaben 
    #key="reg_pw1" ist der interne Name 
    #für Streamlit ist die Unterscheidung zwischen pw1 und pw2 wichtig 

        bewertung = _passwort_staerke_bewerten(pw1 or "")
        st.markdown(
            _passwort_staerke_indikator_html(bewertung),
            unsafe_allow_html=True,
        )
    #Live-Passwort-Balken 
    #Bei jeder neuen Eingabe wird pw1 neu bewertet
        #damit der Balken aktualisiert wird
    #pw1 or "" = falls das Feld leer ist, übergib einen leeren Text 
        pw2 = st.text_input("Passwort wiederholen",
                             type="password", key="reg_pw2")
    #zweite Passworteingabe 
    #damit wird sichergestellt, dass sich der Nutzer nicht vertippt hat 
        agb = st.checkbox(
            "Ich akzeptiere die Datenschutzerklärung und die AGB.",
            key="reg_agb",
        )
    #Box, ein kleines Kästchen, dass man abhaken kann 
    #agb ist true wenn der haken gesetzt wurde 
    #false wenn nicht 
    #ohne Haken keine Registrierung
        ok = st.button("Konto erstellen",
                        key="reg_submit",
                        type="primary",
                        use_container_width=True)
    #Grüner Absende-Knopf
    #st.button statt st.form_submit_button
        #weil hier kein st.form benutzt wird 
    #True wenn gedrückt wurde 

        if ok:
            v_c = (vor or "").strip()
            n_c = (nach or "").strip()
            e_c = (email or "").strip().lower()
    #Wenn der Knopf gedrückt wurde 
        #or "" = falls ein Feld leer ist, nimm einen leeren Text 
        #.strip() = Leerzeichen am Anfang und Ende weg 
        #.lower() = Email wird wieder kleingeschrieben 
            if not all([v_c, n_c, e_c, pw1, pw2]):
                st.error("Bitte füllen Sie alle Pflichtfelder aus.")
        #all([...]) prüft ob alle Felder ausgefüllt sin d
        #Falls eins leer ist -> Fehlermeldung 
        #not all = falls nicht alle ausgefüllt sind 
            elif not re.fullmatch(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", e_c, re.I):
                st.error("Bitte geben Sie eine gültige E-Mail-Adresse ein.")
        #Prüft, ob E-Mail das richtige Format hat 
        #Ob ein @ dabei ist und ein Punkt danach 
        #Passt da was nicht, wieder Fehlermeldung 
            elif len(pw1) < 8:
                st.error("Das Passwort muss mindestens 8 Zeichen lang sein.")
            elif pw1 != pw2:
                st.error("Die Passwörter stimmen nicht überein.")
            elif not agb:
                st.error("Bitte akzeptieren Sie Datenschutzerklärung und AGB.")
        #Drei Prüfungen hintereinander 
        #Elif -> nur prüfen, falls die Prüfung davor oke war 
            #Passwort zu kurz 
            #Passwörter unterschiedlich 
            #Checkbox nicht angehakelt 
            elif not nutzer_anlegen(v_c, n_c, e_c, pw1):
                st.error("Diese E-Mail ist bereits registriert. "
                         "Bitte melden Sie sich stattdessen an.")
        #Erst jetzt wird "nutzer_anlegen" Funktion vom Block davor aufgerufen 
        #Falls False kommt, email schon vergeben
            else:
                st.session_state["anmeldung_eingeloggt"] = True
                st.session_state["anmeldung_email"]     = e_c
                _auth_leistungscheck_uebernehmen()
                st.session_state["aktuelle_seite"] = "dashboard"
                st.session_state["auth_modus"]    = None
                st.rerun()
        #Alles ist tiptop 
        #Direkt einloggen und zum Dashboard weiterleiten 
        #Leistungscheck-Ergebnis wird gerettet 
        
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        #Unsichtbarer Abstandhalter wieder 

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Bereits Konto? Anmelden",
                         key="reg_zu_login",
                         use_container_width=True):
                st.session_state["auth_modus"] = "login"
                st.rerun()
        with c2:
            if st.button("Zurück zur Startseite",
                         key="reg_zurueck",
                         use_container_width=True):
                st.session_state["auth_modus"] = None
                st.rerun()
        #zwei Knöpfe nebeneinander unter dem Formular, deswegen wieder c1 und c2 
        #Links: Wechselt zum Login-Formular
        #Rechts: zurück zur Startseite  
        
#Allgemein für mich: 
    #st.return() ist richtig wichtig 
    #die App lädt dann immer neu 
    #da Streamlit so funktioniert: also immer den Code von oben nach unten zu durchlaufen 

    #Nina Ende 
# ============================================================
# 7) LANDINGPAGE
# ============================================================
#
# Wichtig: Wir umschliessen NIEMALS Streamlit-Widgets mit HTML.
# Jeder Bereich ist entweder:
#   a) reines HTML in EINEM st.markdown() (Sections, Hero-Visual, Footer)
#   b) eine Streamlit-Widget-Reihe (Buttons in st.columns)
# Beide wechseln sich ab, aber überlappen sich nicht.


def landing_topnav_html() -> None:
    """Horizontale Navigationsleiste: Logo | Nav-Links | Anmelden | Registrieren.

    -Layout: 4 Spalten (3:5:1:1) vertikal zentriert.
    -Brand + Nav als HTML mit bestehenden Klassen.
    -Auth-Buttons sind echte Streamlit-Buttons in rechten Spalten.
    -Marker .nela-topnav-marker triggert CSS für Button-Styling.
    -Scroll-Links mit smooth-Behavior zu Seiten-Ankern.
    -Klick auf Auth-Button setzt session_state und triggert rerun.
    """
    col_logo, col_nav, col_login, col_reg = st.columns(
        [3, 5, 1, 1],
        vertical_alignment="center",
    )
    with col_logo:
        st.markdown(
            '<span class="nela-topnav-marker" aria-hidden="true" '
            'style="display:none"></span>'
            '<a class="nela-brand" href="#top">'
            '<span class="nela-brand-text">'
            '<span class="nela-brand-name">Nela</span>'
            '<span class="nela-brand-tagline">Unterstützung, wenn sie zählt</span>'
            '</span></a>',
            unsafe_allow_html=True,
        )
    with col_nav:
        st.markdown(
            '<nav class="nela-topnav-links" style="justify-content:flex-end;">'
            '<a href="#module" onclick="'
            "var e=document.getElementById('module');"
            "if(e){e.scrollIntoView({behavior:'smooth',block:'start'});return false;}"
            '">Module</a>'
            '<a href="#vergleich" onclick="'
            "var e=document.getElementById('vergleich');"
            "if(e){e.scrollIntoView({behavior:'smooth',block:'start'});return false;}"
            '">Vergleich</a>'
            '<a href="#rechner" onclick="'
            "var e=document.getElementById('rechner');"
            "if(e){e.scrollIntoView({behavior:'smooth',block:'start'});return false;}"
            '">Pflegegrad-Rechner</a>'
            '<a href="#leistung" onclick="'
            "var e=document.getElementById('leistung');"
            "if(e){e.scrollIntoView({behavior:'smooth',block:'start'});return false;}"
            '">Leistungslücken</a>'
            '</nav>',
            unsafe_allow_html=True,
        )
    with col_login:
        if st.button("Anmelden", key="nav_login", use_container_width=True):
            st.session_state["auth_modus"] = "login"
            st.rerun()
    with col_reg:
        if st.button("Registrieren", key="nav_register",
                     type="primary",
                     use_container_width=True):
            st.session_state["auth_modus"] = "register"
            st.rerun()


def landing_hero_html() -> None:
    """Hero-Sektion als reiner HTML-Block."""
    st.markdown(
        '<section class="nela-hero nela-fullbleed" id="top">'
        '<div class="nela-section-inner">'
        '<div class="nela-hero-grid">'

        # Linke Spalte: Text
        '<div>'
        '<span class="nela-eyebrow" style="text-transform:none; letter-spacing:0.3px;">'
        'Für pflegende Angehörige</span>'
        '<h1 class="nela-hero-headline">'
        'Sie sorgen für Ihre Eltern.<br>'
        '<span class="akzent">Den Papierkram übernehmen wir.</span>'
        '</h1>'
        '<p class="nela-hero-sub">'
        'Jedes Jahr lassen Familien Geld liegen, das ihnen zusteht '
        '&mdash; weil das System überfordert. Nela zeigt Ihnen in 5 Minuten, '
        'was Ihrer Familie wirklich zusteht.'
        '</p>'
        '<div class="nela-hero-trust">'
        '<span><span class="nela-hero-check">&#x2713;</span> Kostenfrei nutzbar</span>'
        '<span><span class="nela-hero-check">&#x2713;</span> Keine Werbung</span>'
        '<span><span class="nela-hero-check">&#x2713;</span> 5 Minuten bis zum Ergebnis</span>'
        '</div>'
        '</div>'

        # Rechte Spalte: Hero-Card
        '<div class="nela-hero-visual">'
        '<div class="nela-hero-card">'
        '<div class="nela-hero-card-label">Ihre persönliche Geldlücke</div>'
        '<div class="nela-hero-card-headline">So könnte Ihr Leistungscheck aussehen:</div>'
        '<div class="nela-hero-amount">2.847 &euro;</div>'
        '<div class="nela-hero-amount-sub">werden pro Jahr ungenutzt liegen gelassen</div>'
        '<div class="nela-hero-step">'
        '<span class="nela-hero-check">&#x2713;</span> Entlastungsbetrag &mdash; 1.572 &euro;'
        '</div>'
        '<div class="nela-hero-step">'
        '<span class="nela-hero-check">&#x2713;</span> Verhinderungspflege &mdash; 1.275 &euro;'
        '</div>'
        '<div class="nela-hero-step">'
        '<span class="nela-hero-check">&#x2713;</span> Direkt von der Pflegekasse bezahlt'
        '</div>'
        '</div></div>'

        '</div></div></section>',
        unsafe_allow_html=True,
    )


def landing_hero_buttons() -> None:
    """2 Buttons unter dem Hero: "In 5 Min. herausfinden" + "Konto erstellen".

    Button 1 → scrollt zum Rechner (kein Login nötig).
    Button 2 → öffnet Registrierung (session_state + rerun).
    Farbband davor verlängert Hero-Hintergrund visuell nach unten.
    Ohne Band würden Buttons auf weißem Hintergrund schweben.
    """
    # Hintergrund-Band, das die Hero-Section visuell fortsetzt
    st.markdown(
        '<div class="nela-band nela-band-hero"></div>',
        unsafe_allow_html=True,
    )

    spacer, c1, c2, c3 = st.columns([5, 3, 3, 5])
    with c1:
        # spacer regelt abstände der Buttons
        # Pflegegrad Button:
        st.markdown(
            '<a href="#rechner" onclick="'
            "var e=document.getElementById('rechner');"
            "if(e){e.scrollIntoView({behavior:'smooth',block:'start'});return false;}"
            '" style="'
            'display:block; text-align:center; padding:12px 22px; '
            'border-radius:9px; border:1.5px solid #E8B877; '
            'color:#1A2E0D; text-decoration:none; font-weight:700; '
            "font-family:'DM Sans', sans-serif; font-size:15px; "
            'background:#FFE5B4; transition:all 0.18s ease; '
            'cursor:pointer; '
            'box-shadow:0 4px 14px -4px rgba(232,184,119,0.45);">'
            'In 5 Minuten herausfinden'
            '</a>',
            unsafe_allow_html=True,
        )
    with c2:
        # Login Button:
        if st.button("Kostenloses Konto erstellen",
                     key="hero_register",
                     use_container_width=True):
            st.session_state["auth_modus"] = "register"
            st.rerun()


def landing_stats_html() -> None:
    """-Stats-Streifen unter dem Hero teil"""
    st.markdown(
        '<section class="nela-stats nela-fullbleed">'
        '<div class="nela-section-inner">'
        '<div class="nela-stats-grid">'
        '<div class="nela-stat">'
        '<div class="nela-stat-zahl">7,1 Mio.</div>'
        '<div class="nela-stat-label">Menschen pflegen Angehörige in Deutschland</div>'
        '</div>'
        '<div class="nela-stat">'
        '<div class="nela-stat-zahl">5.111&nbsp;&euro;</div>'
        '<div class="nela-stat-label">stehen pro Jahr und Familie zu</div>'
        '</div>'
        '<div class="nela-stat">'
        '<div class="nela-stat-zahl">~70&nbsp;%</div>'
        '<div class="nela-stat-label">davon werden nicht abgerufen</div>'
        '</div>'
        '<div class="nela-stat">'
        '<div class="nela-stat-zahl">15,6 Mrd.&nbsp;&euro;</div>'
        '<div class="nela-stat-label">verfallen so jährlich ungenutzt</div>'
        '</div>'
        '</div></div></section>',
        unsafe_allow_html=True,
    )


def landing_module_html() -> None:
    """4 Modul-Karten mit SVG-Icons."""
    st.markdown(
        '<section class="nela-section nela-section-warm nela-fullbleed" id="module">'
        '<div class="nela-section-inner">'
        '<div class="nela-section-head">'
        '<span class="nela-section-eyebrow">So unterstützt Sie Nela</span>'
        '<h2 class="nela-section-title">Die gesamte Pflege-Kette in einer Plattform</h2>'
        '<p class="nela-section-sub">'
        'Vier ineinandergreifende Module &mdash; vom ersten Leistungscheck bis '
        'zur kassendirekt abgerechneten Hilfe vor Ort. Kein anderer Anbieter '
        'im Markt schliesst diesen Weg vollständig.'
        '</p></div>'

        '<div class="nela-modul-grid">'

        '<div class="nela-modul"><span class="nela-modul-nr">01</span>'
        '<div class="nela-modul-icon">'
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>'
        '</svg></div>'
        '<h3>Leistungscheck</h3>'
        '<p>5-Minuten-Analyse mit konkretem Eurobetrag: '
        '&laquo;Sie lassen 2.847 EUR / Jahr ungenutzt.&raquo; '
        'Sofort sichtbarer Mehrwert.</p>'
        '</div>'

        '<div class="nela-modul"><span class="nela-modul-nr">02</span>'
        '<div class="nela-modul-icon">'
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        '<polyline points="14 2 14 8 20 8"/>'
        '<line x1="9" y1="15" x2="15" y2="15"/>'
        '<line x1="9" y1="11" x2="15" y2="11"/>'
        '</svg></div>'
        '<h3>Antragstellung</h3>'
        '<p>Formulare automatisch vorbefüllt, Einreichung bei der Pflegekasse, '
        'Fristenalarm zum 30. Juni - kein Papierkram für Sie.</p>'
        '</div>'

        '<div class="nela-modul"><span class="nela-modul-nr">03</span>'
        '<div class="nela-modul-icon">'
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>'
        '<circle cx="8.5" cy="7" r="4"/>'
        '<path d="M20 8v6"/><path d="M23 11h-6"/>'
        '</svg></div>'
        '<h3>Helfer-Marktplatz</h3>'
        '<p>Landesrechtlich anerkannte Anbieter mit Direktabrechnung bei der '
        'Kasse. Kein Vorstrecken, keine Belege für Ihre Familie.</p>'
        '</div>'

        '<div class="nela-modul"><span class="nela-modul-nr">04</span>'
        '<div class="nela-modul-icon">'
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M3 21h18"/><path d="M5 21V7l8-4v18"/><path d="M19 21V11l-6-4"/>'
        '</svg></div>'
        '<h3>B2B für Arbeitgeber</h3>'
        '<p>Mitarbeiterlizenz mit HR-Dashboard und ESG-Reporting. '
        '43 % der Pflegenden sind berufstätig &mdash; ein messbares '
        'Retention-Instrument.</p>'
        '</div>'

        '</div></div></section>',
        unsafe_allow_html=True,
    )


def landing_vergleich_html() -> None:
    """Vergleichstabelle aus Businessplan."""
    st.markdown(
        '<section class="nela-section nela-section-soft nela-fullbleed" id="vergleich">'
        '<div class="nela-section-inner">'
        '<div class="nela-section-head">'
        '<span class="nela-section-eyebrow">Im Direktvergleich</span>'
        '<h2 class="nela-section-title">Was Nela anders macht</h2>'
        '<p class="nela-section-sub">'
        'Sechs Fähigkeiten, von denen keine bei einem einzelnen Wettbewerber '
        'vollständig vorhanden ist. Nela schliesst den End-to-End-Flow im '
        'Markt der pflegenden Angehörigen.'
        '</p></div>'

        '<div class="nela-vergleich-wrap">'
        '<table class="nela-vergleich">'
        '<thead><tr>'
        '<th>Fähigkeit</th>'
        '<th>Nui Care</th><th>Perulatus</th><th>fabel</th>'
        '<th class="nela-spalte">Nela</th>'
        '</tr></thead><tbody>'

        '<tr><td>Leistungscheck mit Eurobetrag</td>'
        '<td class="yes">&#x2713;</td><td class="no">&#x2717;</td>'
        '<td class="partial">teilw.</td><td class="yes col-us">&#x2713;</td></tr>'

        '<tr><td>Automatisierte Antragstellung</td>'
        '<td class="yes">&#x2713;</td><td class="partial">teilw.</td>'
        '<td class="no">&#x2717;</td><td class="yes col-us">&#x2713;</td></tr>'

        '<tr><td>Lokaler Helfer-Marktplatz</td>'
        '<td class="partial">teilw.</td><td class="no">&#x2717;</td>'
        '<td class="no">&#x2717;</td><td class="yes col-us">&#x2713;</td></tr>'

        '<tr><td>Kassendirektabrechnung</td>'
        '<td class="no">&#x2717;</td><td class="no">&#x2717;</td>'
        '<td class="no">&#x2717;</td><td class="yes col-us">&#x2713;</td></tr>'

        '<tr><td>B2B Enterprise-Modul</td>'
        '<td class="no">&#x2717;</td><td class="no">&#x2717;</td>'
        '<td class="no">&#x2717;</td><td class="yes col-us">&#x2713;</td></tr>'

        '<tr><td>Vorsorge- und Todesfall-Segment</td>'
        '<td class="no">&#x2717;</td><td class="no">&#x2717;</td>'
        '<td class="no">&#x2717;</td><td class="yes col-us">&#x2713;</td></tr>'

        '</tbody></table>'
        '</div></div></section>',
        unsafe_allow_html=True,
    )


def landing_leistungscheck_section() -> None:
    """Pflegegrad-Rechner auf der Startseite — kein Login nötig.

    -Zeigt Section-Kopf + ruft leistungscheck_anzeigen(eingeloggt=False) auf.
    -Am Ende: Conversion-Box mit "Jetzt registrieren"-Button.
    -Anker id="rechner" — hierher springen Topnav, Hero-Button und Footer.
    """
    st.markdown(
        '<div id="rechner"></div>'
        '<div class="nela-section nela-section-warm nela-fullbleed">'
        '<div class="nela-section-inner">'
        '<div class="nela-section-head">'
        '<span class="nela-section-eyebrow">In 5 Minuten zum Ergebnis</span>'
        '<h2 class="nela-section-title">Welcher Pflegegrad ist wahrscheinlich?</h2>'
        '<p class="nela-section-sub">'
        'Beantworten Sie 7 kurze Fragen zur täglichen Situation der '
        'pflegebedürftigen Person. Sie erhalten eine fundierte erste '
        'Einschätzung &mdash; vollkommen kostenfrei und ohne Anmeldung.'
        '</p></div></div></div>',
        unsafe_allow_html=True,
    )

    # Rechner zentriert in einer Spalte (ohne extra Card-Wrapper:
    # 
    # Code Verweißt auf den leistungscheck rechner, dessen code weiter oben steht
    sp_l, mid, sp_r = st.columns([1, 6, 1])
    with mid:
        leistungscheck_anzeigen(eingeloggt=False)


def landing_leistung_section() -> None:
    """Leistungslücken-Vorschau."""
    st.markdown(
        '<section class="nela-section nela-section-soft nela-fullbleed" id="leistung">'
        '<div class="nela-section-inner">'
        '<div class="nela-section-head">'
        '<span class="nela-section-eyebrow">Nächster Schritt</span>'
        '<h2 class="nela-section-title">Ihre konkrete Geldlücke in Euro</h2>'
        '<p class="nela-section-sub">'
        'Mit dem Leistungslücken-Rechner berechnen wir, wieviel Geld Ihre '
        'Familie pro Jahr ungenutzt liegen lässt. Persönlich, transparent '
        'und nach Pflegegrad aufgeschlüsselt.'
        '</p></div>'

        '<div class="nela-vorschau">'
        '<div class="nela-vorschau-badge">Beispiel</div>'
        '<div class="nela-vorschau-eyebrow">So sieht Ihr Ergebnis aus</div>'
        '<div class="nela-vorschau-amount">2.847 &euro;</div>'
        '<div class="nela-vorschau-label">'
        'werden bei Ihnen pro Jahr ungenutzt liegen gelassen'
        '</div>'

        '<div class="nela-vorschau-grid">'
        '<div class="nela-vorschau-item">'
        '<div class="nela-vorschau-item-label">Entlastungsbetrag</div>'
        '<div class="nela-vorschau-item-value">1.572 &euro;</div>'
        '</div>'
        '<div class="nela-vorschau-item">'
        '<div class="nela-vorschau-item-label">Verhinderungspflege</div>'
        '<div class="nela-vorschau-item-value">1.275 &euro;</div>'
        '</div>'
        '<div class="nela-vorschau-item">'
        '<div class="nela-vorschau-item-label">Pflegehilfsmittel</div>'
        '<div class="nela-vorschau-item-value">~480 &euro;</div>'
        '</div>'
        '</div>'

        '<div class="nela-vorschau-hint">'
        'Melden Sie sich an, um Ihre persönliche Geldlücke zu berechnen.'
        '</div>'
        '</div></div></section>',
        unsafe_allow_html=True,
    )

    # UX: Band verlängert die Leistung-Section-Farbe (HG_HELL), sodass
    # der CTA-Button optisch in der Section sitzt statt auf weißem Übergang.
    st.markdown(
        '<div class="nela-band nela-band-soft"></div>',
        unsafe_allow_html=True,
    )

    # CTA-Button: erzwingt Registrierung
    sp_l, mid, sp_r = st.columns([3, 2, 3])
    with mid:
        if st.button("Geldlücke jetzt berechnen",
                     key="vorschau_leistung_cta",
                     type="primary",
                     use_container_width=True):
            st.session_state["auth_modus"] = "register"
            st.rerun()


def landing_cta_section_html() -> None:
    """Grosse CTA-Section vor dem Footer. Texte als HTML, Buttons separat."""
    st.markdown(
        '<section class="nela-cta nela-fullbleed">'
        '<div class="nela-section-inner">'
        '<h2 class="nela-cta-headline">Bereit, Ihre Geldlücke zu schliessen?</h2>'
        '<p class="nela-cta-sub">'
        'Erstellen Sie jetzt Ihr kostenloses Nela-Konto. Sie behalten Ihre '
        'Daten, erhalten Erinnerungen vor wichtigen Fristen und nutzen unsere '
        'Leistungsanträge.'
        '</p></div></section>',
        unsafe_allow_html=True,
    )

    # UX: Band verlängert die dunkle CTA-Section-Farbe, damit die Buttons
    # nahtlos in der dunklen Section sitzen statt auf weißer Brücke.
    st.markdown(
        '<div class="nela-band nela-band-cta"></div>',
        unsafe_allow_html=True,
    )

    # Buttons in eigener Reihe, mittig, weiss-auf-grun-Stil über CSS
    sp_l, c1, c2, sp_r = st.columns([3, 2, 2, 3])
    with c1:
        if st.button("Kostenloses Konto erstellen",
                     key="cta_register",
                     type="primary",
                     use_container_width=True):
            st.session_state["auth_modus"] = "register"
            st.rerun()
    with c2:
        if st.button("Bereits Konto - Anmelden",
                     key="cta_login",
                     use_container_width=True):
            st.session_state["auth_modus"] = "login"
            st.rerun()


def landing_footer_html() -> None:
    """Footer mit 4 Spalten."""
    st.markdown(
        '<footer class="nela-footer nela-fullbleed">'
        '<div class="nela-section-inner">'
        '<div class="nela-footer-cols">'

        '<div>'
        '<div class="nela-footer-brand">Nela</div>'
        '<div class="nela-footer-tagline">Unterstützung, wenn sie zählt.</div>'
        '<p class="nela-footer-text">'
        'Nela ist eine KI-gestützte Entlastungsplattform für pflegende '
        'Angehörige in Deutschland. Wir begleiten Sie von der ersten Frage '
        'bis zur bezahlten Hilfe vor Ort.'
        '</p></div>'

        '<div>'
        '<div class="nela-footer-col-title">Produkt</div>'
        '<a class="nela-footer-link" href="#module">Module</a>'
        '<a class="nela-footer-link" href="#rechner">Pflegegrad-Rechner</a>'
        '<a class="nela-footer-link" href="#leistung">Leistungslücken</a>'
        '<a class="nela-footer-link" href="#vergleich">Vergleich</a>'
        '</div>'

        '<div>'
        '<div class="nela-footer-col-title">Unternehmen</div>'
        '<a class="nela-footer-link" href="#">Über Nela</a>'
        '<a class="nela-footer-link" href="#">Für Arbeitgeber</a>'
        '<a class="nela-footer-link" href="#">Presse</a>'
        '<a class="nela-footer-link" href="#kontakt">Kontakt</a>'
        '</div>'

        # Rechtliches: nur Überschrift – die anklickbaren Buttons rendern
        # wir direkt darunter als echte Streamlit-Buttons (sonst kein
        # session_state-Wechsel möglich). Visuell als Footer-Links gestylt.
        '<div>'
        '<div class="nela-footer-col-title">Rechtliches</div>'
        '<div id="nela-legal-anker"></div>'
        '</div>'

        '</div>'
        '<div class="nela-footer-bottom">'
        '<div>&copy; 2026 Nela &middot; Alle Rechte vorbehalten</div>'
        '<div>Quellen: Statistisches Bundesamt &middot; pflege.de '
        '&middot; Roland Berger &middot; BMG</div>'
        '</div></div></footer>',
        unsafe_allow_html=True,
    )

    # Rechtliches: echte Buttons als unauffällige Text-Links unten zentriert.
    # Eigener kleiner Bereich, da Streamlit-Buttons nicht im HTML-Footer
    # eingebettet werden können.
    _footer_rechtliches_buttons()


def _footer_rechtliches_buttons() -> None:
    """3 Buttons im Footer: Datenschutz | AGB | Impressum.

    -Sitzen optisch IM dunklen Footer via nela-band-footer.
    -Klick setzt session_state → rerun → zeigt jeweilige Rechtsseite.
    -Spalten [3, 1.4, 1.4, 1.4, 3] — Buttons mittig zentriert.
    """
    # Band-Footer verlängert die dunkle Footer-Farbe nach unten;
    # die folgende Button-Reihe sitzt visuell darin.
    st.markdown(
        '<div class="nela-band nela-band-footer"></div>',
        unsafe_allow_html=True,
    )
    sp_l, c1, c2, c3, sp_r = st.columns([3, 1.4, 1.4, 1.4, 3])
    with c1:
        if st.button("Datenschutz", key="footer_dse",
                     use_container_width=True):
            st.session_state["auth_modus"] = "datenschutz"
            st.rerun()
    with c2:
        if st.button("AGB", key="footer_agb",
                     use_container_width=True):
            st.session_state["auth_modus"] = "agb"
            st.rerun()
    with c3:
        if st.button("Impressum", key="footer_impressum",
                     use_container_width=True):
            st.session_state["auth_modus"] = "impressum"
            st.rerun()


def landing_kontakt_html() -> None:
    """Kontakt-Section: kompakter Bereich oberhalb des Footers (User Story 6).

    Zeigt eine Kurzinfo + die Support-Mailadresse als klickbaren mailto-Link.
    """
    st.markdown(
        '<section id="kontakt" class="nela-section nela-section-warm nela-fullbleed">'
        '<div class="nela-section-inner">'
        '<div style="max-width:680px; margin:0 auto; text-align:center;">'
        '<span class="nela-section-eyebrow">Kontakt</span>'
        '<h2 class="nela-section-title">Sie haben Fragen oder brauchen Hilfe?</h2>'
        '<p class="nela-section-sub">'
        'Unser Support-Team antwortet werktags innerhalb von 24 Stunden. '
        'Schreiben Sie uns gerne direkt – wir sind für Sie da.'
        '</p>'
        '<div style="margin-top:26px;">'
        '<a href="mailto:support@nela.de" '
        f'style="display:inline-flex; align-items:center; gap:10px; '
        f'background:#FFFFFF; border:1.5px solid {PRIMAER}; '
        f'color:{PRIMAER}; padding:14px 28px; border-radius:10px; '
        f'font-family:DM Sans, sans-serif; font-weight:700; font-size:16px; '
        f'text-decoration:none; transition:all 0.18s ease; cursor:pointer; '
        f'box-shadow:0 2px 8px -4px rgba(46,125,50,0.15);">'
        '<span style="font-size:18px;">✉</span>'
        '<span>support@nela.de</span>'
        '</a>'
        '</div>'
        f'<div style="font-size:13px; color:{TEXT_GRAU}; margin-top:18px;">'
        'Klicken Sie auf die Adresse, um Ihr E-Mail-Programm zu öffnen.'
        '</div>'
        '</div></div></section>',
        unsafe_allow_html=True,
    )


def _legal_seite_kopf(titel: str, untertitel: str) -> None:
    """Einheitlicher Kopf für Datenschutz/AGB/Impressum."""
    st.markdown(
        '<div class="nela-app-heading">'
        f'<span class="nela-section-eyebrow">Rechtliches</span>'
        f'<h1>{html.escape(titel)}</h1>'
        f'<p>{html.escape(untertitel)}</p>'
        '</div>',
        unsafe_allow_html=True,
    )


def _legal_zurueck_button(eingeloggt: bool) -> None:
    """Zurück-Button am Ende einer Legal-Seite."""
    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    if eingeloggt:
        if st.button("Zurück zum Dashboard",
                     key="legal_zurueck_app",
                     use_container_width=False):
            st.session_state["aktuelle_seite"] = "dashboard"
            st.rerun()
    else:
        if st.button("Zurück zur Startseite",
                     key="legal_zurueck_landing",
                     use_container_width=False):
            st.session_state["auth_modus"] = None
            st.rerun()


def seite_datenschutz(eingeloggt: bool) -> None:
    """Datenschutzerklärung (User Story 3)."""
    if eingeloggt:
        _app_zurueck_dashboard_button()
    _legal_seite_kopf(
        "Datenschutzerklärung",
        "Wir verarbeiten Ihre Daten nur, soweit dies für den Betrieb von Nela "
        "erforderlich ist – und stets nach Maßgabe der DSGVO."
    )
    st.markdown(
        '<div class="nela-modul" style="max-width:860px;">'
        '<h3 style="margin-top:0;">1. Verantwortlicher</h3>'
        '<p>Verantwortlich für die Datenverarbeitung auf dieser Plattform '
        'ist die Nela GmbH (in Gründung). Kontakt: '
        '<a href="mailto:support@nela.de">support@nela.de</a>.</p>'

        '<h3>2. Welche Daten wir verarbeiten</h3>'
        '<p>Wir verarbeiten ausschließlich die Daten, die Sie uns aktiv '
        'mitteilen: Vor- und Nachname, E-Mail-Adresse, gehashtes Passwort, '
        'Ihre Antworten im Pflegegrad-Rechner sowie das errechnete Ergebnis. '
        'Es gibt keine Tracker, kein Profiling und keine Weitergabe an Dritte.</p>'

        '<h3>3. Zwecke der Verarbeitung</h3>'
        '<p>Ihre Daten dienen ausschließlich dazu, Ihnen die Pflegegrad- und '
        'Leistungs-Einschätzung anzuzeigen, Ergebnisse in Ihrem Profil zu '
        'speichern und Sie an Fristen zu erinnern. Eine Verarbeitung zu '
        'Werbezwecken findet nicht statt.</p>'

        '<h3>4. Rechtsgrundlage</h3>'
        '<p>Art. 6 Abs. 1 lit. a DSGVO (Einwilligung) und lit. b DSGVO '
        '(Erfüllung des Nutzungsvertrags).</p>'

        '<h3>5. Speicherdauer</h3>'
        '<p>Wir speichern Ihre Daten so lange, wie Ihr Nutzer-Konto existiert. '
        'Mit der vollständigen Löschung Ihres Kontos (siehe Profil) werden '
        'alle personenbezogenen Daten unwiderruflich entfernt.</p>'

        '<h3>6. Ihre Rechte</h3>'
        '<p>Sie haben jederzeit das Recht auf Auskunft, Berichtigung, '
        'Löschung, Einschränkung der Verarbeitung und Datenübertragbarkeit. '
        'Sie können Ihre Einwilligungen jederzeit in Ihrem Profil widerrufen '
        'und Ihren Account vollständig löschen.</p>'

        '<h3>7. Kontakt für Datenschutzfragen</h3>'
        '<p>Bei Fragen zum Datenschutz wenden Sie sich an '
        '<a href="mailto:support@nela.de">support@nela.de</a>.</p>'

        '<p style="font-size:12px; color:#888; margin-top:24px;">'
        'Stand: 2026. Stellt eine vereinfachte Studien-Fassung dar.'
        '</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    _legal_zurueck_button(eingeloggt)


def seite_agb(eingeloggt: bool) -> None:
    """Allgemeine Geschäftsbedingungen (User Story 3)."""
    if eingeloggt:
        _app_zurueck_dashboard_button()
    _legal_seite_kopf(
        "Allgemeine Geschäftsbedingungen (AGB)",
        "Die Bedingungen, unter denen Sie Nela nutzen können."
    )
    st.markdown(
        '<div class="nela-modul" style="max-width:860px;">'
        '<h3 style="margin-top:0;">§ 1 Geltungsbereich</h3>'
        '<p>Diese AGB gelten für die Nutzung der Plattform Nela durch '
        'natürliche Personen (im Folgenden „Nutzer:innen“).</p>'

        '<h3>§ 2 Leistungen</h3>'
        '<p>Nela stellt einen kostenlosen Pflegegrad-Rechner, einen '
        'Leistungs-Check und Informationen zu Pflegeleistungen bereit. '
        'Die Ergebnisse sind unverbindliche Einschätzungen und ersetzen '
        'keine offizielle Begutachtung des Medizinischen Dienstes.</p>'

        '<h3>§ 3 Registrierung</h3>'
        '<p>Die Registrierung ist kostenlos. Mit der Registrierung bestätigen '
        'Sie, dass Sie volljährig sind und die angegebenen Daten korrekt sind.</p>'

        '<h3>§ 4 Pflichten der Nutzer:innen</h3>'
        '<p>Sie verpflichten sich, Ihre Zugangsdaten vertraulich zu behandeln '
        'und die Plattform nicht zu missbräuchlichen Zwecken zu verwenden.</p>'

        '<h3>§ 5 Haftung</h3>'
        '<p>Nela haftet ausschließlich für Schäden aus Vorsatz oder grober '
        'Fahrlässigkeit. Die Berechnungen erfolgen nach bestem Wissen, sind '
        'aber unverbindlich.</p>'

        '<h3>§ 6 Kündigung</h3>'
        '<p>Sie können Ihr Konto jederzeit ohne Frist über Ihr Profil löschen. '
        'Damit endet die Nutzungsbeziehung sofort.</p>'

        '<h3>§ 7 Änderungen</h3>'
        '<p>Wir behalten uns vor, diese AGB anzupassen. Wesentliche Änderungen '
        'werden Ihnen rechtzeitig per E-Mail mitgeteilt.</p>'

        '<h3>§ 8 Schlussbestimmungen</h3>'
        '<p>Es gilt deutsches Recht. Gerichtsstand ist – soweit zulässig – '
        'der Sitz der Nela GmbH.</p>'

        '<p style="font-size:12px; color:#888; margin-top:24px;">'
        'Stand: 2026. Stellt eine vereinfachte Studien-Fassung dar.'
        '</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    _legal_zurueck_button(eingeloggt)


def seite_impressum(eingeloggt: bool) -> None:
    """Impressum (Pflichtangaben TMG)."""
    if eingeloggt:
        _app_zurueck_dashboard_button()
    _legal_seite_kopf(
        "Impressum",
        "Pflichtangaben gemäß § 5 TMG."
    )
    st.markdown(
        '<div class="nela-modul" style="max-width:860px;">'
        '<h3 style="margin-top:0;">Anbieter</h3>'
        '<p>Nela GmbH (in Gründung)<br>'
        'c/o Hochschule München FK 10<br>'
        'Deutschland</p>'

        '<h3>Kontakt</h3>'
        '<p>E-Mail: <a href="mailto:support@nela.de">support@nela.de</a></p>'

        '<h3>Verantwortlich für den Inhalt</h3>'
        '<p>Das Nela-Gründungsteam</p>'

        '<h3>Haftungsausschluss</h3>'
        '<p>Alle Inhalte dienen Studien- und Demonstrationszwecken. '
        'Trotz sorgfältiger Prüfung übernehmen wir keine Gewähr für die '
        'Aktualität und Richtigkeit der Inhalte.</p>'

        '<p style="font-size:12px; color:#888; margin-top:24px;">'
        'Stand: 2026.'
        '</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    _legal_zurueck_button(eingeloggt)


def landing_page() -> None:
    """Komplette Landingpage rendern."""
    # Legal-Seiten haben Vorrang über alle anderen Modi (User Story 3)
    auth = st.session_state.get("auth_modus")
    if auth in ("datenschutz", "agb", "impressum"):
        landing_topnav_html()
        if auth == "datenschutz":
            seite_datenschutz(eingeloggt=False)
        elif auth == "agb":
            seite_agb(eingeloggt=False)
        else:
            seite_impressum(eingeloggt=False)
        st.markdown("<div style='height:60px'></div>", unsafe_allow_html=True)
        landing_footer_html()
        return

    # Bei aktivem Auth-Modus: Top-Nav + Auth-Form + Footer
    if auth == "login":
        landing_topnav_html()
        auth_form_anmelden()
        st.markdown("<div style='height:80px'></div>", unsafe_allow_html=True)
        landing_footer_html()
        return
    if auth == "register":
        landing_topnav_html()
        auth_form_registrieren()
        st.markdown("<div style='height:80px'></div>", unsafe_allow_html=True)
        landing_footer_html()
        return

    # Volle Landingpage
    landing_topnav_html()
    landing_hero_html()
    landing_hero_buttons()
    landing_stats_html()
    landing_module_html()
    landing_vergleich_html()
    landing_leistungscheck_section()
    landing_leistung_section()
    landing_cta_section_html()
    landing_kontakt_html()    # NEU: Kontakt-Section (User Story 6)
    landing_footer_html()


# ============================================================
# 8) APP-BEREICH (eingeloggt) #Nina 
# ============================================================

#Allgemein: Die Funktion zeigt die linke Seitenleiste, die jeder eingelogte Nutzer immer sieht
#Logo, Navi, Rechtlichem Namen und Logout 
def app_sidebar(nutzer: dict) -> None:
    #Funktion bekommt das komplette Nutzerprofil 
    #Damit kann es Namen und Email anzeigen
    #None, weil es nur speichert und nichts zurückgibt 
    with st.sidebar:
    #gibt an, alles was innerhalb von dem kommenden Block steht, erscheint in der linken Seitenleiste der App
        logo_uri = logo_als_data_uri()
        if logo_uri:
            st.markdown(
                f'<div style="text-align:center; padding:12px 0 4px 0;">'
                f'<img src="{logo_uri}" alt="Nela" '
                f'style="max-width:130px; height:auto;"></div>',
                unsafe_allow_html=True,
            )
        #Nela Logo wird geladen und als Bild angezeigt 
        #"max-width:130px: Maximale Breite des Bildes 
        #if logo_uri: Sicherheit, falls Logo nicht gefunden wird 
        st.markdown(
            '<div style="text-align:center; margin-bottom:20px;">'
            f'<div style="font-family:Montserrat, sans-serif; font-size:22px; '
            f'font-weight:800; color:{PRIMAER};">Nela</div>'
            f'<div style="font-size:10px; color:{TEXT_GRAU}; '
            'letter-spacing:0.5px; margin-top:2px;">'
            'Unterstützung, wenn sie zählt</div></div>',
            unsafe_allow_html=True,
        )
        #Unter dem Logo erscheint "Nela" und Tagline 
        #Rest kennzeichnet einfach die Farben und sowas 
        #was ist st.markdown? Eine Streamlit Funktion 
        #st steht für Streamlit
        #im Grunde zeigt st.markdown alles auf dem Bildschirm an, in den Farben/Größen/...wie wir es programmiert haben
        #unsafe_allow_html=True =wichtig damit der HTML-Code angezeigt wird  

        st.markdown("### Navigation")
        #Überschrift 
        # die "###" Markdown für mittelgroße Überschrift 
        nav = [
            ("dashboard", "Dashboard"),
            ("rechner",   "Pflegegrad-Rechner"),
            ("leistung",  "Leistungslücken"),
            ("profil",    "Mein Profil"),
        ]
        #Liste für die Navigationsliste 
        akt = st.session_state.get("aktuelle_seite", "dashboard")
        #Holt aus dem "Kurzzeitgedächnis" der App welche Seite gerade offen ist 
        #Falls noch keine Seite offen ist, nimmt er das dashboard automatisch 
        for s, label in nav:
            if st.button(label,
                         key="nav_app_" + s,
                         type="primary" if akt == s else "secondary",
                         use_container_width=True):
                st.session_state["aktuelle_seite"] = s
                # Bei Navigation Logout-Bestätigung zurücksetzen
                st.session_state["logout_bestaetigen"] = False
                #falls gerade der Logout-Dialog offen war, wird er geschlossen 
                st.rerun()
    # Rechtliches-Sektion (User Story 3: jederzeit einsehbar)
    # die "for" Funktion geht alle Navipunkte durch und erstellt einen Knopf 
    # type="primary" if akt == s else "secondary", = aktuell aktive Seite bekommt einen grünen Knopf, alle anderen sind grau 
    #ein Knopf wird gedrückt, aktuelle Seite wird im "Kurzzeitgedächnis" gespeichert 
    #st.return = App neu laden damit die neue Seite erscheint 
        st.markdown(
            f'<hr style="border:none; border-top:1px solid {RAHMEN_GRAU}; '
            'margin:18px 0 10px 0;">',
            unsafe_allow_html=True,
        )
        st.markdown("### Rechtliches")
        legal_nav = [
            ("datenschutz", "Datenschutz"),
            ("agb",         "AGB"),
            ("impressum",   "Impressum"),
        ]
    #horizontale Trennlinie 
        for s, label in legal_nav:
            if st.button(label,
                         key="nav_legal_" + s,
                         type="primary" if akt == s else "secondary",
                         use_container_width=True):
                st.session_state["aktuelle_seite"] = s
                st.session_state["logout_bestaetigen"] = False
                st.rerun()
        st.markdown(
            f'<hr style="border:none; border-top:1px solid {RAHMEN_GRAU}; '
            'margin:18px 0;">',
            unsafe_allow_html=True,
        ) 
    #genau gleich wie oben, nur für die rechtlichen Seiten 
        st.markdown(
            '<div style="padding:6px 4px;">'
            f'<div style="font-size:10px; color:{TEXT_GRAU}; letter-spacing:1.2px; '
            'text-transform:uppercase; margin-bottom:4px;">Angemeldet als</div>'
            f'<div style="font-family:Montserrat, sans-serif; font-size:15px; '
            f'font-weight:700; color:{HEADLINE_FARBE};">'
            f'{nutzer.get("vorname","")} {nutzer.get("nachname","")}</div>'
            f'<div style="font-size:11px; color:{TEXT_GRAU}; '
            f'word-break:break-all;">{nutzer.get("email","")}</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    #Zeigt unten in der Seitenleiste wer gerade eingeloggt ist
    # Sicherer Logout mit 2-Schritt-Bestätigung (User Story 2)
    #.get("vorname", "") = falls kein Vorname vorhanden ist, zeigt einfach nichts statt abzustürzen 
        if not st.session_state.get("logout_bestaetigen", False):
            if st.button("Abmelden", key="app_logout",
                         use_container_width=True):
                st.session_state["logout_bestaetigen"] = True
                st.rerun()
    #Normaler Logout-Knopf
    #Wenn er gedrückt wird, dann wird der Merker auf true gesetzt
    #App lädt neu 
    #der Knopf verschwindet neu und der Bestätigungsvorgang erscheint 
        else:
            st.markdown(
                '<div style="background:#FFF8E1; border:1px solid #FBC02D; '
                'border-radius:8px; padding:10px 12px; margin:8px 0; '
                'font-size:12px; color:#5D4037; line-height:1.4;">'
                'Wirklich abmelden? Sie müssen sich danach neu anmelden.'
                '</div>',
                unsafe_allow_html=True,
            )
            cc1, cc2 = st.columns(2)
            #teilt den verfügbaren Platz in 2 gleichbreite Spalten nebeneinander auf 
            with cc1:
                if st.button("Ja, abmelden", key="app_logout_ja",
                             type="primary", use_container_width=True):
                    session_logout()
                    st.rerun()
            with cc2:
                if st.button("Abbrechen", key="app_logout_nein",
                             use_container_width=True):
                    st.session_state["logout_bestaetigen"] = False
                    st.rerun()
    #Hier beginnt nämlich der Bestätigungsvorgang 
    #Gelbe Warnbox mit "Wirklich abmleden?"
    #"Ja, abmelden" -> session_logout() löscht alles aus dem Kurzzeitgedächtnis -> Nutzer ist ausgeloggt
    #"Abbrechen" -> Merker zurück auf False -> normaler Abmelden-Knopf erscheint wieder
    
#Nina Ende 

#Christian Anfang
# ============================================================
# ROADMAP – geführte Schritt-für-Schritt-Übersicht + KI-Schlachtplan
# ============================================================
#
# Zweck: Dem Nutzer (Zielgruppe 50–60 J.) ruhig und klar zeigen, wo er steht,
# was erledigt ist, was JETZT dran ist und was noch kommt. Sobald die
# Leistungslücke berechnet wurde (session_state["ergebnis"]), erscheint
# darunter der priorisierte KI-„Schlachtplan" (Top-3-Empfehlungen).
#
# Status-Logik ist rein hardcoded (state machine), KEINE KI:
#   - erledigt ✅: der session_state-Key aus "bedingung" ist truthy
#   - aktiv    👉: der erste nicht-erledigte, nicht-gesperrte Schritt
#   - offen    ⬜: alle Schritte danach
#   - bald     🔒: Schritt mit bald=True ("Bald verfügbar")

# Hardcoded Schritt-Liste. "bedingung" = Name eines session_state-Keys
# (truthy -> Schritt erledigt). "ziel" = Navigations-Ziel für den CTA des
# aktiven Schritts (Wert für st.session_state["aktuelle_seite"]).
#Hierbei handelt es sich um eine festcodierte Liste als dict = dictionary mit definierten Werten je Schlüssel, mit der chronologischen Reihenfolge anhand der Nummern, Titel ist die Headline, Bedingung sagt, was im Speicher hier existiert und wenn das erfüllt ist, wird der Schritt als erledigt angezeigt, Ziel ist der jeweilige CTA Button link. Schritt 5 und 6 existieren noch nicht daher keine Bedingung und bald ist "true" sodass das Bals verfügbar Badge angezeigt wird.
SCHRITTE = [
    {"nr": 1, "titel": "Registrieren & anmelden",     "bedingung": "eingeloggt",         "ziel": "dashboard"},
    {"nr": 2, "titel": "Pflegegrad ermitteln",         "bedingung": "pflegegrad",         "ziel": "rechner"},
    {"nr": 3, "titel": "Genutzte Leistungen angeben",  "bedingung": "leistungen_erfasst", "ziel": "leistung"},
    {"nr": 4, "titel": "Ansprüche berechnen",          "bedingung": "ergebnis",           "ziel": "leistung"},
    {"nr": 5, "titel": "Dokumente hochladen",          "bedingung": None, "bald": True},
    {"nr": 6, "titel": "Anträge generieren",           "bedingung": None, "bald": True},
]

# Beispiel-Ergebnis für den Demo-Schalter. Struktur ist IDENTISCH zu dem,
# was zeige_schlachtplan() erwartet, damit die komplette Roadmap inkl.
# Schlachtplan ohne den echten Rechner getestet werden kann.
# Hier werden folgende Demo Daten im Backend genutzt um hier eine passende Anzeige dem Nutzer bieten zu können mit einheitlichen Beiepsielen. Diese Demo-Daten werden hier nicht in der Datenbank gespeichert und sind auch nur gültig für den einen Lauf, beim refresh werden hier die Daten auf die vorherigen zurückgesetzt da diese in der Datenbank gespeichert sind.
ROADMAP_DEMO_ERGEBNIS = {
    "pflegegrad": "Pflegegrad 3", # Ist der angenommene Pflegegrad 3
    "luecke_jaehrlich": 5100, # jährliche Leistungslücke
    "empfehlungen": [ # Ist hier ein dict, Liste von Leistungen die später in den Top 3 Karten angezeigt werden
        {"titel": "Entlastungsbetrag abrufen",      "betrag_jaehrlich": 1572, # titel = Headline, betrag_jaehrlich = jährlicher Euro Betrag wird genutzt zum späteren sortieren
         "begruendung": "131 € pro Monat stehen Ihnen zu – aktuell ungenutzt."}, # begründung = Erklärtext
        {"titel": "Verhinderungspflege beantragen", "betrag_jaehrlich": 1612,
         "begruendung": "Ersatzpflege, wenn die Hauptpflegeperson einmal ausfällt."},
        {"titel": "Pflegehilfsmittel zum Verbrauch", "betrag_jaehrlich": 504,
         "begruendung": "42 € pro Monat für Handschuhe, Desinfektion und mehr."},
        {"titel": "Kurzzeitpflege nutzen",          "betrag_jaehrlich": 1774,
         "begruendung": "Vollstationäre Pflege für bis zu 8 Wochen im Jahr."},
    ],
}


# Antwortmöglichkeiten der Pflegegrad-Status-Abfrage (auch im Demo-Helper genutzt). Sind variablen und fest definierte Konstanten
ANERKANNT_JA = "Ja, ich habe einen Bescheid"
ANERKANNT_NEIN = "Nein, noch nicht"


def _euro(betrag) -> str: # nur Intern, Bei "betrag" wird hier die eingegebene Zahl verwendet, mit "-> str:" = bedeutet es wird was zurückgeliefert daher der Pfeil und der Inhalt ist ein str daher in Text-Form
    """Formatiert einen Betrag als deutschen Euro-String (Tausenderpunkt, ohne Cent)."""
    return f"{float(betrag):,.0f}".replace(",", ".") + " €"
# das f" macht hier die Inhalte von der geschweiften Klammer ausrechnenbar und einsetztbar und der jeweilige Inhalt wird dann angezeigt, nicht die Klammer.
# float(betrag) = Wandelt sie Zahl von "betrag" in eine Kommazahl um
# :,.0f = Formatierungsanweisung, -> "," ist Tausendertrennzeichen -> ".0f" zeigt 0 Nachkommastellen an und rundet aug ganze Euro auf
# .replace(",", ".") = tauscht das Komma zum Punkt
# + " €" = hängt am Ende das Euro Zeichen dran.
# Testaufruf: _euro(1612) -> "1.612 €"


def _leistung_kurzname(titel: str) -> str:
    """Reduziert eine Empfehlungs-Überschrift auf den reinen Leistungsnamen.
    Die Empfehlungs-Titel sind Aktionsphrasen ("Kurzzeitpflege nutzen",
    "Entlastungsbetrag abrufen"). Für den zeitlichen Ablaufplan brauchen wir nur
    den Leistungsnamen selbst ("Kurzzeitpflege"). Bekannte Aktions-Zusätze am
    Ende werden abgeschnitten; bleibt nichts übrig, nehmen wir den Titel.
    """
    zusaetze = (" nutzen", " beantragen", " abrufen", " zum Verbrauch",
                " anfordern", " stellen", " einrichten") # hierbei handelt es sich lediglich um eine Liste von Aktions-Endungen die abgeschnitten werden sollen
    name = titel.strip() # ".strip()" entfernt hier unsichtbare Leerzeichen am Anfang und Ende
    for zusatz in zusaetze:
        if name.endswith(zusatz):
            name = name[: -len(zusatz)].strip() # "name[: -len(zusatz)]" schneidet hier die Endung ab heißt alles außer den letzten X Zeichen
            break # Stoppt sofort, da eine Endung reicht, der Rest muss nicht mehr geprüft werden
    return name or titel.strip() # Wenn nach dem Abschneiden nichts überig bleibt, nimmt die Dunktion den Originaltitel.
# Testaufruf: _leistung_kurzname("Kurzzeitpflege nutzen") -> "Kurzzeitpflege"


def _anspruch_summe_jaehrlich(ergebnis: dict) -> int:
    """Summe der jährlichen Beträge der Top-3-Ansprüche aus dem ergebnis-dict.
    Verwendet dieselbe Sortierung wie der Schlachtplan (absteigend nach
    Jahresbetrag, nur die Top-3), damit Dashboard-Card und Schlachtplan denselben
    Wert zeigen. KEINE neue Berechnung – summiert nur die bereits im
    session_state vorhandenen betrag_jaehrlich-Werte.
    """
    top3 = sorted( # Sortiert lediglich hier die Empfehlungen
        ergebnis.get("empfehlungen", []), # holt die Empfehlungsliste, falls keine da ist kommt eine leere Liste
        key=lambda e: e.get("betrag_jaehrlich", 0), # sortiert die Liste nach den Jahresbeträgen, das "lambda" ist eine Mini-Funktion die für jede Empfehlung sagt: "Nimm betrag_jaehrlich als Sortierkriterium"
        reverse=True, # bedeutet absteigend, -> höchster Betrag zu erst
    )[:3] # Nimmmt nur die drei obersten
    return sum(int(e.get("betrag_jaehrlich", 0)) for e in top3) # geht durch die Top 3 und addiert deren Beträge, macht aus jedem Wert einen Zahl (int) und gibt die Gesamtsumme aus
# Das "e.get(...,0) und e.get(...,[]) bedeutet wenn mal ein Feld fehlt, dass die FUnktion dann einen harmlosen Standardwert nimmt und weitermacht.
# Testaufruf: _anspruch_summe_jaehrlich(ROADMAP_DEMO_ERGEBNIS) -> 4958


def _roadmap_status(schritte: list, nutzer: dict) -> list:
    """Bestimmt den Status jedes Schritts (erledigt / aktiv / offen / bald).
    Reine state machine, keine KI. Der Erledigt-Status wird deterministisch aus
    dem echten App-State (session_state + nutzer-Dict) abgeleitet – funktioniert
    daher mit UND ohne Demo-Daten. "aktiv" ist immer der erste noch nicht
    erledigte Schritt. Liefert eine Liste von (schritt, status)-Tupeln.
    """
    erledigt_nach_bedingung = { # hier wird wieder ein dict gebaut, das für jede Bedingung true / false speichert. 
        "eingeloggt":         bool(st.session_state.get("anmeldung_eingeloggt", False)), # ist der Nutzer angemeldet
        "pflegegrad":         nutzer.get("pflegegrad_punkte") is not None or bool(nutzer.get("pflegegrad")), # Gibt es Punkte oder einen Pflegegrad Text, das or bedeutet eines von beiden reicht
        "leistungen_erfasst": bool(nutzer.get("genutzte_leistungen")), # Wurden genutzte Leistungen eingetragen
        "ergebnis":           bool(st.session_state.get("ergebnis")), # Liegt ein Berechnungsergebnis vor
        # bool(...) wandelt jeden Wert in ein klares Ja/Nein um (leer/None → False, befüllt → True
        # .get(..., False) ist die Ausfallsicherung: fehlt ein Wert, gilt „nicht erledigt" statt Absturz.
    }
    ergebnis = []
    aktiv_vergeben = False
    for schritt in schritte: # Die Funktion geht jeden Schritt durch und prüft in dieser Reihenfolge, nach bald, Bedingung erfüllt -> erledigt, noch kein aktiver Schritt -> erste nicht erledigte Schritt wird aktiv, alles andere als offen
        if schritt.get("bald"):
            status = "bald"
        elif erledigt_nach_bedingung.get(schritt["bedingung"]):
            status = "erledigt"
        elif not aktiv_vergeben:
            status = "aktiv"
            aktiv_vergeben = True
        else:
            status = "offen"
        ergebnis.append((schritt, status)) # gibt hier anschließend eine Liste zurück mit Paaren und jedes erhält den Schritt und Status, wird in zeige_roadmap dargestellt
    return ergebnis
# Warum „funktioniert mit UND ohne Demo"? → Weil die Funktion nur den echten App-Zustand liest. Egal ob die Werte durch echte Nutzung oder durch den Demo-Schalter befüllt wurden – die Logik ist dieselbe.
# Testaufruf: _roadmap_status(SCHRITTE, {}) -> [({...}, "aktiv"), ...]


def _roadmap_demo_daten_setzen(aktiv: bool, nutzer: dict) -> None: # "-> None:" bedeutet intern es wird nichts zurückgegeben
    """Befüllt bzw. entfernt die Demo-Daten für den Test-Schalter der Roadmap.
    Bei aktivem Schalter werden die ECHTEN State-Quellen befüllt (session_state
    und das übergebene nutzer-Dict), damit die deterministische Status-Ableitung
    in _roadmap_status() die Schritte korrekt als erledigt anzeigt. Die in das
    nutzer-Dict geschriebenen Felder sind nur die In-Memory-Kopie dieses Renders –
    das ist für die Demo gewollt und ausreichend.
    Bei deaktiviertem Schalter werden NUR die Demo-eigenen Keys entfernt, ohne
    echte Nutzerdaten oder den Login zu zerstören.
    """
    if aktiv: # Dies ist der Schalter, wenn an und somit aktiv werden hier die Beispieldaten in die echten Speicher Quellen geschrieben, in folgende, da alle Inhalte befüllt sind werden auch de Schritt 1 bis 4 als erledigt angezeigt
        st.session_state["anmeldung_eingeloggt"] = True # angemeldet?
        nutzer["pflegegrad"] = "Pflegegrad 3" # Pflegegrad
        nutzer["pflegegrad_punkte"] = 47.5 # Pflegegrad Punkte
        nutzer["genutzte_leistungen"] = ["Pflegegeld"] # Leistungen genutzt
        st.session_state["ergebnis"] = ROADMAP_DEMO_ERGEBNIS # Summe der einzelnen Beträge, die als Gesamtbetrag angezeigt werden
        # In der Demo gilt der Pflegegrad standardmäßig als anerkannt, damit der
        # bisherige Geld-Schlachtplan sichtbar bleibt.
        st.session_state["pg_anerkannt"] = True
        # Radio-Vorbelegung nur einmal setzen (setdefault), damit man zum Testen
        # des anderen Falls manuell auf "Nein" umschalten kann.
        st.session_state.setdefault("pg_anerkannt_radio", ANERKANNT_JA) # "setdefault" bedeutet es wird Ja gesetzt, falls noch kein Wert da ist, manuell kann man auf Nein umschalten sodass das nicht bei jedem Render zurückgesetzt wird
    else:
        # Echtes Ergebnis nicht löschen – nur das Demo-Ergebnis entfernen.
        if st.session_state.get("ergebnis") is ROADMAP_DEMO_ERGEBNIS: # hier wird exakt zuerst geprüft ob das Objekt "ROADMAP_DEMO_ERGEBNIS" hier im Speicher ist, wenn es das Demo Ergebnis ist wird es gelöscht alles andere vom echten Datensatz nicht
            st.session_state.pop("ergebnis", None)
        st.session_state.pop("pg_anerkannt", None)
        st.session_state.pop("pg_anerkannt_radio", None)
        # pop(key, None) entfernt einen Wert – und das None als zweites Argument verhindert einen Absturz, falls der Schlüssel gar nicht existiert.
        # anmeldung_eingeloggt bleibt unangetastet – das Dashboard setzt den
        # echten Login ohnehin voraus.
# Warum „nur In-Memory" so wichtig ist: Die Demo überschreibt den echten Pflegegrad nur für die aktuelle Anzeige, nicht dauerhaft in der Datenbank. Dadurch ist der Demo-Schalter ungefährlich: Er kann echte Nutzerdaten nicht kaputtmachen.
# Testaufruf: _roadmap_demo_daten_setzen(True, {}) -> session_state["ergebnis"] gesetzt


# Google-Gemini-Modell (Free Tier) für die Ausformulierung des Schlachtplans.
# Angesprochen über die OpenAI-kompatible Schnittstelle von Gemini.
KI_MODELL = "gemini-2.5-flash" # Legt fest, welches KI-Modell den Schlachtplan-Text formuliert, hier ist flash die schnelle günstige Modell Variante

# Versions-Marke für den erzeugten Ablaufplan-Text. Wird mit dem Text im
# session_state gespeichert. Bei einer Prompt-Änderung diese Zahl erhöhen –
# dann wird alter, im Browser gecachter Text NICHT mehr angezeigt, sondern erst
# nach erneutem Button-Klick frisch erzeugt.
KI_SCHLACHTPLAN_VERSION = 2 # Das ist eine Versionsnummer für den erzeugten KI-Text, Der teuer erzeugte KI-Text wird zwischengespeichert (im session_state), damit nicht bei jedem Klick neu (und kostenpflichtig) generiert werden muss.
                            # Beim Speichern wird diese Versionsnummer mit dem Text zusammen abgelegt. Beim Anzeigen vergleicht der Code: „Passt die gespeicherte Version noch zur aktuellen?"
                            # Passt → gespeicherten Text anzeigen (schnell, kein API-Aufruf). / Passt nicht (weil ihr die Zahl von 2 auf 3 erhöht habt) → alter Text wird verworfen, neuer wird erst nach Button-Klick frisch erzeugt.
                            # Das Zwischenspeichern macht die App schneller und sparsamer.

def _schlachtplan_notfalltext(ergebnis: dict, top3: list) -> str:
    """Hardcoded deutscher Notfall-Ablaufplan, falls der KI-Call fehlschlägt.
    Liefert – wie der KI-Pfad – einen zeitlichen Ablaufplan (Woche 1 /
    Woche 2-3 / danach) und nennt die Maßnahmen beim Namen, wiederholt aber
    bewusst KEINE Beträge oder Beschreibungstexte der Karten. So sieht der
    Nutzer auch bei fehlendem Key, Rate-Limit oder Timeout immer einen Plan.
    """
    pg = ergebnis.get("pflegegrad", "Ihrem Pflegegrad") # Holt den Pflegegrad. Fehlt der Wert, wird der lesbare Ersatztext „Ihrem Pflegegrad eingesetzt, sodass die Sätze auch grammatikalisch richtig sind
    namen = [_leistung_kurzname(e["titel"]) for e in top3] # Holt für jede Top-3-Empfehlung den kurzen Leistungsnamen (über die früher erklärte Funktion _leistung_kurzname, die „nutzen", „beantragen" usw. abschneidet).
    anzahl = len(namen) # zählt, wie viele Empfehlungen es gibt – wichtig für den nächsten Punkt.
    teile = [ # Der Text wird Stück für Stück in einer Liste teile gesammelt und am Ende zusammengefügt.
        f"So gehen Sie mit {pg} am besten vor – ein Schritt nach dem anderen, "
        "ganz in Ruhe:"
        # das f" macht hier die Inhalte von der geschweiften Klammer ausrechnenbar und einsetztbar und der jeweilige Inhalt wird dann angezeigt, nicht die Klammer.
    ]
    # Die Funktion darf nicht blind auf namen[1] oder namen[2] zugreifen. Gäbe es nur eine Empfehlung, würde namen[1] einen Absturz verursachen (IndexError – „dieses Element gibt es nicht"). Durch die Mengen-Prüfung baut die Funktion den Plan nur so lang, wie wirklich Empfehlungen da sind.
    teile.append(
        f"Woche 1: {namen[0]}. Rufen Sie Ihre Pflegekasse an oder schicken Sie "
        "ein kurzes Schreiben und notieren Sie das Datum."
    )
    if anzahl >= 2: # Woche 2-3 nur, wenn es eine 2. Empfehlung gibt
        teile.append(
            f"Woche 2-3: {namen[1]}. Holen Sie die nötigen Unterlagen zusammen "
            "und reichen Sie sie ein."
        )
    if anzahl >= 3: # "Danach" nur, wenn es eine 3. Empfehlung gibt
        teile.append(
            f"Danach: {namen[2]}, sobald die ersten beiden Schritte auf den Weg "
            "gebracht sind. So bleibt alles übersichtlich."
        )
    teile.append(
        "Sie müssen nicht alles auf einmal schaffen. Schon der erste Schritt "
        "bringt Sie spürbar voran."
    )
    return "\n\n".join(teile)
    # Fügt alle gesammelten Text-Stücke zu einem Text zusammen.
    # \n\n sind zwei Zeilenumbrüche → erzeugt Absatz-Abstände zwischen den Schritten, damit der Plan luftig und gut lesbar wirkt.
# Testaufruf: _schlachtplan_notfalltext(ROADMAP_DEMO_ERGEBNIS, [{...},{...},{...}]) -> "So gehen Sie ..."


def _ki_schlachtplan_nachrichten(ergebnis: dict, top3: list,
                                  pg_anerkannt: bool = True) -> list:
    """Baut die Chat-Nachrichten für den KI-Call (zeitlicher Ablaufplan).
    Die KI bekommt die bereits deterministisch sortierten Top-3 als
    Reihenfolge-Kontext und erzeugt daraus einen personalisierten ZEITLICHEN
    Ablaufplan (Woche 1 / Woche 2-3 / danach). Sie SOLL die Leistungen beim
    Namen nennen, damit die Reihenfolge klar wird (z.B. "Woche 1:
    Kurzzeitpflege"), aber die €-Beträge und die Card-Beschreibungen NICHT
    wiederholen.
    """
    zeilen = []
    for i, e in enumerate(top3, start=1): # "enumerate(top3, start=1)" durchläuft die Top-3 mit Zähler, beginnend bei 1. So entsteht eine nummerierte Reihenfolge, Die Reihenfolge wurde vorher schon deterministisch sortiert (nach Betrag). Die KI bekommt sie als fertige Vorgabe
        zeilen.append(f"{i}. {_leistung_kurzname(e['titel'])}")
    daten = "\n".join(zeilen)
    pg = ergebnis.get("pflegegrad") or st.session_state.get("pflegegrad", "unbekannt") # Holt den Pflegegrad mit doppelter Absicherung: erst aus dem Ergebnis, sonst aus dem Session-Speicher, sonst „unbekannt".
    situation = ("Der Pflegegrad ist bereits offiziell anerkannt."
                 if pg_anerkannt else
                 "Der Pflegegrad ist noch nicht offiziell anerkannt.")# Je nachdem, ob der Bescheid schon da ist, bekommt die KI unterschiedlichen Kontext, damit der Plan zur Situation passt.

    system = ( # Grundregeln / Persönlichkeit der KI. Hier wird festgelegt, Wer die KI ist, Was sie tun sollWas sie NICHT tun darf
        "Du bist Nela, eine warmherzige, ruhige Assistenz für pflegende "
        "Angehörige (Zielgruppe 50-60 Jahre). Sprich einfaches, freundliches "
        "Deutsch und sieze die Person. Du erstellst einen zeitlichen "
        "Ablaufplan, der dem Nutzer zeigt, in welcher Reihenfolge und mit "
        "welchem Timing er die Maßnahmen angeht. "
        "WICHTIG: Nenne in jedem Wochen-Schritt die zugehörige Maßnahme beim "
        "Namen (z.B. 'Woche 1: Kurzzeitpflege'). Wiederhole NICHT die €-Beträge "
        "und nicht die Beschreibungstexte der Karten, die schon auf dem Screen "
        "stehen. Fokus: was zuerst, was dann, was danach. "
        "Erfinde KEINE Zahlen, Fristen, Prozente oder Paragraphen und behaupte "
        "keine rechtliche oder medizinische Beratung."
    )
    user = ( # die konkrete Aufgabe mit den konkreten Daten, exakte Formate, Wortlimit
        f"Pflegegrad: {pg}. {situation}\n"
        f"Maßnahmen in dieser Reihenfolge:\n{daten}\n\n"
        "Schreibe einen kurzen, ermutigenden Ablaufplan in genau drei Phasen, "
        "jede Phase mit ihrer Überschrift am Zeilenanfang: 'Woche 1:', "
        "'Woche 2-3:' und 'Danach:'. Ordne die Maßnahmen den Phasen zu und "
        "nenne sie dabei beim Namen. Sage pro Phase in 1-2 Sätzen, was konkret "
        "zu tun ist (z.B. anrufen, Antrag stellen, Termin vereinbaren). "
        "Wiederhole KEINE €-Beträge und keine langen Beschreibungen. Schließe "
        "mit einem ruhigen Mut-Satz. Insgesamt höchstens 120 Wörter."
    )
    return [ # gibt am Ende eine Liste mit den zwei dicts zurück, das "role" mit zwei Schlüsseln wer spricht, bei "content" werden hier die oben gebauten Variablen eingesetzt
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
# Testaufruf: _ki_schlachtplan_nachrichten(ROADMAP_DEMO_ERGEBNIS, [{...}], True) -> [{...}, {...}]


def _schlachtplan_karte(rang: int, empf: dict, gedaempft: bool = False) -> None: # das "-> None" bedeutet, sie gibt nichts zurück, sondern malt direkt etwas auf die Seite.
    """Rendert eine einzelne Schlachtplan-Karte (Rang, Titel, Begründung, Betrag).
    gedaempft=True stellt die Maßnahme als ausgegraute Vorschau dar – etwa
    solange der Pflegegrad noch nicht offiziell anerkannt ist und die Leistung
    daher noch nicht abrufbar ist.
    """
    if gedaempft: # wenn das true ist, kommt die ausgegraute Vorschau
                  # Das wird genutzt, wenn der Pflegegrad noch nicht offiziell anerkannt ist – die Leistung ist dann noch nicht abrufbar, also zeigt man sie „blass" als Ausblick.
        karten_bg = "#FAFAFA"
        badge_bg = "#F0F0F0"
        badge_farbe = "#9E9E9E"
        titel_farbe = "#757575"
        betrag_farbe = "#9E9E9E"
    else: # wenn false, kommen normale, kräftige Farben, Marken-konstanten
        karten_bg = "#FFFFFF"
        badge_bg = AKZENT_HELL
        badge_farbe = PRIMAER_DUNKEL
        titel_farbe = HEADLINE_FARBE
        betrag_farbe = PRIMAER

    st.markdown( # Hier wird die Karte als HTML mit CSS-Styling zusammengebaut und angezeigt.
                 # Streamlit (das App-Framework) kann normalerweise nur einfache Bausteine, mit st.markdown und eigenem HTML kann man frei gestaltete Karten bauen.
        # im folgenden der Hintergrund der Karte und vom Badge des Rangs
        '<div style="display:flex; align-items:flex-start; gap:18px; '
        'background:' + karten_bg + '; border:1px solid ' + RAHMEN_GRAU + '; '
        'border-radius:14px; padding:20px 22px; margin-bottom:14px;">'
        '<div style="flex:0 0 auto; width:40px; height:40px; border-radius:50%; '
        'background:' + badge_bg + '; color:' + badge_farbe + '; '
        # Definition Schriftart und Darstellung Rang links
        'font-family:Montserrat, sans-serif; font-weight:800; font-size:18px; '
        'display:flex; align-items:center; justify-content:center;">'
        f'{rang}</div>'
        '<div style="flex:1 1 auto;">'
        # Definition Schriftart und Darstellung Titel und Begründung
        '<div style="font-family:Montserrat, sans-serif; font-size:18px; '
        'font-weight:700; color:' + titel_farbe + '; margin-bottom:4px;">'
        f'{empf["titel"]}</div>'
        f'<div style="color:{TEXT_GRAU}; font-size:15px; line-height:1.5;">'
        f'{empf["begruendung"]}</div></div>'
        '<div style="flex:0 0 auto; text-align:right; '
        # Definition Schriftart und Darstellung Euro Betrag rechts
        'font-family:Montserrat, sans-serif; font-weight:800; font-size:18px; '
        'color:' + betrag_farbe + ';">'
        f'{_euro(empf["betrag_jaehrlich"])}'
        f'<div style="font-size:11px; font-weight:600; color:{TEXT_GRAU}; '
        'text-transform:uppercase; letter-spacing:0.5px; margin-top:2px;">'
        'pro Jahr</div></div>'
        '</div>',
        unsafe_allow_html=True,
        # Dieser Schalter erlaubt Streamlit, den HTML-Code wirklich als Layout darzustellen statt als reinen Text.
        # Das Wort „unsafe" (unsicher) ist eine Warnung: HTML aus fremden/unbekannten Quellen könnte Schadcode einschleusen.
        # Hier ist es vertretbar, weil der HTML-Text vollständig aus eigenem Code stammt
    )


def zeige_schlachtplan(ergebnis: dict) -> None:
    """Zeigt den Schlachtplan – abhängig davon, ob der Pflegegrad anerkannt ist.
    Erwartet ein ergebnis-dict mit "empfehlungen" (titel, betrag_jaehrlich,
    begruendung). Die Sortierung ist deterministisch (absteigend nach
    jährlichem Betrag). Ist der Pflegegrad noch NICHT offiziell anerkannt, wird
    zuerst der Antrags-Schritt gezeigt und die Leistungen nur als gedämpfte
    Vorschau. Ist er anerkannt, erscheint der Geld-Schlachtplan inkl.
    KI-Ausformulierung. Keine Datenbank.
    """
    empfehlungen = sorted(
        ergebnis.get("empfehlungen", []), # holt die Empfehlungsliste, falls keine da ist kommt eine leere Liste
        key=lambda e: e.get("betrag_jaehrlich", 0),# Sortiert die Empfehlungen absteigend nach Betrag und nimmt die Top-3 (dieselbe Logik wie bei der Summen-Funktion → garantiert konsistente Anzeige
                                                   # sortiert die Liste nach den Jahresbeträgen, das "lambda" ist eine Mini-Funktion die für jede Empfehlung sagt: "Nimm betrag_jaehrlich als Sortierkriterium"
        reverse=True, # bedeutet absteigend, -> höchster Betrag zu erst
    )[:3] # Nimmmt nur die drei obersten
    if not empfehlungen: # Gibt es gar keine Empfehlungen, bricht die Funktion sofort ab, bevor irgendwas gezeichnet wird. Verhindert Abstürze und leere Karten.
        return

    pg = ergebnis.get("pflegegrad", "Ihr Pflegegrad") # lediglich eine variable

    st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True) # vgl. Zeile ca. 5142

    # NEUE FRAGE vor dem Schlachtplan: Unser Rechner liefert nur eine
    # Einschätzung. Ohne offiziellen Bescheid der Pflegekasse bestehen noch
    # KEINE Ansprüche auf Geld-Leistungen – das muss der Schlachtplan abbilden.
    wahl = st.radio( # Zeigt die Auswahl-Knöpfe (mit den früher erklärten Konstanten).
        "Ist Ihr Pflegegrad schon offiziell von Ihrer Pflegekasse anerkannt?",
        [ANERKANNT_JA, ANERKANNT_NEIN],
        key="pg_anerkannt_radio",
    )
    st.session_state["pg_anerkannt"] = (wahl == ANERKANNT_JA) # Sie speichert ein Ja/Nein (True/False), indem sie prüft, ob die Wahl gleich ANERKANNT_JA ist.

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    if not st.session_state["pg_anerkannt"]:
        # Fall: noch KEIN anerkannter Pflegegrad. Erster, hervorgehobener
        # Schritt 1 = Antrag stellen (hardcoded, KEINE KI).
        st.markdown( # Hier wird die Karte als HTML mit CSS-Styling zusammengebaut und angezeigt.
                     # Streamlit (das App-Framework) kann normalerweise nur einfache Bausteine, mit st.markdown und eigenem HTML kann man frei gestaltete Karten bauen.
            # Hintergrund und Umrandung
            '<div style="background:#FFFFFF; border:2px solid ' + PRIMAER + '; '
            'border-radius:16px; padding:22px 24px; margin-bottom:18px; '
            'box-shadow:0 6px 22px rgba(46,125,50,0.10);">'
            '<div style="display:flex; align-items:center; gap:12px;">'
            '<div style="flex:0 0 auto; width:40px; height:40px; border-radius:50%; '
            f'background:{AKZENT_HELL}; color:{PRIMAER_DUNKEL}; '
            # Schriftart + Titel
            'font-family:Montserrat, sans-serif; font-weight:800; font-size:18px; '
            'display:flex; align-items:center; justify-content:center;">1</div>'
            f'<div style="font-family:Montserrat, sans-serif; font-size:19px; '
            f'font-weight:700; color:{HEADLINE_FARBE};">'
            'Pflegegrad offiziell beantragen</div></div>'
            # Beschreibung unter dem Titel
            f'<p style="color:{TEXT_GRAU}; font-size:15px; line-height:1.6; '
            'margin:14px 0 0 0;">'
            'Stellen Sie einen formlosen Antrag bei Ihrer Pflegekasse (Anruf '
            'oder kurzes Schreiben genügt – Datum notieren!). Die Kasse '
            'beauftragt dann den Medizinischen Dienst mit der Begutachtung. '
            'Erst mit dem Bescheid haben Sie Anspruch auf die folgenden '
            'Leistungen.</p></div>',
            unsafe_allow_html=True, # vgl. Zeile ca. 5142
        )

        # Geld-Leistungen nur als gedämpfte Vorschau.
        st.markdown( # Hier wird die Karte als HTML mit CSS-Styling zusammengebaut und angezeigt.
                     # Streamlit (das App-Framework) kann normalerweise nur einfache Bausteine, mit st.markdown und eigenem HTML kann man frei gestaltete Karten bauen.
            f'<h3 style="font-family:Montserrat, sans-serif; font-size:18px; '
            f'font-weight:700; color:{HEADLINE_FARBE}; margin:8px 0 14px 0;">'
            f'Das steht Ihrer Familie zu, sobald {pg} anerkannt ist:</h3>',
            unsafe_allow_html=True, # vgl. Zeile ca. 5142
        )
        for rang, empf in enumerate(empfehlungen, start=1): # Diese Schleife geht die Top-3-Empfehlungen einzeln durch.
                                                            # "empfehlungen" = die drei sortierten Leistungen.
                                                            # "enumerate(..., start=1)" liefert bei jedem Durchlauf zwei Dinge gleichzeitig:
            _schlachtplan_karte(rang, empf, gedaempft=True) # Bei jedem Durchlauf wird die früher erklärte Karten-Funktion aufgerufen und eine Karte gezeichnet.
                                                            # rang = die Platznummer (1, dann 2, dann 3) – durch start=1 beginnt die Zählung bei 1 statt wie üblich bei 0.
                                                            # empf = die jeweilige Empfehlung selbst (das dict mit Titel, Betrag, Begründung).
                                                            # gedaempft=True. Genau dieser Schalter sorgt dafür, dass die Karte grau/blass dargestellt wird – als Vorschau, nicht als abrufbare Leistung.
        return # beendet die gesamte Funktion an dieser Stelle.
               # weil die Anzeige fertig ist. Es sollte bewusst nichts mehr danach passieren (kein Geldplan, keine KI). Das return hat die Funktion dort abgeschlossen.

    # Fall: Pflegegrad anerkannt -> Geld-Schlachtplan wie bisher.
    st.markdown( # Hier wird die Karte als HTML mit CSS-Styling zusammengebaut und angezeigt.
                 # Streamlit (das App-Framework) kann normalerweise nur einfache Bausteine, mit st.markdown und eigenem HTML kann man frei gestaltete Karten bauen.
        # kleine Über-Überschrift
        '<div style="margin-bottom:18px;">'
        '<span class="nela-section-eyebrow">Ihr Schlachtplan</span>'
        # Hauptüberschrift
        f'<h2 style="font-family:Montserrat, sans-serif; font-size:24px; '
        f'font-weight:700; color:{HEADLINE_FARBE}; margin:6px 0 4px 0;">'
        'Womit Sie jetzt am meisten erreichen</h2>'
        # erklärender Untertitel
        f'<p style="color:{TEXT_GRAU}; font-size:15px; margin:0;">'
        'Diese drei Maßnahmen holen für Ihre Familie das meiste Geld zurück.</p>'
        '</div>',
        unsafe_allow_html=True, # vgl. Zeile ca. 5142
    )

    for rang, empf in enumerate(empfehlungen, start=1): # Dieselbe Schleife wie im nicht-anerkannt-Fall
        _schlachtplan_karte(rang, empf) # Hier fehlt das gedaempft=True, Da "_schlachtplan_karte" den Parameter mit Standardwert gedaempft=False definiert hat, werden die Karten jetzt automatisch in normaler, kräftiger Farbe gezeichnet – nicht ausgegraut.

    # hier ist kein return, da danach noch etwas kommen soll, nämlich der KI-Ablaufplan.

    # --- Echter, sichtbarer KI-Call (Google Gemini, OpenAI-kompatibel) -----
    # Aus den deterministisch sortierten Top-3 (empfehlungen) baut Gemini einen
    # personalisierten ZEITLICHEN Ablaufplan (Woche 1 / Woche 2-3 / danach) –
    # Reihenfolge und Timing, KEINE Wiederholung der Beträge/Namen vom Screen.
    # Schlägt irgendetwas fehl (fehlender Key, 429, Timeout o.ä.), nutzen wir
    # einen hardcoded Notfall-Ablaufplan – die App zeigt NIEMALS einen Fehler.
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True) # vgl. Zeile ca. 5142
    if st.button("Zeitlichen Ablaufplan von Nela erstellen", # zeigt einen Knopf an und liefert True, genau in dem Moment, wo er geklickt wird. Durch das "if" läuft der ganze KI-Block also nur auf Klick – nicht automatisch bei jedem Laden.
                 key="ki_schlachtplan_btn", # Button Funktion bzw. interner Name
                 type="primary"): # lediglich Fargestaltung
    # Der Knopf sorgt dafür, dass die KI nur auf bewussten Wunsch des Nutzers anläuft – nicht ungewollt bei jeder Interaktion.
        pg_anerkannt = bool(st.session_state.get("pg_anerkannt", True)) # Holt den Anerkennungs-Status (Ja/Nein) aus dem Speicher, um ihn gleich an die Prompt-Funktion weiterzugeben.
                                                                        # bool(...) macht ein klares Wahr/Falsch daraus
                                                                        # .get(..., True) liefert „True" als Standard, falls der Wert fehlt.
        with st.spinner("Nela erstellt Ihren Ablaufplan …"): # st.spinner zeigt während des KI-Aufrufs einen Ladekreisel mit Text. Alles, was eingerückt darunter steht, läuft währenddessen.
                                                             # Sobald es fertig ist, verschwindet der Kreisel. Das ist reine Nutzerführung – der Nutzer weiß, dass etwas passiert und die App nicht hängt.
            try: # steht in try. Geht irgendetwas schief, springt das Programm in den except-Block – statt abzustürzen.
                # Der GESAMTE Block liegt im try – auch das Lesen des Keys aus
                # st.secrets, damit ein fehlender Key den Fallback auslöst statt
                # die App abstürzen zu lassen.
                # Lazy-Import: App läuft auch ohne installierte openai-Lib.
                from openai import OpenAI # Die App startet auch dann, wenn openai gar nicht installiert ist – der Import wird ja nur gebraucht, wenn wirklich jemand klickt.
                gemini_key = st.secrets["GEMINI_KEY"] # Der API-Schlüssel wird aus einem sicheren Geheimnis-Speicher geladen
                client = OpenAI( # Baut die Verbindung auf. Weil Gemini „OpenAI-kompatibel" ist, funktioniert derselbe Code wie für ChatGPT – nur die Adresse und der Key zeigen auf Google.
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                    api_key=gemini_key,
                )
                antwort = client.chat.completions.create(
                    model=KI_MODELL, # welches Modell (die früher erklärte Konstante).
                    messages=_ki_schlachtplan_nachrichten(
                        ergebnis, empfehlungen, pg_anerkannt), # die Anweisungen hier werden die vorbereiteten Prompt-Nachrichten (system + user) eingesetzt, die die andere Funktion gebaut hat.
                    temperature=0.5, # Kreativität / Haluzinationen, je kleiner desto geringer mittlere Kreativität: verlässlich und sachlich, aber nicht roboterhaft.
                    timeout=20, # max. Wartezeit bricht nach 20 Sekunden ab, damit der Nutzer nicht ewig wartet.
                )
                st.session_state["ki_schlachtplan_text"] = (
                    antwort.choices[0].message.content # antwort.choices[0].message.content → holt aus der KI-Antwort den eigentlichen Text heraus die Antwort ist verschachtelt; choices[0] ist die erste/einzige Antwortoption,
                                                       # .message.content der Textinhalt
                )
                st.session_state["ki_schlachtplan_quelle"] = "ki" # Wird im Speicher abgelegt, und die Quelle wird auf „ki" markiert (für das ehrliche Badge später).
            except Exception as e: # fängt jeden erdenklichen Fehler ab – fehlender Key, Rate-Limit (Fehler „429"), Timeout, kein Internet, Bibliothek fehlt.
                # Fehler NUR in die Konsole loggen, nie dem Nutzer zeigen.
                print("[Nela] Gemini-Call fehlgeschlagen:", repr(e)) #  print(...) der Fehler wird nur in die Konsole (für euch Entwickler) geschrieben,
                                                                     # repr(e) zeigt die technischen Details.
                st.session_state["ki_schlachtplan_text"] = (
                    _schlachtplan_notfalltext(ergebnis, empfehlungen) # Dem Nutzer wird der Fehler NIE gezeigt. Stattdessen wird der hartkodierte Notfalltext geladen
                )
                st.session_state["ki_schlachtplan_quelle"] = "fallback" # die Quelle wird auf „fallback" gesetzt.
            # Frisch erzeugten Text mit der aktuellen Prompt-Version markieren.
            st.session_state["ki_schlachtplan_version"] = KI_SCHLACHTPLAN_VERSION # Diese Zeile steht außerhalb von try/except (gleiche Einrückung), läuft also in beiden Fällen – egal ob KI oder Fallback.
                                                                                  # Sie stempelt den frisch erzeugten Text mit der aktuellen Prompt-Version. So weiß der Anzeige-Teil später, ob der Text noch aktuell ist (verhindert veralteten Cache nach Prompt-Änderungen).

    # Nur anzeigen, wenn der Text mit der AKTUELLEN Prompt-Version erzeugt wurde.
    # So verschwindet alter, im Browser gecachter Text nach einer Prompt-Änderung
    # automatisch, statt veraltet stehen zu bleiben.
    
    # Streamlit speichert den Text im session_state, damit er beim Weiterklicken sichtbar bleibt.
    # zeigt den fertigen KI-Text (oder Notfalltext) auf dem Bildschirm an – in einer hübschen grünen Box mit ehrlichem Hinweis, woher der Text stammt.
    # Der Text wird nur angezeigt, wenn zwei Bedingungen gleichzeitig (and) erfüllt sind, siehe folgenden beiden
    if (st.session_state.get("ki_schlachtplan_text") # Es gibt überhaupt einen Text → get("ki_schlachtplan_text") liefert etwas (nicht leer). Solange niemand den Knopf geklickt hat, ist hier nichts → es wird nichts angezeigt
            and st.session_state.get("ki_schlachtplan_version") == KI_SCHLACHTPLAN_VERSION): # Die Version stimmt → die gespeicherte Version ist gleich der aktuellen KI_SCHLACHTPLAN_VERSION.
        # Badge ehrlich kennzeichnen: echter KI-Ablaufplan vs. Notfall-Plan.
        if st.session_state.get("ki_schlachtplan_quelle") == "ki":
            badge = "Ihr Ablaufplan · von Nelas KI · " + html.escape(KI_MODELL) # Echte KI ("ki") → „…von Nelas KI · gemini-2.5-flash". Es wird sogar das Modell offengelegt. html.escape(KI_MODELL) entschärft hier vorsorglich Sonderzeichen im Modellnamen
        else:
            badge = "Ihr Ablaufplan · von Nela erstellt" # Fallback → schlicht „…von Nela erstellt" (ohne KI zu behaupten).

        st.markdown(
            # Hintergrund und größen
            '<div style="background:#F1F8E9; border:1px solid ' + AKZENT_HELL + '; '
            'border-radius:14px; padding:20px 22px; margin-top:6px;">'
            # Badge in Großbuchstaben siehe "(text-transform:uppercase)"
            f'<div style="font-size:11px; font-weight:700; color:{PRIMAER}; '
            'text-transform:uppercase; letter-spacing:1px; margin-bottom:8px;">'
            + badge + '</div>'
            # eigentliche Plan-Text
            f'<div style="color:{HEADLINE_FARBE}; font-size:15px; line-height:1.6; '
            'white-space:pre-wrap;">' # white-space:pre-wrap → sorgt dafür, dass die Absätze und Zeilenumbrüche des Textes (die \n\n) auch wirklich als Absätze angezeigt werden. Ohne das würde HTML alle Umbrüche zusammenquetschen und der Plan wäre ein einziger Textklumpen.
            + html.escape(st.session_state["ki_schlachtplan_text"]) + # Der Plan-Text kommt von außen (von der KI). "html.escape" wandelt gefährliche Sonderzeichen (wie < oder >) in eine harmlose Form um, bevor sie ins HTML eingesetzt werden.
            '</div></div>',
            unsafe_allow_html=True, # vgl. Zeile ca. 5142
        )


def zeige_roadmap(nutzer: dict) -> None: # Hauptanzeige der Roadmap. Sie holt sich für jeden Schritt den Status (von _roadmap_status), malt die passende Karte und hängt am Ende den Schlachtplan ein. es wird nichts zurückgegeben
    """Zeigt die geführte Roadmap (Schritt-Liste) und – falls vorhanden – den Schlachtplan.
    Der Fortschritt wird deterministisch aus dem echten App-State des übergebenen
    nutzer-Dicts und dem session_state abgeleitet. Oben ein Demo-Schalter, der
    Beispiel-Daten in die echten Quellen legt, damit die komplette Roadmap inkl.
    Schlachtplan sofort sichtbar ist.
    """
    # Test-Schalter: lädt Beispieldaten bzw. setzt alles wieder zurück.
    demo_an = st.checkbox("Demo-Daten laden", key="roadmap_demo") # "st.checkbox(...)" zeigt ein Häkchen-Feld und liefert True/False, je nachdem ob es angehakt ist.
    _roadmap_demo_daten_setzen(demo_an, nutzer) # Dieser Wert geht direkt in die früher erklärte Funktion "_roadmap_demo_daten_setzen". Angehakt → Beispieldaten werden gesetzt; abgehakt → Demo-Daten werden entfernt.

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True) # vgl. Zeile ca. 5142
    st.markdown( # zeichnet den Kopfbereich, Eyebrow + Überschrift + ruhiger Untertitel
        '<div style="margin-bottom:22px;">'
        '<span class="nela-section-eyebrow">Ihre Roadmap</span>'
        f'<h2 style="font-family:Montserrat, sans-serif; font-size:24px; '
        f'font-weight:700; color:{HEADLINE_FARBE}; margin:6px 0 4px 0;">'
        'Ihr Weg – Schritt für Schritt</h2>'
        f'<p style="color:{TEXT_GRAU}; font-size:15px; margin:0;">'
        'Sie müssen nichts auswendig wissen. Nela führt Sie ruhig durch jeden Schritt.</p>'
        '</div>',
        unsafe_allow_html=True, # vgl. Zeile ca. 5142
    )

    # Symbole je Status (ruhig, gut lesbar für die Zielgruppe).
    symbole = {"erledigt": "✅", "aktiv": "👉", "offen": "⬜", "bald": "🔒"} # "symbole" ist ein dict, das jedem Status ein Emoji zuordnet. Das ist eine Übersetzungstabelle: aus dem technischen Wort "erledigt" wird das Symbol ✅.

    for schritt, status in _roadmap_status(SCHRITTE, nutzer): # Die for Schleife ruft _roadmap_status(SCHRITTE, nutzer) auf – das liefert die Liste aus (Schritt, Status)-Paaren.
        symbol = symbole[status] # Pro Durchlauf wird: der passende Emoji geholt (symbole[status]),
        titel = schritt["titel"] # Pro Durchlauf wird: Titel und Nummer des Schritts ausgepackt.
        nr = schritt["nr"] # Pro Durchlauf wird: Diese Zeile holt die Schritt-Nummer aus dem aktuellen Schritt heraus und legt sie in eine eigene Variable namens nr.

        if status == "aktiv":
            # Der aktive Schritt bekommt eine hervorgehobene Karte (dicker grüner Rand, Schatten, Label „Jetzt dran") – damit der Nutzer sofort sieht, was er als Nächstes tun soll.
            # Hervorgehobene Card mit Handlungsaufforderung + ein CTA-Button.
            st.markdown(
                '<div style="background:#FFFFFF; border:2px solid ' + PRIMAER + '; '
                'border-radius:16px; padding:22px 24px; margin-bottom:14px; '
                'box-shadow:0 6px 22px rgba(46,125,50,0.10);">'
                '<div style="display:flex; align-items:center; gap:12px;">'
                f'<span style="font-size:22px;">{symbol}</span>'
                '<div>'
                f'<div style="font-size:12px; font-weight:700; color:{PRIMAER}; '
                'text-transform:uppercase; letter-spacing:1px;">Jetzt dran</div>'
                f'<div style="font-family:Montserrat, sans-serif; font-size:19px; '
                f'font-weight:700; color:{HEADLINE_FARBE};">'
                f'Schritt {nr}: {titel}</div></div></div>'
                f'<p style="color:{TEXT_GRAU}; font-size:15px; line-height:1.5; '
                'margin:12px 0 0 0;">'
                'Das ist Ihr nächster Schritt. Klicken Sie hier, dann begleitet '
                'Nela Sie weiter.</p>'
                '</div>',
                unsafe_allow_html=True, # vgl. Zeile ca. 5142
            )
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True) # vgl. Zeile ca. 5142
            if st.button(f"Schritt {nr} starten", # Diese Zeile erzeugt einen Knopf und prüft gleichzeitig, ob er geklickt wurde
                         # (f"Schritt {nr} starten") Das ist ein f-String (der formatierte Text). Die {nr} wird durch die echte Schritt-Nummer ersetzt. Steht nr z. B. auf 2
                         # "st.button(...)" zeigt den Knopf auf dem Bildschirm an und liefert einen Wahrheitswert zurück: True, genau in dem Moment, wo der Nutzer klickt – sonst False.
                         key=f"roadmap_cta_{nr}", # "key=f"roadmap_cta_{nr}"" → eindeutiger Name pro Schritt (deshalb die Nummer drin – sonst Namenskonflikt).
                         type="primary", # optische gestaltung
                         use_container_width=True): # Sie sorgt dafür, dass der Knopf die volle verfügbare Breite seines Bereichs ausfüllt
                st.session_state["aktuelle_seite"] = schritt["ziel"] # laufen nur, wenn der Button geklickt wurde,
                                                                     # st.session_state["aktuelle_seite"] = ... → schreibt diesen Wert in den Session-Speicher unter dem Namen "aktuelle_seite".
                                                                     # "schritt["ziel"]" → holt aus dem aktuellen Schritt-dict das hinterlegte Ziel (aus der SCHRITTE-Liste vom Anfang). Bei Schritt 2 ist das z. B. "rechner".
                st.rerun() # -> Führe das ganze Skript sofort von vorne aus, Streamlit zeigt eine Seite immer auf Basis des aktuellen session_state an. 
            st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True) # vgl. Zeile ca. 5142
        else:
            # Dieser Teil zeichnet die Schritte, die nicht der aktive sind – also die erledigten, „bald"- und offenen Schritte. 
            # Ruhige Zeile: Symbol + "Schritt X: Titel". Erledigt = grün,
            # bald = ausgegraut + Label "Bald verfügbar", offen = neutral.
            if status == "erledigt": # Erledigt: kräftig und „grün" dargestellt = optisch als geschafft markiert.
                farbe = HEADLINE_FARBE
                rand = AKZENT_HELL
                deko = ""
            elif status == "bald": # Bald: alles ausgegraut + ein kleines Pillen-Label „Bald verfügbar" als deko
                farbe = "#9E9E9E"
                rand = RAHMEN_GRAU
                deko = ('<span style="margin-left:auto; font-size:12px; ' # margin-left:auto im „bald"-Label schiebt es ganz nach rechts an den Kartenrand.
                        'font-weight:700; color:#9E9E9E; background:#F5F5F5; '
                        'border-radius:20px; padding:4px 12px;">Bald verfügbar</span>')
            else:  # offen: neutral, unauffällig = „kommt später dran, ist aber freigeschaltet".
                farbe = TEXT_GRAU
                rand = RAHMEN_GRAU
                deko = ""

            st.markdown(
                '<div style="display:flex; align-items:center; gap:14px; ' # display:flex; align-items:center sorgt dafür, dass Symbol, Text und Label nebeneinander in einer Reihe stehen, sauber mittig ausgerichtet.
                'background:#FFFFFF; border:1px solid ' + rand + '; '
                'border-radius:14px; padding:16px 20px; margin-bottom:10px;">'
                f'<span style="font-size:20px;">{symbol}</span>'
                f'<span style="font-family:Montserrat, sans-serif; font-size:16px; '
                f'font-weight:600; color:{farbe};">Schritt {nr}: {titel}</span>'
                f'{deko}'
                '</div>',
                unsafe_allow_html=True, # vgl. Zeile ca. 5142
            )

    # KI-Schlachtplan einhängen: sobald die Leistungslücke berechnet ist.
    # Prüft: „Gibt es schon ein Berechnungs-Ergebnis?"
    if st.session_state.get("ergebnis"): # "st.session_state.get("ergebnis")" holt das gespeicherte Ergebnis aus dem Session-Speicher. Existiert der Schlüssel "ergebnis" noch nicht (Nutzer hat noch nicht gerechnet), liefert es None statt eines Absturzes.
        zeige_schlachtplan(st.session_state["ergebnis"]) # Liegt ein Ergebnis vor, wird deine Funktion zeige_schlachtplan aufgerufen und das Ergebnis übergeben. Damit erscheint direkt unter der Roadmap der komplette Schlachtplan inkl. Top-3-Karten und KI-Button.
    else: # Gibt es noch kein Ergebnis, wird statt des Schlachtplans eine freundliche Hinweis-Box gezeigt
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True) # vgl. Zeile ca. 5142, setzt nur einen Abstand (20px Leerraum) nach oben.
        st.markdown( # zeichnet eine Box mit gestricheltem Rand (border: ... dashed) und dem Text „Berechnen Sie zuerst Ihre Leistungslücke…".
            '<div style="background:#FAFAFA; border:1px dashed ' + RAHMEN_GRAU + '; '
            'border-radius:14px; padding:20px 22px; text-align:center;">'
            f'<p style="color:{TEXT_GRAU}; font-size:15px; line-height:1.5; margin:0;">'
            'Berechnen Sie zuerst Ihre Leistungslücke, dann zeigt Nela Ihnen, '
            'womit Sie anfangen sollten.</p>'
            '</div>',
            unsafe_allow_html=True, # vgl. Zeile ca. 5142
        )

# ==================== TEIL VON MAX ====================

def seite_dashboard(nutzer: dict) -> None:
    """Dashboard mit Begrüßung + Status-Tiles + Roadmap."""
    # Begrüßung mit Vornamen aus dem Nutzer-Dict
    # unsafe_allow_html=True nötig, damit Streamlit das HTML rendert statt es als Text zu zeigen
    st.markdown(
        '<div class="nela-app-heading">'
        '<span class="nela-section-eyebrow">Dashboard</span>'
        f'<h1>Guten Tag, {nutzer.get("vorname","")}.</h1>'
        '<p>Hier ist Ihre Übersicht. Sie können jederzeit Änderungen '
        'an Ihrem Profil vornehmen.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Liest Pflegegrad/Punkte/Leistungsanzahl mit Fallback-Texten aus
    # is_not_None statt or, damit 0.0 Punkte nicht als "leer" gilt
    pg = nutzer.get("pflegegrad") or "Noch nicht ermittelt"
    pkt = nutzer.get("pflegegrad_punkte")
    pg_zusatz = (f"{float(pkt):.1f} / 100 Punkte") if pkt is not None else "Pflegegrad ermitteln"

    leist = len(nutzer.get("genutzte_leistungen") or [])
    leist_txt = (str(leist) + " erfasst") if leist else "Noch nicht erfasst"

    # ISO-Datum in lesbares deutsches Format umwandeln, try/except gegen Fehler
    cre = nutzer.get("created_at", "")
    if cre:
        try:
            cre_les = datetime.fromisoformat(cre).strftime("%d.%m.%Y")
        except ValueError:
            cre_les = "k.A."
    else:
        cre_les = "k.A."

    # Drei Status-Tiles nebeneinander: Pflegegrad, Leistungslücke, Konto-Alter
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            '<div class="nela-tile">'
            '<div class="nela-tile-label">Pflegegrad</div>'
            f'<div class="nela-tile-value">{pg}</div>'
            f'<div class="nela-tile-sub">{pg_zusatz}</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with c2:
        # Sobald der Pflegegrad-Flow durchlaufen ist, liegen die Ansprüche in
        # st.session_state["ergebnis"]. Wir zeigen die Summe der Top-3 (gleiche
        # Werte wie der Schlachtplan), sonst "Bald verfügbar".
        # Greift auf Pflegegrad-Ergebnis von Person 2 (Louis/Christian) zu
        # Berechnet Leistungslücke über gemeinsame Hilfsfunktion
        ergebnis_ds = st.session_state.get("ergebnis")
        if ergebnis_ds and ergebnis_ds.get("empfehlungen"):
            luecke_wert = _euro(_anspruch_summe_jaehrlich(ergebnis_ds))
            luecke_sub = "pro Jahr potenziell ungenutzt"
        else:
            luecke_wert = "Bald verfügbar"
            luecke_sub = leist_txt
        st.markdown(
            '<div class="nela-tile">'
            '<div class="nela-tile-label">Leistungslücke</div>'
            f'<div class="nela-tile-value">{luecke_wert}</div>'
            f'<div class="nela-tile-sub">{luecke_sub}</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            '<div class="nela-tile">'
            '<div class="nela-tile-label">Konto erstellt</div>'
            f'<div class="nela-tile-value">{cre_les}</div>'
            '<div class="nela-tile-sub">Kostenloses Basis-Konto</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:42px'></div>", unsafe_allow_html=True)

    # Geführte Roadmap (ersetzt den früheren "Nächste Schritte"-Block)
    # Schnittstelle zu Christian (Person 6) - nicht mein Code
    zeige_roadmap(nutzer)

    # ============================================================
    # KONTO & SICHERHEIT (US2 Logout, US4 Einwilligungen, US5 Löschen)
    # ============================================================
    # 3 Karten: Einwilligungen, Account löschen (beide leiten zur Profilseite)
    # Logout läuft direkt hier mit 2-Schritt-Bestätigung
    st.markdown("<div style='height:48px'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="nela-app-heading">'
        '<span class="nela-section-eyebrow">Konto &amp; Sicherheit</span>'
        '<h1 style="font-size:clamp(22px, 2.6vw, 28px);">'
        'Verwalten Sie Ihr Konto</h1>'
        '<p>Sie können Ihre Einwilligungen widerrufen, Ihren Account '
        'dauerhaft löschen oder sich sicher abmelden – alles aus einem Ort.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    col_k1, col_k2, col_k3 = st.columns(3)

    # 1) Einwilligungen verwalten → leitet zum Profil mit Einwilligungs-Sektion
    # Navigations-Pattern: session_state setzen + rerun() statt echtem Link
    with col_k1:
        st.markdown(
            '<div class="nela-modul">'
            '<div class="nela-modul-icon">'
            '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round">'
            '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'
            '<path d="m9 12 2 2 4-4"/>'
            '</svg></div>'
            '<h3>Einwilligungen verwalten</h3>'
            '<p>Datenschutzerklärung und AGB einsehen, prüfen oder bei '
            'Bedarf widerrufen.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        if st.button("Einwilligungen öffnen",
                     key="dash_zu_einwilligungen",
                     use_container_width=True):
            st.session_state["aktuelle_seite"] = "profil"
            st.rerun()

    # 2) Account löschen → leitet zum Profil mit Lösch-Sektion
    with col_k2:
        st.markdown(
            '<div class="nela-modul">'
            '<div class="nela-modul-icon" style="background:#FFEBEE; color:#D32F2F;">'
            '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round">'
            '<polyline points="3 6 5 6 21 6"/>'
            '<path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>'
            '<path d="M10 11v6M14 11v6"/>'
            '<path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/>'
            '</svg></div>'
            '<h3>Account löschen</h3>'
            '<p>Ihr Konto und alle gespeicherten Daten unwiderruflich '
            'entfernen.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        if st.button("Zur Account-Löschung",
                     key="dash_zu_loeschen",
                     use_container_width=True):
            st.session_state["aktuelle_seite"] = "profil"
            st.rerun()

    # 3) Sicher abmelden → 2-Schritt-Logout direkt auf dem Dashboard
    # Erster Klick setzt nur Bestätigungs-Flag, zweiter Klick loggt aus
    with col_k3:
        st.markdown(
            '<div class="nela-modul">'
            '<div class="nela-modul-icon">'
            '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round">'
            '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>'
            '<polyline points="16 17 21 12 16 7"/>'
            '<line x1="21" y1="12" x2="9" y2="12"/>'
            '</svg></div>'
            '<h3>Sicher abmelden</h3>'
            '<p>Beenden Sie Ihre Sitzung mit Sicherheitsbestätigung – '
            'schützt vor versehentlichem Klick.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        if not st.session_state.get("dash_logout_bestaetigen", False):
            if st.button("Abmelden",
                         key="dash_logout_start",
                         use_container_width=True):
                st.session_state["dash_logout_bestaetigen"] = True
                st.rerun()
        else:
            st.markdown(
                '<div style="background:#FFF8E1; border:1px solid #FBC02D; '
                'border-radius:8px; padding:10px 12px; margin-bottom:8px; '
                'font-size:12px; color:#5D4037; line-height:1.4;">'
                'Wirklich abmelden? Sie müssen sich danach neu anmelden.'
                '</div>',
                unsafe_allow_html=True,
            )
            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("Ja, abmelden",
                             key="dash_logout_ja",
                             type="primary",
                             use_container_width=True):
                    session_logout()
                    st.rerun()
            with cc2:
                if st.button("Abbrechen",
                             key="dash_logout_nein",
                             use_container_width=True):
                    st.session_state["dash_logout_bestaetigen"] = False
                    st.rerun()


def seite_rechner_app(nutzer: dict) -> None:
    """Pflegegrad-Rechner im App-Bereich."""
    # Wrapper: bettet Louis/Christians Pflegegrad-Rechner in den App-Rahmen ein
    # nutzer wird übergeben, aber hier nicht gebraucht (einheitliche Signatur für app_dispatch)
    _app_zurueck_dashboard_button()
    st.markdown(
        '<div class="nela-app-heading">'
        '<span class="nela-section-eyebrow">Pflegegrad-Rechner</span>'
        '<h1>Fragen zur Pflegesituation</h1>'
        '<p>Beantworten Sie die folgenden Fragen ehrlich. Sie können den '
        'Rechner jederzeit neu starten. Ihr Ergebnis wird automatisch '
        'in Ihrem Profil gespeichert.</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    # Rechner in begrenzter Spalte (ohne extra Card-Wrapper, sonst leere
    # weiße Box oberhalb des Rechners – vgl. Hinweis bei den Auth-Forms).
    # sp_l/sp_r sind nur Platzhalter-Spalten für die Zentrierung
    # pflegegrad_rechner_anzeigen() ist Schnittstelle zu Person 2, nicht mein Code
    sp_l, mid, sp_r = st.columns([1, 6, 1])
    with mid:
        pflegegrad_rechner_anzeigen()


def seite_leistung_app(nutzer: dict) -> None:
    """Leistungslücken-Vorschau im App-Bereich."""
    # Zeigt VORSCHAU mit Demo-Werten - echtes Berechnungsmodul folgt später
    _app_zurueck_dashboard_button()
    st.markdown(
        '<div class="nela-app-heading">'
        '<span class="nela-section-eyebrow">Leistungslücken-Rechner</span>'
        '<h1>Ihre konkrete Geldlücke</h1>'
        '<p>Wir berechnen, wieviel Geld Ihnen pro Jahr zusteht und welche '
        'Leistungen aktuell ungenutzt verfallen. Dieses Modul befindet sich '
        'noch in Entwicklung.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # or-Fallback: eingeloggt → echter Pflegegrad, sonst Wert aus Leistungscheck
    # is_not_None statt or bei Punkten, damit 0.0 nicht als "leer" zählt
    pg = nutzer.get("pflegegrad") or st.session_state.get("lc_ergebnis_text", "")
    pkt_roh = (nutzer.get("pflegegrad_punkte")
               if nutzer.get("pflegegrad_punkte") is not None
               else st.session_state.get("lc_ergebnis_punkte"))
    if pg:
        punkte_zeile = (
            f'<div style="font-size:12px; color:{TEXT_GRAU}; margin-top:4px;">'
            f'{float(pkt_roh):.1f} von 100 möglichen Punkten</div>'
            if pkt_roh is not None else ""
        )
        st.markdown(
            f'<div style="background:{HG_HELLGRUEN}; border-left:4px solid {PRIMAER}; '
            'border-radius:12px; padding:18px 22px; margin-bottom:24px;">'
            f'<div style="font-size:11px; font-weight:700; letter-spacing:1.5px; '
            f'text-transform:uppercase; color:{PRIMAER}; margin-bottom:6px;">'
            'Ihr ermittelter Pflegegrad</div>'
            f'<div style="font-family:Montserrat, sans-serif; font-size:18px; '
            f'font-weight:700; color:{HEADLINE_FARBE};">{pg}</div>'
            + punkte_zeile +
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        # Guard Clause: ohne Pflegegrad nur Warnung zeigen und früh aussteigen
        st.warning(
            "Sie haben noch keinen Pflegegrad ermittelt. Bitte nutzen Sie "
            "zuerst den Pflegegrad-Rechner."
        )
        if st.button("Zum Pflegegrad-Rechner",
                     key="leist_zu_rechner",
                     type="primary"):
            st.session_state["aktuelle_seite"] = "rechner"
            st.rerun()
        return

    # Vorschau-Box (gleiche Klasse wie auf Landingpage)
    # Zahlen sind fest codierte Demo-Werte, keine echte Berechnung
    st.markdown(
        '<div class="nela-vorschau">'
        '<div class="nela-vorschau-badge">Vorschau</div>'
        '<div class="nela-vorschau-eyebrow">So sieht Ihr Ergebnis später aus</div>'
        '<div class="nela-vorschau-amount">2.847 &euro;</div>'
        '<div class="nela-vorschau-label">werden bei Ihnen pro Jahr ungenutzt liegen gelassen</div>'
        '<div class="nela-vorschau-grid">'
        '<div class="nela-vorschau-item">'
        '<div class="nela-vorschau-item-label">Entlastungsbetrag</div>'
        '<div class="nela-vorschau-item-value">1.572 &euro;</div></div>'
        '<div class="nela-vorschau-item">'
        '<div class="nela-vorschau-item-label">Verhinderungspflege</div>'
        '<div class="nela-vorschau-item-value">1.275 &euro;</div></div>'
        '<div class="nela-vorschau-item">'
        '<div class="nela-vorschau-item-label">Pflegehilfsmittel</div>'
        '<div class="nela-vorschau-item-value">~480 &euro;</div></div>'
        '</div>'
        '<div class="nela-vorschau-hint">'
        'Das Berechnungsmodul wird im nächsten Entwicklungsschritt freigeschaltet.'
        '</div></div>',
        unsafe_allow_html=True,
    )

def seite_profil_app(nutzer: dict) -> None:
    """Profil-Seite: Stammdaten + Pflegestatus."""
    # Größte Funktion: Stammdaten, genutzte Leistungen, Einwilligungen, Account löschen
    _app_zurueck_dashboard_button()
    st.markdown(
        '<div class="nela-app-heading">'
        '<span class="nela-section-eyebrow">Mein Profil</span>'
        '<h1>Ihre persönlichen Daten</h1>'
        '<p>Hier sehen Sie alle bei Nela gespeicherten Informationen. '
        'In den nächsten Versionen werden Sie diese direkt bearbeiten.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ISO-Daten in lesbares deutsches Format umwandeln, try/except gegen Fehler
    cre = nutzer.get("created_at", "")
    if cre:
        try:
            cre_les = datetime.fromisoformat(cre).strftime("%d.%m.%Y um %H:%M Uhr")
        except ValueError:
            cre_les = "unbekannt"
    else:
        cre_les = "unbekannt"

    pgd = nutzer.get("pflegegrad_datum", "")
    if pgd:
        try:
            pgd_les = datetime.fromisoformat(pgd).strftime("%d.%m.%Y")
        except ValueError:
            pgd_les = "k.A."
    else:
        pgd_les = "noch nicht ermittelt"

    # Zwei Spalten: links Stammdaten, rechts Pflegestatus - beides reine Anzeige
    # Keine Eingabefelder, Bearbeitung folgt in späterer Version
    cl, cr = st.columns(2)
    with cl:
        st.markdown(
            '<div class="nela-modul"><span class="nela-modul-nr">Stammdaten</span>'
            '<div style="margin-top:14px;">'
            '<div class="nela-profil-feld">'
            '<div class="nela-profil-label">Vorname</div>'
            f'<div class="nela-profil-value">{nutzer.get("vorname","")}</div></div>'
            '<div class="nela-profil-feld">'
            '<div class="nela-profil-label">Nachname</div>'
            f'<div class="nela-profil-value">{nutzer.get("nachname","")}</div></div>'
            '<div class="nela-profil-feld">'
            '<div class="nela-profil-label">E-Mail-Adresse</div>'
            f'<div class="nela-profil-value" style="font-size:14px; word-break:break-all;">'
            f'{nutzer.get("email","")}</div></div>'
            '<div class="nela-profil-feld">'
            '<div class="nela-profil-label">Konto erstellt</div>'
            f'<div class="nela-profil-value" style="font-size:14px;">{cre_les}</div></div>'
            '</div></div>',
            unsafe_allow_html=True,
        )
    with cr:
        pg = nutzer.get("pflegegrad") or "Noch nicht ermittelt"
        pkt = nutzer.get("pflegegrad_punkte")
        # &mdash; als Platzhalter statt leerem Feld, wenn keine Punktzahl vorhanden
        pkt_z = (f"{float(pkt):.1f} von 100 Punkten") if pkt is not None else "&mdash;"
        st.markdown(
            '<div class="nela-modul"><span class="nela-modul-nr">Pflegestatus</span>'
            '<div style="margin-top:14px;">'
            '<div class="nela-profil-feld">'
            '<div class="nela-profil-label">Ermittelter Pflegegrad</div>'
            f'<div class="nela-profil-value" style="font-family:Montserrat,sans-serif;">{pg}</div></div>'
            '<div class="nela-profil-feld">'
            '<div class="nela-profil-label">Punktzahl</div>'
            f'<div class="nela-profil-value" style="font-size:14px;">{pkt_z}</div></div>'
            '<div class="nela-profil-feld">'
            '<div class="nela-profil-label">Zuletzt aktualisiert</div>'
            f'<div class="nela-profil-value" style="font-size:14px;">{pgd_les}</div></div>'
            '</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    # pg_reset() ist gemeinsame Basisfunktion, danach Navigation zum Rechner
    if st.button("Pflegegrad neu ermitteln",
                 key="profil_neu", type="primary"):
        pg_reset()
        st.session_state["aktuelle_seite"] = "rechner"
        st.rerun()

    # ============================================================
    # NEU: Bereits genutzte Leistungen (User Story 2/3)
    # ============================================================
    # Fachlicher Zweck: bereits beanspruchte Leistungen erfassen
    # Schnittstelle zu Jonas (Person 3) - wird dort als "ungenutzt" ausgefiltert
    st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="nela-app-heading">'
        '<span class="nela-section-eyebrow">Genutzte Leistungen</span>'
        '<h1 style="font-size:clamp(22px, 2.6vw, 28px);">'
        'Welche Leistungen nutzen Sie bereits?</h1>'
        '<p>Markieren Sie alles, was Sie bereits beantragt haben oder '
        'beanspruchen. Der Leistungs-Rechner blendet diese Posten dann aus '
        'und zeigt Ihnen nur noch die wirklich ungenutzten Beträge an. '
        'Standard: keine Leistung erfasst.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    genutzt_aktuell = set(nutzer.get("genutzte_leistungen") or [])

    # Checkboxen in 2-Spalten-Grid für übersichtliches Layout
    # Manuelles Grid: Streamlit hat kein fertiges Grid-Element, daher selbst gebaut:
    # äußere Schleife läuft in 2er-Schritten durch die Liste, schneidet pro
    # Durchlauf 2 Namen heraus (Slicing) und setzt sie in 2 neue Spalten
    # Bei ungerader Gesamtzahl bleibt die letzte Zeile automatisch einspaltig
    # Slug entfernt Sonderzeichen, da jedes Widget einen eindeutigen Key braucht
    auswahl = {}
    spalten_pro_zeile = 2
    for i in range(0, len(NELA_LEISTUNGEN_ALLE), spalten_pro_zeile):
        zeile = NELA_LEISTUNGEN_ALLE[i:i + spalten_pro_zeile]
        cols = st.columns(spalten_pro_zeile)
        for idx, name in enumerate(zeile):
            with cols[idx]:
                # Schlüssel-sicher: Sonderzeichen aus dem Namen entfernen
                slug = (name.replace("/", "_")
                            .replace(" ", "_")
                            .replace("-", "_"))
                auswahl[name] = st.checkbox(
                    name,
                    value=(name in genutzt_aktuell),
                    key=f"gen_leist_{slug}",
                )

    # Speichern nur wenn sich etwas geändert hat
    # neu_genutzt filtert aus dem Dict nur die angehakten Namen heraus
    # sorted() auf beiden Seiten verhindert Fehlalarm bei reiner Reihenfolge-Änderung
    # Button erscheint nur bei echter Änderung, Speichern selbst läuft über Nina (P1)
    neu_genutzt = sorted([n for n, v in auswahl.items() if v])
    alt_genutzt = sorted(list(genutzt_aktuell))
    if neu_genutzt != alt_genutzt:
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        col_save, _ = st.columns([1, 2])
        with col_save:
            if st.button("Auswahl speichern",
                         key="genutzt_speichern",
                         type="primary",
                         use_container_width=True):
                nutzer_genutzte_leistungen_speichern(
                    nutzer["email"], neu_genutzt,
                )
                st.success("Ihre Auswahl wurde gespeichert.")
                st.rerun()
    elif genutzt_aktuell:
        st.markdown(
            f'<div style="font-size:12px; color:{TEXT_GRAU}; '
            'margin-top:8px;">'
            f'Aktuell als genutzt erfasst: {len(genutzt_aktuell)} '
            f'von {len(NELA_LEISTUNGEN_ALLE)} Leistungen.'
            '</div>',
            unsafe_allow_html=True,
        )

    # ============================================================
    # Einwilligungen verwalten (User Story 4)
    # ============================================================
    # Nutzer kann Zustimmung zu DSE/AGB jederzeit widerrufen (DSGVO-Pflicht)
    # Default True: wer registriert ist, hat bei Anmeldung beiden zugestimmt
    st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="nela-app-heading">'
        '<span class="nela-section-eyebrow">Datenschutz &amp; Einwilligungen</span>'
        '<h1 style="font-size:clamp(22px, 2.6vw, 28px);">'
        'Ihre Einwilligungen verwalten</h1>'
        '<p>Sie können Ihre Zustimmung zu Datenschutzerklärung und AGB '
        'jederzeit widerrufen. Beide sind für die Nutzung von Nela '
        'erforderlich – widerrufen Sie eine Einwilligung, müssen Sie Ihren '
        'Account löschen.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    dse_akt = bool(nutzer.get("einwilligung_datenschutz", True))
    agb_akt = bool(nutzer.get("einwilligung_agb", True))

    # 2 Checkboxen nebeneinander, value=aktueller Stand vorausgewählt
    # dse_neu/agb_neu sind nur die UI-Eingabe, noch nicht gespeichert
    col_ew_l, col_ew_r = st.columns(2)
    with col_ew_l:
        st.markdown(
            '<div class="nela-modul" style="margin-bottom:0;">'
            '<span class="nela-modul-nr">Datenschutz</span>'
            '<h3 style="margin-top:10px;">Datenschutzerklärung</h3>'
            '<p>Verarbeitung Ihrer Daten gemäß DSGVO und unserer '
            '<a href="#" style="color:'+PRIMAER+';">Datenschutzerklärung</a>.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        dse_neu = st.checkbox(
            "Ich stimme der Datenschutzerklärung zu",
            value=dse_akt,
            key="ew_dse_check",
        )
    with col_ew_r:
        st.markdown(
            '<div class="nela-modul" style="margin-bottom:0;">'
            '<span class="nela-modul-nr">AGB</span>'
            '<h3 style="margin-top:10px;">Allgemeine Geschäftsbedingungen</h3>'
            '<p>Nutzungsbedingungen der Nela-Plattform gemäß unserer aktuellen AGB.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        agb_neu = st.checkbox(
            "Ich stimme den AGB zu",
            value=agb_akt,
            key="ew_agb_check",
        )

    # Sichtbares Speichern erst bei Änderung
    # Vergleich neu vs. gespeichert: Button nur sichtbar, wenn sich etwas geändert hat
    # Speichern selbst läuft über Ninas DB-Funktion (Person 1), nicht meinen Code
    geaendert = (dse_neu != dse_akt) or (agb_neu != agb_akt)
    if geaendert:
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        if st.button("Einwilligungs-Änderung speichern",
                     key="ew_speichern", type="primary"):
            nutzer_einwilligungen_aktualisieren(
                nutzer["email"], dse_neu, agb_neu,
            )
            st.rerun()

    # Wenn aktuell eine Einwilligung fehlt → Hinweis + Lösch-Aufforderung
    # Prüft dse_akt/agb_akt (gespeicherter Stand), nicht dse_neu/agb_neu -
    # Warnung erscheint erst NACH dem Speichern eines Widerrufs, nicht beim Klick
    # " und ".join() verbindet sprachlich korrekt; html.escape() schützt vor XSS
    if not dse_akt or not agb_akt:
        fehlend = []
        if not dse_akt:
            fehlend.append("Datenschutzerklärung")
        if not agb_akt:
            fehlend.append("AGB")
        fehl_text = " und ".join(fehlend)
        st.markdown(
            '<div style="background:#FFEBEE; border:1.5px solid #D32F2F; '
            'border-radius:12px; padding:18px 22px; margin:18px 0 6px 0;">'
            f'<div style="font-weight:700; color:#B71C1C; font-size:15px; '
            'margin-bottom:6px;">Einwilligung fehlt</div>'
            f'<div style="color:#5D4037; font-size:14px; line-height:1.5;">'
            f'Sie haben Ihre Einwilligung zur {html.escape(fehl_text)} widerrufen. '
            'Ohne diese können wir Ihre Daten rechtlich nicht weiter verarbeiten. '
            'Bitte löschen Sie Ihren Account oder stimmen Sie erneut zu.'
            '</div></div>',
            unsafe_allow_html=True,
        )

    # ============================================================
    # NEU: Account dauerhaft löschen (User Story 5)
    # ============================================================
    # 2-Schritt-Bestätigung wie beim Logout, gegen Versehen-Klicks
    st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div class="nela-app-heading">'
        '<span class="nela-section-eyebrow" style="color:#D32F2F;">'
        'Account &amp; Daten</span>'
        '<h1 style="font-size:clamp(22px, 2.6vw, 28px);">'
        'Account löschen</h1>'
        '<p>Wenn Sie Nela nicht mehr nutzen möchten, können Sie Ihren '
        'Account und alle gespeicherten Daten unwiderruflich entfernen. '
        'Diese Aktion kann <strong>nicht rückgängig</strong> gemacht werden.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    if not st.session_state.get("account_loeschen_bestaetigen", False):
        col_del_l, _ = st.columns([1, 2])
        with col_del_l:
            if st.button("Account löschen",
                         key="profil_del_start",
                         use_container_width=True):
                st.session_state["account_loeschen_bestaetigen"] = True
                st.rerun()
    else:
        st.markdown(
            '<div style="background:#FFEBEE; border:2px dashed #D32F2F; '
            'border-radius:12px; padding:20px 24px; margin:8px 0;">'
            '<div style="font-family:Montserrat, sans-serif; font-weight:800; '
            'color:#B71C1C; font-size:17px; margin-bottom:8px;">'
            'Sind Sie sicher?</div>'
            '<div style="color:#5D4037; font-size:14px; line-height:1.55; '
            'margin-bottom:14px;">'
            'Ihr Konto, Ihre Pflegegrad-Ergebnisse, Ihre Leistungs-Check-Daten '
            'und alle weiteren bei Nela gespeicherten Informationen werden '
            '<strong>dauerhaft und unwiderruflich</strong> gelöscht.'
            '</div></div>',
            unsafe_allow_html=True,
        )
        col_ja, col_nein, _ = st.columns([1, 1, 2])
        with col_ja:
            if st.button("Ja, dauerhaft löschen",
                         key="profil_del_confirm",
                         type="primary",
                         use_container_width=True):
                # Reihenfolge wichtig: erst DB-Löschung (DSGVO Art.17), dann Logout
                email = nutzer.get("email", "")
                nutzer_loeschen(email)
                session_logout()
                st.rerun()
        with col_nein:
            if st.button("Abbrechen",
                         key="profil_del_abbruch",
                         use_container_width=True):
                st.session_state["account_loeschen_bestaetigen"] = False
                st.rerun()


def app_dispatch(nutzer: dict) -> None:
    """Routet die App-Seiten."""
    # Routing: liest die Steuervariable und ruft die passende Seitenfunktion auf
    # Gegenstück zu jedem "aktuelle_seite = ...; st.rerun()" in meinen Funktionen
    # else-Zweig fängt ungültige Werte ab und springt zurück zum Dashboard
    s = st.session_state.get("aktuelle_seite", "dashboard")
    if s == "dashboard":
        seite_dashboard(nutzer)
    elif s == "rechner":
        seite_rechner_app(nutzer)
    elif s == "leistung":
        seite_leistung_app(nutzer)
    elif s == "profil":
        seite_profil_app(nutzer)
    elif s == "datenschutz":
        seite_datenschutz(eingeloggt=True)
    elif s == "agb":
        seite_agb(eingeloggt=True)
    elif s == "impressum":
        seite_impressum(eingeloggt=True)
    else:
        st.session_state["aktuelle_seite"] = "dashboard"
        seite_dashboard(nutzer)



# ============================================================
# 9) HAUPTPROGRAMM
# ============================================================

def main() -> None:
    """Einstiegspunkt der Anwendung."""
    # set_page_config MUSS der erste Streamlit-Aufruf sein
    page_icon = LOGO_PFAD if os.path.exists(LOGO_PFAD) else "🌿"
    st.set_page_config(
        page_title="Nela - Unterstützung, wenn sie zählt",
        page_icon=page_icon,
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # Setup
    session_init()

    eingeloggt = st.session_state.get("anmeldung_eingeloggt", False)

    # CSS injizieren (früh, vor allen anderen Streamlit-Aufrufen mit Content)
    globales_css_injizieren(sidebar_anzeigen=eingeloggt)

    # Routing
    if eingeloggt:
        nutzer = nutzer_holen(st.session_state.get("anmeldung_email", ""))
        if nutzer is None:
            session_logout()
            st.rerun()
            return
        app_sidebar(nutzer)
        app_dispatch(nutzer)
    else:
        landing_page()


main()