"""Categorise root-children into base subtracts vs. sub-assembly groups.

The "build separate, combine later" pattern requires knowing which children
of the root are independent parts (sub-assemblies) and which are direct
operations on the root body (base subtracts).
"""

from dataclasses import dataclass, field

from src.graph.feature_tree import FeatureTree


@dataclass
class SubAssembly:
    """One independent sub-assembly built from an additive child of root.

    children: feature ids that operate on this sub-assembly's part body.
    parent_face: face on the root where this part is placed.
    parent_z: Z height of the root, used by the translate emitter.
    """
    root_fid: str
    children: list[str] = field(default_factory=list)
    parent_face: str = ">Z"
    parent_z: float = 0.0


@dataclass
class AssemblyGroups:
    root_id: str | None
    base_subtracts: list[str] = field(default_factory=list)
    sub_assemblies: list[SubAssembly] = field(default_factory=list)

    def is_sub_assembly_eligible(self) -> bool:
        """True if at least one sub-assembly has children needing isolated build."""
        return any(sa.children for sa in self.sub_assemblies)


def build_assembly_groups(ft: FeatureTree) -> AssemblyGroups:
    """Group features for the sub-assembly emit pattern.

    A root child with operation="add" starts a sub-assembly (it becomes a
    standalone part). Anything else on the root is a base subtract.
    Grandchildren follow their parent into the sub-assembly.
    """
    root_id = _find_root(ft)
    if root_id is None:
        return AssemblyGroups(root_id=None)

    children_of = _build_children_map(ft)
    root_params = ft.features[root_id].params or {}
    parent_z = float(root_params.get("z", root_params.get("height", 0)))

    base_subtracts: list[str] = []
    sub_assemblies: list[SubAssembly] = []

    for child_fid in children_of.get(root_id, []):
        child = ft.features.get(child_fid)
        if not child:
            continue

        if child.operation == "add":
            sub_assemblies.append(SubAssembly(
                root_fid=child_fid,
                children=_descendants(children_of, child_fid),
                parent_face=child.placement.face if child.placement else ">Z",
                parent_z=parent_z,
            ))
        else:
            base_subtracts.append(child_fid)

    return AssemblyGroups(
        root_id=root_id,
        base_subtracts=base_subtracts,
        sub_assemblies=sub_assemblies,
    )


def _find_root(ft: FeatureTree) -> str | None:
    for fid in ft.build_order:
        f = ft.features.get(fid)
        if f and f.parent is None:
            return fid
    return None


def _build_children_map(ft: FeatureTree) -> dict[str, list[str]]:
    children: dict[str, list[str]] = {}
    for fid in ft.build_order:
        f = ft.features.get(fid)
        if f and f.parent:
            children.setdefault(f.parent, []).append(fid)
    return children


def _descendants(children_of: dict[str, list[str]], fid: str) -> list[str]:
    result: list[str] = []
    for child in children_of.get(fid, []):
        result.append(child)
        result.extend(_descendants(children_of, child))
    return result
