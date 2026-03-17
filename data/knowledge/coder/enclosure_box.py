# Example: Enclosure box (open top, 2mm walls, lid pocket)
# 80x60x40mm outer dimensions, 2mm wall, open top with 1mm lid pocket

import cadquery as cq

result = (
    cq.Workplane("XY")
    # Outer shell
    .box(80, 60, 40, centered=(True, True, False))
    # Shell operation: 2mm walls, open the top face
    .faces(">Z")
    .shell(-2)
    # Lid pocket: 1mm step around top edge for lid to sit in
    .faces(">Z").workplane()
    .rect(76, 56)         # slightly smaller than outer = 2mm step
    .cutBlind(-1)         # 1mm deep pocket
)

cq.exporters.export(result, OUTPUT_PATH)
