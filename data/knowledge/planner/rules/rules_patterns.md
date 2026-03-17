## Pattern / Array Rules

MULTIPLE HOLES AT SPECIFIC POSITIONS → hole_pattern:
  Use ONE hole_pattern node with a positions list.
  ⚠ Do NOT use separate hole nodes for each position.
  positions: [[x1,y1],[x2,y2],...] — absolute from face bbox center.

REGULAR GRID → hole_grid:
  x_spacing: distance between holes in X direction
  y_spacing: distance between holes in Y direction
  x_count: number of holes along X
  y_count: number of holes along Y
  Grid is centered on the face — total span = spacing*(count-1)
  Example: 3×2 grid, 20mm spacing → spans 40mm×20mm, centered at origin.

CORNER HOLES (most common pattern):
  Use hole_pattern with 4 positions computed from corner formula:
  x = ±(W/2 - D),  y = ±(L/2 - D)   (D = distance from edge)
  positions: [[+x,+y],[-x,+y],[+x,-y],[-x,-y]]
