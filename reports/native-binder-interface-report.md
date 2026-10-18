# FOLD STUDIO molecular intelligence report

Analysis: da018f29-5b5a-4db7-bc7a-a0e2feb5a266 · calculation engine 1.1.0
Source: design_l60_7eeb451168a769ef_seq0
Coordinate SHA-256: aa00439f682ce01152a51bd9b3c8aa316a21cdd1ec2146fdba9ca103f979359f
Created: 2026-10-18T04:03:56.542604+00:00

## Experiment and structural characterization

Chain A: Prepared target · target · 115 protein residues · 921 atoms.
Observed sequence: AFTVTVPKDLYVVEYGSNMTIECKFPVEKQLDLAALIVYWEMEDKNIIQFVHGEEDLKVQHSSYRQRARLLKDQLSLGNAALQITDVKLQDAGVYRCMISYGGADYKRITVKVNA
Quality: 0 residues with missing standard heavy atoms; 0 numbering gaps; 0 unusual consecutive peptide C–N distances.

Chain B: BindCraft2 designed binder · candidate · 60 protein residues · 504 atoms.
Observed sequence: MEKEKEIEKRMWINIIKGLPERVSEEKKEELIKYVEEQYKTGTFDRNEVSAKIHAELAKV
Quality: 0 residues with missing standard heavy atoms; 0 numbering gaps; 0 unusual consecutive peptide C–N distances.

Prediction metadata retained with the source:
- Prediction model: Unavailable
- Software version: Unavailable
- Random seed: Unavailable
- Recycles: Unavailable
- Diffusion steps: Unavailable
- Samples: Unavailable
- MSA source: Unavailable

## Calculated interface measurements

Heavy-atom contacts at ≤4.0 Å: 161 atom pairs, 39 unique residue pairs, 38 interface residues.
Steric clashes: 15 atom pairs across 7 residue pairs; 3 severe atom overlaps.
Contact composition: 120 atom pairs involving N/O/S and 41 other heavy-atom pairs. These descriptive atom categories are not an electrostatic-energy calculation.

Isolated target SASA: 7021.187 Å²; isolated peptide SASA: 4680.626 Å²; complex SASA: 9953.909 Å².
Total solvent-accessible area loss: 1747.904 Å². Conventional per-interface area (half the total loss): 873.952 Å².

Chemical interaction records (atom-level unless ring centroids are specified):
- hydrophobic contact: 34 (geometric)
- polar approach: 21 (tentative)
- salt bridge: 15 (tentative)

ChimeraX strict cross-partner hydrogen bonds: 3. Original chemical geometry criteria, zero distance/angle slack; donor geometry may be inferred for missing H. Separate from explicit-hydrogen screens; no hydrogens or protonation were added. Full donor/acceptor identities and criteria are retained in JSON.

Closest measured contact atom pairs:
- A ARG125 NH2 ↔ B GLU4 OE2: 1.543 Å
- A GLU58 OE1 ↔ B ARG10 NH2: 1.994 Å
- A ARG125 NH2 ↔ B GLU4 CD: 2.213 Å
- A ARG125 CZ ↔ B GLU4 OE2: 2.264 Å
- A ARG113 NH1 ↔ B ILE7 CG2: 2.273 Å
- A SER117 OG ↔ B SER50 OG: 2.339 Å
- A ARG125 NH1 ↔ B GLU4 OE2: 2.371 Å
- A HIS69 ND1 ↔ B ARG22 NH2: 2.462 Å
- A TYR123 OH ↔ B GLU4 OE2: 2.483 Å
- A ARG125 NH2 ↔ B GLU4 OE1: 2.491 Å

Largest steric overlaps:
- A ARG125 NH2 ↔ B GLU4 CD: distance 2.213 Å, overlap 1.307 Å (severe)
- A ARG113 NH1 ↔ B ILE7 CG2: distance 2.273 Å, overlap 1.247 Å (severe)
- A ARG125 NH2 ↔ B GLU4 OE2: distance 1.543 Å, overlap 1.117 Å (severe)
- A HIS69 CB ↔ B ARG22 NH2: distance 2.608 Å, overlap 0.912 Å (moderate)
- A GLU58 CD ↔ B ARG10 NH2: distance 2.642 Å, overlap 0.878 Å (moderate)
- A ASP61 CA ↔ B ARG10 NH1: distance 2.681 Å, overlap 0.839 Å (moderate)
- A ARG113 NH1 ↔ B ILE7 CD1: distance 2.701 Å, overlap 0.819 Å (moderate)
- A HIS69 ND1 ↔ B ARG22 NH2: distance 2.462 Å, overlap 0.818 Å (moderate)
- A HIS69 CE1 ↔ B LEU57 CB: distance 2.823 Å, overlap 0.817 Å (moderate)
- A ARG125 CZ ↔ B GLU4 OE2: distance 2.264 Å, overlap 0.766 Å (moderate)

## Prediction confidence

Chain A mean pLDDT: 91.937 / 100.
Chain B mean pLDDT: 90.528 / 100.
Target-row → peptide-column PAE: Unavailable; peptide-row → target-column PAE: Unavailable.
pTM: Unavailable; ipTM: Unavailable.
PAE row/column orientation follows the source provider. No missing matrix was inferred from pLDDT.
PAE unavailable; no matrix is inferred from pLDDT.

## Hotspots and residue correspondence

No hotspot set was selected.

## Methods draft

FOLD deterministic analysis engine 1.1.0 analysed coordinate model 1. One residue-level alternate conformer was selected by highest summed occupancy; ties were resolved lexicographically. Zero-occupancy atoms and waters were omitted. Heavy-atom Euclidean contacts use distance ≤ 4.0 Å. Atom-pair and unique residue-pair counts were reported separately.
Clashes use chimerax-default radii with overlap ≥ 0.6 Å (severe ≥ 1.0 Å), with hydrogen-bond allowance 0.4 Å. Native mode uses installed ChimeraX chemical atom typing and a four-bond exclusion; offline Bondi mode uses elemental radii without hydrogen-bond allowance. No source coordinates were relaxed or protonated.
Potential hydrogen bonds require explicit template-bonded hydrogens with donor–acceptor ≤ 3.5 Å, H–acceptor ≤ 2.5 Å and donor–H–acceptor ≥ 120.0°. Missing-hydrogen donor/acceptor approaches remain tentative, rather than being called hydrogen bonds.
SASA uses elemental Bondi radii in both clash modes and Shrake–Rupley with 240 deterministic Fibonacci sphere points per heavy atom and 1.4 Å probe. Both partners use the same point sampling. Conventional interface area is half the sum of isolated partner areas minus complex area. This is a geometric area, not an affinity measurement.
Chemical screens, settings, mapped atom identities and source confidence hashes are included in the paired JSON export.

## Reproducibility and matched controls

This single-coordinate report does not establish cross-seed reproducibility or an advantage over a control. Use saved multi-analysis comparisons and the candidate/control dashboard. Historical manually reported counts are not inputs to these calculations.

## Evidence-calibrated interpretation

The supplied model contains geometric contacts under the stated settings. These calculations do not establish sequence-specific binding, affinity, inhibition or therapeutic efficacy.

## Limitations

- Measurements describe the supplied coordinate model, not experimentally demonstrated binding, inhibition or affinity.
- Default analysis uses one coordinate model and one residue-level alternate conformer (highest summed occupancy); zero-occupancy atoms and waters are omitted.
- Distances are in Å and areas in Å². Contacts include heavy atoms only; unique residue pairs are counted separately.
- Clash radii follow the saved radiusMethod: elemental Bondi, or source-specific ChimeraX default chemical radii. Native hydrogen-bond allowance follows the saved hbAllowance setting; offline Bondi mode uses zero. Cross-partner covalent links are not automatically excluded; native-default clash counts can differ.
- Standard-residue chemistry assumes neutral pH Lys/Arg positive and Asp/Glu negative. Histidine protonation is unspecified. No hydrogens are added during analysis; optional preparation creates a separate derived structure.
- Only explicit-hydrogen donor–H–acceptor geometry is called a potential hydrogen bond; missing-H approaches remain tentative. Electrostatic complementarity is unavailable without validated charge/protonation preparation.
- Shrake–Rupley SASA uses finite Fibonacci sphere sampling and heavy atoms; inspect convergence before using absolute areas. Interface area is half the total SASA loss.
- Observed sequence gaps do not establish missing biological residues. Full-length/mature identity requires a verified reference sequence and numbering metadata.
- Cross-partner strict native chemical geometry; may infer donor geometry for missing H. Distinct from explicit-hydrogen screens; not energetic or experimental validation.

## Scientific methods sources

- Bondi A. van der Waals Volumes and Radii. J Phys Chem (1964), DOI: 10.1021/j100785a001.
- Shrake A, Rupley JA. Environment and exposure to solvent of protein atoms. J Mol Biol (1973), DOI: 10.1016/0022-2836(73)90011-9.
- Horn BKP. Closed-form solution of absolute orientation using unit quaternions. JOSA A (1987), DOI: 10.1364/JOSAA.4.000629.

Export the JSON and CSV alongside this report to retain complete numerical tables and source provenance.