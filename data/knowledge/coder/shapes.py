# CadQuery Basic Shapes
# All fundamental 3D primitives with correct syntax.

import cadquery as cq

# --- BOX ---
# box(length, width, height)
# Centered at origin by default
result = cq.Workplane("XY").box(30, 20, 10)

# Box positioned so bottom is at Z=0 (not centered)
result = cq.Workplane("XY").box(30, 20, 10, centered=(True, True, False))

# --- CYLINDER ---
# circle(radius) then extrude(height)
result = cq.Workplane("XY").circle(15).extrude(20)

# Cylinder not centered (starts at Z=0)
result = cq.Workplane("XY").circle(10).extrude(30)

# --- SPHERE ---
result = cq.Workplane("XY").sphere(15)

# --- CONE ---
# Use revolve or loft — cone via sketch
result = (
    cq.Workplane("XY")
    .workplane()
    .add(cq.Solid.makeCone(10, 0, 20))  # base_radius, top_radius, height
)

# --- TORUS ---
result = cq.Workplane("XY").torus(20, 5)  # major_radius, minor_radius

# --- WEDGE / PRISM ---
# Use a polygon profile and extrude
result = (
    cq.Workplane("XY")
    .polygon(6, 20)   # 6-sided polygon, circumradius 20
    .extrude(10)
)

# --- TUBE / HOLLOW CYLINDER ---
# Circle then cutBlind to hollow it out
result = (
    cq.Workplane("XY")
    .circle(15)          # outer radius
    .extrude(30)
    .faces(">Z")
    .workplane()
    .circle(12)          # inner radius (wall thickness = 15-12 = 3mm)
    .cutBlind(-30)       # cut downward through full height
)

# --- RECTANGULAR TUBE ---
result = (
    cq.Workplane("XY")
    .rect(30, 20)
    .extrude(50)
    .faces(">Z")
    .workplane()
    .rect(26, 16)        # inner rect (2mm wall)
    .cutBlind(-50)
)
