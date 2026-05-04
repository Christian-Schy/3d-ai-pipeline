"""Inventar-Parser darf Aktionen nicht droppen, wenn das LLM den
Beschreibungs-Key nach dem Inhalt benennt ('bohrung': '...' statt
'beschreibung': '...'). Reproduziert aus Run 3f21f541."""

from src.agents.inventar_agent import _normalize_aktion_description


def test_normalizes_bohrung_to_beschreibung():
    a = {"seite": "vorne", "bohrung": "Bohrung Ø20, 10mm tief, unten links"}
    _normalize_aktion_description(a)
    assert a["beschreibung"] == "Bohrung Ø20, 10mm tief, unten links"


def test_keeps_existing_beschreibung():
    a = {"seite": "oben", "beschreibung": "echte beschreibung", "bohrung": "ignoriert"}
    _normalize_aktion_description(a)
    assert a["beschreibung"] == "echte beschreibung"


def test_skips_when_no_alias_present():
    a = {"seite": "oben"}
    _normalize_aktion_description(a)
    assert "beschreibung" not in a


def test_normalizes_nut_alias():
    a = {"seite": "oben", "nut": "Nut 5x5 entlang x-Achse"}
    _normalize_aktion_description(a)
    assert a["beschreibung"] == "Nut 5x5 entlang x-Achse"


def test_normalizes_breite_alias():
    # Reproduziert aus Runs 96fc404a/5b0527d8/b4f94178: das Modell schreibt bei
    # langen Specs reproduzierbar einmal 'breite' statt 'beschreibung'.
    a = {"seite": "unten",
         "breite": "Bohrung Ø20, 10mm tief, oben rechts (20mm von den Kanten entfernt)"}
    _normalize_aktion_description(a)
    assert a["beschreibung"].startswith("Bohrung Ø20")


def test_ignores_non_string_alias_value():
    a = {"seite": "oben", "bohrung": {"d": 20}}
    _normalize_aktion_description(a)
    assert "beschreibung" not in a


def test_smart_fallback_picks_unique_string_field():
    # Unbekannter Key, aber eindeutig: nur ein String-Feld neben 'seite'.
    a = {"seite": "oben", "durchmesser": "Bohrung Ø12, 5mm tief, zentral"}
    _normalize_aktion_description(a)
    assert a["beschreibung"].startswith("Bohrung Ø12")


def test_smart_fallback_skips_when_ambiguous():
    # Zwei String-Felder neben 'seite' → nicht raten.
    a = {"seite": "oben", "x": "foo", "y": "bar"}
    _normalize_aktion_description(a)
    assert "beschreibung" not in a


def test_smart_fallback_ignores_teil_id_string():
    # 'teil_id' darf nicht als beschreibung interpretiert werden.
    a = {"seite": "oben", "teil_id": "wuerfel"}
    _normalize_aktion_description(a)
    assert "beschreibung" not in a


def test_validate_normalizes_during_oneshot_path():
    """_validate must also normalize so the oneshot path doesn't lose actions."""
    from src.agents.inventar_agent import InventarAgent

    raw = {
        "teile": [
            {"id": "wuerfel", "type": "box",
             "raw_params": {"x": 100, "y": 100, "z": 100}}
        ],
        "aktionen": [
            {"seite": "vorne", "bohrung": "Bohrung Ø20, 10mm tief"},
        ],
    }
    out = InventarAgent.__new__(InventarAgent)
    import structlog
    out.log = structlog.get_logger()
    result = InventarAgent._validate(out, raw)
    assert result["aktionen"][0]["beschreibung"] == "Bohrung Ø20, 10mm tief"
    assert result["aktionen"][0]["teil_id"] == "wuerfel"
