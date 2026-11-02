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
The M1 snapshot did not include AlphaFold model parameters. Fold's experimental float32 PyTorch
attention adapter follows the upstream equations and is explicitly limited to
kernel-level compatibility; it does not imply an official upstream association.

ChimeraX remains a separately installed, unmodified runtime in this milestone.
No ChimeraX source, executable or Qt interface has been added to the distribution.
The local installation's license is available at
`Contents/share/docs/license.html`. A fully self-contained runtime distribution
is a separate packaging milestone; existing user permissions are not revoked or
reinterpreted here. Nothing in this development milestone is uploaded or published.

## Current development runtime and AlphaFold 2 parameters

Subsequent to M1/M2, the native development build includes a CPython/JAX scientific
runtime with original Python LICENSE, package license files and dist-info.
Unchanged AlphaFold 2 parameter files (five multimer v3 models and two pTM models)
are included with provenance and attribution in `models/alphafold/NOTICE.md`.
The official AlphaFold repository identifies AF2 parameters as CC BY 4.0:
https://github.com/google-deepmind/alphafold#model-parameters-license
https://creativecommons.org/licenses/by/4.0/
ChimeraX remains separately installed; no ChimeraX binary is bundled.

The experimental Metal runtime additionally includes MetalJAX 0.11.9 by the
MetalJAX contributors (Apache-2.0), https://github.com/eterevsky/metaljax .
Its bundled MLX implementation and all dependency licenses/dist-info are retained
in runtime-metal. The adapter changes execution precision and initialization
without modifying vendored BindCraft2 files. Exact tested package pins are in
`reports/requirements-metaljax.txt`. No upstream endorsement is implied.

The next development package stages the existing tested Boltz Community 2.10.12
and PyTorch 2.14.1 runtime, preserving their dependency licenses. Eighteen
scikit-learn extension OpenMP dependency paths are made relative within the
private runtime copy; original environments and numerical library algorithms
remain unchanged. Boltz confidence model provenance is pinned to the publisher
repository Git LFS object in `scientific/boltz-parameters.json`. Model and chemical
resources remain in managed application data, rather than being part of the
source repository.


The bounded local quantum tool uses PySCF 2.14.0 (Apache-2.0,
https://github.com/pyscf/pyscf), h5py 3.16.0 (BSD-style,
https://github.com/h5py/h5py), and their wheel-provided dependencies. All supplied
license/notice files remain in the private runtime's distribution metadata,
including h5py's bundled HDF5 and compression-library notices. Exact public
wheel URLs, versions and SHA-256 values are in `vendor/quantum-runtime.json`.
PySCF and Libxc scientific citations accompany calculation results. This CPU
library integration does not bundle GPU4PySCF or trained model checkpoints.

### pysam 0.24.1 and bundled HTSlib/SAMtools

Pinned macOS ARM CPU genomic I/O wheel, SHA-256 and official source are recorded in `vendor/genomics-runtime.json`. pysam is MIT licensed; the wheel-provided HTSlib/SAMtools and bundled dependency license notices are retained in the packaged runtime. No reference genomes, alignments or trained weights are redistributed by this dependency.

### ViennaRNA 2.7.2 (Vienna RNA Package)

Pinned macOS ARM CPU wheel, SHA-256 and official source are recorded in `vendor/rna-runtime.json`; it is installed into the main scientific runtime for the RNA-to-Protein Laboratory. Vienna RNA Package, © Institute for Theoretical Chemistry, University of Vienna (https://www.tbi.univie.ac.at/RNA/). Licensed for research, educational and commercial use and modification provided it is not redistributed for any fee other than media costs and the authors are credited. Please cite: Lorenz R et al. (2011) ViennaRNA Package 2.0, Algorithms Mol Biol 6:26, doi:10.1186/1748-7188-6-26. Inclusion in a commercial product requires contacting the authors. The wheel's own licence files are retained in the packaged runtime.


### Published PNA benchmark data

`scientific/antisense_data/pna-2022.json` derives from Table 1 of Popella et al., Nucleic Acids Research 50(11), 6435–6452 (2022), https://doi.org/10.1093/nar/gkac362, under CC BY-NC 4.0 (https://creativecommons.org/licenses/by-nc/4.0/). Non-commercial research use; commercial reuse requires appropriate rights. `pna-2025.json` derives from Supplementary Tables 1 and 3 of Danti et al., Advanced Science 12, 2504284 (2025), https://doi.org/10.1002/advs.202504284; article license CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Sequence case was normalized; ranges, bounds, preparation identity, source attribution and footnotes are retained. Neither author group endorses this app or its exploratory fitted baseline.

### xterm.js terminal

@xterm/xterm 5.5.0 and @xterm/addon-fit 0.10.0, MIT licensed, https://github.com/xtermjs/xterm.js. Copyright the xterm.js authors. The upstream license text is retained at `vendor/xterm-LICENSE` and packaged with the app.
