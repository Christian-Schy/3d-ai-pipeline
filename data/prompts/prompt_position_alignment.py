# POSITION-ALIGNMENT-AGENT — System Prompt
# Token-Budget: ~200 System + ~200 Input = ~400 total
# Aufgabe: Wo auf der bereits gewaehlten Fläche sitzt das Teil?
# Die erlaubten Keywords werden aus Python generiert (per-seite), damit das
# Flächen-Wort NICHT in der Ausrichtung auftauchen kann — strukturelle Prävention.

SYSTEM_PROMPT = """Du bestimmst, wo auf einer Fläche ein CAD-Teil sitzt.
Antworte NUR mit einer Zeile: ausrichtung: <keyword>

Erlaubte Keywords stehen unten in der Eingabe — nur diese sind gültig.

★ Das Wort das die Fläche beschreibt (oben/rechts/links etc.) ist NICHT erlaubt —
  es wurde bereits als Fläche verbraucht. Ignoriere es für die Ausrichtung.
★ Nur wenn ein zweites, anderes Ortswort die Position auf der Fläche beschreibt,
  wähle das passende Keyword. Sonst: zentriert.
★ EINE Zeile, kein Text drumherum.

★★ ECKEN-REGEL: NUR wenn "ins Eck" / "in die Ecke" / "Ecke" explizit im Text steht!
   Dann beide Achsen kombinieren:
   "oben rechts ins eck"      → buendig_oben_rechts  (NICHT nur buendig_rechts!)
   "vordere linke ecke"       → buendig_unten_links
   Ohne "eck/ecke" → NUR das eine genannte Richtungswort verwenden!

★★ ACHTUNG: Das Flächen-Wort ist KEIN Positions-Wort!
   "auf der rechten Seite oben" → seite=rechts (Fläche), nur "oben" = Position
   → buendig_oben  (NICHT buendig_rechts_oben! "rechts" ist die Fläche, nicht Position!)

★★ GANZ-REGEL: "ganz unten / ganz rechts / ganz oben" = NUR diese eine Richtung.
   "ganz unten"  → buendig_unten   (NICHT buendig_unten_links o.ä.)
   "ganz rechts" → buendig_rechts"""

# Per-seite: welche Richtungswörter und Keywords sind auf dieser Fläche gültig?
# Invariante: das Flächen-Wort selbst fehlt in der Liste.
_SEITE_VOCAB = {
    # Auf der Oben/Unten-Fläche schaut man von oben/unten drauf.
    # "oben" und "hinten" sind dasselbe (hintere Kante), "unten" = "vorne".
    "oben": {
        "synonyme": "Bedeutung der Kanten auf dieser Fläche: 'hinten' bedeutet 'oben' (z.B. buendig_oben), 'vorne' bedeutet 'unten' (z.B. buendig_unten), rechts bleibt rechts, links bleibt links.",
        "keywords": [
            "zentriert",
            "buendig_oben",      # hinten bündig (hintere Kante)
            "buendig_unten",     # vorne bündig (vordere Kante)
            "buendig_rechts",
            "buendig_links",
            "buendig_oben_rechts",
            "buendig_oben_links",
            "buendig_unten_rechts",
            "buendig_unten_links",
        ],
    },
    "unten": {
        "synonyme": "Bedeutung der Kanten auf dieser Fläche: 'hinten' bedeutet 'oben' (z.B. buendig_oben), 'vorne' bedeutet 'unten' (z.B. buendig_unten), rechts bleibt rechts, links bleibt links.",
        "keywords": [
            "zentriert",
            "buendig_oben", "buendig_unten",
            "buendig_rechts", "buendig_links",
            "buendig_oben_rechts", "buendig_oben_links",
            "buendig_unten_rechts", "buendig_unten_links",
        ],
    },
    # Auf der Vorne/Hinten-Fläche: oben/unten/rechts/links direkt.
    "vorne": {
        "synonyme": "oben bleibt oben, unten bleibt unten, rechts bleibt rechts, links bleibt links.",
        "keywords": [
            "zentriert",
            "buendig_oben", "buendig_unten",
            "buendig_rechts", "buendig_links",
            "buendig_oben_rechts", "buendig_oben_links",
            "buendig_unten_rechts", "buendig_unten_links",
        ],
    },
    "hinten": {
        "synonyme": "oben bleibt oben, unten bleibt unten, rechts bleibt rechts, links bleibt links.",
        "keywords": [
            "zentriert",
            "buendig_oben", "buendig_unten",
            "buendig_rechts", "buendig_links",
            "buendig_oben_rechts", "buendig_oben_links",
            "buendig_unten_rechts", "buendig_unten_links",
        ],
    },
    # Auf der Rechts-Fläche (Blick von rechts nach links):
    # oben=oben, unten=unten, vorne≡links, hinten≡rechts
    "rechts": {
        "synonyme": "Bedeutung der Kanten auf dieser Fläche: 'vorne' bedeutet 'links' (z.B. buendig_links), 'hinten' bedeutet 'rechts' (z.B. buendig_rechts), oben bleibt oben, unten bleibt unten.",
        "keywords": [
            "zentriert",
            "buendig_oben", "buendig_unten",
            "buendig_links",         # = vorne
            "buendig_rechts",        # = hinten
            "buendig_oben_links",    # = oben+vorne
            "buendig_oben_rechts",   # = oben+hinten
            "buendig_unten_links",   # = unten+vorne
            "buendig_unten_rechts",  # = unten+hinten
        ],
    },
    # Auf der Links-Fläche (Blick von links nach rechts):
    # oben=oben, unten=unten, vorne≡rechts, hinten≡links
    "links": {
        "synonyme": "Bedeutung der Kanten auf dieser Fläche: 'vorne' bedeutet 'rechts' (z.B. buendig_rechts), 'hinten' bedeutet 'links' (z.B. buendig_links), oben bleibt oben, unten bleibt unten.",
        "keywords": [
            "zentriert",
            "buendig_oben", "buendig_unten",
            "buendig_rechts",        # = vorne
            "buendig_links",         # = hinten
            "buendig_oben_rechts",   # = oben+vorne
            "buendig_oben_links",    # = oben+hinten
            "buendig_unten_rechts",  # = unten+vorne
            "buendig_unten_links",   # = unten+hinten
        ],
    },
}


def get_alignment_vocab(seite: str) -> dict:
    """Return vocab dict for the given seite (fallback: oben)."""
    return _SEITE_VOCAB.get(seite.lower(), _SEITE_VOCAB["oben"])


def build_alignment_template(seite: str) -> str:
    """Build a seite-specific template string with injected keyword list."""
    vocab = get_alignment_vocab(seite)
    keywords_str = "\n  ".join(f"- {k}" for k in vocab["keywords"])
    return f"""POSITIONSBESCHREIBUNG:
{{specification}}

GEWAEHLTE FLAECHE: {seite}
  Das Wort "{seite}" ist die Fläche — KEIN Positions-Wort!
  "auf der {seite}en Seite oben" → "{seite}" ist nur die Fläche, "oben" = Position → buendig_oben
  NUR wenn "{seite}" zusammen mit "ins Eck" oder "Ecke" auftaucht:
  "{seite} rechts ins eck" → kombiniere! z.B. buendig_oben_rechts (über Synonyme).
  Synonyme auf dieser Fläche: {vocab["synonyme"]}

ERLAUBTE KEYWORDS (nur diese):
  {keywords_str}

Welches Keyword passt? (NUR eine Zeile: ausrichtung: <keyword>):"""


# Legacy template (fallback, wird durch build_alignment_template ersetzt)
POSITION_ALIGNMENT_TEMPLATE = build_alignment_template("oben")
