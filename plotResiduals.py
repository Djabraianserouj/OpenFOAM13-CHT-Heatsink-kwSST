#!/usr/bin/env python3
"""
Plot residuals from OpenFOAM postProcessing residuals.dat files.

Reads from:
  postProcessing/fluid/residuals(...)/0/residuals.dat
  postProcessing/solid/residuals(...)/0/residuals.dat

Usage:
  ./plotResiduals.py                          # auto-detect from current directory
  ./plotResiduals.py /path/to/case            # specify case directory
  ./plotResiduals.py /path/to/case --live     # refresh every 2s while solver runs
  ./plotResiduals.py /path/to/case -o out.png # save to PNG

Requires: matplotlib  (pip install matplotlib)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
except ImportError:
    print("matplotlib is required:  pip install matplotlib", file=sys.stderr)
    sys.exit(1)


# ── File discovery ─────────────────────────────────────────────────────────────

def find_residuals_dat(case_dir: Path, region: str) -> Path | None:
    """
    Search postProcessing/<region>/residuals*/0/residuals.dat
    The folder name contains the field list e.g. residuals(p_rgh,U,h,k,omega,region=fluid)
    so we glob for any folder starting with 'residuals'.
    """
    base = case_dir / "postProcessing" / region
    if not base.exists():
        return None
    candidates = sorted(base.glob("residuals*/0/residuals.dat"))
    if not candidates:
        # also try without subdirectory (older layout)
        candidates = sorted(base.glob("residuals*residuals.dat"))
    return candidates[0] if candidates else None


# ── Parsing ────────────────────────────────────────────────────────────────────

def parse_dat(path: Path) -> tuple[list[str], dict[str, list[tuple[float, float]]]]:
    """
    Parse an OpenFOAM residuals.dat file.

    Returns:
        headers : list of field names (excluding Time)
        series  : dict fieldName -> [(time, residual), ...]
                  N/A values and time=0 rows are skipped.
    """
    headers: list[str] = []
    series: dict[str, list[tuple[float, float]]] = {}

    text = path.read_text(errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Header line: "# Time   p_rgh   Ux ..."
        if line.startswith("# Time"):
            headers = line.lstrip("# ").split()
            # first token is "Time", rest are field names
            headers = headers[1:]
            for h in headers:
                series[h] = []
            continue

        # Skip comment lines that are not the header
        if line.startswith("#"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        try:
            t = float(parts[0])
        except ValueError:
            continue

        # Skip time=0 row (all N/A)
        if t == 0.0:
            continue

        for i, h in enumerate(headers):
            val_str = parts[i + 1] if i + 1 < len(parts) else "N/A"
            if val_str.upper() == "N/A":
                continue
            try:
                val = float(val_str)
            except ValueError:
                continue
            series[h].append((t, max(val, 1e-30)))

    return headers, series


# ── Plotting ───────────────────────────────────────────────────────────────────

COLORS_FLUID = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2",
]
COLORS_SOLID = ["#17becf", "#bcbd22"]


def draw_axes(ax: plt.Axes,
              fluid_series: dict[str, list[tuple[float, float]]],
              solid_series: dict[str, list[tuple[float, float]]],
              title: str) -> None:
    ax.clear()
    ax.set_yscale("log")
    ax.set_xlabel("Pseudo-time / iteration", fontsize=11)
    ax.set_ylabel("Initial residual", fontsize=11)
    ax.set_title(title, fontsize=12)
    ax.grid(True, which="both", linestyle=":", alpha=0.5)

    for i, (field, pts) in enumerate(sorted(fluid_series.items())):
        if not pts:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        color = COLORS_FLUID[i % len(COLORS_FLUID)]
        ax.plot(xs, ys, lw=1.4, color=color, label=f"fluid/{field}")

    for i, (field, pts) in enumerate(sorted(solid_series.items())):
        if not pts:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        color = COLORS_SOLID[i % len(COLORS_SOLID)]
        ax.plot(xs, ys, lw=1.4, color=color, linestyle="--", label=f"solid/{field}")

    ax.legend(loc="upper right", fontsize=8, framealpha=0.9)


def plot_static(case_dir: Path, outfile: Path | None) -> None:
    fluid_path = find_residuals_dat(case_dir, "fluid")
    solid_path = find_residuals_dat(case_dir, "solid")

    if not fluid_path and not solid_path:
        print(
            f"No residuals.dat files found under {case_dir}/postProcessing/",
            file=sys.stderr,
        )
        sys.exit(1)

    fluid_series: dict[str, list[tuple[float, float]]] = {}
    solid_series: dict[str, list[tuple[float, float]]] = {}

    if fluid_path:
        print(f"Reading fluid residuals: {fluid_path}")
        _, fluid_series = parse_dat(fluid_path)
    else:
        print("Warning: fluid residuals.dat not found", file=sys.stderr)

    if solid_path:
        print(f"Reading solid residuals:  {solid_path}")
        _, solid_series = parse_dat(solid_path)
    else:
        print("Warning: solid residuals.dat not found", file=sys.stderr)

    n_fluid = sum(len(v) for v in fluid_series.values())
    n_solid = sum(len(v) for v in solid_series.values())
    n_steps = max(
        (max(t for t, _ in v) for v in fluid_series.values() if v),
        default=0,
    )

    title = f"Residuals — {case_dir.name}  ({int(n_steps)} iterations)"

    fig, ax = plt.subplots(figsize=(11, 6))
    draw_axes(ax, fluid_series, solid_series, title)
    plt.tight_layout()

    if outfile:
        fig.savefig(outfile, dpi=150)
        print(f"Saved: {outfile}")
    else:
        plt.show()


def run_live(case_dir: Path) -> None:
    """Refresh the plot every 2 s while the solver writes new data."""
    fig, ax = plt.subplots(figsize=(11, 6))
    plt.ion()

    def refresh(_frame: int) -> None:
        fluid_path = find_residuals_dat(case_dir, "fluid")
        solid_path = find_residuals_dat(case_dir, "solid")

        fluid_series: dict[str, list[tuple[float, float]]] = {}
        solid_series: dict[str, list[tuple[float, float]]] = {}

        if fluid_path and fluid_path.exists():
            try:
                _, fluid_series = parse_dat(fluid_path)
            except OSError:
                pass

        if solid_path and solid_path.exists():
            try:
                _, solid_series = parse_dat(solid_path)
            except OSError:
                pass

        n_steps = max(
            (max(t for t, _ in v) for v in fluid_series.values() if v),
            default=0,
        )
        title = f"Residuals (live) — {case_dir.name}  ({int(n_steps)} iterations)"
        draw_axes(ax, fluid_series, solid_series, title)
        fig.canvas.draw_idle()

    _ani = animation.FuncAnimation(
        fig, refresh, interval=2000, cache_frame_data=False
    )
    plt.show(block=True)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Plot OpenFOAM CHT residuals from postProcessing residuals.dat files."
    )
    ap.add_argument(
        "case_dir",
        nargs="?",
        default=".",
        help="Path to OpenFOAM case directory (default: current directory)",
    )
    ap.add_argument(
        "-o", "--output",
        type=Path,
        help="Save plot to PNG file (non-live mode only)",
    )
    ap.add_argument(
        "--live",
        action="store_true",
        help="Refresh plot every 2 s while solver is running",
    )
    args = ap.parse_args()

    case_dir = Path(args.case_dir).resolve()
    if not case_dir.is_dir():
        print(f"Case directory not found: {case_dir}", file=sys.stderr)
        sys.exit(1)

    if args.live:
        if args.output:
            print("--output is ignored in --live mode", file=sys.stderr)
        run_live(case_dir)
    else:
        plot_static(case_dir, args.output)


if __name__ == "__main__":
    main()