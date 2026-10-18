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
System/Integrator XML and final State XML.

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
