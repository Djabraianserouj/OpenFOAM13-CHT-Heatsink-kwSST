#!/usr/bin/env python3
"""
GCI Mesh Study Definition — CHT Pin Fin Heat Sink
==================================================
Defines the three mesh levels for the GCI study across all geometries.
Outputs mesh sizes, refinement ratios, and naming convention.

Run this script first to confirm the mesh plan, then run meshGenerator.py
to generate all meshes automatically via PyFluent.

Usage:
    python3 calcGCI.py                    # print mesh plan only
    python3 calcGCI.py --fill             # compute GCI from filled-in results

Based on:
    Roache (1994), Celik et al. (2008), Slater/NASA (2008)

Mesh naming convention:
    pinfin{geometry}_{level}.msh
    e.g.  pinfin4x4_1.msh  (coarse)
          pinfin4x4_2.msh  (medium)
          pinfin4x4_3.msh  (fine)
    where _1 = coarse, _2 = medium, _3 = fine
"""

import math
import argparse

# =============================================================================
#  MESH PLAN — edit cell sizes here to adjust the study
# =============================================================================

# Global max cell sizes [m] — only this changes between mesh levels
MESH_LEVELS = {
    1: {"label": "coarse", "max_cell_size": 0.0045, "local_face_size": 0.0006},
    2: {"label": "medium", "max_cell_size": 0.0030, "local_face_size": 0.0004},
    3: {"label": "fine",   "max_cell_size": 0.0020, "local_face_size": 0.0002},
}

# Fixed boundary layer settings — same for ALL geometries and mesh levels
FIRST_LAYER_HEIGHT = 0.0002   # [m] — validated for 4x4 at 4.7 m/s, y+ ~ 0.4-2.0
N_LAYERS           = 6
GROWTH_RATE_BL     = 1.2

# Surface mesh settings — fixed across all meshes
MIN_SURFACE_SIZE   = 0.0002   # [m]
# local_face_size is now per mesh level in MESH_LEVELS (scaled at r=1.5)
GROWTH_RATE_VOL    = 1.3
CURVATURE_ANGLE    = 18       # degrees

# Geometries in this study
GEOMETRIES = ["4x4", "5x5", "6x6", "7x7"]

# Safety factor for GCI (Roache 1994)
Fs = 1.25

# =============================================================================
#  RESULTS — fill in after running simulations
#  Format: {geometry: {level: value}}
#  Leave as None until simulation is complete
# =============================================================================

# Thermal resistance R_hs [K/W]
R_hs = {
    "4x4": {1: None, 2: None, 3: None},
    "5x5": {1: None, 2: None, 3: None},
    "6x6": {1: None, 2: None, 3: None},
    "7x7": {1: None, 2: None, 3: None},
}

# Pressure drop delta_p [Pa]
delta_p = {
    "4x4": {1: None, 2: None, 3: None},
    "5x5": {1: None, 2: None, 3: None},
    "6x6": {1: None, 2: None, 3: None},
    "7x7": {1: None, 2: None, 3: None},
}

# Convective HTC [W/(m²·K)] — use h_bulk from extractedData.txt
h_conv = {
    "4x4": {1: None, 2: None, 3: None},
    "5x5": {1: None, 2: None, 3: None},
    "6x6": {1: None, 2: None, 3: None},
    "7x7": {1: None, 2: None, 3: None},
}

# =============================================================================
#  GCI FUNCTIONS
# =============================================================================

def refinement_ratio(h_coarse: float, h_fine: float) -> float:
    """r = h_coarse / h_fine"""
    return h_coarse / h_fine


def apparent_order(f1, f2, f3, r21, r32, max_iter=100):
    """
    Apparent order of convergence p.
    f1=coarse, f2=medium, f3=fine
    p = ln|eps32/eps21| / ln(r)
    """
    eps21 = f2 - f1
    eps32 = f3 - f2
    if abs(eps21) < 1e-15 or abs(eps32) < 1e-15:
        return float("nan")
    s = math.copysign(1.0, eps32 / eps21)
    try:
        p = abs(math.log(abs(eps32 / eps21))) / math.log(r21)
    except (ValueError, ZeroDivisionError):
        return float("nan")
    for _ in range(max_iter):
        try:
            q = math.log((r21**p - s) / (r32**p - s))
        except (ValueError, ZeroDivisionError):
            break
        p_new = (1.0 / math.log(r21)) * abs(math.log(abs(eps32 / eps21)) + q)
        if abs(p_new - p) < 1e-6:
            p = p_new
            break
        p = p_new
    return p


def richardson_extrapolation(f3, f2, r32, p):
    """
    f_exact = (r^p * f_fine - f_medium) / (r^p - 1)
    Best estimate of true grid-independent solution.
    """
    return (r32**p * f3 - f2) / (r32**p - 1.0)


def gci_value(f_fine, f_coarse, r, p, Fs):
    """
    GCI = Fs * |e_a| / (r^p - 1)
    e_a = |(f_coarse - f_fine) / f_fine|
    """
    if abs(f_fine) < 1e-15:
        return float("nan")
    e_a = abs((f_coarse - f_fine) / f_fine)
    return Fs * e_a / (r**p - 1.0)


def asymptotic_ratio(gci_fine, gci_medium, r, p):
    """
    ratio = GCI_medium / (r^p * GCI_fine)  should be approx 1.0
    """
    denom = r**p * gci_fine
    if abs(denom) < 1e-15:
        return float("nan")
    return gci_medium / denom


# =============================================================================
#  PRINT MESH PLAN
# =============================================================================

def print_mesh_plan():
    SEP = "=" * 68

    h1 = MESH_LEVELS[1]["max_cell_size"]
    h2 = MESH_LEVELS[2]["max_cell_size"]
    h3 = MESH_LEVELS[3]["max_cell_size"]
    r21 = refinement_ratio(h1, h2)
    r32 = refinement_ratio(h2, h3)

    print()
    print(SEP)
    print("  GCI Mesh Study — CHT Pin Fin Heat Sink")
    print(SEP)
    print()
    print("  Fixed settings (all geometries, all mesh levels):")
    print(f"    First layer height   : {FIRST_LAYER_HEIGHT*1e3:.2f} mm")
    print(f"    Number of BL layers  : {N_LAYERS}")
    print(f"    BL growth rate       : {GROWTH_RATE_BL}")
    print(f"    Min surface size     : {MIN_SURFACE_SIZE*1e3:.2f} mm")
    print(f"    Volume growth rate   : {GROWTH_RATE_VOL}")
    print(f"    Curvature angle      : {CURVATURE_ANGLE} deg")
    print(f"    Local face size scales with mesh level at r=1.5 (see table)")
    print()
    print("  Mesh levels:")
    print(f"    {'Level':<8} {'Label':<10} {'Max cell [mm]':>14}  {'Local face [mm]':>16}  {'Example name':>20}")
    print(f"    {'-'*8} {'-'*10} {'-'*14}  {'-'*16}  {'-'*20}")
    for lvl, cfg in MESH_LEVELS.items():
        size_mm  = cfg["max_cell_size"]   * 1e3
        local_mm = cfg["local_face_size"] * 1e3
        ex = f"pinfin4x4_{lvl}.msh"
        print(f"    {lvl:<8} {cfg['label']:<10} {size_mm:>12.2f}   {local_mm:>14.2f}   {ex:>20}")
    print()
    print("  Refinement ratios:")
    print(f"    r21 = {h1*1e3:.2f}mm / {h2*1e3:.2f}mm = {r21:.3f}  (coarse to medium)")
    print(f"    r32 = {h2*1e3:.2f}mm / {h3*1e3:.2f}mm = {r32:.3f}  (medium to fine)")
    if min(r21, r32) > 1.3:
        print(f"    Both ratios > 1.3 : OK")
    else:
        print(f"    WARNING: ratio < 1.3 — increase mesh size difference")
    print()
    print("  All mesh files to be generated:")
    for geo in GEOMETRIES:
        for lvl, cfg in MESH_LEVELS.items():
            name = f"pinfin{geo}_{lvl}.msh"
            print(f"    {name:<28}  ({cfg['label']}, max cell = {cfg['max_cell_size']*1e3:.2f} mm)")
    print()
    print(SEP)
    print("  Next step: run meshGenerator.py to generate all meshes")
    print(SEP)
    print()


# =============================================================================
#  COMPUTE GCI (when results are available)
# =============================================================================

def compute_gci():
    SEP  = "=" * 68
    SEP2 = "-" * 68

    h1 = MESH_LEVELS[1]["max_cell_size"]
    h2 = MESH_LEVELS[2]["max_cell_size"]
    h3 = MESH_LEVELS[3]["max_cell_size"]
    r21 = refinement_ratio(h1, h2)
    r32 = refinement_ratio(h2, h3)

    variables = {
        "R_hs [K/W]":       R_hs,
        "delta_p [Pa]":     delta_p,
        "h_conv [W/(m2K)]": h_conv,
    }

    print()
    print(SEP)
    print("  GCI Results — CHT Pin Fin Heat Sink")
    print(SEP)

    for geo in GEOMETRIES:
        print()
        print(f"  Geometry: {geo}")
        print(SEP2)

        for var_name, var_data in variables.items():
            f1 = var_data[geo][1]
            f2 = var_data[geo][2]
            f3 = var_data[geo][3]

            if any(v is None for v in [f1, f2, f3]):
                print(f"    {var_name}: results not yet available")
                continue

            p     = apparent_order(f1, f2, f3, r21, r32)
            f_ext = richardson_extrapolation(f3, f2, r32, p) \
                    if not math.isnan(p) else float("nan")
            gci32 = gci_value(f3, f2, r32, p, Fs) * 100
            gci21 = gci_value(f2, f1, r21, p, Fs) * 100
            e_a   = abs((f2 - f3) / f3) * 100 if abs(f3) > 1e-15 else float("nan")
            asym  = asymptotic_ratio(gci32/100, gci21/100, r32, p)
            verdict = "GRID INDEPENDENT" if gci32 < 5.0 else "REFINE FURTHER"

            print(f"    {var_name}")
            print(f"      Coarse (f1)          = {f1:.6g}")
            print(f"      Medium (f2)          = {f2:.6g}")
            print(f"      Fine   (f3)          = {f3:.6g}")
            print(f"      Apparent order p     = {p:.3f}  (ideal approx 2)")
            print(f"      Extrapolated f_exact = {f_ext:.6g}")
            print(f"      Relative error       = {e_a:.2f} %  (medium vs fine)")
            print(f"      GCI coarse to medium = {gci21:.2f} %")
            print(f"      GCI medium to fine   = {gci32:.2f} %  (< 5% = acceptable)")
            print(f"      Asymptotic ratio     = {asym:.3f}  (approx 1.0 = in range)")
            print(f"      Verdict              : {verdict}")
            print()

    print(SEP)
    print()


# =============================================================================
#  ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="GCI study plan and calculator for CHT pin fin heat sink."
    )
    ap.add_argument(
        "--fill",
        action="store_true",
        help="Compute GCI from filled-in results (default: print mesh plan only)"
    )
    args = ap.parse_args()

    if args.fill:
        compute_gci()
    else:
        print_mesh_plan()