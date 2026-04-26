# OpenFOAM v13 — CHT Pin Fin Heat Sink (k-ω SST)

Steady-state conjugate heat transfer (CHT) simulation of a pin fin heat sink placed in a rectangular wind tunnel duct. A 25 W heater is applied underneath the heat sink solid region. The study covers four pin fin array configurations (4×4, 5×5, 6×6, 7×7) with a grid convergence index (GCI) mesh study to ensure solution accuracy.

**Turbulence model:** k-ω SST with automatic wall treatment (y⁺ ≈ 0.5–2)

---

## Materials

| Region | Material | ρ [kg/m³] | Cp [J/kg·K] | κ [W/m·K] | μ [Pa·s] |
|--------|----------|-----------|-------------|-----------|----------|
| Solid  | AlSi12   | 2650      | 880         | 160       | —        |
| Fluid  | Air 20°C | 1.204     | 1005        | —         | 1.8×10⁻⁵ |

---

## Software

- Ansys 2024 R2 (Fluent Meshing)
- OpenFOAM 13 (Foundation version)
- Python 3.14 (post-processing and automation scripts)

---

## Repository Structure

```
├── 0/                          # Initial conditions (fluid + solid regions)
├── constant/                   # Physical properties and mesh
├── system/                     # Solver settings, schemes, functions
├── figures/                    # Simulation result images
├── guideMeshing.md             # Detailed GCI meshing guide
├── Allparallelrun              # Parallel run script (decompose → solve → reconstruct)
├── extractData.py              # Extracts converged results to extractedData.txt
├── plotResiduals.py            # Plots residuals from postProcessing .dat files
├── calcGCI.py                  # GCI mesh study definition and calculator
├── meshGenerator.py            # Automated mesh generation via PyFluent API
├── calcTurbulence.py           # Computes k, ε/ω initial conditions and y⁺ layer height
└── extractedData.txt           # Extracted converged results (auto-generated)
```

---

## Meshing Workflow

Meshes are generated automatically using **PyFluent** (Ansys Python API) via `meshGenerator.py`, which reads all mesh parameters from `calcGCI.py`. No manual GUI interaction is required once the geometry files are in place.

**Mesh settings (fixed across all geometries and refinement levels):**

| Parameter | Value |
|-----------|-------|
| First layer height | 0.20 mm |
| Boundary layer count | 6 |
| BL growth ratio | 1.2 |
| Local face size (interface) | 0.20 mm |
| Surface min size | 0.20 mm |
| Volume growth rate | 1.3 |
| Curvature normal angle | 18° |
| Volume fill | Polyhedra |

**Three GCI mesh levels (only global max cell size changes):**

| Level | Label | Max cell size | Refinement ratio |
|-------|-------|--------------|-----------------|
| 1 | coarse | 4.5 mm | — |
| 2 | medium | 3.0 mm | r = 1.50 |
| 3 | fine   | 2.0 mm | r = 1.50 |

Mesh files are named `pinfin{geometry}_{level}.msh` — e.g. `pinfin4x4_1.msh` (4×4, coarse).

Full meshing guide: [guideMeshing.md](guideMeshing.md)

---

## Running the Simulation

**1. Convert and split the mesh:**
```bash
fluent3DMeshToFoam mesh.msh
splitMeshRegions -cellZones -overwrite
```

**2. Run in parallel:**
```bash
./Allparallelrun
```

This script decomposes all regions, runs `foamMultiRun` in parallel, reconstructs, creates `case.foam` for ParaView, removes processor directories, and calls `extractData.py` automatically.

**3. Monitor residuals live (separate terminal):**
```bash
python3 plotResiduals.py --live
```

---

## Post-Processing Scripts

### `extractData.py`
Reads converged results from `postProcessing/` and writes `extractedData.txt`. Extracts:
- y⁺ statistics per patch
- Probe temperatures and pressures at two locations in the fluid
- Patch-averaged T and p at inlet, outlet, interface and heater
- Wall heat flux statistics from `wallHeatFlux.dat`
- **Two independent HTC calculations:**
  - Method 1 — Bulk temperature: `h = 1 / (A · R_hs)`, `R_hs = (T_heater − T_mean) / Q`
  - Method 2 — Wall heat flux: `h = q_wall / (T_wall − T_inlet)`
- Wetted area read automatically from the mesh header — no manual update needed when switching geometries

```bash
./extractData.py                        # run from case directory
./extractData.py /path/to/case          # specify path
```

### `plotResiduals.py`
Reads residuals from `postProcessing/fluid/residuals*/0/residuals.dat` and `postProcessing/solid/residuals*/0/residuals.dat`. Fluid fields plotted as solid lines, solid region as dashed.

```bash
python3 plotResiduals.py                # static plot of completed run
python3 plotResiduals.py --live         # refresh every 2 s during run
python3 plotResiduals.py -o out.png     # save to file
```

### `calcTurbulence.py`
Computes k, ε initial conditions and first layer height for target y⁺ values. Edit the four input parameters at the top and run — output is formatted for direct copy-paste into OpenFOAM field files.

```bash
python3 calcTurbulence.py
```

### `calcGCI.py`
Defines the GCI mesh study parameters and computes GCI once simulation results are available. Run without arguments to print the mesh plan; run with `--fill` after entering results to compute GCI, Richardson extrapolation and asymptotic ratio.

```bash
python3 calcGCI.py           # print mesh plan and file naming
python3 calcGCI.py --fill    # compute GCI from filled-in results
```

### `meshGenerator.py`
Generates all meshes automatically via the PyFluent API. Reads all parameters from `calcGCI.py`. Supports single geometry or single level via command-line arguments.

```bash
python3 meshGenerator.py                      # all geometries, all levels
python3 meshGenerator.py --geo 4x4            # single geometry, all levels
python3 meshGenerator.py --geo 4x4 --level 1  # single geometry, single level
```

---

## GCI Study

The grid convergence index (GCI) method (Roache 1994, Celik et al. 2008) is used to quantify discretisation error and confirm grid independence. Three quantities are monitored: thermal resistance R_hs, pressure drop ΔP, and convective HTC h. GCI < 5% between medium and fine mesh is the acceptance criterion.

Full methodology: [guideMeshing.md](guideMeshing.md)

---

## Results

![Heatsink Simulation Result](figures/heatsink.png)

**Mesh views (from Fluent Meshing):**

![Mesh Side View](figures/mesh_side.png)
![Mesh Top View](figures/mesh_top.png)

---

## References

- Menter, F.R. (1994). Two-equation eddy-viscosity turbulence models. *AIAA Journal*, 32(8).
- Roache, P.J. (1994). Perspective: A Method for Uniform Reporting of Grid Refinement Studies. *J. Fluids Eng.*, 116(3).
- Celik, I.B. et al. (2008). Procedure for Estimation and Reporting of Uncertainty Due to Discretization in CFD. *J. Fluids Eng.*, 130(7).
- Benhamadouche, S. et al. (2020). Numerical Simulations of Flow and Heat Transfer in a Wall-Bounded Pin Matrix. *Flow, Turbulence and Combustion*, 104.