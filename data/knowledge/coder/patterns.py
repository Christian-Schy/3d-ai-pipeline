# CadQuery Patterns
# Arrays, hole patterns, mirroring, polar arrays.

import cadquery as cq

# --- LINEAR ARRAY OF HOLES ---
# rarray: rectangular array
# rarray(x_spacing, y_spacing, x_count, y_count)

result = (
    cq.Workplane("XY")
    .box(60, 40, 10)
    .faces(">Z").workplane()
    .rarray(15, 15, 3, 2)    # 3 columns x 2 rows, 15mm spacing
    .hole(4)                  # 4mm diameter holes
)

# --- POLAR ARRAY OF HOLES ---
# polarArray: holes in a circle pattern
# polarArray(radius, start_angle, angle, count)

result = (
    cq.Workplane("XY")
    .cylinder(5, 30)
    .faces(">Z").workplane()
    .polarArray(20, 0, 360, 6)   # 6 holes on radius 20, full circle
    .hole(4)
)

# --- SINGLE HOLE AT SPECIFIC POSITION ---
# Move to position, then drill

result = (
    cq.Workplane("XY")
    .box(50, 50, 10)
    .faces(">Z").workplane()
    .center(10, 10)      # move to position (10, 10) from center
    .hole(5)
)

# Multiple holes at specific positions
result = (
    cq.Workplane("XY")
    .box(50, 50, 10)
    .faces(">Z").workplane()
    .pushPoints([(10, 10), (-10, 10), (10, -10), (-10, -10)])  # 4 corner positions
    .hole(4)
)

# --- MIRROR ---
# Mirror geometry across a plane

result = (
    cq.Workplane("XY")
    .box(40, 20, 10)
    .faces(">Z").workplane()
    .center(-10, 0)
    .hole(5)
    .mirror("YZ")        # mirror across YZ plane
)

# --- SHELL PATTERN (ribs / gussets) ---
result = (
    cq.Workplane("XY")
    .box(60, 60, 20)
    .faces(">Z")
    .shell(-2)
)

# --- SLOT ---
# Elongated hole (slot)
result = (
    cq.Workplane("XY")
    .box(60, 40, 10)
    .faces(">Z").workplane()
    .slot2D(20, 6)       # length 20mm, width 6mm
    .cutBlind(-10)
)

# Slot at specific position
result = (
    cq.Workplane("XY")
    .box(60, 40, 10)
    .faces(">Z").workplane()
    .center(0, 10)
    .slot2D(30, 5, angle=45)   # angled slot
    .cutBlind(-10)
)

# --- THREAD (external) ---
# CadQuery has basic thread support via Solid.makeHelix
# For most prints, a cylinder with correct diameter is sufficient

# Simple threaded rod approximation
result = cq.Workplane("XY").circle(3).extrude(20)  # M6 rod, 20mm long
