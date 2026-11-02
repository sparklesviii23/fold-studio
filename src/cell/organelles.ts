/** Organelle names and short descriptions, indexed by the shader's material id. */
export const organelles: Record<number, {name: string; note: string}> = {
  1: {name: 'Plasma membrane', note: 'A lipid bilayer about 5 nm thick that bounds the cell and carries its receptors, channels and transporters.'},
  2: {name: 'Nuclear envelope', note: 'Two membranes pierced by thousands of nuclear pore complexes that gate the traffic of RNA and proteins.'},
  3: {name: 'Chromatin', note: 'DNA wound around histone octamers and folded into loops and territories. Active genes sit in open, accessible regions.'},
  4: {name: 'Nucleolus', note: 'Where ribosomal RNA is transcribed and ribosomal subunits are assembled.'},
  5: {name: 'Mitochondrion', note: 'A double-membraned organelle that makes ATP by oxidative phosphorylation and carries its own 16.6 kb genome.'},
  6: {name: 'Cristae', note: 'Folds of the inner mitochondrial membrane, packed with respiratory complexes and ATP synthase.'},
  7: {name: 'Endoplasmic reticulum', note: 'Sheets and tubules where secreted and membrane proteins are made, folded and checked.'},
  8: {name: 'Golgi apparatus', note: 'Stacked cisternae that modify, sort and package proteins for their destinations.'},
  9: {name: 'Ribosome', note: 'An RNA–protein machine of about 4.3 MDa that translates messenger RNA into protein, a few amino acids per second.'},
  10: {name: 'Vesicle', note: 'Membrane carriers and lysosomes moving cargo between compartments.'},
  11: {name: 'Microtubule', note: 'Hollow tubulin polymers 25 nm across: the tracks for kinesin and dynein motors.'},
  12: {name: 'Cytosolic proteins', note: 'The cytosol holds 200–300 mg/mL of protein, so neighbouring molecules are only a few nanometres apart.'},
  13: {name: 'Centrosome', note: 'The main microtubule-organising centre, built around a pair of centrioles.'},
  14: {name: 'Lipid droplet', note: 'Neutral lipids — triglycerides and sterol esters — wrapped in a phospholipid monolayer.'},
  15: {name: 'Glycogen granules', note: 'Branched glucose polymer stored as rosettes, abundant in liver cells.'},
};

export const NUCLEUS: [number, number, number] = [-0.12, 0.03, 0.02];
export const journeys: {id: string; name: string; target: [number, number, number]; distance: number; yaw: number; pitch: number; slice: number}[] = [
  {id: 'overview', name: 'Whole cell', target: [0, 0, 0], distance: 3.4, yaw: 0.6, pitch: 0.28, slice: 0.12},
  {id: 'nucleus', name: 'Into the nucleus', target: NUCLEUS, distance: 1.45, yaw: 0.9, pitch: 0.2, slice: 0.04},
  {id: 'chromatin', name: 'Chromatin', target: [-0.16, 0.0, 0.05], distance: 0.62, yaw: 1.2, pitch: 0.15, slice: 0.0},
  {id: 'mitochondrion', name: 'Mitochondrion', target: [0.55, 0.36, 0.22], distance: 0.55, yaw: 0.2, pitch: 0.35, slice: 0.0},
  {id: 'golgi', name: 'Golgi & ER', target: [0.3, 0.18, -0.05], distance: 0.8, yaw: -0.3, pitch: 0.25, slice: 0.02},
];

export const styles = ['Illustrative', 'Cinematic', 'Fluorescence', 'Cryo-ET', 'Cel cartoon', 'Electron micrograph', 'Confocal'] as const;

/**
 * Illustrative cell archetypes. Geometry is schematic; `diameter` sets the
 * scale bar (typical published sizes), not a measured model.
 */
export interface CellType {id: string; name: string; note: string; diameter: number; nucleus: [number, number, number]; nucleusRadius: number; golgi: [number, number, number]; box: number; droplet: [number, number, number, number]; mitoExtra: boolean; glycogen: boolean}
export const cellTypes: CellType[] = [
  {id: 'generic', name: 'Generic', note: 'A textbook animal cell.', diameter: 20, nucleus: [-0.12, 0.03, 0.02], nucleusRadius: 0.37, golgi: [0.33, 0.21, -0.06], box: 0, droplet: [0, 0, 0, 0], mitoExtra: false, glycogen: false},
  {id: 'hepatocyte', name: 'Hepatocyte', note: 'Polyhedral liver cell, rich in mitochondria, ER and glycogen.', diameter: 25, nucleus: [-0.05, 0.02, 0.0], nucleusRadius: 0.3, golgi: [0.3, 0.24, -0.08], box: 0.75, droplet: [0, 0, 0, 0], mitoExtra: true, glycogen: true},
  {id: 'lymphocyte', name: 'Lymphocyte', note: 'A small immune cell: a large nucleus in a thin rim of cytoplasm.', diameter: 8, nucleus: [-0.06, 0.0, 0.0], nucleusRadius: 0.6, golgi: [0.62, 0.3, -0.1], box: 0, droplet: [0, 0, 0, 0], mitoExtra: false, glycogen: false},
  {id: 'adipocyte', name: 'Adipocyte', note: 'A fat cell: one lipid droplet fills it and pushes the nucleus to the edge.', diameter: 100, nucleus: [-0.62, 0.22, 0.2], nucleusRadius: 0.2, golgi: [-0.55, -0.3, -0.2], box: 0, droplet: [0.14, -0.04, -0.05, 0.62], mitoExtra: false, glycogen: false},
];
export const layerNames = ['Nucleus', 'Chromatin', 'Mitochondria', 'ER', 'Golgi', 'Ribosomes', 'Vesicles', 'Cytoskeleton', 'Crowding'] as const;

