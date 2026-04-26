"""
meshGenerator.py — Automated mesh generation for GCI study
============================================================
Generates all meshes for all geometries and mesh levels defined in calcGCI.py.
Uses PyFluent (Ansys Fluent Meshing API) with the Watertight Geometry workflow.

Mesh naming convention (from calcGCI.py):
    pinfin{geometry}_{level}.msh
    e.g.  pinfin4x4_1.msh  (coarse)
          pinfin4x4_2.msh  (medium)
          pinfin4x4_3.msh  (fine)

Usage:
    python3 meshGenerator.py                      # generate all meshes
    python3 meshGenerator.py --geo 4x4            # single geometry, all levels
    python3 meshGenerator.py --geo 4x4 --level 1  # single geometry, single level

Edit GEOMETRY_DIR and OUTPUT_DIR below to match your paths.
"""

import argparse
import os
import sys

import ansys.fluent.core as pyfluent

# Import mesh plan from calcGCI.py — must be in the same directory
sys.path.insert(0, ".")
from calcGCI import (
    MESH_LEVELS,
    FIRST_LAYER_HEIGHT,
    N_LAYERS,
    GROWTH_RATE_BL,
    MIN_SURFACE_SIZE,
    GROWTH_RATE_VOL,
    CURVATURE_ANGLE,
    GEOMETRIES,
)

# =============================================================================
#  PATHS — edit these to match your directory structure
# =============================================================================

GEOMETRY_DIR = r"G:/3_PUBLICATIONS/Articles/1_PENDING/2026 - Cooling Structures II/FLUENT/geometry"
OUTPUT_DIR   = r"G:/3_PUBLICATIONS/Articles/1_PENDING/2026 - Cooling Structures II/FLUENT/mesh"

# Geometry file extension
GEO_EXT = ".scdoc"


# =============================================================================
#  MESH GENERATION FUNCTION
# =============================================================================

def generate_mesh(geometry: str, level: int) -> None:
    """
    Generate a single mesh for a given geometry and mesh level.
    geometry : e.g. "4x4"
    level    : 1 (coarse), 2 (medium), 3 (fine)
    """
    cfg            = MESH_LEVELS[level]
    max_size       = cfg["max_cell_size"]     # volume max cell size — changes per level
    local_face     = cfg["local_face_size"]   # interface local face size — changes per level
    label          = cfg["label"]
    mesh_name      = f"pinfin{geometry}_{level}.msh"
    geo_file       = os.path.join(GEOMETRY_DIR, f"pinfin{geometry}{GEO_EXT}")
    out_file       = os.path.join(OUTPUT_DIR, mesh_name)

    print()
    print("=" * 60)
    print(f"  Geometry   : {geometry}  |  Level : {level} ({label})")
    print(f"  Max cell   : {max_size*1e3:.2f} mm")
    print(f"  Local face : {local_face*1e3:.2f} mm  (interface)")
    print(f"  Output     : {mesh_name}")
    print("=" * 60)

    # ── Launch Fluent Meshing ─────────────────────────────────────────────────
    meshing_session = pyfluent.launch_fluent(
        mode=pyfluent.FluentMode.MESHING,
        precision=pyfluent.Precision.DOUBLE,
        processor_count=4,
        product_version="24.2",
    )

    meshing = meshing_session.meshing
    meshing.GlobalSettings.LengthUnit.set_state("m")
    meshing.GlobalSettings.AreaUnit.set_state("m^2")
    meshing.GlobalSettings.VolumeUnit.set_state("m^3")

    workflow = meshing_session.workflow
    workflow.InitializeWorkflow(WorkflowType="Watertight Geometry")
    tasks = workflow.TaskObject

    # ── Import geometry ───────────────────────────────────────────────────────
    print(f"  [1/7] Importing geometry: {geo_file}")
    tasks["Import Geometry"].Arguments.set_state({
        "FileName": geo_file,
        "ImportCadPreferences": {"MaxFacetLength": 0},
        "LengthUnit": "m",
    })
    tasks["Import Geometry"].Execute()

    # ── Local face sizing on interface ────────────────────────────────────────
    # Scales with mesh level at ratio r=1.5 — same ratio as max cell size
    # Keeps surface-to-BL transition consistent across all levels
    print(f"  [2/7] Adding local face sizing on interface ({local_face*1e3:.2f} mm)")
    tasks["Add Local Sizing"].Arguments.set_state({
        "AddChild": "yes",
        "BOICellsPerGap": 1,
        "BOICurvatureNormalAngle": CURVATURE_ANGLE,
        "BOIExecution": "Face Size",
        "BOIFaceLabelList": ["interface"],
        "BOIGrowthRate": GROWTH_RATE_BL,
        "BOISize": local_face,
        "BOIZoneorLabel": "label",
    })
    tasks["Add Local Sizing"].AddChildAndUpdate(DeferUpdate=False)

    # ── Surface mesh ──────────────────────────────────────────────────────────
    # Min size fixed — controls minimum feature resolution
    # Max size scales with mesh level — controls global surface density
    print(f"  [3/7] Generating surface mesh "
          f"(min={MIN_SURFACE_SIZE*1e3:.2f} mm, max={max_size*1e3:.2f} mm)")
    tasks["Generate the Surface Mesh"].Arguments.set_state({
        "CFDSurfaceMeshControls": {
            "MaxSize": max_size,
            "MinSize": MIN_SURFACE_SIZE,
        },
    })
    tasks["Generate the Surface Mesh"].Execute()

    # ── Describe geometry ─────────────────────────────────────────────────────
    print("  [4/7] Describing geometry (fluid + solid)")
    tasks["Describe Geometry"].UpdateChildTasks(SetupTypeChanged=False)
    tasks["Describe Geometry"].Arguments.set_state({
        "NonConformal": "No",
        "SetupType": "The geometry consists of both fluid and solid regions and/or voids",
    })
    tasks["Describe Geometry"].UpdateChildTasks(SetupTypeChanged=True)
    tasks["Describe Geometry"].Execute()

    # ── Update boundaries ─────────────────────────────────────────────────────
    print("  [5/7] Updating boundaries")
    tasks["Update Boundaries"].Arguments.set_state({
        "BoundaryLabelList": ["interface"],
        "BoundaryLabelTypeList": ["interface"],
        "OldBoundaryLabelList": ["interface"],
        "OldBoundaryLabelTypeList": ["wall"],
    })
    tasks["Update Boundaries"].Execute()

    tasks["Create Regions"].Arguments.set_state({"NumberOfFlowVolumes": 1})
    tasks["Create Regions"].Execute()

    tasks["Update Regions"].Arguments.set_state({
        "OldRegionNameList": ["solid-solid", "fluid-id2"],
        "OldRegionTypeList": ["solid", "fluid"],
        "RegionNameList": ["solid", "fluid"],
        "RegionTypeList": ["solid", "fluid"],
    })
    tasks["Update Regions"].Execute()

    # ── Boundary layers ───────────────────────────────────────────────────────
    # First layer height FIXED across all mesh levels and all geometries
    # Validated to give y+ ~ 0.4-2.0 for air at 4.7 m/s
    print(f"  [6/7] Adding boundary layers "
          f"(first height={FIRST_LAYER_HEIGHT*1e3:.2f} mm, {N_LAYERS} layers)")
    tasks["Add Boundary Layers"].Arguments.set_state({
        "BLControlName": "last-ratio_1",
        "FaceScope": {"GrowOn": "selected-zones", "RegionsType": "fluid-regions"},
        "FirstHeight": FIRST_LAYER_HEIGHT,
        "LocalPrismPreferences": {"Continuous": "Continuous"},
        "NumberOfLayers": N_LAYERS,
        "OffsetMethodType": "last-ratio",
        "ZoneSelectionList": ["interface", "wall-channel"],
    })
    tasks["Add Boundary Layers"].AddChildAndUpdate(DeferUpdate=False)

    # ── Volume mesh ───────────────────────────────────────────────────────────
    # TetPolyMaxCellLength is the primary variable that changes between levels
    print(f"  [7/7] Generating volume mesh "
          f"(max cell = {max_size*1e3:.2f} mm, polyhedra)")
    tasks["Generate the Volume Mesh"].Arguments.set_state({
        "VolumeFill": "polyhedra",
        "VolumeFillControls": {
            "GrowthRate": GROWTH_RATE_VOL,
            "TetPolyMaxCellLength": max_size,
        },
        "VolumeMeshPreferences": {
            "Avoid1_8Transition": "no",
            "QualityWarningLimit": 0.05,
        },
    })
    tasks["Generate the Volume Mesh"].Execute()

    # ── Export mesh ───────────────────────────────────────────────────────────
    print(f"  Exporting: {out_file}")
    meshing_session.tui.file.file_format("no")   # ASCII — no binary
    meshing.File.WriteMesh(FileName=out_file)
    meshing_session.exit()

    print(f"  Done: {mesh_name}")
    print()


# =============================================================================
#  ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Generate GCI study meshes for CHT pin fin heat sink."
    )
    ap.add_argument(
        "--geo",
        choices=GEOMETRIES,
        default=None,
        help="Generate meshes for a single geometry only (default: all geometries)"
    )
    ap.add_argument(
        "--level",
        type=int,
        choices=list(MESH_LEVELS.keys()),
        default=None,
        help="Generate a single mesh level only (default: all levels)"
    )
    args = ap.parse_args()

    geos   = [args.geo]   if args.geo   else GEOMETRIES
    levels = [args.level] if args.level else list(MESH_LEVELS.keys())

    total = len(geos) * len(levels)
    print()
    print(f"  Generating {total} mesh(es):")
    for geo in geos:
        for lvl in levels:
            cfg = MESH_LEVELS[lvl]
            print(f"    pinfin{geo}_{lvl}.msh  "
                  f"({cfg['label']}, "
                  f"max={cfg['max_cell_size']*1e3:.2f} mm, "
                  f"local={cfg['local_face_size']*1e3:.2f} mm)")
    print()

    for geo in geos:
        for lvl in levels:
            generate_mesh(geo, lvl)

    print("  All meshes generated successfully.")
    print()