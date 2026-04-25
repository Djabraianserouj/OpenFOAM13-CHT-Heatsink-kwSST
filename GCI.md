# Grid Convergence Index (GCI) Study
## CHT Pin Fin Heat Sink — OpenFOAM 13 + Fluent Meshing

---

## Table of Contents

1. [Theory and Equations](#1-theory-and-equations)
2. [Quantities of Interest](#2-quantities-of-interest)
3. [Mesh Strategy](#3-mesh-strategy)
4. [Mesh Generation in Fluent Meshing](#4-mesh-generation-in-fluent-meshing)
5. [Running the Simulations](#5-running-the-simulations)
6. [Post-Processing with calcGCI.py](#6-post-processing-with-calcgcipy)
7. [References](#7-references)

---

## 1. Theory and Equations

The GCI method follows Slater (2008) and Celik et al. (2008). Three meshes are required — coarse, medium and fine — with a constant refinement ratio `r` between consecutive meshes:

```
r = h_coarse / h_fine
```

where `h` is the global maximum cell size. The minimum recommended value is `r ≥ 1.1` [Slater 2008].

**Apparent order of convergence** [Slater 2008]:

```
p = ln|( f3 - f2 ) / ( f2 - f1 )| / ln(r)
```

where `f1` = coarse, `f2` = medium, `f3` = fine result. For second-order schemes (OpenFOAM default) the theoretical value is `p = 2`.

**Relative errors** between consecutive meshes [Slater 2008]:

```
ε²¹ = |( f2 - f1 ) / f1|        (coarse → medium)
ε³² = |( f3 - f2 ) / f2|        (medium → fine)
```

**Grid Convergence Index** [Celik et al. 2008]:

```
GCI²¹ = Fs · ε²¹ / (r^p - 1)
GCI³² = Fs · ε³² / (r^p - 1)
```

where `Fs = 1.25` is the safety factor for studies using three or more meshes. GCI < 5% is considered acceptable for engineering purposes.

**Asymptotic range check** — confirms the three meshes are within the asymptotic convergence regime [Celik et al. 2008]:

```
GCI³² / ( r^p · GCI²¹ ) ≈ 1
```

A value close to 1.0 means the solution is grid-independent and further refinement will not change the results significantly.

**Richardson extrapolation** — estimates the true grid-independent value at infinite mesh resolution [Richardson 1911, as described in Celik et al. 2008]:

```
f_exact = ( r^p · f3 - f2 ) / ( r^p - 1 )
```

Richardson extrapolation uses the known order of convergence `p` to project the numerical solution to zero cell size — i.e. what the result would be on a perfect, infinitely fine mesh. It is the most rigorous way to estimate the true solution and is used as the reference value when reporting GCI results in publications. This is computed automatically by `calcGCI.py`.

---

## 2. Quantities of Interest

The following integral quantities are monitored across the three meshes. They are extracted automatically by `extractData.py`:

| Symbol | Description | Unit |
|--------|-------------|------|
| R_hs | Thermal resistance of the heat sink | K/W |
| ΔP | Pressure drop inlet → outlet | Pa |
| h | Area-averaged convective heat transfer coefficient | W/(m²·K) |

---

## 3. Mesh Strategy

For a clean GCI study, **only the global maximum cell size is changed** between the three meshes. All other parameters — boundary layer settings, surface sizing, growth rates, turbulence model — are held constant.

The current validated settings for the **7×7 pin fin geometry** (7,753,071 cells at medium refinement) are:

| Parameter | Coarse | Medium | Fine |
|-----------|--------|--------|------|
| Global max cell size | 0.004 m | 0.002 m | 0.0013 m |
| Min surface size | 0.0002 m | 0.0002 m | 0.0002 m |
| Max surface size | 0.002 m | 0.002 m | 0.002 m |
| Local face size (fluid_to_solid) | 0.0002 m | 0.0002 m | 0.0002 m |
| Surface growth rate | 1.2 | 1.2 | 1.2 |
| Curvature normal angle | 18° | 18° | 18° |
| BL first layer height | 0.0002 m | 0.0002 m | 0.0002 m |
| BL number of layers | 6 | 6 | 6 |
| BL growth ratio | 1.2 | 1.2 | 1.2 |
| BL applied to | fluid_to_solid, wall-channel | ← same | ← same |
| Volume fill | Polyhedra | Polyhedra | Polyhedra |
| Volume growth rate | 1.2 | 1.2 | 1.2 |
| Turbulence model | k-ω SST | k-ω SST | k-ω SST |

The refinement ratios for this study are:

```
r_coarse/medium = 0.004 / 0.002  = 2.00
r_medium/fine   = 0.002 / 0.0013 = 1.54
```

Both are above the recommended minimum of 1.1.

**Why the boundary layer is fixed:** The k-ω SST model requires y⁺ ≈ 0.5–2 at all wall surfaces. Scaling the first layer height with the bulk mesh would change y⁺ between meshes, making it impossible to isolate the effect of bulk refinement. The first layer height of 0.0002 m was validated on the 4×4 geometry and is assumed transferable to the 7×7 geometry given the same inlet velocity and duct hydraulic diameter.

**Note on boundary layer regions:** Boundary layers are applied to both `fluid_to_solid` (pin fin and base surfaces) and `wall-channel` (duct walls) as a single specification. These do not need to be split into separate entries — this is the correct approach.

---

## 4. Mesh Generation in Fluent Meshing

The following settings are used in the **Watertight Geometry** workflow. Repeat the procedure three times, changing **only** the global max cell size in the **Generate Volume Mesh** step.

### 4.1 Local Face Sizing — fluid_to_solid interface

Add a local face sizing on the `interface` patch:

```
Local face size         : 0.0002 m
Growth Rate             : 1.2
```

This ensures the coupled fluid-solid interface (pin fin surfaces + heater base) is resolved at the same scale as the first boundary layer cell height, giving a smooth transition into the boundary layer.

### 4.2 Generate Surface Mesh

```
Minimum Size            : 0.0002 m
Maximum Size            : 0.002 m          ← keep fixed across all three meshes
Growth Rate             : 1.2
Curvature Normal Angle  : 18°
```

The curvature normal angle of 18° automatically refines cells on the curved cylindrical pin fin surfaces until adjacent face normals differ by less than 18°. This ensures the pin geometry is adequately resolved without a manually specified local size per pin.

> **Note:** The surface mesh maximum size is kept fixed at 0.002 m across all three meshes. Only the volume mesh global max size changes. This ensures that boundary layer quality and near-surface resolution are consistent across all refinement levels.

### 4.3 Describe Geometry

- Set the wind tunnel volume as **Fluid**
- Set the heat sink volume as **Solid**
- The shared surfaces are automatically identified as the fluid-solid interface, which becomes the `fluid_to_solid` / `solid_to_fluid` coupled patch pair in OpenFOAM

### 4.4 Add Boundary Layers

```
Number of Layers        : 6
First Layer Height      : 0.0002 m         ← FIXED — do not change between meshes
Growth Rate             : 1.2
Apply to                : interface, wall-channel
```

### 4.5 Generate Volume Mesh

```
Fill With               : Polyhedra
Max Cell Length         : 0.002 m          ← change to 0.004 m (coarse) or 0.0013 m (fine)
Growth Rate             : 1.2
```

This is the **only parameter that changes** between the three meshes.

### 4.6 Export and Convert

Export from Fluent Meshing as an OpenFOAM case. Convert using:

```bash
fluent3DMeshToFoam mesh.msh
splitMeshRegions -cellZones -overwrite
```

---

## 5. Running the Simulations

Create three case directories:

```
GCI_study/
├── case_coarse/     ← max cell length 0.004 m
├── case_medium/     ← max cell length 0.002 m  (current validated mesh)
└── case_fine/       ← max cell length 0.0013 m
```

Copy the validated case setup into all three. Replace only the `constant/*/polyMesh/` directories with the respective mesh. Run each case:

```bash
cd case_coarse  && ./Allparallelrun
cd case_medium  && ./Allparallelrun
cd case_fine    && ./Allparallelrun
```

Extract results after each run:

```bash
cd case_coarse  && ./extractData.py
cd case_medium  && ./extractData.py
cd case_fine    && ./extractData.py
```

---

## 6. Post-Processing with calcGCI.py

Open `calcGCI.py` and fill in the INPUT DATA section with values from each `extractedData.txt`:

```python
h1 = 0.004      # coarse max cell size [m]
h2 = 0.002      # medium max cell size [m]
h3 = 0.0013     # fine max cell size   [m]

N1 = ...        # coarse cell count
N2 = 7753071    # medium cell count (7x7 geometry)
N3 = ...        # fine cell count

R_hs    = [coarse, medium, fine]
delta_p = [coarse, medium, fine]
h_conv  = [coarse, medium, fine]
```

Run:

```bash
python3 calcGCI.py
```

Output: terminal report with `p`, `f_exact`, GCI values and asymptotic ratio per quantity, plus `gci_convergence.png`.

---

## 7. References

- Slater, J.W. (2008). *Examining Spatial (Grid) Convergence.* NASA Glenn Research Center.
  https://www.grc.nasa.gov/WWW/wind/valid/tutorial/spatconv.html

- Celik, I.B., Ghia, U., Roache, P.J., Freitas, C.J., Coleman, H., & Raad, P.E. (2008).
  "Procedure for Estimation and Reporting of Uncertainty Due to Discretization in CFD Applications."
  *Journal of Fluids Engineering*, 130(7), 078001.
  https://doi.org/10.1115/1.2960953

- Roache, P.J. (1994). "Perspective: A Method for Uniform Reporting of Grid Refinement Studies."
  *Journal of Fluids Engineering*, 116(3), 405–413.
  https://doi.org/10.1115/1.2910291

---

*Document maintained as part of the OpenFOAM13-CHT-Heatsink-kwSST repository.*
*Last updated: April 2026*