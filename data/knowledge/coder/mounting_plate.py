# Example: Mounting plate with corner holes and center bore
# A 60x40x8mm plate with M4 corner holes and a center M10 hole

import cadquery as cq

result = (
    cq.Workplane("XY")
    # Base plate
    .box(60, 40, 8, centered=(True, True, False))
    # Corner holes: 5mm from each edge = positions at (+/-25, +/-15)
    .faces(">Z").workplane()
    .pushPoints([(25, 15), (-25, 15), (25, -15), (-25, -15)])
    .hole(4)              # M4 clearance hole
    # Center bore
    .faces(">Z").workplane()
    .hole(10)             # M10 center hole
    # Fillet all top edges for clean look
    .faces(">Z").edges()
    .fillet(1)
)

cq.exporters.export(result, OUTPUT_PATH)
