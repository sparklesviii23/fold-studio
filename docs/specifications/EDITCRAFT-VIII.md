# FOLD STUDIO Ω — EDITCRAFT Ω
## ADDENDUM VIII — COMPLETE DNA, RNA AND RIBOSOME 3D MOLECULAR OBSERVATORY

**Append these requirements to the existing EditCraft Master Completion Directive. Preserve all previous requirements.**

# 34. HIGH PRIORITY — MAKE DNA AND RNA STRUCTURES ACTUALLY VIEWABLE

I want to be able to inspect DNA and RNA molecular structures inside Fold Studio, with the same level of interactivity and scientific detail as our existing protein molecular viewer.

This is not optional.

The existing RNA secondary-structure diagrams are useful, but they are insufficient.

**Implement real, interactive three-dimensional DNA, RNA, DNA–RNA hybrid and ribosomal molecular visualization.**

The complete visual interface must operate inside the native macOS Fold Studio application.

Actual structural prediction and other substantial scientific computations should run through our Modal scientific engine.

Rendering, rotation, structure selection and everyday visualization must work natively on the Mac without requiring a cloud GPU.

## A. DNA visualization

Support authentic 3D structures containing:

- Double-stranded DNA.
- Single-stranded DNA.
- DNA–protein complexes.
- DNA–RNA hybrids.
- Experimental DNA conformations.

Display:

- Sugar-phosphate backbone.
- Individual nucleotides.
- Base pairs.
- Major and minor grooves.
- Hydrogen-bond geometry where supported.
- Molecular surfaces.
- Individual atoms.
- Strand direction.

Provide multiple representation modes:

**Helix**

**Cartoon**

**Backbone**

**Sticks**

**Ball and Stick**

**Atoms**

**Molecular Surface**

Allow users to color individual strands, nucleotides, residues and molecular chains.

## B. RNA visualization

Support real 3D structures containing:

- mRNA fragments.
- tRNA.
- rRNA.
- Structured noncoding RNA.
- RNA hairpins.
- RNA–protein complexes.
- RNA–ligand complexes.

Render authentic available atomic structures from PDB/mmCIF files.

Provide:

- Backbone visualization.
- Nucleotide coloring.
- Base-pair inspection.
- Stem-loop highlighting.
- Tertiary structure analysis.
- Interaction inspection.
- Atomic distance measurement.
- Structure comparison.

RNA must be treated as a genuine molecular polymer, not incorrectly rendered as a protein sequence.

## C. RNA secondary structure

Preserve and extend the existing ViennaRNA functionality.

Display:

- Predicted stems.
- Hairpin loops.
- Internal loops.
- Bulges.
- Multiloops.
- Base-pair probabilities.
- Minimum-free-energy structures.
- Alternative conformations.
- Predicted nucleotide accessibility.

Provide an intuitive secondary-structure diagram alongside the sequence.

Allow users to select a nucleotide in the diagram and highlight the corresponding nucleotide in a 3D structure when one is available and correctly mapped.

Do not imply that ViennaRNA's secondary-structure output is an experimentally established 3D atomic structure.

---

# 35. SUPPORT ACTUAL STRUCTURAL FILES

Extend the existing molecular viewer and data contracts to recognize nucleic acid structures correctly.

Support:

- PDB.
- mmCIF.
- Valid nucleic acid structural coordinate records.
- Multiple polymer chains.
- DNA–RNA complexes.
- RNA–protein complexes.
- Modified nucleotides where properly annotated.
- Experimental structures.
- Computationally predicted structures.

Handle nucleic acid residues, including appropriate DNA and RNA residue nomenclature.

Preserve:

- Original atomic coordinates.
- Chain identifiers.
- Residue numbering.
- Insertion codes.
- Alternate locations.
- Occupancy.
- Original chemical identity.
- Experimental metadata where available.

Do not interpret nucleotide residue names as amino acids.

Do not silently discard unfamiliar modified nucleotides.

Where chemical components are not recognized, preserve the atoms and explicitly label unsupported representations.

### Atomic geometry

Implement scientifically appropriate:

- Backbone bonds.
- Base-pair representation.
- Atom selection.
- Nucleotide selection.
- Molecular contacts.
- Distance measurement.
- Structural alignment.
- Coordinate-preserving exports.

Keep generated visual elements distinct from measured or predicted atomic coordinates.

---

# 36. CONNECT DNA/RNA SEQUENCES TO THE 3D VIEWER

This is a defining usability requirement.

I want synchronized molecular inspection.

### DNA example

When I select a nucleotide in the DNA sequence viewer, highlight the corresponding nucleotide in the 3D DNA structure.

When I select a base pair in the 3D viewer, highlight its mapped positions in the sequence view.

### RNA example

When I select a nucleotide in RNA secondary structure, highlight its mapped position in the 3D RNA model.

When I select a structural helix, show its nucleotide range.

### Protein connection

When an RNA sequence contains a valid coding region:

- Show the nucleotide sequence.
- Show the corresponding codons.
- Show the translated amino acids.
- Open the available protein structure.
- Highlight correctly mapped positions.

Use verified coordinate relationships.

Never invent a genomic-to-structure mapping when it is unavailable.

---

# 37. COMPLETE THE RIBOSOME OBSERVATORY

The previous session successfully transferred and parsed the authentic 4V9D structure with 146,921 atoms.

However, full native rendered acceptance remained unfinished.

Complete it now.

### Required capabilities

- Display the entire genuine structure.
- Rotate and zoom smoothly.
- Isolate ribosomal subunits.
- Color rRNA separately from ribosomal proteins.
- Inspect individual polymer chains.
- Select nucleotides and amino-acid residues.
- Display available tRNA/mRNA components correctly.
- Inspect molecular contacts.
- Control molecular representation styles.
- Preserve accurate atomic coordinates.

Optimize rendering performance without deleting atoms from the scientific structure.

Use appropriate level-of-detail rendering where necessary, while preserving the underlying complete molecular data.

### Translation visualization

Provide an optional educational explanation of:

- mRNA codons.
- tRNA recognition.
- Ribosomal A, P and E sites.
- Polypeptide elongation.
- Ribosomal translocation.
- Translation termination.

Use schematic animation where appropriate and clearly distinguish it from experimentally observed molecular motion.

---

# 38. ADD A STRUCTURAL DISCOVERY AND IMPORT PANEL

Inside Molecular Biology Observatory, implement:

**Open Molecular Structure**

The user should be able to:

- Import a local PDB/mmCIF file.
- Open a structure from the Research Library.
- Retrieve an appropriate public structure from RCSB PDB.
- Search by structure identifier.
- Search for compatible DNA/RNA structures.
- Open previously saved scientific structures.
- Compare two compatible molecular structures.

### Initial validation examples

Use appropriate authentic reference structures such as:

- A well-characterized B-DNA duplex.
- An experimentally determined tRNA.
- The previously imported 4V9D ribosome.
- A suitable RNA–protein complex.

Verify the actual structure identifiers, molecular contents and source metadata before using them as reference fixtures.

Do not hardcode arbitrary illustrations as molecular data.

### Cloud prediction integration

If the user submits a sequence without a known 3D structure, distinguish:

**Sequence available**

**Secondary structure predicted**

**3D structure unavailable**

**3D prediction available**

**Experimental structure available**

Investigate suitable validated RNA tertiary-structure prediction methods as a separate scientific-engine integration.

Do not claim arbitrary RNA or DNA tertiary structures can be predicted accurately by a basic sequence viewer.

---

# 39. PREMIUM MOLECULAR OBSERVATORY DESIGN

The visualizer must follow the existing premium Fold Studio aesthetic:

**PlayStation 5 × Apple TV × Scientific Molecular Workstation**

Design a professional, immersive interface.

### Proposed layout

**Left panel — Structure Explorer**

- Molecular chains.
- DNA strands.
- RNA chains.
- Protein chains.
- Structural components.
- Visibility controls.
- Coloring controls.

**Center — Large interactive 3D viewport**

- Genuine atomic structure.
- Smooth rotation.
- Zoom.
- Pan.
- Structure selection.
- Molecular representations.
- Optional molecular labels.

**Right panel — Molecular Inspector**

- Selected nucleotide.
- Selected residue.
- Atom identity.
- Chain.
- Sequence position.
- Structural annotations.
- Base-pair information.
- Molecular contacts.
- Available experimental metadata.

**Bottom panel — Sequence and RNA Structure**

- DNA sequence.
- RNA sequence.
- Base-pair arcs.
- Nucleotide annotations.
- Codon translation where relevant.
- Structural selection synchronization.

Allow panels to be resized and hidden.

Keep the molecular viewer usable on a MacBook display.

Maintain smooth performance for large biological complexes.

---

# 40. MANDATORY REAL VIEWER ACCEPTANCE

Do not mark DNA/RNA visualization as complete until the installed Fold Studio application demonstrates:

1. A real double-stranded DNA structure can be opened.
2. Both DNA strands render correctly.
3. Individual nucleotides can be selected.
4. A genuine RNA 3D structure can be opened.
5. RNA molecular geometry renders correctly.
6. Real RNA secondary-structure calculations can be displayed.
7. A selected nucleotide maps correctly between sequence and structure when valid mapping exists.
8. The 4V9D ribosome can be opened and interacted with.
9. Chain coloring and visibility controls work.
10. Camera rotation, zoom and pan work.
11. Atom and nucleotide inspection functions correctly.
12. Real coordinates remain intact.
13. The viewer survives large-structure loading without crashing.
14. DNA, RNA and protein polymers are classified correctly.
15. Generated and experimental structure origins remain clearly labeled.
16. Structure import and export preserve scientific information.
17. The native app remains responsive.
18. Existing protein viewing and molecular engineering features remain fully functional.

### Final instruction

**I want to actually SEE DNA and RNA molecules in three dimensions, explore their structure, select nucleotides, examine molecular interactions, and move between sequence, secondary structure and 3D structure inside Fold Studio.**

Do not satisfy this requirement with RNA diagrams alone.

Do not satisfy it with static images.

Do not satisfy it with a nonfunctional viewer panel.

Implement, install and verify the real scientific visualizations.

Keep the interface native on macOS and substantive structural prediction on Modal.

Preserve everything already implemented.

**Make Molecular Biology Observatory a genuine, interactive DNA–RNA–Ribosome–Protein visual research instrument.**