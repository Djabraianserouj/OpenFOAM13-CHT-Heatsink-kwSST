#!/usr/bin/env python3
"""
Grid Convergence Index (GCI) Calculator for OpenFOAM CHT Pin Fin Heat Sink Study
==================================================================================
Based on: Roache, P.J. (1994) "Perspective: A Method for Uniform Reporting of
          Grid Refinement Studies", Journal of Fluids Engineering, Vol. 116.

NASA guide: https://www.grc.nasa.gov/WWW/wind/valid/tutorial/spatconv.html

Usage:
    python3 calcGCI.py

    Edit the INPUT DATA section below with your three mesh results.
    Run extractData.py on each case first to get the values.

Mesh convention:
    Mesh 1 = COARSE   (largest cells)
    Mesh 2 = MEDIUM
    Mesh 3 = FINE     (smallest cells, most accurate)

Output:
    - GCI table printed to terminal
    - Convergence plots saved to gci_convergence.png
"""

import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# =============================================================================
#  INPUT DATA — edit these values from your extractedData.txt files
# =============================================================================

# --- Mesh sizes (representative cell size h = V^(1/3) or just use max cell size)
# These are the global max cell sizes used in Fluent Meshing [m]
# h1 > h2 > h3  (coarse to fine)

h1 = 0.004      # coarse mesh cell size  [m]
h2 = 0.002      # medium mesh cell size  [m]  ← your current working mesh
h3 = 0.0013     # fine mesh cell size    [m]

# --- Number of cells in each mesh (for plotting)
N1 = 500000     # coarse mesh cell count
N2 = 1500000    # medium mesh cell count
N3 = 3500000    # fine mesh cell count

# --- Simulation results from extractedData.txt
# Format: [coarse, medium, fine]

# Thermal resistance R_hs [K/W]
R_hs = [
    0.936,      # Mesh 1 coarse  ← from your coarse k-epsilon result (placeholder)
    0.662,      # Mesh 2 medium  ← from your fine k-epsilon result
    0.650,      # Mesh 3 fine    ← fill in after running fine mesh
]

# Pressure drop delta_p [Pa]
delta_p = [
    58.37,      # Mesh 1 coarse
    49.74,      # Mesh 2 medium
    48.50,      # Mesh 3 fine    ← fill in after running fine mesh
]

# Convective heat transfer coefficient h [W/(m²·K)]
h_conv = [
    84.72,      # Mesh 1 coarse
    119.8,      # Mesh 2 medium
    122.5,      # Mesh 3 fine    ← fill in after running fine mesh
]

# =============================================================================
#  CONSTANTS
# =============================================================================

# Safety factor for GCI (Roache 1994 recommends Fs = 1.25 for 3+ meshes)
# Fs = 3.0 is used when only 2 meshes are compared (more conservative)
Fs = 1.25

# =============================================================================
#  GCI CALCULATION FUNCTIONS
# =============================================================================

def refinement_ratio(h_coarse: float, h_fine: float) -> float:
    """
    Refinement ratio between two meshes.

    r = h_coarse / h_fine

    Should be > 1.3 for reliable GCI. Ideally 1.5 - 2.0.
    """
    return h_coarse / h_fine


def apparent_order(f1: float, f2: float, f3: float,
                   r21: float, r32: float,
                   max_iter: int = 100) -> float:
    """
    Apparent (observed) order of convergence p.

    Solved iteratively from:
        p = (1/ln(r21)) * |ln(|epsilon32/epsilon21|) + ln((r21^p - s)/(r32^p - s))|

    where:
        epsilon21 = f2 - f1   (change from coarse to medium)
        epsilon32 = f3 - f2   (change from medium to fine)
        s = sign(epsilon32 / epsilon21)

    For monotonic convergence (same sign), this reduces to:
        p = ln(|epsilon32 / epsilon21|) / ln(r21/r32)

    Reference: Celik et al. (2008) ASME J. Fluids Eng. 130(7)
    """
    eps21 = f2 - f1   # coarse -> medium change
    eps32 = f3 - f2   # medium -> fine change

    if abs(eps21) < 1e-15 or abs(eps32) < 1e-15:
        return float('nan')   # solution not changing — already converged

    s = math.copysign(1.0, eps32 / eps21)

    # Simple estimate (works for monotonic convergence)
    try:
        p_simple = abs(math.log(abs(eps32 / eps21))) / math.log(r21)
    except (ValueError, ZeroDivisionError):
        return float('nan')

    # Iterative refinement for oscillatory convergence
    p = p_simple
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


def extrapolated_value(f1: float, f2: float, r21: float, p: float) -> float:
    """
    Richardson extrapolated value f_exact (best estimate of true solution).

    f_exact = (r21^p * f1 - f2) / (r21^p - 1)

    This is the value the solution would converge to at infinite mesh resolution.
    f1 = fine mesh result, f2 = medium mesh result.
    """
    return (r21**p * f1 - f2) / (r21**p - 1.0)


def gci(f_fine: float, f_coarse: float, r: float, p: float, Fs: float) -> float:
    """
    Grid Convergence Index (GCI) for the fine mesh.

    GCI_fine = Fs * |e_a| / (r^p - 1)

    where:
        e_a = (f_coarse - f_fine) / f_fine   (approximate relative error)
        r   = refinement ratio
        p   = apparent order of convergence
        Fs  = safety factor (1.25 for 3+ meshes, 3.0 for 2 meshes)

    GCI < 5% is generally acceptable for engineering CFD.
    GCI < 1% indicates grid-independent solution.
    """
    if abs(f_fine) < 1e-15:
        return float('nan')
    e_a = abs((f_coarse - f_fine) / f_fine)
    return Fs * e_a / (r**p - 1.0)


def asymptotic_ratio(gci_fine: float, gci_medium: float,
                     r: float, p: float) -> float:
    """
    Asymptotic ratio check — verifies solution is in asymptotic range.

    ratio = GCI_medium / (r^p * GCI_fine)

    Should be close to 1.0 (within 0.95 - 1.05) to confirm
    the solution is in the asymptotic convergence regime.
    If ratio >> 1 or << 1, the meshes are not in the asymptotic range.
    """
    denom = r**p * gci_fine
    if abs(denom) < 1e-15:
        return float('nan')
    return gci_medium / denom


# =============================================================================
#  MAIN COMPUTATION
# =============================================================================

# Refinement ratios
# r21 = ratio between coarse (1) and medium (2)
# r32 = ratio between medium (2) and fine (3)
r21 = refinement_ratio(h1, h2)
r32 = refinement_ratio(h2, h3)

print()
print("=" * 65)
print("  Grid Convergence Index (GCI) Study")
print("  Pin Fin Heat Sink — CHT OpenFOAM")
print("=" * 65)
print()
print(f"  Mesh sizes:")
print(f"    Coarse  (Mesh 1): h = {h1*1000:.2f} mm,  N = {N1:,} cells")
print(f"    Medium  (Mesh 2): h = {h2*1000:.2f} mm,  N = {N2:,} cells")
print(f"    Fine    (Mesh 3): h = {h3*1000:.2f} mm,  N = {N3:,} cells")
print()
print(f"  Refinement ratios:")
print(f"    r21 = h1/h2 = {r21:.3f}  (coarse/medium)")
print(f"    r32 = h2/h3 = {r32:.3f}  (medium/fine)")
print(f"    (recommended: > 1.3, ideally 1.5-2.0)")
print()
print(f"  Safety factor Fs = {Fs} (Roache 1994, 3+ meshes)")
print()

# Store results for plotting
variables = {
    "R_hs [K/W]":        R_hs,
    "delta_p [Pa]":      delta_p,
    "h_conv [W/(m²·K)]": h_conv,
}

gci_results = {}

SEP = "-" * 65

for name, vals in variables.items():
    f1, f2, f3 = vals[0], vals[1], vals[2]   # coarse, medium, fine

    p  = apparent_order(f1, f2, f3, r21, r32)
    f_ext = extrapolated_value(f3, f2, r32, p) if not math.isnan(p) else float('nan')

    # GCI between medium and fine (the important pair)
    gci_32 = gci(f3, f2, r32, p, Fs) * 100   # convert to %
    # GCI between coarse and medium
    gci_21 = gci(f2, f1, r21, p, Fs) * 100

    asym = asymptotic_ratio(gci_32/100, gci_21/100, r32, p)

    # Approximate relative error medium -> fine
    e_a = abs((f2 - f3) / f3) * 100 if abs(f3) > 1e-15 else float('nan')

    gci_results[name] = {
        "vals":   vals,
        "p":      p,
        "f_ext":  f_ext,
        "gci_21": gci_21,
        "gci_32": gci_32,
        "e_a":    e_a,
        "asym":   asym,
    }

    print(SEP)
    print(f"  Variable: {name}")
    print(SEP)
    print(f"    Coarse  (f1) = {f1:.6g}")
    print(f"    Medium  (f2) = {f2:.6g}")
    print(f"    Fine    (f3) = {f3:.6g}")
    print()
    print(f"    Apparent order p          = {p:.3f}")
    print(f"      (ideal p ≈ 2 for 2nd-order schemes)")
    print(f"    Extrapolated value f_ext  = {f_ext:.6g}")
    print(f"      (best estimate of true/grid-independent value)")
    print()
    print(f"    Approx. relative error    = {e_a:.2f} %")
    print(f"      (medium vs fine: |f2-f3|/f3 * 100)")
    print(f"    GCI coarse→medium         = {gci_21:.2f} %")
    print(f"    GCI medium→fine           = {gci_32:.2f} %")
    print(f"      (< 5%  = acceptable,  < 1% = grid-independent)")
    print(f"    Asymptotic ratio          = {asym:.3f}")
    print(f"      (should be ≈ 1.0 to confirm asymptotic convergence)")
    verdict = "✅ GRID INDEPENDENT" if gci_32 < 5.0 else "⚠️  REFINE FURTHER"
    print(f"    Verdict: {verdict}")
    print()

print("=" * 65)

# =============================================================================
#  PLOTTING
# =============================================================================

cell_counts = [N1, N2, N3]
h_sizes     = [h1*1000, h2*1000, h3*1000]   # in mm for x-axis

fig = plt.figure(figsize=(14, 10))
fig.suptitle("Grid Convergence Study — CHT Pin Fin Heat Sink",
             fontsize=14, fontweight='normal', y=0.98)

gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.35)

var_list  = list(gci_results.keys())
colors    = ["#1f77b4", "#d62728", "#2ca02c"]
ax_list   = [fig.add_subplot(gs[0, i]) for i in range(3)]
ax_gci    = fig.add_subplot(gs[1, 0])
ax_order  = fig.add_subplot(gs[1, 1])
ax_error  = fig.add_subplot(gs[1, 2])

# ── Row 1: convergence curves per variable ────────────────────────────────────
for ax, name, color in zip(ax_list, var_list, colors):
    res  = gci_results[name]
    vals = res["vals"]

    ax.plot(cell_counts, vals, 'o-', color=color, linewidth=2,
            markersize=7, markerfacecolor='white', markeredgewidth=2)

    # extrapolated value as horizontal dashed line
    if not math.isnan(res["f_ext"]):
        ax.axhline(res["f_ext"], color=color, linestyle='--',
                   linewidth=1, alpha=0.6, label=f'Extrapolated: {res["f_ext"]:.4g}')

    ax.set_xlabel("Number of cells", fontsize=10)
    ax.set_ylabel(name, fontsize=10)
    short = name.split("[")[0].strip()
    ax.set_title(f"{short} convergence", fontsize=11, fontweight='normal')
    ax.legend(fontsize=8, loc='best')
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.ticklabel_format(axis='x', style='sci', scilimits=(0, 0))

# ── Row 2 left: GCI bars ──────────────────────────────────────────────────────
var_labels  = [n.split("[")[0].strip() for n in var_list]
gci_21_vals = [gci_results[n]["gci_21"] for n in var_list]
gci_32_vals = [gci_results[n]["gci_32"] for n in var_list]

x     = np.arange(len(var_labels))
width = 0.35

bars1 = ax_gci.bar(x - width/2, gci_21_vals, width,
                   label='GCI coarse→medium', color='#ff7f0e', alpha=0.8)
bars2 = ax_gci.bar(x + width/2, gci_32_vals, width,
                   label='GCI medium→fine',   color='#1f77b4', alpha=0.8)

ax_gci.axhline(5.0,  color='red',    linestyle='--', linewidth=1,
               label='5% threshold (acceptable)')
ax_gci.axhline(1.0,  color='green',  linestyle='--', linewidth=1,
               label='1% threshold (grid-independent)')
ax_gci.set_xticks(x)
ax_gci.set_xticklabels(var_labels, fontsize=9)
ax_gci.set_ylabel("GCI [%]", fontsize=10)
ax_gci.set_title("Grid Convergence Index", fontsize=11, fontweight='normal')
ax_gci.legend(fontsize=7, loc='upper right')
ax_gci.grid(True, linestyle=':', alpha=0.6, axis='y')

# Add value labels on bars
for bar in bars1 + bars2:
    h = bar.get_height()
    ax_gci.text(bar.get_x() + bar.get_width()/2., h + 0.1,
                f'{h:.1f}%', ha='center', va='bottom', fontsize=8)

# ── Row 2 middle: apparent order of convergence ────────────────────────────────
p_vals = [gci_results[n]["p"] for n in var_list]
bar_colors = ['#1f77b4', '#d62728', '#2ca02c']
bars = ax_order.bar(var_labels, p_vals, color=bar_colors, alpha=0.8)
ax_order.axhline(2.0, color='black', linestyle='--', linewidth=1,
                 label='p=2 (2nd order ideal)')
ax_order.axhline(1.0, color='gray',  linestyle='--', linewidth=1,
                 label='p=1 (1st order)')
ax_order.set_ylabel("Apparent order p [-]", fontsize=10)
ax_order.set_title("Apparent order of convergence", fontsize=11, fontweight='normal')
ax_order.legend(fontsize=8)
ax_order.grid(True, linestyle=':', alpha=0.6, axis='y')
for bar, val in zip(bars, p_vals):
    ax_order.text(bar.get_x() + bar.get_width()/2., val + 0.02,
                  f'{val:.2f}', ha='center', va='bottom', fontsize=9)

# ── Row 2 right: relative error medium→fine ───────────────────────────────────
e_vals = [gci_results[n]["e_a"] for n in var_list]
bars = ax_error.bar(var_labels, e_vals, color=bar_colors, alpha=0.8)
ax_error.axhline(5.0, color='red',   linestyle='--', linewidth=1,
                 label='5% threshold')
ax_error.axhline(1.0, color='green', linestyle='--', linewidth=1,
                 label='1% threshold')
ax_error.set_ylabel("Relative error |f2-f3|/f3 × 100 [%]", fontsize=10)
ax_error.set_title("Medium → Fine relative error", fontsize=11, fontweight='normal')
ax_error.legend(fontsize=8)
ax_error.grid(True, linestyle=':', alpha=0.6, axis='y')
for bar, val in zip(bars, e_vals):
    ax_error.text(bar.get_x() + bar.get_width()/2., val + 0.02,
                  f'{val:.2f}%', ha='center', va='bottom', fontsize=9)

# ── Save and show ──────────────────────────────────────────────────────────────
outfile = "gci_convergence.png"
fig.savefig(outfile, dpi=150, bbox_inches='tight')
print(f"\n  Plot saved to: {outfile}")
plt.show()
print()