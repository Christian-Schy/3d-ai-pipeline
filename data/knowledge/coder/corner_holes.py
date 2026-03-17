# CadQuery Corner Holes Pattern
# Plate with holes at corners — the most common industrial pattern.
# KEY: always use pushPoints for multiple same-size holes, never repeat .hole()

import cadquery as cq

# --- PLATE WITH 4 CORNER HOLES ---
# 200x200x40mm plate, M8 holes (8mm diameter), 20mm from each corner
# Corner offset = plate_size/2 - margin = 100 - 20 = 80mm from center

result = (
    cq.Workplane("XY")
    .box(200, 200, 40)
    .faces(">Z").workplane()
    .pushPoints([(80, 80), (-80, 80), (80, -80), (-80, -80)])
    .hole(8)  # M8 = 8mm diameter, through-hole
)
cq.exporters.export(result, OUTPUT_PATH)

# --- GENERAL FORMULA for corner holes ---
# plate W x L x H, holes diameter D, margin M from corners:
#   offset_x = W/2 - M
#   offset_y = L/2 - M
#   positions = [(ox,oy), (-ox,oy), (ox,-oy), (-ox,-oy)]
#
# Example: 100x60 plate, M4 holes (4mm), 8mm from corners:
#   offset_x = 50 - 8 = 42
#   offset_y = 30 - 8 = 22
result2 = (
    cq.Workplane("XY")
    .box(100, 60, 10)
    .faces(">Z").workplane()
    .pushPoints([(42, 22), (-42, 22), (42, -22), (-42, -22)])
    .hole(4)
)

# --- 6 HOLES (2 rows x 3 cols) — use rarray instead ---
# rarray(x_spacing, y_spacing, x_count, y_count) centers the grid automatically
result3 = (
    cq.Workplane("XY")
    .box(120, 80, 15)
    .faces(">Z").workplane()
    .rarray(40, 30, 3, 2)   # 3 cols 40mm apart, 2 rows 30mm apart
    .hole(5)
)

# --- WRONG way (never do this for same-size holes) ---
# BAD: result.faces(">Z").workplane().center(80,80).hole(8)
# BAD: result.faces(">Z").workplane().center(-80,80).hole(8)  <- loses previous holes!
# The .center() approach only drills one hole and loses context.
# ALWAYS use pushPoints for multiple holes in one operation.
