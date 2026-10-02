"""
Reads the converged values (last line) from postProcessing/ and writes results.csv in the case directory.
Run from inside the case directory: python3 extractData.py
R_hs = (T_heater - T_in) / Q, with area-averaged temperatures at the heater face and the inlet.
"""
import glob
import os
import re

Q = 25.0   # heater power [W]


def last_line(pattern):
    # last data line of the first file matching pattern, split into columns
    lines = open(glob.glob(pattern)[0]).read().split("\n")
    lines = [l for l in lines if l.strip() and not l.startswith("#")]
    return lines[-1].split()


def n_cells(region):
    header = open(f"constant/{region}/polyMesh/owner", errors="ignore").read(2000)
    return int(re.search(r"nCells:\s*(\d+)", header).group(1))


inlet  = last_line("postProcessing/fluid/patchAverage_inlet*/0/surfaceFieldValue.dat")    # time T p
outlet = last_line("postProcessing/fluid/patchAverage_outlet*/0/surfaceFieldValue.dat")   # time T p
heater = last_line("postProcessing/solid/patchAverage_heater*/0/surfaceFieldValue.dat")   # time T

# wallHeatFlux.dat and yPlus.dat have one line per patch and time step: keep the last heat sink line
whf  = [l.split() for l in open(glob.glob("postProcessing/fluid/wallHeatFlux*/0/wallHeatFlux.dat")[0])
        if "fluid_to_solid" in l][-1]     # time patch min max Q q
yplus = [l.split() for l in open(glob.glob("postProcessing/fluid/yPlus*/0/yPlus.dat")[0])
         if "fluid_to_solid" in l][-1]    # time patch min max average

T_in, T_out, T_heater = float(inlet[1]), float(outlet[1]), float(heater[1])
row = {
    "case":         os.path.basename(os.getcwd()),
    "iterations":   inlet[0],
    "cells_fluid":  n_cells("fluid"),
    "cells_solid":  n_cells("solid"),
    "T_in":         T_in,
    "T_out":        T_out,
    "T_heater":     T_heater,
    "R_hs":         (T_heater - T_in) / Q,
    "dp":           float(inlet[2]) - float(outlet[2]),
    "Q_wall":       float(whf[4]),         # heat into the air, should be close to Q
    "yplus_hs_avg": float(yplus[4]),
    "yplus_hs_max": float(yplus[3]),
}

with open("results.csv", "w") as f:
    f.write(",".join(row.keys()) + "\n")
    f.write(",".join(str(v) for v in row.values()) + "\n")
print(open("results.csv").read())
