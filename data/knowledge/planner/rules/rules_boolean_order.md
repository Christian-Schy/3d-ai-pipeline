## Boolean Operation Rules

STACKING (part ON TOP of another):
  z_center = base_height/2 + tool_height/2
  Example: 10mm plate + 20mm cube on top → cube position.z = 5 + 10 = 15

THROUGH-HOLES IN STACKED PARTS:
  If a hole must go through ALL stacked parts:
  1. The parts should be expressed as a union in the root tree
  2. Set hole depth=null (through-all) — NOT depth=base_height (only through first part!)
  3. depth=null + single hole feature drills through the entire union

FACE SELECTOR AFTER STACKING:
  faces(">Z") = HIGHEST Z face (= top of the stacked tool/boss)
  faces(">Z[-2]") = SECOND-HIGHEST Z face (= top of the base plate)
  Example: 10mm plate (top at Z=5) + 20mm cube on top (top at Z=25):
    features on plate → face: ">Z[-2]"
    features on cube  → face: ">Z"

CUT TOOL SIZING (clean through-cuts in root tree):
  tool height = target height + 2 mm
  tool position.z = -1 mm (offset so tool exits both sides)
