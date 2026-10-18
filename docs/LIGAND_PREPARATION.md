# Local ligand preparation

Open Molecular Architect → Design campaigns → Prepare a small molecule · RDKit.
Enter one connected isomeric SMILES, an explicit name and seed, and choose how
many conformers to sample. The job uses the existing local compute queue. Saved
conformers appear as structures in Research Library; Export SDF checks the saved
chemical file's checksum. Complete project ZIPs include both coordinate and SDF
assets, their integrity manifest, inputs and execution logs.

The included RDKit runtime performs ETKDGv3 sampling followed by MMFF94s local
minimization, with one CPU thread and a fixed seed. Only converged, finite-energy
conformers are eligible. The lowest energy sampled conformer is saved; this is
not proof of the global minimum. Energies are in kcal/mol for the specified
molecule and force field, and are not binding free energies.

Formal charges and specified stereochemistry are retained. Hydrogens complete
the input's explicit valence state. Preparation does not titrate pH, strip salts,
neutralize, enumerate tautomers or predict binding. Potential stereochemistry
must be specified; disconnected compounds, unsupported isotope/radical transport,
and incomplete MMFF parameter coverage are refused. Initial bounds: 128 heavy
atoms, 512 total atoms and eight conformers.

SDF is the chemical interchange representation, retaining connectivity, bond
orders, charge and stereochemistry. Its coordinate rounding is checked within
0.0001 Å. The coordinate file and recorded atom/bond graph link the same atoms to
the existing molecular viewer. Native partial charges are not inferred from
formal charges. Docking, simulation and biological activity require separate
validated workflows.

Runtime: RDKit 2026.09.1 (wheel metadata 2026.9.1), BSD-3-Clause. The existing
bundled scientific runtime retains its upstream license files. No new model
weights or separate Python installation are required in the packaged app.

Validation evidence: `reports/ligand-chemistry-acceptance.json` and
`reports/ligand-native-transport.json`. These are small-molecule integration and
interchange checks, not independent force-field accuracy or biological validation.
Native form and visual acceptance are tracked separately in the master progress
file; do not infer their completion from backend checks.

Original method references: [RDKit 3D molecule guide](https://www.rdkit.org/docs/GettingStartedInPython.html#working-with-3d-molecules),
[MMFF optimization status and parameters](https://www.rdkit.org/docs/cppapi/MMFF_8h_source.html),
and [force-field energy units](https://www.rdkit.org/new_docs/source/rdkit.ForceField.rdForceField.html).
The runtime is pinned separately from the current online documentation.
