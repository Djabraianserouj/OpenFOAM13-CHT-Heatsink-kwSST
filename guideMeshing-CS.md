# Importing a COMSOL Topology-Optimised Cooling Structure into Fluent Meshing
## SpaceClaim Geometry Preparation Guide

This guide describes how to prepare a topology-optimised cooling structure exported from COMSOL as an STL file for use in Fluent Meshing. This workflow differs from the pin fin setup — an STL faceted body is used instead of a clean CAD STEP file.

---

## Prerequisites

- COMSOL model with topology-optimised cooling structure
- Ansys SpaceClaim (part of Ansys 2024 R2)
- Ansys Fluent Meshing (Watertight Geometry workflow)

---

## Step 1 — Export from COMSOL

Export **only the cooling structure solid** as an STL file:

```
Mesh → Export → STL
```

---

## Step 2 — Import STL into SpaceClaim

```
File → Open → select .stl file. If units are incorrect, then SpaceClaim options → File Options → STL → Import → Units (set the correct unit)
```

---

## Step 3 — Check Facet Health

Before any geometry operations, verify the mesh is clean:

```
Facets tab → Check Facets
```

SpaceClaim will highlight any degenerate triangles, open edges, or self-intersections. A clean mesh shows no errors. If errors are found, return to COMSOL and re-export with a finer STL resolution or repair using:

```
Facets tab → Repair Facets
```

---

## Step 4 — Position the Cooling Structure

Move the imported STL body to its correct position within the wind tunnel domain:

```
Design tab → Move
```

Apply the following translations:

| Direction | Offset |
|-----------|--------|
| X | 90 mm |
| Y | 5 mm |
| Z | 0 mm |

This positions the cooling structure at the correct location relative to the duct inlet and base plate.

---

## Step 5 — Create the Base Plate

Sketch and extrude a base plate underneath the cooling structure:

```
Sketch tab → Rectangle → 50 × 50 mm footprint
Design tab → Pull → extrude 3 mm downward
```

The base plate dimensions are **50 × 50 × 3 mm**. This represents the heater base that connects the cooling structure to the heater boundary condition in OpenFOAM.

Convert the cooling structures to a solid body:

```
Right-click on Facets in Structure tree → Convert to Solid → Do not Merge Faces
```

Combine the base plate facets with the cooling structure into a single body

This produces a single solid body representing the complete heat sink (cooling structure + base plate).

---

## Step 6 — Create the Fluid Domain

Sketch and extrude the wind tunnel fluid volume:

```
Sketch tab → Rectangle → 40 × 50 mm cross-section
Design tab → Pull → extrude full duct length
```

When prompted for merge behaviour, select **No Merge** — this keeps the fluid volume as a separate body from the heat sink solid.

---

## Step 7 — Boolean Cut (Fluid − Solid)

Remove the heat sink solid from the fluid volume to create the fluid region with the heat sink void:

```
Design tab → Combine
→ Target body: fluid volume
→ Tool body: heat sink solid
→ Operation: Cut
```

The fluid volume now has the exact negative shape of the heat sink inside it.

---

## Step 8 — Split the Heater Base Face

The bottom face of the fluid channel must be split to isolate the heater patch from the remaining channel floor. Create two cut lines at the sides of the base plate footprint:

```
Design tab → Split Body → create splitting planes at the base plate edges
```

---

## Step 9 — Organise into Components

Move the two bodies into separate named components:

```
Structure tree → right-click on heat sink solid → Move to New Component → rename to "solid"
Structure tree → right-click on fluid volume  → Move to New Component → rename to "fluid"
```

The Structure tree should show:

```
Components
├── solid
│   └── solid
└── fluid
    └── fluid
```

---

## Step 10 — Set Shared Topology

Shared topology ensures conformal meshing at the fluid-solid interface — essential for CHT coupling in OpenFOAM:

```
Select both components (solid + fluid) in Structure tree
right-click → Share Topology → Share
```

---

## Step 11 — Create Named Selections

Named selections define the patch names that appear in Fluent Meshing and carry through to OpenFOAM boundary conditions.

Select each surface group and create a named selection:

| Named selection | Surfaces to select |
|----------------|-------------------|
| `interface` | all surfaces of the heat sink that touch the fluid (sides, top, fins) |
| `heater` | bottom face of the base plate (central 50×50 mm region) |
| `wall-channel` | top, left, right and bottom walls of the duct |
| `wall-hsside` | four side strips of the channel floor beside the base plate |
| `inlet` | inlet face of the duct |
| `outlet` | outlet face of the duct |

---

## Step 12 — Save as .scdoc

```
File → Save As → SpaceClaim Document (*.scdoc)
```

Name the file descriptively, e.g. `TOPO_classical.scdoc`.

---

## Step 13 — Import into Fluent Meshing

The `.scdoc` file is now ready for the Watertight Geometry workflow in Fluent Meshing. The named selections (`interface`, `heater`, `inlet`, `outlet`, `wall-channel`, `wall-hsside`) will appear automatically in the **Update Boundaries** step.

Proceed with the standard meshing workflow as described in [guideMeshing.md](guideMeshing.md).

---

*Last updated: April 2026*