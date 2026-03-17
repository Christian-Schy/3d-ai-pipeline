## Positioning Rules

EDGE-RELATIVE ("Xmm from the [edge]"):
  Models are CENTERED at origin — edges are at ±HALF the dimension!
  offset = half_dim - X   (X = distance from wall)
  "10mm from -Y edge" on 30mm cube (half=15): y = -15+10 = -5
  "20mm from edge" on 200mm plate (half=100): offset = 100-20 = 80

⚠ "Xmm from edge" = distance from WALL to hole CENTER
   Do NOT subtract hole radius — X is already the center-to-wall distance.

CORNER PATTERN (all 4 corners, D from each edge):
  x_offset = W/2 - D
  y_offset = L/2 - D
  positions: [[+x,+y], [-x,+y], [+x,-y], [-x,-y]]
  Example: 20mm from edge on 200×200mm → x=80, y=80
    positions: [[80,80],[-80,80],[80,-80],[-80,-80]]

RESIZE CORNER FEATURE:
  new_center = ±(half_plate - half_NEW_feature)  NOT the old coordinates!
