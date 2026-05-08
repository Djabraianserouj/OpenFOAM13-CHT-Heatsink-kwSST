#!/bin/bash -l
#SBATCH --job-name=PLACEHOLDER
#SBATCH --nodes=1
#SBATCH --ntasks=16
#SBATCH --ntasks-per-node=16
#SBATCH --time=10:00:00
#SBATCH --partition=work
#SBATCH --output=log.slurm_%j.out
#SBATCH --error=log.slurm_%j.err
#SBATCH --export=NONE

module purge
module load openfoam/13
module load python/3.12-conda
unset SLURM_EXPORT_ENV

. "$WM_PROJECT_DIR/bin/tools/RunFunctions"

# ── Convert mesh ───────────────────────────────────────────────────────────
runApplication fluent3DMeshToFoam ../meshes/${SLURM_JOB_NAME}.msh
runApplication splitMeshRegions -cellZones -overwrite

# ── Decompose ──────────────────────────────────────────────────────────────
NP="$(getNumberOfProcessors)"
echo "Decomposing all regions for $NP MPI processes..."
runApplication decomposePar -allRegions -force

# ── Solve ──────────────────────────────────────────────────────────────────
echo "Running foamMultiRun in parallel ($NP cores)..."
runParallel foamMultiRun

# ── Reconstruct ────────────────────────────────────────────────────────────
runApplication reconstructPar -allRegions

# ── Post-process ───────────────────────────────────────────────────────────
touch case.foam
rm -rf processor*
python3 extractData.py

echo "============================================================"
echo "  Job complete : $SLURM_JOB_NAME"
echo "============================================================"