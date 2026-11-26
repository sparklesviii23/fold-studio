# Supplied coordinate ensembles

In Research Library choose **Import coordinate ensemble**, then select a
multi-MODEL PDB. Open the saved structure and choose **Trajectories** in the
Molecular Laboratory. The slider selects a supplied frame; Play transfers frames
in order and waits for each scene update. Pause stops further frame requests.
Changing models also stops playback.

Every frame must have the same ordered atom identities, elements, charges,
occupancies and B factors. Coordinates may differ. Resolve alternate locations
before import. Frame IDs must be positive, unique and increasing. Initial limits
are 1,000 frames, 250,000 atoms per frame and the existing 100 MB file limit.
Per-frame anisotropic and uncertainty records require a separate importer.
Use ordinary structure import for models with differing topology or metadata.

The complete original PDB remains a checksummed library asset and is included in
the project ZIP. ChimeraX reads it as coordinate sets with the original MODEL
numbers, while fold displays the active coordinates in its existing
viewer. Reopening a linked record retains the authoritative model and current
frame. Atom handles remain stable across frame changes.

This does not generate a molecular-dynamics simulation. Frame IDs do not imply
physical time. No force field, sampling interval, temperature or trajectory
equilibration is inferred. A supplied ensemble may come from NMR, modeling,
simulation, or another source; retain that source's method and uncertainty.

Evidence: eight import contracts and `reports/coordinate-ensemble.json` verify
three explicitly artificial frames, five repeated native frame switches, exact
coordinates/IDs/handles, analytic unfitted RMSD and complete raw project export.
This is integration and geometry evidence, not biological validation. Native
form and viewport acceptance are tracked separately in the master progress file.
