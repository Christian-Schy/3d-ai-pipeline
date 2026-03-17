## Workplane / Face Selector Rules

ALWAYS specify face for every feature (default: ">Z" = top face).
  ">Z"     = top face (highest Z)
  "<Z"     = bottom face
  ">Z[-2]" = second-highest Z face (base plate top in a stacked union)
  ">X"     = rightmost face. "<X" = leftmost. ">Y" = back. "<Y" = front.

STACKED UNIONS — face selector matters:
  When a tool is stacked ON TOP of a target at different Z height:
  - features on BASE target → use face: ">Z[-2]"
  - features on STACKED tool → use face: ">Z"

WORKPLANE INDEPENDENCE (Coder rule — for reference):
  Each feature uses centerOption='CenterOfBoundBox' so origin always
  resets to face bbox center. Position coordinates in blueprint are
  ABSOLUTE from face center — never relative to each other.
