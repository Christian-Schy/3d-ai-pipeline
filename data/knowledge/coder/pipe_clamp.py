# Example: Pipe clamp / pipe holder
# Holds a 25mm OD pipe, mounts to wall with 2x M5 screws
# Split clamp design — single piece with semicircle cutout

import cadquery as cq

pipe_od = 25          # pipe outer diameter
clamp_w = 30          # clamp width
clamp_h = 40          # clamp height
clamp_depth = 20      # depth (extrude length)
wall_thickness = 5    # material around pipe
mount_hole_d = 5      # M5 mounting holes

result = (
    cq.Workplane("XY")
    # Base block
    .box(clamp_w, clamp_h, clamp_depth, centered=(True, True, False))
    # Semicircular pipe channel — cut from front face
    .faces("<Y").workplane()
    .center(0, clamp_h / 2)      # center on top half of face
    .circle((pipe_od / 2) + 1)   # +1mm clearance
    .cutBlind(-clamp_depth)      # cut through full depth
    # Mounting holes on bottom half
    .faces(">Z").workplane()
    .pushPoints([(-8, -10), (8, -10)])
    .hole(mount_hole_d)
    # Fillet front edges
    .edges("|Z")
    .fillet(2)
)

cq.exporters.export(result, OUTPUT_PATH)
