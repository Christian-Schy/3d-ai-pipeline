## Slot / Groove Rules

- Use `slot` feature type — NEVER encode as cut+box in root tree.
- depth=null → through-slot. depth=5 → 5mm deep groove.
- angle=0 → X-axis slot. angle=90 → Y-axis slot.
- LENGTH FORMULA (avoids visible walls at ends):
    length = solid_dimension_along_slot + slot_width + 2
    Example: 5mm slot through 30mm solid → length = 30+5+2 = 37
- Coder uses rect().cutBlind(-depth) for fixed depth — NOT slot2D!
  slot2D().cutThruAll() only for through-slots (depth=null).
- Slot MUST come AFTER all holes in features list.
- Slot depth MUST be less than solid height (no depth=20 on 10mm solid!).
