# ANCHOR CLASSIFIER — one phrase -> anchor reference (ADR 0014 W5b)
#
# Mikro-Klassifizierer mit GENAU EINER Aufgabe: erkennt, ob eine Aktions-
# Phrase einen Anker auf das Parent-Bauteil enthaelt. Ausgegliedert aus
# den typ-Klassifizierern, weil die Anker-Disambiguierung dort als
# 6. parallele Aufgabe das kleine Modell ueberlastet hat (pocket/slot
# Hang, siehe ADR 0014 §13).

from src.utils.prompt_loader import load_convention

_ANKER = load_convention("anker")
_JSON_ONLY = load_convention("json_only")


SYSTEM_PROMPT = f"""Du pruefst GENAU EINE CAD-Aktions-Phrase auf einen Anker.

Ein Anker ist ein EXPLIZITER Bezug eines Feature-Punkts auf einen Punkt
des Parent-Bauteils. Das ist deine EINZIGE Aufgabe — keine Masse, keine
Positionierung, kein typ.

Antwort: striktes JSON mit den Feldern anker_kind und anker_eltern.
  - Enthaelt die Phrase einen Anker: beide Felder mit den Enum-Tokens.
  - Enthaelt die Phrase KEINEN Anker: {{"anker_kind": "", "anker_eltern": ""}}.

Die allermeisten Phrasen haben KEINEN Anker. Im Zweifel: leer.

{_ANKER}

{_JSON_ONLY}"""


ANCHOR_TEMPLATE = """\
PHRASE:
{phrase}

JSON:"""
