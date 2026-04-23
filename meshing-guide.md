================================================================================
  CONJUGATE HEAT TRANSFER (CHT) MESHING WORKFLOW GUIDE
  Fluent Meshing -> OpenFOAM via fluent3DMeshToFoam
================================================================================

This guide documents the step-by-step process for preparing and meshing a
Conjugate Heat Transfer (CHT) geometry in Ansys Fluent Meshing and transferring
the mesh to OpenFOAM.

--------------------------------------------------------------------------------
PHASE 1: GEOMETRY PREPARATION IN INVENTOR & SPACECLAIM
--------------------------------------------------------------------------------

1.  Export the geometry from Autodesk Inventor as a STEP file (.step / .stp).

2.  Open the STEP file in Ansys SpaceClaim.

3.  Set the Share Topology property to "Share" for all components.
    - This ensures that shared/connected mesh interfaces are generated between
      adjacent regions (e.g., fluid-solid interfaces) during meshing.

4.  Label surfaces using Named Selections:
    - Go to the "Groups" tab and use the "Create Named Selection" option.
    - Define the following named selections as appropriate for your geometry:
        * inlet          -> the fluid inlet surface(s)
        * outlet         -> the fluid outlet surface(s)
        * wall           -> external walls (e.g., outer surface of the heat
                            exchanger pipe or enclosure)
        * interface      -> the surface(s) between the fluid and solid region.
                            NOTE: It is sufficient to select the surface from
                            ONE side only (e.g., the outer surfaces of the fluid
                            domain that are in contact with the solid domain).

5.  Save the geometry as a SpaceClaim document file with the ".scdoc" extension.
    - This format ensures a smooth and reliable transition between the geometry
      and meshing stages within the Fluent Meshing environment.

--------------------------------------------------------------------------------
PHASE 2: MESHING IN FLUENT MESHING
--------------------------------------------------------------------------------

6.  Import the .scdoc file into Ansys Fluent Meshing.

7.  Apply mesh sizing settings as appropriate for your geometry.
    - NOTE: There are no universal sizing guidelines. Select element sizes and
      mesh controls based on the nature, complexity, and required resolution of
      your specific geometry.

8.  Under "Describe Geometry", configure the following:
    - Select: "The geometry consists of both fluid and solid regions and/or voids"
    - Set all remaining options to: "No"

9.  Under "Update Boundaries", assign the correct boundary types:
    - velocity-inlet   -> for inlet surface(s)
    - pressure-outlet  -> for outlet surface(s)
    - wall             -> for wall surface(s)
    - interface        -> for the fluid-solid interface surface(s)
    
    IMPORTANT: The interface surface(s) will be assigned as "wall" by default.
    This MUST be manually changed to "interface". This is critical because the
    interface boundary type is required by OpenFOAM to properly combine the
    fluid and solid regions when the mesh is imported.

10. Under "Update Regions", rename and assign the mesh regions:
    - Rename regions to "fluid" and "solid" (use clear, descriptive names).
    - Assign the correct region type (fluid or solid) to each region.

11. Under "Boundary Layers", configure the boundary layer settings:
    - "Grow on"  -> select "solid-fluid-interface"
      (This restricts boundary layer growth to the interface between the fluid
      and solid regions only, avoiding unnecessary layers on other surfaces.)
    - "Add in"   -> select "fluid-regions"
      (This ensures the boundary layers are generated inside the fluid domain,
      where the velocity and thermal gradients are most significant.)

12. Generate the Volume Mesh using the appropriate cell size settings for your
    simulation requirements.

--------------------------------------------------------------------------------
PHASE 3: EXPORT AND IMPORT INTO OPENFOAM
--------------------------------------------------------------------------------

13. Write the mesh from Fluent Meshing in Legacy Compressed Mesh Files (.msh.gz) format while de-selecting the "Write Binary Files" option.

14. In your OpenFOAM case directory, run the following conversion command:

        fluent3DMeshToFoam <meshFile>.msh

    This converts the Fluent mesh format into the OpenFOAM polyMesh format,
    preserving boundary names, region assignments, and interface definitions.

15. Check the converted mesh and boundary conditions in the OpenFOAM case to
    verify that all regions, boundaries, and interfaces have been correctly
    transferred.

================================================================================
  NOTES & REMINDERS
================================================================================

- The "interface" boundary type in Fluent Meshing is essential for CHT cases.
  Without it, OpenFOAM will treat the fluid-solid boundary as a wall instead
  of a coupled thermal interface between two regions.

- Named selections defined in SpaceClaim carry over as boundary names into
  Fluent Meshing, which simplifies the boundary assignment step.

- Saving the geometry as .scdoc (rather than re-importing the STEP) preserves
  the Share Topology and Named Selection settings made in SpaceClaim.

- Always verify the mesh quality (skewness, aspect ratio, orthogonality) before
  exporting to OpenFOAM.

================================================================================
  END OF GUIDE
================================================================================

