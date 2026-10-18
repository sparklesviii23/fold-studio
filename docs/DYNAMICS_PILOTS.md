# Short protein pilots with OpenMM

Open a protein in Molecular Laboratory → Trajectories → **Run a short protein
pilot · OpenMM**. Select a saved source, give the pilot a name, and choose a step
count and nonzero seed. The workflow uses the shared compute queue and can be
cancelled from the same panel or experiment history.

Initial method: OpenMM 8.6.1, native Apple Silicon CPU, one thread with
deterministic force evaluation; Amber ff14SB protein parameters and OBC2 implicit
solvent, nonperiodic NoCutoff interactions, dielectric constants 1 and 78.5.
OpenMM adds hydrogens using its standard pH-7 assumptions. Existing heavy atoms
must retain their identity and coordinates through that preparation; missing
heavy atoms are not repaired. Inspect histidine variants and any disulfide
assignments through the saved prepared structure and serialized system.

Bounded local minimization uses at most 500 iterations and a requested tolerance
of 10 kJ/mol/nm. This does not certify convergence or a global minimum. A
Langevin-middle integrator then runs at 300 K, friction 1/ps, 1 fs time steps,
hydrogen-bond constraints and constraint tolerance 1e-6. The UI saves eleven
frames, including the state before integration, with explicit MODEL ID, step and
physical-time mapping. Energies are kJ/mol; forces are kJ/mol/nm; displayed
coordinate files use Å and have normal PDB rounding.

The original source file remains unchanged. Three distinct library structures
are saved: hydrogen-prepared, locally minimized, and multi-frame trajectory. No
prediction confidence is assigned. Project ZIPs retain those assets, the original
input, request, execution log, method/runtime/parameter-file hashes, complete
System/Integrator XML, final State XML and an original OpenMM binary checkpoint.
The checkpoint retains internal integration/random state and requires matching
OpenMM version, platform and compatible hardware for restart.

Initial scope is 1–64 canonical protein residues, at most 1,500 prepared atoms,
continuous complete backbones, one coordinate model, resolved alternate
locations, positive occupancy and one-character nonblank chain identifiers.
Force-field template mismatches fail without publishing partial results. Water,
ions, general ligands, arbitrary protonation/force fields and explicit-solvent
simulation require further integration. Pilot duration is at most 5 ps; these
short runs establish neither equilibration nor biological stability, binding or
free energy. Exact trajectories are not promised across runtime/platform changes.

The product runtime includes CPU/Reference components and retained upstream
notices. OpenCL GPU plugins are omitted; this is not a Metal dynamics backend.
Its pinned NumPy ARM64 wheel requires macOS 14 or newer. OpenMM's PyPI checksum,
source revision and license receipts are in `vendor/openmm-runtime.json`.

Evidence includes independent analytic harmonic energy/force checks, original
Reference-versus-CPU comparisons on a 35-residue protein, a real 20-step pilot,
and shared jobs/import/export checks on PDB and mmCIF inputs. See
`reports/openmm-protein-pilot.json`, `openmm-shared-workflow.json` and
`openmm-shared-workflow-cif.json`. Native form and sealed relocated execution
are tracked separately; the full Dynamics Lab remains in development.

Upstream references: [OpenMM simulation guide](https://docs.openmm.org/latest/userguide/application/02_running_sims.html),
[model preparation](https://docs.openmm.org/latest/userguide/application/03_model_building_editing.html),
and [platforms and licenses](https://docs.openmm.org/latest/userguide/library/01_introduction.html).

## Saved-frame motion measurements

In Trajectories choose **Measure coordinate motion · Cα RMSD / RMSF**. This reads
all canonical protein Cα atoms from the saved ensemble with identical identities
in each frame. Optional fitting removes a proper rigid rotation and translation
to the first frame; it needs at least three noncollinear selected atoms. Disabling
fitting reports raw displacement, including whole-body motion. Coordinates and
the live scientific scene remain unchanged.

RMSD is measured against the first saved frame. RMSF is the square root of the
population mean squared displacement about each atom's mean analyzed coordinate,
with equal frame weights and denominator N. Values are Å. Physical times are
shown only when an exact saved OpenMM receipt matches the trajectory checksum
and MODEL IDs. Other supplied ensembles retain frame IDs without inferred times.
Measurements are saved in the shared research history and export as complete
JSON; on-screen tables bound the number of rows. Initial bound: 200,000 selected
atom/frame pairs. Measurement waits for any active local compute job to finish.

Analytic rigid translations/rotations, population RMSF, reflection refusal and
degenerate-geometry checks pass. Raw/fitted RMSD and RMSF on the real 35-Cα,
11-frame native pilot agree with original ChimeraX geometry alignment and
population moments within 0.0001 Å (`trajectory-motion-reference.json`). This
numerical evidence does not establish equilibrated sampling, biological
flexibility, stability or statistical confidence.

`openmm-checkpoint-restoration.json` verifies recorded positions, velocities and
time restored exactly on this machine, followed by two independent matching
five-step CPU continuations. It does not establish portability across platforms,
hardware or OpenMM versions. Native analysis form and relocated checkpoint
acceptance are tracked separately in the master progress file.
