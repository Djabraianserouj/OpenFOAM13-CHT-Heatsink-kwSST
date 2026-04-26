#!/usr/bin/env python3
"""
Extract converged postProcessing data from an OpenFOAM CHT case and write
to extractedData.txt in the case directory.

Only the last non-comment line is read from each file (= converged value).

Usage:
    ./extractData.py                          # run from inside the case directory
    ./extractData.py /path/to/case            # specify case directory
    ./extractData.py /path/to/case -o myOut.txt

Output file: extractedData.txt  (or custom name via -o)

HTC is calculated using two independent methods:
  Method 1 — Bulk temperature method:
      h = 1 / (A_total * R_hs)
      R_hs = (T_heater - T_mean) / Q
      T_mean = (T_inlet + T_outlet) / 2
      Uses: patchAverage_inlet, patchAverage_outlet, patchAverage_heater

  Method 2 — Wall heat flux method (more direct):
      h = q_wall / (T_wall - T_inlet)
      q_wall = area-averaged wall heat flux from wallHeatFlux.dat
      T_wall = area-averaged fluid temperature at fluid_to_solid interface
      Uses: wallHeatFlux.dat, patchAverage_interface
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


# ── Constants (edit these to match your case) ──────────────────────────────────
Q        = 25.0          # Applied heater power [W]
A_TOTAL  = 12617e-6      # Fallback wetted area [m²] — overridden by mesh header if available


# ── Helpers ────────────────────────────────────────────────────────────────────

def find_dir(base: Path, prefix: str) -> Path | None:
    """
    Find the first directory under `base` whose name starts with `prefix`.
    Handles the OpenFOAM naming convention e.g. patchAverage_inlet(region=fluid).
    """
    matches = sorted(base.glob(f"{prefix}*"))
    matches = [m for m in matches if m.is_dir()]
    return matches[0] if matches else None


def last_data_line(path: Path) -> list[str] | None:
    """
    Return the columns of the last non-comment, non-empty line in a file.
    Returns None if no data line is found.
    """
    last: list[str] | None = None
    for line in path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            last = stripped.split()
    return last


def read_patch_area(case_dir: Path, region: str, folder_prefix: str,
                    filename: str = "surfaceFieldValue.dat") -> float | None:
    """
    Read the wetted area from the '# Area : X.XXX' header line
    in a surfaceFieldValue.dat file. Returns area in m² or None if not found.
    """
    base = case_dir / "postProcessing" / region
    folder = find_dir(base, folder_prefix)
    if folder is None:
        return None
    dat = folder / "0" / filename
    if not dat.exists():
        return None
    for line in dat.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("# Area"):
            try:
                return float(stripped.split(":")[-1].strip())
            except ValueError:
                return None
    return None


def read_dat(case_dir: Path, region: str, folder_prefix: str,
             filename: str = "surfaceFieldValue.dat") -> list[str] | None:
    """
    Locate  postProcessing/<region>/<folder_prefix>*/0/<filename>
    and return the columns of the last data line.
    """
    base = case_dir / "postProcessing" / region
    folder = find_dir(base, folder_prefix)
    if folder is None:
        print(f"  [WARN] folder not found: {base / folder_prefix}*")
        return None
    dat = folder / "0" / filename
    if not dat.exists():
        print(f"  [WARN] file not found: {dat}")
        return None
    cols = last_data_line(dat)
    if cols is None:
        print(f"  [WARN] no data in: {dat}")
    return cols


def read_probe(case_dir: Path, region: str, field: str) -> list[str] | None:
    """
    Locate  postProcessing/<region>/probes*/0/<field>
    and return the columns of the last data line.
    """
    base = case_dir / "postProcessing" / region
    folder = find_dir(base, "probes")
    if folder is None:
        print(f"  [WARN] probes folder not found under {base}")
        return None
    probe_file = folder / "0" / field
    if not probe_file.exists():
        print(f"  [WARN] probe file not found: {probe_file}")
        return None
    cols = last_data_line(probe_file)
    if cols is None:
        print(f"  [WARN] no data in: {probe_file}")
    return cols


def read_yplus(case_dir: Path) -> dict[str, dict[str, str]]:
    """
    Parse postProcessing/fluid/yPlus*/0/yPlus.dat.
    Returns { patch_name: {min, max, average} } for the last iteration only.
    Columns: Time  patch  min  max  average
    """
    base = case_dir / "postProcessing" / "fluid"
    folder = find_dir(base, "yPlus")
    if folder is None:
        print("  [WARN] yPlus folder not found")
        return {}
    dat = folder / "0" / "yPlus.dat"
    if not dat.exists():
        print(f"  [WARN] yPlus.dat not found: {dat}")
        return {}
    rows: list[list[str]] = []
    for line in dat.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            rows.append(stripped.split())
    if not rows:
        return {}
    last_time = rows[-1][0]
    result: dict[str, dict[str, str]] = {}
    for cols in rows:
        if cols[0] == last_time and len(cols) >= 5:
            patch = cols[1]
            result[patch] = {"min": cols[2], "max": cols[3], "average": cols[4]}
    return result


def read_wallheatflux(case_dir: Path) -> list[str] | None:
    """
    Parse postProcessing/fluid/wallHeatFlux*/0/wallHeatFlux.dat.
    Returns the last data row for the fluid_to_solid patch.
    Columns: Time  patch  min[W/m2]  max[W/m2]  Q[W]  q[W/m2]
    """
    base = case_dir / "postProcessing" / "fluid"
    folder = find_dir(base, "wallHeatFlux")
    if folder is None:
        print("  [WARN] wallHeatFlux folder not found")
        return None
    dat = folder / "0" / "wallHeatFlux.dat"
    if not dat.exists():
        print(f"  [WARN] wallHeatFlux.dat not found: {dat}")
        return None
    last = None
    for line in dat.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            cols = stripped.split()
            if len(cols) >= 6 and cols[1] == "fluid_to_solid":
                last = cols
    if last is None:
        print("  [WARN] no fluid_to_solid data found in wallHeatFlux.dat")
    return last


def safe(cols: list[str] | None, index: int, label: str = "N/A") -> str:
    """Safely retrieve a column value, return label if missing."""
    if cols is None:
        return label
    try:
        return cols[index]
    except IndexError:
        return label


# ── Main extraction ────────────────────────────────────────────────────────────

def extract(case_dir: Path) -> dict:
    """
    Extract all converged values. Returns a dict with numeric floats where
    available, else the raw string 'N/A'.
    """
    r: dict = {}

    # ── Raw column reads ───────────────────────────────────────────────────────
    inlet      = read_dat(case_dir, "fluid", "patchAverage_inlet")
    outlet     = read_dat(case_dir, "fluid", "patchAverage_outlet")
    heater     = read_dat(case_dir, "solid", "patchAverage_heater")
    interface  = read_dat(case_dir, "fluid", "patchAverage_interface")
    probe_T    = read_probe(case_dir, "fluid", "T")
    probe_p    = read_probe(case_dir, "fluid", "p")
    yplus      = read_yplus(case_dir)
    whf        = read_wallheatflux(case_dir)

    # ── Wetted area — read from mesh header, fall back to constant ─────────────
    # Area is extracted from the '# Area : X.XXX' line in patchAverage_interface
    A_mesh = read_patch_area(case_dir, "fluid", "patchAverage_interface")
    r["A_mesh"]        = A_mesh if A_mesh is not None else A_TOTAL
    r["A_mesh_source"] = "mesh header (patchAverage_interface)" if A_mesh is not None \
                         else "fallback constant (A_TOTAL)"

    # ── Iteration (inlet file used — all patches converge at same step) ────────
    r["iteration"] = safe(inlet, 0)
    r["yplus"]     = yplus

    # ── Probes ─────────────────────────────────────────────────────────────────
    r["probe0_T"] = safe(probe_T, 1)
    r["probe0_p"] = safe(probe_p, 1)
    r["probe1_T"] = safe(probe_T, 2)
    r["probe1_p"] = safe(probe_p, 2)

    # ── Fluid patches ──────────────────────────────────────────────────────────
    r["inlet_T"]  = safe(inlet,  1)
    r["inlet_p"]  = safe(inlet,  2)
    r["outlet_T"] = safe(outlet, 1)
    r["outlet_p"] = safe(outlet, 2)

    # ── Solid patch ────────────────────────────────────────────────────────────
    r["heater_T"] = safe(heater, 1)

    # ── Interface patch (fluid side of fluid_to_solid) ─────────────────────────
    r["interface_T"] = safe(interface, 1)   # area-averaged fluid T at interface [K]

    # ── Wall heat flux at fluid_to_solid interface ─────────────────────────────
    # Columns: Time  patch  min  max  Q  q
    r["whf_q_min"] = safe(whf, 2)   # min local heat flux    [W/m²]
    r["whf_q_max"] = safe(whf, 3)   # max local heat flux    [W/m²]
    r["whf_Q"]     = safe(whf, 4)   # total integrated power [W] — sanity check
    r["whf_q_avg"] = safe(whf, 5)   # area-averaged heat flux [W/m²]

    # ── Derived: pressure drop and temperature rise ────────────────────────────
    try:
        r["delta_p"] = float(r["inlet_p"]) - float(r["outlet_p"])
    except (ValueError, TypeError):
        r["delta_p"] = None

    try:
        r["delta_T"] = float(r["outlet_T"]) - float(r["inlet_T"])
    except (ValueError, TypeError):
        r["delta_T"] = None

    # ── Method 1: Bulk temperature HTC ────────────────────────────────────────
    # h = 1 / (A * R_hs)
    # R_hs = (T_heater - T_mean) / Q
    # T_mean = (T_inlet + T_outlet) / 2
    try:
        T_in     = float(r["inlet_T"])
        T_out    = float(r["outlet_T"])
        T_heater = float(r["heater_T"])
        A        = float(r["A_mesh"])
        T_mean   = (T_in + T_out) / 2.0
        R_hs     = (T_heater - T_mean) / Q
        h_bulk   = 1.0 / (A * R_hs)
        r["T_mean"] = T_mean
        r["R_hs"]   = R_hs
        r["h_bulk"] = h_bulk
    except (ValueError, TypeError, ZeroDivisionError):
        r["T_mean"] = None
        r["R_hs"]   = None
        r["h_bulk"] = None

    # ── Method 2: Wall heat flux HTC ──────────────────────────────────────────
    # h = q_wall / (T_wall - T_inlet)
    # q_wall from wallHeatFlux.dat
    # T_wall from patchAverage_interface (fluid side)
    # T_ref = T_inlet
    try:
        q_avg  = float(r["whf_q_avg"])
        T_wall = float(r["interface_T"])
        T_ref  = float(r["inlet_T"])
        r["h_wallflux"] = q_avg / (T_wall - T_ref)
    except (ValueError, TypeError, ZeroDivisionError):
        r["h_wallflux"] = None

    return r


# ── Formatting helpers ─────────────────────────────────────────────────────────

def fmt(val, unit: str = "", precision: int = 6) -> str:
    """Format a numeric value or return N/A."""
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return f"{val:.{precision}e} {unit}".strip()
    return f"{val} {unit}".strip()


# ── Writer ─────────────────────────────────────────────────────────────────────

def write_output(r: dict, out_path: Path, case_dir: Path) -> None:
    SEP  = "=" * 62
    SEC  = "*** "        # section marker
    SEP2 = "-" * 62

    lines = [
        SEP,
        "  OpenFOAM CHT — Extracted converged results",
        f"  Case      : {case_dir.name}",
        f"  Iteration : {r['iteration']}",
        SEP,
        "",
        f"{SEC}y+ wall distance — mesh quality check",
    ]

    yplus = r.get("yplus", {})
    if yplus:
        for patch_name, vals in sorted(yplus.items()):
            lines.append(f"    {patch_name}")
            lines.append(f"      min                  : {vals['min']}")
            lines.append(f"      max                  : {vals['max']}")
            lines.append(f"      average              : {vals['average']}")
    else:
        lines.append("    N/A")

    lines += [
        "",
        f"{SEC}Probes — fluid region",
        "    Probe 0  (0.035, 0.025, 0.0) m",
        f"      T                    : {fmt(r['probe0_T'], 'K')}",
        f"      p                    : {fmt(r['probe0_p'], 'Pa')}",
        "    Probe 1  (0.275, 0.025, 0.0) m",
        f"      T                    : {fmt(r['probe1_T'], 'K')}",
        f"      p                    : {fmt(r['probe1_p'], 'Pa')}",
        "",
        f"{SEC}Patch averages — fluid region",
        "    Inlet",
        f"      Average T            : {fmt(r['inlet_T'],  'K')}",
        f"      Average p            : {fmt(r['inlet_p'],  'Pa')}",
        "    Outlet",
        f"      Average T            : {fmt(r['outlet_T'], 'K')}",
        f"      Average p            : {fmt(r['outlet_p'], 'Pa')}",
        "    Interface (fluid_to_solid — fluid side)",
        f"      Average T            : {fmt(r['interface_T'], 'K')}",
        "",
        f"{SEC}Patch average — solid region",
        "    Heater",
        f"      Average T            : {fmt(r['heater_T'], 'K')}",
        "",
        f"{SEC}Wall heat flux — fluid_to_solid interface",
        f"    q_min                  : {fmt(r['whf_q_min'], 'W/m²')}",
        f"    q_max                  : {fmt(r['whf_q_max'], 'W/m²')}",
        f"    q_avg                  : {fmt(r['whf_q_avg'], 'W/m²')}",
        f"    Q_total (sanity check) : {fmt(r['whf_Q'],     'W')}",
        "",
        f"{SEC}Derived quantities",
        f"    Pressure drop          : {fmt(r['delta_p'], 'Pa')}",
        f"    Temperature rise       : {fmt(r['delta_T'], 'K')}",
        "",
        f"{SEC}Heat sink performance metrics",
        f"    Applied power    Q     : {Q:.2f} W",
        f"    Wetted area      A     : {fmt(r['A_mesh'], 'm²')}",
        f"    Area source            : {r['A_mesh_source']}",
        "",
        "    --> Method 1 — Bulk temperature method",
        "        h = 1 / (A * R_hs),  R_hs = (T_heater - T_mean) / Q",
        "        T_mean = (T_inlet + T_outlet) / 2",
        f"        Mean fluid temp  T_m : {fmt(r['T_mean'], 'K')}",
        f"        Thermal resist. R_hs : {fmt(r['R_hs'],   'K/W')}",
        f"        HTC (bulk)       h   : {fmt(r['h_bulk'], 'W/(m²·K)')}",
        "",
        "    --> Method 2 — Wall heat flux method",
        "        h = q_wall / (T_wall - T_inlet)",
        "        q_wall from wallHeatFlux.dat, T_wall from patchAverage_interface",
        f"        Wall temp    T_wall  : {fmt(r['interface_T'], 'K')}",
        f"        HTC (wallflux)   h   : {fmt(r['h_wallflux'], 'W/(m²·K)')}",
        "",
        SEP,
        "",
        "  Raw key-value pairs (for scripted parsing)",
        SEP2,
    ]

    # Scripted parsing block — skip iteration and yplus dict
    skip = {"iteration", "yplus", "A_mesh_source"}
    for key, val in r.items():
        if key in skip:
            continue
        lines.append(f"  {key:<25} {fmt(val)}")
    yplus = r.get("yplus", {})
    if yplus:
        for patch_name, vals in sorted(yplus.items()):
            lines.append(f"  yplus_{patch_name}_min     {vals['min']}")
            lines.append(f"  yplus_{patch_name}_max     {vals['max']}")
            lines.append(f"  yplus_{patch_name}_avg     {vals['average']}")

    lines += ["", SEP]

    text = "\n".join(lines) + "\n"
    out_path.write_text(text)
    print(text)
    print(f"Written to: {out_path}")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Extract converged postProcessing data from an OpenFOAM CHT case."
    )
    ap.add_argument(
        "case_dir",
        nargs="?",
        default=".",
        help="Path to OpenFOAM case directory (default: current directory)",
    )
    ap.add_argument(
        "-o", "--output",
        default="extractedData.txt",
        help="Output filename (default: extractedData.txt)",
    )
    args = ap.parse_args()

    case_dir = Path(args.case_dir).resolve()
    if not case_dir.is_dir():
        print(f"Case directory not found: {case_dir}", file=sys.stderr)
        sys.exit(1)

    out_path = case_dir / args.output
    print(f"Case directory : {case_dir}")
    print(f"Output file    : {out_path}\n")

    results = extract(case_dir)
    write_output(results, out_path, case_dir)


if __name__ == "__main__":
    main()