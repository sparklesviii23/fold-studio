# Third-party notices

FOLD STUDIO application code is provided under the MIT license. Third-party packages, downloaded models, reference data, and optional external software retain their own licenses and attribution requirements. Lockfiles identify the exact JavaScript and Rust packages. `scientific/requirements-tested-macos-arm64.txt` identifies the validated inference environment.

Primary components include React (MIT), Mol* (MIT), Tauri and its plugins (MIT or Apache-2.0), Lucide (ISC), and Boltz community code and model weights (MIT). See the license files in each upstream repository and installed package for authoritative terms and transitive dependencies.

Bundled reference data were retrieved on 9 October 2026:

- UniProt Consortium: canonical human records ANGPTL3 Q9Y5C1, ANGPTL8 Q6UXH0, APOA5 Q6Q788, and LPL P06858. UniProt data are available under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Source: [UniProt licensing](https://www.uniprot.org/help/license), [API support data](https://www.uniprot.org/api-documentation/support-data), and https://rest.uniprot.org/.
- AlphaFold Protein Structure Database, a collaboration of Google DeepMind and EMBL-EBI: AF-Q9Y5C1-F1 model v6 and associated metadata for ANGPTL3. Model file: https://alphafold.ebi.ac.uk/files/AF-Q9Y5C1-F1-model_v6.cif. Data license: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); see the [official license and disclaimer](https://alphafold.ebi.ac.uk/assets/License-Disclaimer.pdf).

The included structures labeled database references are attributed predictions, not locally produced scientific results. The separately included Boltz coordinate outputs were produced by real local runs and retain execution provenance. Neither type is experimental validation.

Upstream model weights are downloaded to local application storage and are excluded from the application and source archives. ColabFold is opened as its official external notebook. The Molecular Laboratory uses a separately installed UCSF ChimeraX 1.12 scientific runtime in a GUI-free helper process. The runtime, original Qt interface, upstream Python/C++ implementations and model weights are not bundled. Original FOLD adapter code and a metadata-only capability inventory are included. UCSF ChimeraX is developed by the UCSF Resource for Biocomputing, Visualization, and Informatics (RBVI), with scientific credits at https://www.rbvi.ucsf.edu/chimerax/docs/credits.html. The installed ChimeraX license governs use; see https://www.rbvi.ucsf.edu/chimerax/docs/licensing.html and the installation’s share/docs/license.html. Permission for private academic use does not grant permission to redistribute ChimeraX binaries or modified upstream code.

This notice is not a replacement for dependency license files. Redistribution should preserve those notices and the reference-data attribution.

## wwPDB Chemical Component Dictionary

The 20 canonical amino-acid CCD components in `scientific/components/` and their normalized subset in `scientific/amino-acids.json` were retrieved from RCSB PDB on 10 October 2026. The data remain attributed to the [wwPDB Chemical Component Dictionary](https://www.wwpdb.org/data/ccd). Individual file URLs, SHA-256 checksums and component modification dates accompany every template. Reference: Westbrook et al., *The chemical component dictionary: complete descriptions of constituent molecules in experimentally determined 3D macromolecules in the Protein Data Bank* (2015), [doi:10.1093/bioinformatics/btu789](https://doi.org/10.1093/bioinformatics/btu789). These are chemical definitions and ideal coordinates, not new experimental or prediction results.

## Project Metal: versioned BindCraft2 component

`vendor/bindcraft2` is an unmodified source snapshot of BindCraft2 revision
`c0ee638d11bc010817c2c97ee58ed5c323e664e2`. The source-available hosting-restricted
license and copyright notices are retained in `vendor/bindcraft2/LICENSE` and
`README_licensing_section.md`. It is not covered by Fold Studio's MIT license.
AlphaFold/ColabDesign code, ProteinMPNN code and HyperMPNN parameters retain their
upstream notices/terms. The per-file SHA-256 manifest is `vendor/bindcraft2-source.json`.
No AlphaFold model parameters are included. Fold's experimental float32 PyTorch
attention adapter follows the upstream equations and is explicitly limited to
kernel-level compatibility; it does not imply an official upstream association.

ChimeraX remains a separately installed, unmodified runtime in this milestone.
No ChimeraX source, executable or Qt interface has been added to the distribution.
The local installation's license is available at
`Contents/share/docs/license.html`. A fully self-contained runtime distribution
is a separate packaging milestone; existing user permissions are not revoked or
reinterpreted here. Nothing in this development milestone is uploaded or published.
