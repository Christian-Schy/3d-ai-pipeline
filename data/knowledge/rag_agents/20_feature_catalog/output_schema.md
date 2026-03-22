# Output Schema — JSON-Format des Feature Taggers
Tags: schema, output, json, format

## JSON-Schema

```json
{
  "features": [
    {
      "id": "string (eindeutig, z.B. 'base', 'steg_rechts', 'bohrung_1')",
      "type": "string (aus Feature-Katalog: base_plate, hole_single, etc.)",
      "rag_tags": ["string (1-3 Tags für RAG-Query)"]
    }
  ],
  "dependencies": [
    {
      "child": "string (Feature-ID)",
      "parent": "string (Feature-ID oder 'null' für Basis)",
      "placement": "string (top_center, top_right, side_right, etc.)"
    }
  ]
}
```

## Placement-Werte
`top_center`, `top_right`, `top_left`, `top_front`, `top_back`,
`top_right_back`, `top_right_front`, `top_left_back`, `top_left_front`,
`side_right`, `side_left`, `side_front`, `side_back`,
`bottom_center`,
`in_parent_center`, `in_parent_top`, `in_parent_side`

## Beispiel

Input: "100x100x20 Platte, oben rechts hinten ein 50x50x20 Aufsatz, darin ein Lochkreis ∅60 mit 6 Löchern ∅10"

```json
{
  "features": [
    {"id": "base", "type": "base_plate", "rag_tags": ["box"]},
    {"id": "aufsatz", "type": "extrusion_rect", "rag_tags": ["extrusion", "box_on_face"]},
    {"id": "lochkreis", "type": "hole_pattern_circular", "rag_tags": ["bolt_circle", "polar_array"]}
  ],
  "dependencies": [
    {"child": "aufsatz", "parent": "base", "placement": "top_right_back"},
    {"child": "lochkreis", "parent": "aufsatz", "placement": "top_center"}
  ]
}
```
