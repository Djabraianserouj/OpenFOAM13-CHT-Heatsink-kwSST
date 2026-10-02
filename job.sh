#!/bin/bash -l
# Converts the Fluent mesh ../meshes/<job name>.msh, runs the case in parallel and extracts the results.
# Submitted by runCases.sh with: sbatch --job-name=<case> --chdir=<case> <case>/job.sh
#SBATCH --nodes=1
#SBATCH --ntasks=16
#SBATCH --ntasks-per-node=16
#SBATCH --time=24:00:00
#SBATCH --partition=work
#SBATCH --output=log.slurm_%j.out
#SBATCH --error=log.slurm_%j.err
#SBATCH --export=NONE

module purge
module load openfoam/13
module load python/3.12-conda
unset SLURM_EXPORT_ENV
. "$WM_PROJECT_DIR/bin/tools/RunFunctions"

rm -f log.*   # runApplication skips an application if its log file already exists

runApplication fluent3DMeshToFoam ../meshes/${SLURM_JOB_NAME}.msh
rm constant/polyMesh/faceZones   # Fluent face zones are not needed and break the region split
runApplication splitMeshRegions -cellZonesOnly

runApplication decomposePar -allRegions -force
runParallel foamMultiRun
runApplication reconstructPar -allRegions -latestTime
rm -rf processor*

touch case.foam
python3 extractData.py
