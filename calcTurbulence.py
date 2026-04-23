#!/usr/bin/env python3
"""
Turbulence initial condition calculator for OpenFOAM CHT cases.

Computes:
  - k and omega initial conditions    (k-omega SST model)
  - First cell layer height           (for target y+ value)
  - Guidance for k-epsilon vs k-omega SST mesh requirements

Usage:
    python3 calcTurbulence.py
    (edit the INPUT PARAMETERS section below, then run)
"""

import math

# =============================================================================
#  INPUT PARAMETERS — edit these values
# =============================================================================

U    = 4.7      # Inlet velocity            [m/s]
I    = 0.05     # Turbulence intensity       [-]     (0.05 = 5%)
W    = 0.040    # Duct width                 [m]
H    = 0.050    # Duct height                [m]

# Fluid properties (air at 20°C)
rho  = 1.204    # Density                    [kg/m³]
mu   = 1.8e-5   # Dynamic viscosity          [Pa·s]

# Target y+ values for first layer height calculation
yplus_kepsilon  = 30.0   # target y+ for k-epsilon  (wall functions, aim 30-300)
yplus_kwsst     = 1.0    # target y+ for k-omega SST (resolved, aim < 1)

# =============================================================================
#  CONSTANTS
# =============================================================================

Cmu  = 0.09     # k-epsilon model constant   [-]
k_l  = 0.07     # Length scale prefactor     [-]     l = 0.07 * Dh

# =============================================================================
#  CALCULATIONS — GEOMETRY
# =============================================================================

# Kinematic viscosity
# nu = mu / rho
nu = mu / rho

# Hydraulic diameter
# Dh = 4 * A / P = 4 * (W * H) / (2 * (W + H))
Dh = 4 * W * H / (2 * (W + H))

# Reynolds number
# Re = U * Dh / nu
Re = U * Dh / nu

# =============================================================================
#  CALCULATIONS — TURBULENCE INITIAL CONDITIONS
# =============================================================================

# Turbulent length scale
# l = 0.07 * Dh
l = k_l * Dh

# Turbulent kinetic energy
# k = 1.5 * (U * I)^2
k = 1.5 * (U * I) ** 2

# Turbulent dissipation rate (intermediate)
# epsilon = Cmu^0.75 * k^1.5 / l
epsilon = (Cmu ** 0.75) * (k ** 1.5) / l

# Specific dissipation rate (k-omega SST)
# omega = epsilon / (Cmu * k)
omega = epsilon / (Cmu * k)

# Mixing length for turbulentMixingLengthFrequencyInlet BC
# mixingLength = l = 0.07 * Dh
mixing_length = l

# =============================================================================
#  CALCULATIONS — FIRST LAYER HEIGHT (y+ based)
# =============================================================================
#
# Step 1: skin friction coefficient (Schlichting correlation for pipe/duct flow)
#   Cf = 0.026 * Re^(-1/7)
#
# Step 2: wall shear stress
#   tau_w = 0.5 * Cf * rho * U^2
#
# Step 3: friction velocity
#   u_tau = sqrt(tau_w / rho)
#
# Step 4: first layer height from target y+
#   delta_y = y+ * nu / u_tau
#

# Skin friction coefficient
# Cf = 0.026 * Re^(-1/7)
Cf = 0.026 * Re ** (-1.0 / 7.0)

# Wall shear stress
# tau_w = 0.5 * Cf * rho * U^2
tau_w = 0.5 * Cf * rho * U ** 2

# Friction velocity
# u_tau = sqrt(tau_w / rho)
u_tau = math.sqrt(tau_w / rho)

# First layer height for k-epsilon (y+ ~ 30-300, wall functions)
# delta_y = y+ * nu / u_tau
delta_y_kepsilon = yplus_kepsilon * nu / u_tau

# First layer height for k-omega SST (y+ < 1, resolves viscous sublayer)
# delta_y = y+ * nu / u_tau
delta_y_kwsst = yplus_kwsst * nu / u_tau

# =============================================================================
#  OUTPUT
# =============================================================================

SEP  = "=" * 60
SEP2 = "-" * 60

print()
print(SEP)
print("  OpenFOAM — turbulence calculator")
print(SEP)
print()
print("  Input parameters:")
print(f"    U    = {U}     m/s     (inlet velocity)")
print(f"    I    = {I*100:.1f} %          (turbulence intensity)")
print(f"    W    = {W*1e3:.1f}   mm      (duct width)")
print(f"    H    = {H*1e3:.1f}   mm      (duct height)")
print(f"    rho  = {rho}   kg/m³   (fluid density)")
print(f"    mu   = {mu:.2e}  Pa·s    (dynamic viscosity)")
print()
print("  Derived geometry:")
print(f"    nu   = {nu:.4e}  m²/s    (kinematic viscosity)")
print(f"    Dh   = {Dh*1e3:.4f}  mm      (hydraulic diameter)")
print(f"    Re   = {Re:.0f}             (Reynolds number)")
print(f"    l    = {l*1e3:.4f}  mm      (turbulent length scale)")
print()

print(SEP2)
print("  Turbulence initial conditions")
print(SEP2)
print()
print("  0/fluid/k")
print(f"    internalField   uniform {k:.6f};        // m²/s²")
print()
print("  0/fluid/omega")
print(f"    internalField   uniform {omega:.6f};        // s⁻¹")
print()
print("  Inlet BC — turbulentMixingLengthFrequencyInlet")
print(f"    mixingLength    {mixing_length:.6f};              // m")
print()
print("  Reference equations:")
print(f"    k       = 1.5 * (U*I)^2             = {k:.6f}  m²/s²")
print(f"    epsilon = Cmu^0.75 * k^1.5 / l      = {epsilon:.6f}  m²/s³")
print(f"    omega   = epsilon / (Cmu * k)        = {omega:.6f}  s⁻¹")
print()

print(SEP2)
print("  First cell layer height (wall meshing)")
print(SEP2)
print()
print("  Friction estimates:")
print(f"    Cf              = {Cf:.6f}             (skin friction coeff)")
print(f"    tau_w           = {tau_w:.6f}  Pa       (wall shear stress)")
print(f"    u_tau           = {u_tau:.6f}  m/s     (friction velocity)")
print()
print("  +-----------------------------------------------------+")
print(f"  |  k-epsilon   (target y+ = {yplus_kepsilon:>5.1f})                    |")
print(f"  |    first layer height = {delta_y_kepsilon*1e3:.4f} mm               |")
print(f"  |    wall functions valid, coarser mesh OK           |")
print("  +-----------------------------------------------------+")
print(f"  |  k-omega SST (target y+ = {yplus_kwsst:>5.1f})                     |")
print(f"  |    first layer height = {delta_y_kwsst*1e6:.4f} um               |")
print(f"  |    viscous sublayer resolved, finer mesh needed    |")
print("  +-----------------------------------------------------+")
print()
print("  mesh settings:")
print(f"    k-epsilon   firstLayerThickness  {delta_y_kepsilon:.6f};  // m")
print(f"    k-omega SST firstLayerThickness  {delta_y_kwsst:.6f};  // m")
print()
print(SEP)
print()
