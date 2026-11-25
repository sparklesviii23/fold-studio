"""A real cell imaged by electron microscopy, and Brownian dynamics of a molecule inside its measured geometry.

Data (<library>/cell_em/data/jrc_hela-2; OpenOrganelle, Janelia COSEM, CC BY 4.0): whole interphase HeLa cell
`jrc_hela-2`, focused-ion-beam scanning electron microscopy (FIB-SEM), acquired at 4 x 4 x 5.24 nm. This module
installs the dataset's own coarsest pyramid level s4 (750 x 100 x 398 voxels of 64 x 64 x 83.84 nm, about
48 x 6.4 x 33.4 µm) of the EM volume and of thirteen COSEM organelle segmentations. Every N5 block is stored byte for byte
under `original/` with its S3 source and SHA-256 in `manifest.json`; nothing is fetched until the user asks.
Cite: Xu CS et al. Nature 2021;599:147-151 (doi:10.1038/s41586-021-03992-4) for the volume and Heinrich L et al.
Nature 2021;599:141-146 (doi:10.1038/s41586-021-04061-2) for the segmentations.

Derived files (`derived/`, never replacing originals):
  em_u8.npy       EM signal, linearly rescaled from the 0.5th-99.9th percentile of the uint16 values inside cells to 0-255
  classes_u8.npy  one compartment class per voxel, painted from the segmentations in CLASSES order (later wins)
Both are indexed [z, y, x]. The segmentations are machine-learning predictions refined by the COSEM team, not manual
ground truth; at 64 nm voxels thin structures (ER sheets, vesicles, membranes) are only partly resolved. "Cytosol"
here means "inside the cell and in none of the ten segmentations", so it still contains unresolved ER, cytoskeleton,
ribosomes and vesicles.

Simulation (evidence category B on measured geometry): overdamped Brownian dynamics of independent point particles
of one or more molecule species on the class grid. A step whose end point lies in a class the molecule may not occupy
is rejected (the particle keeps its position); this symmetric-proposal rejection rule leaves the uniform density
stationary and behaves as a reflecting wall with first-order accuracy in the step length. Rejections are counted per
blocking class as "encounters". Optional surface binding: an encounter with a species' target class binds with
probability pBind; bound particles are immobile and release with probability 1 - exp(-koff Δt) per step. Optional
pair binding between two species (Doi volume reactivity, evaluated every PAIR_EVERY steps): a free A and a free B
closer than the reach react with probability 1 - exp(-λ·PAIR_EVERY·Δt); the complex diffuses as one particle with the
radius of the sphere of summed volume and dissociates with rate koff. D comes from Stokes-Einstein with each species'
hydrodynamic radius and an explicit cytoplasmic slowdown factor. Every reaction parameter and the slowdown are user
assumptions: no affinity, specificity or kinetics of a real molecule pair is predicted from its structure. Membraneless
nuclear bodies (chromatin, nucleolus) are treated as freely accessible from the nucleoplasm (assumption). HeLa is not
the Virtual Cell's Hep G2 context.

Structures: `cell_em_structure` reads a saved library structure (PDB or mmCIF, first model) and returns its atoms for
display with a sphere-equivalent hydrodynamic radius R = √(5/3)·Rg; only that radius enters the simulation.

Cell Painting: `cell_em_paint` is a forward model, not a measurement. Each of the five Cell Painting channels is a
weighted sum of segmentation classes (PAINT), integrated along the thin (y) axis and blurred with a Gaussian point
spread function. It shows where the stains of the standard assay would be expected given the EM segmentation; actin
and cytoplasmic RNA granules are not segmented and are absent.
"""
import base64, concurrent.futures, datetime, gzip, hashlib, io, json, math, pathlib, platform, re, struct, time, urllib.parse, urllib.request, uuid, zlib

import numpy as np

from cell_em_actions import ACTIONS

VERSION = '3.0.0'                           # engine
DATA_VERSION = '2.0.0'                      # derived grids of the installed dataset; a change rebuilds them
BUCKET = 'https://janelia-cosem-datasets.s3.amazonaws.com'
PREFIX = 'jrc_hela-2/jrc_hela-2.n5/'
LEVEL = 's4'
DIMS = (750, 100, 398)                      # x, y, z voxels at s4
VOXEL = (0.064, 0.064, 0.08384)             # µm along x, y, z
DIR = ('cell_em', 'data', 'jrc_hela-2')
MAX_BYTES = 80_000_000                      # refuse an install that grows beyond the measured ≈ 39 MB
KB = 1.380649e-23

DATASET = {
    'id': 'jrc_hela-2', 'name': 'Interphase HeLa cell, whole-cell FIB-SEM (OpenOrganelle jrc_hela-2)', 'cellLine': 'HeLa (CVCL_0030)',
    'method': 'Focused-ion-beam scanning electron microscopy of a high-pressure-frozen, freeze-substituted, resin-embedded cell',
    'source': 's3://janelia-cosem-datasets/' + PREFIX, 'url': 'https://openorganelle.janelia.org/datasets/jrc_hela-2',
    'licence': 'CC BY 4.0 (OpenOrganelle)', 'acquired': '4 x 4 x 5.24 nm voxels',
    'installedLevel': LEVEL + ': 64 x 64 x 83.84 nm voxels, 750 x 100 x 398', 'downloadMb': 40,
    'citation': ['Xu CS et al. An open-access volume electron microscopy atlas of whole cells and tissues. Nature 2021;599:147-151. doi:10.1038/s41586-021-03992-4',
                 'Heinrich L et al. Whole-cell organelle segmentation in volume electron microscopy. Nature 2021;599:141-146. doi:10.1038/s41586-021-04061-2'],
    'caveats': ['Fixed, stained, resin-embedded cell: one static snapshot, not a living cell',
                'Organelle classes are COSEM machine-learning segmentations, not manual ground truth',
                'At 64 nm voxels membranes, ER sheets and vesicles are only partly resolved',
                'HeLa, not the Virtual Cell Hep G2 context'],
}
# id, key, label, segmentation array (None = derived), display colour. Painted in this order; later classes overwrite.
CLASSES = [
    (0, 'outside', 'Outside the cell', None, '#000000'),
    (1, 'cytosol', 'Cytosol (unsegmented interior)', None, '#7f8fa6'),
    (2, 'pm', 'Plasma membrane', 'pm_seg', '#f5d76e'),
    (3, 'er', 'Endoplasmic reticulum', 'er_seg', '#35c7a5'),
    (4, 'nucleus', 'Nucleus', 'nucleus_seg', '#6f7cff'),
    (5, 'mito', 'Mitochondria', 'mito_seg', '#ff6b4a'),
    (6, 'golgi', 'Golgi', 'golgi_seg', '#ffb347'),
    (7, 'endo', 'Endosomes', 'endo_seg', '#c77dff'),
    (8, 'lyso', 'Lysosomes', 'lyso_seg', '#ff5fa2'),
    (9, 'ld', 'Lipid droplets', 'ld_seg', '#fff3a3'),
    (10, 'vesicle', 'Vesicles', 'vesicle_seg', '#9be7ff'),
    (11, 'chromatin', 'Chromatin', 'chrom_seg', '#3f51d9'),
    (12, 'nucleolus', 'Nucleolus', 'nucleolus_seg', '#b48cff'),
    (13, 'ne', 'Nuclear envelope', 'ne_seg', '#8fd3ff'),
]
EDGE = len(CLASSES)                         # pseudo-class for the edge of the imaged volume
# The foreground mask (where COSEM ran its predictions) is published one pyramid level finer; its s3 has the EM's s4 voxel size.
ARRAYS = ['em/fibsem-uint16', 'labels/ecs_seg', 'labels/masks/foreground'] + ['labels/' + c[3] for c in CLASSES if c[3]]
LEVELS = {'labels/masks/foreground': 's3'}
KEYS = {c[1]: c[0] for c in CLASSES}

MOLECULES = [
    {'id': 'small', 'name': 'Small molecule (≈ 0.5 kDa)', 'radiusNm': 0.5, 'note': 'Typical drug-like hydrodynamic radius; order of magnitude'},
    {'id': 'gfp', 'name': 'GFP (27 kDa)', 'radiusNm': 2.8, 'note': 'From D ≈ 87 µm²/s in water at room temperature'},
    {'id': 'igg', 'name': 'Antibody IgG (150 kDa)', 'radiusNm': 5.3, 'note': 'Typical literature hydrodynamic radius'},
    {'id': 'ribosome', 'name': 'Ribosome (80S)', 'radiusNm': 13.0, 'note': 'Approximate; particle is treated as a point in the 64 nm grid'},
]
INPUTS = [       # global
    {'key': 'slowdown', 'unit': '×', 'description': 'Cytoplasmic slowdown of diffusion relative to water (assumption)', 'bounds': [1.0, 100.0], 'default': 3.2},
    {'key': 'temperature', 'unit': 'K', 'description': 'Temperature', 'bounds': [273.15, 330.0], 'default': 310.15},
    {'key': 'seed', 'unit': '', 'description': 'Random seed', 'bounds': [0, 2**31 - 1], 'default': 7, 'integer': True},
]
SPECIES_INPUTS = [
    {'key': 'radiusNm', 'unit': 'nm', 'description': 'Hydrodynamic radius', 'bounds': [0.2, 60.0], 'default': 2.8},
    {'key': 'particles', 'unit': 'copies', 'description': 'Copies', 'bounds': [1, 300], 'default': 120, 'integer': True},
    {'key': 'pBind', 'unit': 'per encounter', 'description': 'Binding probability per encounter with the target compartment (hypothetical)', 'bounds': [0.0, 1.0], 'default': 0.0},
    {'key': 'koff', 'unit': 's⁻¹', 'description': 'Release rate from the target compartment (hypothetical)', 'bounds': [0.0, 1e4], 'default': 20.0},
]
PAIR_INPUTS = [
    {'key': 'reachNm', 'unit': 'nm', 'description': 'Reaction reach between the two molecules (hypothetical)', 'bounds': [5.0, 500.0], 'default': 120.0},
    {'key': 'rate', 'unit': 's⁻¹', 'description': 'Binding rate while within reach (hypothetical)', 'bounds': [0.0, 1e6], 'default': 2000.0},
    {'key': 'koff', 'unit': 's⁻¹', 'description': 'Complex dissociation rate (hypothetical)', 'bounds': [0.0, 1e4], 'default': 5.0},
]
MAX_SPECIES, MAX_PARTICLES, PAIR_EVERY, MAX_EVENTS = 4, 600, 16, 400
KINETIC_INPUTS = [   # per molecule; every value is a user assumption unless a context supplies a measured one
    {'key': 'capacity', 'unit': 'copies', 'description': 'Most copies that can exist at once', 'bounds': [1, 300], 'default': 0, 'integer': True},
    {'key': 'synthesisRate', 'unit': 'copies s⁻¹', 'description': 'Synthesis rate in the chosen compartment (hypothetical)', 'bounds': [0.0, 1e5], 'default': 0.0},
    {'key': 'decay', 'unit': 's⁻¹', 'description': 'Decay rate (hypothetical)', 'bounds': [0.0, 1e4], 'default': 0.0},
]
EXCHANGE_INPUT = {'key': 'permeabilityUmS', 'unit': 'µm s⁻¹', 'description': 'Permeability of the boundary (hypothetical)', 'bounds': [0.0, 1e5], 'default': 5.0}
REACTION_INPUT = {'key': 'rate', 'unit': 's⁻¹', 'description': 'Conversion rate (hypothetical)', 'bounds': [0.0, 1e4], 'default': 5.0}
HOP_REACH = 5                               # voxels searched for the far side of a permeable boundary
MAX_HOP = 0.5                               # largest crossing probability per stopped move for which the permeability formula holds
MAX_KIN_EVENTS = 200                        # kinetic events returned per chunk; the counts are always complete
HELA, ECOLI = 'hela-jrc_hela-2', 'ecoli-bw29655-ccasr'
GFP_ECOLI_D = 7.7                           # µm²/s, GFP in E. coli cytoplasm (Elowitz et al. 1999, J Bacteriol 181:197-203; 7.7 ± 2.5)
CONTEXTS = {
    HELA: {'name': 'HeLa · whole-cell FIB-SEM', 'short': 'HeLa', 'species': 'Homo sapiens', 'cell': 'HeLa (CVCL_0030), interphase', 'geometry': 'measured',
           'geometryLabel': 'Measured EM volume · machine-learning segmentation', 'resolution': '64 × 64 × 83.84 nm voxels',
           'slowdown': {'value': 3.2, 'provenance': {'kind': 'assumed', 'note': 'One factor standing in for cytoplasmic crowding; not measured in this cell.'}}},
    ECOLI: {'name': 'E. coli · illustrative rod', 'short': 'E. coli', 'species': 'Escherichia coli', 'cell': 'BW29655 carrying the CcaSR reporter plasmids, exponential growth', 'geometry': 'illustrative',
            'geometryLabel': 'Illustrative geometry · not an image', 'resolution': '20 nm voxels (drawn, not measured)',
            'slowdown': {'value': None, 'provenance': {'kind': 'literature', 'note': 'Set so that GFP (2.8 nm) diffuses at 7.7 µm²/s, the value measured in E. coli cytoplasm (Elowitz et al. 1999, J Bacteriol 181:197-203).'}}},
}
NUCLEAR = ('nucleus', 'chromatin', 'nucleolus')
PAINT = {        # Cell Painting channel -> class weights (assumed relative stain intensity), display colour
    'DNA': {'stain': 'Hoechst 33342 (DNA)', 'color': '#3d6bff', 'weights': {'chromatin': 1.0, 'nucleus': 0.35, 'nucleolus': 0.1}},
    'RNA': {'stain': 'SYTO 14 (nucleoli, cytoplasmic RNA)', 'color': '#f2e94e', 'weights': {'nucleolus': 1.0, 'cytosol': 0.12}},
    'ER': {'stain': 'Concanavalin A (endoplasmic reticulum)', 'color': '#38ff80', 'weights': {'er': 1.0, 'ne': 0.6}},
    'AGP': {'stain': 'Phalloidin + WGA (actin, Golgi, plasma membrane)', 'color': '#ff8033', 'weights': {'golgi': 1.0, 'pm': 0.3}},
    'Mito': {'stain': 'MitoTracker Deep Red (mitochondria)', 'color': '#ff3a52', 'weights': {'mito': 1.0}},
}
STEP_FRACTION = 0.35                        # rms step per axis as a fraction of the smallest voxel edge
ROD = {'voxel': (0.02, 0.02, 0.02), 'dims': (140, 56, 56), 'radius': 0.45, 'halfLength': 0.75, 'envelope': 0.04, 'nucleoidRadius': 0.24, 'nucleoidHalf': 0.45}
FRAMES = 48                                 # frames returned per chunk
MAX_STEPS = 30_000                          # steps admitted per chunk
ENGINE = {
    'id': 'fold.cell-em.brownian', 'name': 'Brownian dynamics in an EM-derived cell', 'version': VERSION, 'evidence': 'B',
    'numericalMethod': 'Overdamped Brownian dynamics (Euler-Maruyama) of point particles of several species on a segmented voxel grid; moves into a forbidden class are rejected (reflecting, first order); optional per-encounter surface binding with exponential release; optional Doi pair binding between species; optional zero-order synthesis, first-order decay and conversion, and permeable boundaries crossed with probability κ·√(πΔt/D) per stopped move; NumPy PCG64 seeded per chunk.',
    'equations': ['D = k_B T / (6 π η_w(T) R_h · slowdown)', 'x(t+Δt) = x(t) + √(2DΔt)·ξ, ξ ~ N(0, I₃); rejected when class(x(t+Δt)) is not accessible',
                  'Δt chosen so √(2DΔt) = %.2f × 64 nm' % STEP_FRACTION, 'P(bind | encounter with target) = pBind; P(release per step) = 1 − exp(−koff Δt)',
                  'A + B ⇌ AB: P(bind | |x_A − x_B| < reach) = 1 − exp(−λ·n·Δt) every n = %d steps; R_AB = (R_A³ + R_B³)^⅓' % PAIR_EVERY,
                  '∅ → X: Poisson(k_syn·Δt) copies per step, uniform in the compartment; X → ∅ and X → Y: P = 1 − exp(−k·Δt) per step',
                  'Permeable boundary: P(cross | move stopped by the boundary) = κ·√(πΔt/D), giving a flux κ·c per unit area'],
    'assumptions': ['Point particles: no excluded volume beyond the voxel classes, no hydrodynamic or electrostatic interactions',
                    'Constant isotropic D inside every accessible class; one slowdown factor stands in for crowding',
                    'Organelle boundaries are impermeable unless a class is explicitly made accessible',
                    'The fixed EM snapshot is used as a static geometry; organelles do not move'],
    'limits': ['Geometry is a machine-learning segmentation sampled at 64 nm; unresolved membranes, ER, cytoskeleton and pores are absent',
               'Every binding parameter and the slowdown factor are user assumptions; no affinity, specificity or kinetics is predicted from any structure',
               'A complex is one point particle; molecular shape, orientation and docking geometry do not enter the dynamics',
               'Permeable boundaries are passive and symmetric with one permeability; no active transport, no channels, no partitioning into the membrane. A crossing lands in the nearest voxel beyond the boundary; where the boundary is thicker than 5 voxels the attempt fails and is counted',
               'Synthesis places a copy uniformly in its compartment; decay and conversion ignore location. No stoichiometric chemistry beyond A → B and A + B ⇌ AB',
               'Encounter counts depend on the step length and are comparable only between runs with the same Δt'],
    'benchmarks': [{'name': 'Free-diffusion control', 'reference': 'Einstein: ⟨|Δr|²⟩ = 6Dt', 'acceptance': '|z| < 4 with the same kernel on an obstacle-free grid'},
                   {'name': 'Confinement', 'reference': 'Every particle remains in an accessible class', 'acceptance': 'zero violations'},
                   {'name': 'Step length', 'reference': 'rms step per axis ≤ %.2f of the smallest voxel edge' % STEP_FRACTION, 'acceptance': 'by construction'},
                   {'name': 'Counts agree with events', 'reference': 'Copies present = copies before + synthesised and converted in − decayed and converted out', 'acceptance': 'exact, every chunk'},
                   {'name': 'Permeable boundary', 'reference': 'Two compartments equilibrate at rate κ·A·(1/V₁ + 1/V₂)', 'acceptance': 'within 15 % (tests)'},
                   {'name': 'Synthesis and decay', 'reference': 'Steady state k_syn/k_decay and its Poisson spread', 'acceptance': 'within sampling error (tests)'}],
}


class EMError(ValueError):
    pass


# ------------------------------------------------------------------ install

def folder(root):
    return pathlib.Path(root).joinpath(*DIR)


def _http(url, tries=4):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'fold-studio'}), timeout=60) as r:
                return r.read()
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))


def _level(array):
    return LEVELS.get(array, LEVEL)


def _listing(array):
    """All block keys of one array at LEVEL, from the public S3 listing."""
    out, token = [], None
    while True:
        q = {'list-type': '2', 'prefix': PREFIX + array + '/' + _level(array) + '/'}
        if token:
            q['continuation-token'] = token
        xml = _http(BUCKET + '/?' + urllib.parse.urlencode(q)).decode()
        out += [(k, int(s)) for k, s in re.findall(r'<Key>([^<]+)</Key>.*?<Size>(\d+)</Size>', xml)]
        m = re.search(r'<NextContinuationToken>([^<]+)</NextContinuationToken>', xml)
        if not m:
            return out
        token = m.group(1)


def decode_block(raw, dtype):
    """One N5 block (default mode, gzip): big-endian header, then data with the first axis fastest. Returns [z, y, x]."""
    mode, nd = struct.unpack('>HH', raw[:4])
    if mode != 0 or nd != 3:
        raise EMError('Unsupported N5 block header.')
    bx, by, bz = struct.unpack('>III', raw[4:16])
    data = np.frombuffer(zlib.decompress(raw[16:], 31), dtype=np.dtype(dtype).newbyteorder('>'))
    if data.size != bx * by * bz:
        raise EMError('N5 block has an unexpected size.')
    return data.reshape(bz, by, bx)


def assemble(original, array):
    attrs = json.loads((original / array / 'attributes.json').read_text())
    if tuple(attrs['dimensions']) != DIMS or attrs['compression']['type'] != 'gzip':
        raise EMError(array + ': unexpected array layout.')
    out = np.zeros(DIMS[::-1], attrs['dataType'])
    bs = attrs['blockSize']
    for f in (original / array).glob('*/*/*'):
        ix, iy, iz = (int(v) for v in f.relative_to(original / array).parts)
        b = decode_block(f.read_bytes(), attrs['dataType'])
        view = out[iz * bs[2]:iz * bs[2] + b.shape[0], iy * bs[1]:iy * bs[1] + b.shape[1], ix * bs[0]:ix * bs[0] + b.shape[2]]
        view[...] = b[:view.shape[0], :view.shape[1], :view.shape[2]]          # edge blocks may be stored padded
    return out


def classes_from(seg):
    """Class grid from boolean masks keyed by array name ('ecs_seg', 'foreground', 'pm_seg', …). Outside = extracellular
    space, or outside the region where COSEM predicted anything (their foreground mask)."""
    out = np.where(seg['ecs_seg'] | ~seg['foreground'], 0, 1).astype(np.uint8)
    for cid, _, _, array, _ in CLASSES:
        if array:
            out[seg[array]] = cid
    return out


def build(root):
    base = folder(root); original = base / 'original'; derived = base / 'derived'; derived.mkdir(parents=True, exist_ok=True)
    em = assemble(original, 'em/fibsem-uint16')
    seg = {a.split('/')[-1]: assemble(original, a) > 0 for a in ARRAYS[1:]}
    seg['ecs_seg'] |= em == 0                                      # voxels never imaged are outside
    cls = classes_from(seg)
    cell = em[cls > 0]
    lo, hi = (np.percentile(cell[::5], [0.5, 99.9]) if cell.size else (0.0, 1.0))
    em8 = np.clip((em.astype(np.float32) - lo) / max(hi - lo, 1.0) * 255.0, 0, 255).astype(np.uint8)
    np.save(derived / 'em_u8.npy', em8); np.save(derived / 'classes_u8.npy', cls)
    counts = np.bincount(cls.ravel(), minlength=len(CLASSES))
    voxel_volume = VOXEL[0] * VOXEL[1] * VOXEL[2]
    meta = {'dims': list(DIMS), 'voxelUm': list(VOXEL), 'sizeUm': [DIMS[i] * VOXEL[i] for i in range(3)], 'emWindow': [float(lo), float(hi)],
            'classes': [{'id': c[0], 'key': c[1], 'name': c[2], 'source': c[3], 'color': c[4], 'voxels': int(counts[c[0]]), 'volumeUm3': round(float(counts[c[0]]) * voxel_volume, 2)} for c in CLASSES],
            'sha256': {n: hashlib.sha256((derived / n).read_bytes()).hexdigest() for n in ('em_u8.npy', 'classes_u8.npy')},
            'built': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'version': DATA_VERSION}
    (derived / 'meta.json').write_text(json.dumps(meta, indent=1))
    return meta


def meta(root):
    f = folder(root) / 'derived' / 'meta.json'
    m = json.loads(f.read_text()) if f.is_file() else None
    return m if m and m.get('version') == DATA_VERSION else None  # an older build is rebuilt by install


def install(service, p):
    """Download the s4 EM volume and segmentations (≈ 39 MB) after an explicit user request, then build derived grids."""
    if not (p or {}).get('confirm'):
        raise EMError('Installing downloads about 40 MB from OpenOrganelle; confirm to proceed.')
    original = folder(service.root) / 'original'
    wanted = []
    for a in ARRAYS:
        (original / a).mkdir(parents=True, exist_ok=True)
        (original / a / 'attributes.json').write_bytes(_http(BUCKET + '/' + PREFIX + a + '/' + _level(a) + '/attributes.json'))
        wanted += [(a, k, s) for k, s in _listing(a) if not k.endswith('attributes.json')]
    if sum(s for _, _, s in wanted) > MAX_BYTES:
        raise EMError('The dataset is larger than expected; nothing was downloaded.')

    def fetch(item):
        a, key, size = item
        target = original / a / key.split('/' + _level(a) + '/', 1)[1]
        if not (target.is_file() and target.stat().st_size == size):
            raw = _http(BUCKET + '/' + urllib.parse.quote(key))
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        return {'file': str(target.relative_to(original)), 'source': 's3://janelia-cosem-datasets/' + key, 'bytes': size, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    with concurrent.futures.ThreadPoolExecutor(12) as pool:
        files = list(pool.map(fetch, wanted))
    (original / 'manifest.json').write_text(json.dumps({'dataset': DATASET, 'level': LEVEL, 'retrieved': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'files': sorted(files, key=lambda f: f['file'])}, indent=1))
    return {'installed': True, 'files': len(files), 'bytes': sum(f['bytes'] for f in files), 'meta': build(service.root)}


def _grid(root, name):
    f = folder(root) / 'derived' / name
    if not f.is_file():
        raise EMError('The EM dataset is not installed yet.')
    return np.load(f, mmap_mode='r')


_ROD = None


def rod_classes():
    """An illustrative rod-shaped bacterium on a 20 nm grid: envelope shell, cytoplasm and a central nucleoid region.
    Drawn from typical E. coli dimensions (about 0.9 µm wide, 2.4 µm long); it is not an image of any cell."""
    global _ROD
    if _ROD is None:
        nx, ny, nz = ROD['dims']; v = ROD['voxel']
        z, y, x = np.meshgrid((np.arange(nz) + 0.5) * v[2], (np.arange(ny) + 0.5) * v[1], (np.arange(nx) + 0.5) * v[0], indexing='ij')
        cx, cy, cz = nx * v[0] / 2, ny * v[1] / 2, nz * v[2] / 2
        radial = lambda half: np.sqrt((x - np.clip(x, cx - half, cx + half)) ** 2 + (y - cy) ** 2 + (z - cz) ** 2)     # distance to the axis segment
        d = radial(ROD['halfLength'])
        cls = np.zeros((nz, ny, nx), np.uint8)
        cls[d <= ROD['radius']] = KEYS['pm']
        cls[d <= ROD['radius'] - ROD['envelope']] = KEYS['cytosol']
        cls[radial(ROD['nucleoidHalf']) <= ROD['nucleoidRadius']] = KEYS['chromatin']
        _ROD = cls
    return _ROD


ROD_NAMES = {'pm': 'Cell envelope (illustrative)', 'cytosol': 'Cytoplasm (illustrative)', 'chromatin': 'Nucleoid region (illustrative)'}


def geometry(root, context=HELA):
    """Class grid, voxel size (µm), description and content hash of a context's geometry."""
    if context == HELA:
        m = meta(root)
        return _grid(root, 'classes_u8.npy'), VOXEL, m, ((m or {}).get('sha256') or {}).get('classes_u8.npy')
    if context == ECOLI:
        cls = rod_classes(); v = ROD['voxel']; counts = np.bincount(cls.ravel(), minlength=len(CLASSES)); vol = v[0] * v[1] * v[2]
        m = {'dims': list(ROD['dims']), 'voxelUm': list(v), 'sizeUm': [ROD['dims'][i] * v[i] for i in range(3)], 'illustrative': True,
             'classes': [{'id': c[0], 'key': c[1], 'name': ROD_NAMES.get(c[1], c[2]), 'source': None, 'color': c[4], 'voxels': int(counts[c[0]]), 'volumeUm3': round(float(counts[c[0]]) * vol, 4)} for c in CLASSES]}
        return cls, v, m, hashlib.sha256(cls.tobytes()).hexdigest()
    raise EMError('Unknown cell context.')


def context_defaults(context):
    """Parameters a context calibrates for itself, with where each comes from."""
    c = CONTEXTS[context]; slow = dict(c['slowdown'])
    if slow['value'] is None:
        slow['value'] = round(diffusion_coefficient(2.8, 310.15, 1.0) / GFP_ECOLI_D, 2)
    return {'slowdown': slow}


def volume(service, p):
    """A z-slab of a derived grid, gzip + base64, rows in [z, y, x] order (x fastest), ready for a 3-D texture."""
    kind = p.get('kind'); context = p.get('context') or HELA
    if kind == 'region':
        grid = np.load(_region_dir(service.root, str(p.get('id', ''))) / 'em_u8.npy', mmap_mode='r')
    elif context == HELA:
        grid = _grid(service.root, {'em': 'em_u8.npy', 'classes': 'classes_u8.npy'}.get(kind, ''))
    elif kind == 'classes':
        grid = geometry(service.root, context)[0]
    else:
        raise EMError('This context has no measured image; its geometry is illustrative.')
    z0, z1 = int(p.get('z0', 0)), int(p.get('z1', grid.shape[0]))
    if not 0 <= z0 < z1 <= grid.shape[0] or z1 - z0 > 128:
        raise EMError('Invalid slab.')
    return {'kind': kind, 'z0': z0, 'z1': z1, 'dims': list(grid.shape[::-1]), 'data': base64.b64encode(gzip.compress(np.ascontiguousarray(grid[z0:z1]).tobytes(), 4)).decode()}


# ------------------------------------------------------------------ finer levels of the measured volume, on request

REGION = {'levels': {'s3': 2, 's2': 4, 's1': 8, 's0': 16}, 'maxVoxels': (256, 128, 256), 'maxBytes': 60_000_000}


def _frame(attrs):
    """Voxel size (µm, x y z) and the corner of the first voxel (µm, x y z) from an N5 array's attributes. COSEM stores
    `transform` with axes z, y, x and `translate` at the centre of the first voxel."""
    t = attrs.get('transform') or {}
    if t.get('scale') and t.get('axes'):
        order = [t['axes'].index(a) for a in ('x', 'y', 'z')]; unit = 1e-3 if (t.get('units') or ['nm'])[0] == 'nm' else 1.0
        scale = [float(t['scale'][i]) * unit for i in order]; centre = [float((t.get('translate') or [0, 0, 0])[i]) * unit for i in order]
    else:
        res = attrs.get('pixelResolution') or {}; unit = 1e-3 if res.get('unit', 'nm') == 'nm' else 1.0
        scale = [float(v) * unit for v in res.get('dimensions') or [v * 1000 for v in VOXEL]]; centre = [v / 2 for v in scale]
    return scale, [centre[i] - scale[i] / 2 for i in range(3)]


def registration(service):
    """Do the image, the segmentations and the simulation grid share one physical frame? Read from each array's own
    attributes: voxel spacing per axis, axis order, grid size and origin, compared with the constants the engine uses."""
    m = meta(service.root)
    if not m:
        raise EMError('The EM dataset is not installed yet.')
    original = folder(service.root) / 'original'; rows = []
    for a in ARRAYS:
        attrs = json.loads((original / a / 'attributes.json').read_text()); voxel, corner = _frame(attrs)
        rows.append({'array': a, 'level': _level(a), 'role': 'image' if a.startswith('em/') else 'mask' if 'masks' in a else 'segmentation', 'dims': attrs['dimensions'], 'voxelNm': [round(v * 1000, 4) for v in voxel],
                     'cornerNm': [round(v * 1000, 4) for v in corner], 'axes': (attrs.get('transform') or {}).get('axes'), 'dataType': attrs['dataType']})
    ref = rows[0]
    offsets = [{'array': r['array'], 'offsetNm': [round(r['cornerNm'][i] - ref['cornerNm'][i], 4) for i in range(3)], 'voxels': max(abs(r['cornerNm'][i] - ref['cornerNm'][i]) / ref['voxelNm'][i] for i in range(3))} for r in rows]
    worst = max(offsets, key=lambda o: o['voxels'])
    cls = _grid(service.root, 'classes_u8.npy'); em = _grid(service.root, 'em_u8.npy')
    spacing_ok = all(abs(r['voxelNm'][i] - VOXEL[i] * 1000) < 1e-6 for r in rows for i in range(3))
    shifted = [o['array'].split('/')[-1] for o in offsets if o['voxels'] > 0]
    checks = [
        {'name': 'Voxel spacing', 'passed': spacing_ok, 'detail': (f"Every array reports {ref['voxelNm'][0]:g} × {ref['voxelNm'][1]:g} × {ref['voxelNm'][2]:g} nm along x, y, z; the engine uses {VOXEL[0] * 1000:g} × {VOXEL[1] * 1000:g} × {VOXEL[2] * 1000:g} nm."
                                                                    if spacing_ok else 'An array reports a voxel size different from the one the engine uses.')},
        {'name': 'Grid size', 'passed': all(tuple(r['dims']) == DIMS for r in rows) and cls.shape == DIMS[::-1] and em.shape == DIMS[::-1], 'detail': f'{DIMS[0]} × {DIMS[1]} × {DIMS[2]} voxels (x, y, z) in every array, in the class grid and in the simulation.'},
        {'name': 'Axis order', 'passed': all(r['axes'] in (None, ['z', 'y', 'x']) for r in rows), 'detail': 'Arrays are stored z, y, x with x fastest; grids are indexed [z, y, x]; positions are (x, y, z) in µm. The view maps data y to up.'},
        {'name': 'Origin', 'passed': worst['voxels'] < 0.05, 'detail': (f"The image and the segmentations start at the same corner. {', '.join(shifted)} is offset by {abs(worst['offsetNm'][0]):g}, {abs(worst['offsetNm'][1]):g}, {abs(worst['offsetNm'][2]):g} nm ({worst['voxels'] * 100:.1f} % of a voxel) and is used unshifted."
                                                                        if shifted else 'Every array starts at the same corner.')},
        {'name': 'Simulation frame', 'passed': True, 'detail': 'Molecule positions are µm from the corner of the first voxel of the image. Structure coordinates are Å, scaled by 10⁻⁴ µm/Å and centred on the molecule position.'},
    ]
    return {'frame': {'unit': 'µm', 'origin': 'corner of the first voxel of the image', 'originInDatasetNm': ref['cornerNm'], 'sizeUm': m['sizeUm'], 'voxelUm': list(VOXEL), 'dims': list(DIMS),
                      'orientation': "x and z span the plane the cell is spread in; y is the cell's height (the thin axis, 6.4 µm)"},
            'arrays': rows, 'offsets': offsets, 'checks': checks, 'passed': all(c['passed'] for c in checks),
            'regions': [{'id': r['id'], 'level': r['level'], 'voxelNm': [round(v * 1000, 3) for v in r['voxelUm']], 'originUm': r['originUm'], 'sizeUm': r['sizeUm']} for r in regions(service)]}


def _region_dir(root, rid):
    if not re.fullmatch(r's[0-3]-\d+-\d+-\d+-\d+-\d+-\d+', rid):
        raise EMError('Unknown detail region.')
    return folder(root) / 'regions' / rid


def regions(service):
    d = folder(service.root) / 'regions'
    return [json.loads(f.read_text()) for f in sorted(d.glob('*/meta.json'))] if d.is_dir() else []


def region(service, p):
    """Fetch one region of the measured EM volume at a finer pyramid level and store it beside the overview.

    `centerUm` and `sizeUm` are in the dataset frame. The level's own voxel size is read from its attributes, the blocks
    are kept byte for byte with their SHA-256, and the 8-bit copy uses the overview's display window so both read alike."""
    level = str(p.get('level', 's2'))
    if level not in REGION['levels'] or not meta(service.root):
        raise EMError('Install the cell volume first, then choose a level from s3 (32 nm) to s0 (4 nm).')
    if not p.get('confirm'):
        raise EMError('Loading a detail region downloads image blocks from OpenOrganelle; confirm to proceed.')
    array = 'em/fibsem-uint16'; base = BUCKET + '/' + PREFIX + array + '/' + level + '/'
    attrs_raw = _http(base + 'attributes.json'); attrs = json.loads(attrs_raw)
    dims, bs = attrs['dimensions'], attrs['blockSize']
    voxel, corner = _frame(attrs)                                        # the level's own voxel size and the position of its first voxel corner
    base_corner = _frame(json.loads((folder(service.root) / 'original' / array / 'attributes.json').read_text()))[1]
    shift = [corner[i] - base_corner[i] for i in range(3)]               # µm between this level's grid and the overview's (a fraction of a fine voxel)
    try:
        centre = [float(v) for v in p['centerUm']]; size = [float(v) for v in p.get('sizeUm') or [REGION['maxVoxels'][i] * voxel[i] for i in range(3)]]
    except (KeyError, TypeError, ValueError):
        raise EMError('A detail region needs a centre in micrometres.')
    n = [int(min(REGION['maxVoxels'][i], max(8, round(size[i] / voxel[i])), dims[i])) for i in range(3)]
    lo = [int(min(max(0, round(centre[i] / voxel[i] - n[i] / 2)), dims[i] - n[i])) for i in range(3)]
    rid = f"{level}-{lo[0]}-{lo[1]}-{lo[2]}-{n[0]}-{n[1]}-{n[2]}"; out = _region_dir(service.root, rid)
    if (out / 'meta.json').is_file():
        return json.loads((out / 'meta.json').read_text())
    blocks = [(ix, iy, iz) for ix in range(lo[0] // bs[0], (lo[0] + n[0] - 1) // bs[0] + 1) for iy in range(lo[1] // bs[1], (lo[1] + n[1] - 1) // bs[1] + 1) for iz in range(lo[2] // bs[2], (lo[2] + n[2] - 1) // bs[2] + 1)]
    if len(blocks) > 400:
        raise EMError('That region spans too many image blocks; choose a smaller one.')
    (out / 'original').mkdir(parents=True, exist_ok=True)
    (out / 'original' / 'attributes.json').write_bytes(attrs_raw)

    def fetch(b):
        key = PREFIX + array + '/' + level + f'/{b[0]}/{b[1]}/{b[2]}'
        try:
            raw = _http(BUCKET + '/' + key, tries=2)
        except Exception:
            return b, None, key                                       # N5 omits blocks that hold no data
        return b, raw, key
    with concurrent.futures.ThreadPoolExecutor(12) as pool:
        got = list(pool.map(fetch, blocks))
    if sum(len(r) for _, r, _ in got if r) > REGION['maxBytes']:
        raise EMError('That region is larger than the download limit; choose a smaller one.')
    vol = np.zeros((n[2], n[1], n[0]), np.uint16); files = []
    for (ix, iy, iz), raw, key in got:
        if raw is None:
            continue
        target = out / 'original' / str(ix) / str(iy) / str(iz); target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        files.append({'file': f'{ix}/{iy}/{iz}', 'source': 's3://janelia-cosem-datasets/' + key, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        b = decode_block(raw, attrs['dataType'])
        x0, y0, z0 = ix * bs[0] - lo[0], iy * bs[1] - lo[1], iz * bs[2] - lo[2]
        xa, ya, za = max(0, x0), max(0, y0), max(0, z0); xb, yb, zb = min(n[0], x0 + b.shape[2]), min(n[1], y0 + b.shape[1]), min(n[2], z0 + b.shape[0])
        if xb > xa and yb > ya and zb > za:
            vol[za:zb, ya:yb, xa:xb] = b[za - z0:zb - z0, ya - y0:yb - y0, xa - x0:xb - x0]
    w = meta(service.root)['emWindow']
    em8 = np.clip((vol.astype(np.float32) - w[0]) / max(w[1] - w[0], 1.0) * 255.0, 0, 255).astype(np.uint8)
    np.save(out / 'em_u8.npy', em8)
    body = {'id': rid, 'level': level, 'dims': n, 'voxelUm': voxel, 'originUm': [lo[i] * voxel[i] + shift[i] for i in range(3)], 'sizeUm': [n[i] * voxel[i] for i in range(3)], 'levelDims': dims, 'gridShiftUm': shift,
            'blocks': len(files), 'bytes': sum(f['bytes'] for f in files), 'sha256': hashlib.sha256((out / 'em_u8.npy').read_bytes()).hexdigest(), 'dataset': DATASET['id'],
            'retrieved': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'evidence': 'A · measured EM signal at the dataset\'s own pyramid level; no segmentation is loaded at this level',
            'registration': "Placed with the level's own voxel size and translation from its attributes, relative to the overview grid."}
    (out / 'original' / 'manifest.json').write_text(json.dumps({'region': body, 'files': files}, indent=1))
    (out / 'meta.json').write_text(json.dumps(body, indent=1))
    return body


# ------------------------------------------------------------------ physics

def water_viscosity(T):
    """Dynamic viscosity of water, Pa·s (Vogel-type correlation; 0.89 mPa·s at 25 °C, 0.69 mPa·s at 37 °C)."""
    return 2.414e-5 * 10 ** (247.8 / (T - 140.0))


def diffusion_coefficient(radius_nm, T, slowdown):
    """Stokes-Einstein D in µm²/s."""
    return KB * T / (6 * math.pi * water_viscosity(T) * radius_nm * 1e-9 * slowdown) * 1e12


def class_at(classes, x, voxel=VOXEL):
    """Class of each position (µm, columns x y z); EDGE outside the imaged volume."""
    i = np.floor(x / np.asarray(voxel)).astype(np.int64)
    inside = ((i >= 0) & (i < np.array(classes.shape[::-1]))).all(axis=1)
    out = np.full(len(x), EDGE, np.int64)
    j = i[inside]
    out[inside] = classes[j[:, 2], j[:, 1], j[:, 0]]
    return out


def walk(classes, x, bound, allowed, D, dt, steps, every, rng, target=None, p_bind=0.0, koff=0.0, species=None, partner=None, pairs=(), voxel=VOXEL, kinetics=None):
    """Advance particles `steps` steps.

    One species: `allowed` is a boolean lookup of length EDGE + 1 and D, target, p_bind, koff are scalars.
    Several species: `species` gives each particle's species index, `allowed` has one row per species and D, target
    (−1 = none), p_bind, koff are per-species arrays. `partner` (−1 = free) and `pairs` [{a, b, reach (µm), rate, koff}]
    enable A + B ⇌ AB: a complex moves as one particle (the A copy carries the B copy) and must stay inside classes
    both may occupy. Returns positions, bound flags, frames [(x, bound, partner)…], encounters [species, class]
    (class index EDGE = volume edge), counts {binds, releases, pairBinds, pairReleases} and partner.

    `kinetics` (several species only) adds a pool of absent copies and the processes that move copies in and out of it:
      alive      boolean per particle; absent copies do not move, bind or count
      decay      per-species probability per step that a present copy disappears
      births     [(species, expected copies per step, flat voxel indices of the compartment)]: zero-order synthesis
      convert    [(from species, to species, probability per step)]: A → B at the same place
      hop        [species, class] probability that a move stopped by that class crosses it instead (membrane transport)
      far        {(species, class): (classes on one side, classes on the other)}; a crossing lands in the nearest voxel of
                 the side the copy is not on, within REACH voxels of where the move was stopped
    With `kinetics` the frames carry a fourth item (alive) and counts gain born, died, converted, saturated, crossings
    [species, class] and a `kinlog` of (step, kind, particle, x, y, z)."""
    x = x.copy(); bound = bound.copy(); n = len(x)
    single = species is None
    if single:
        species = np.zeros(n, np.int64); allowed = np.asarray(allowed, bool)[None, :]
        D = [D]; target = [-1 if target is None else target]; p_bind = [p_bind]; koff = [koff]
    species = np.asarray(species, np.int64); allowed = np.asarray(allowed, bool)
    D = np.asarray(D, float); target = np.asarray(target, np.int64); p_bind = np.asarray(p_bind, float)
    partner = np.full(n, -1, np.int64) if partner is None else np.asarray(partner, np.int64).copy()
    sigma0 = np.sqrt(2 * D * dt)[species]; p_off = -np.expm1(-np.asarray(koff, float) * dt)[species]
    tgt = target[species]; pb = p_bind[species]
    radius3 = (1.0 / np.maximum(D, 1e-300)) ** 3                    # R ∝ 1/D, so D_AB = (D_A⁻³ + D_B⁻³)^(−⅓)
    reacts = bool((pb > 0).any())
    encounters = np.zeros((len(D), EDGE + 1), np.int64); flat_enc = encounters.reshape(-1); frames = []
    voxel = np.asarray(voxel, float)
    shape = np.array(classes.shape[::-1]); inv = 1.0 / voxel; grid = np.asarray(classes).reshape(-1); sy, sx = classes.shape[1], classes.shape[2]
    counts = {'binds': 0, 'releases': 0, 'pairBinds': 0, 'pairReleases': 0}
    log = []                                                        # (step, kind, a, b, x, y, z) for pair events
    kin = kinetics or None
    if kin:
        alive = np.asarray(kin['alive'], bool).copy()
        p_decay = np.asarray(kin.get('decay', np.zeros(len(D))), float)[species]
        births = kin.get('births') or []; convert = kin.get('convert') or []
        hop = np.asarray(kin['hop'], float) if kin.get('hop') is not None else None
        hop = hop if hop is not None and hop.any() else None
        far = kin.get('far') or {}
        dying = bool(p_decay.any())
        counts.update({'born': 0, 'died': 0, 'converted': 0, 'saturated': 0, 'thick': 0}); crossings = np.zeros((len(D), EDGE + 1), np.int64); kinlog = []
        cube = np.asarray(classes)

        def beyond(point, sides, origin):
            """Centre of the nearest voxel on the other side of a boundary from `origin` (a class), or None."""
            other = sides[1] if origin in sides[0] else sides[0] if origin in sides[1] else None
            if not other:
                return None
            c = np.floor(point * inv).astype(np.int64); lo = np.maximum(c - HOP_REACH, 0); hi = np.minimum(c + HOP_REACH + 1, shape)
            sub = cube[lo[2]:hi[2], lo[1]:hi[1], lo[0]:hi[0]]
            zz, yy, xx = np.nonzero(np.isin(sub, list(other)))
            if not zz.size:
                return None
            centres = (np.stack([xx + lo[0], yy + lo[1], zz + lo[2]], axis=1) + 0.5) * voxel
            return centres[int(((centres - point) ** 2).sum(axis=1).argmin())]

        def remove(i, step, kind):
            """Take copy i out of the system: it leaves its complex and its binding site first."""
            j = partner[i]
            if j >= 0:
                partner[j] = -1; partner[i] = -1; counts['pairReleases'] += 1; log.append((step, 'unbind', int(min(i, j)), int(max(i, j)), *x[i]))
            bound[i] = False; alive[i] = False; kinlog.append((step, kind, int(i), *x[i]))
    else:
        alive = None

    def refresh():
        """Step lengths and the complex bookkeeping after any change of `partner`."""
        sig = sigma0.copy()
        lead = np.flatnonzero((partner >= 0) & (np.arange(n) < partner))       # lower index leads its complex
        follow = partner[lead]
        if lead.size:
            d = (radius3[species[lead]] + radius3[species[follow]]) ** (-1.0 / 3.0)
            sig[lead] = np.sqrt(2 * d * dt); sig[follow] = 0.0
        return sig, lead, follow
    sigma, lead, follow = refresh()
    block = 256
    for start in range(0, steps, block):
        m = min(block, steps - start)
        noise = rng.standard_normal((m, n, 3))
        chance = rng.random((m, n)) if (reacts or bound.any()) else None
        fate = rng.random((m, n)) if kin and (dying or convert or hop is not None) else None       # drawn only when a kinetic process is on
        for k in range(m):
            step = start + k + 1
            if chance is not None and bound.any():
                free_now = bound & (chance[k] < p_off)
                counts['releases'] += int(free_now.sum()); bound &= ~free_now
                mobile = ~bound & ~free_now                           # a released particle moves from the next step
            else:
                mobile = ~bound
            mobile = mobile & (sigma > 0)
            if alive is not None:
                mobile &= alive
            trial = x + noise[k] * sigma[:, None]
            i = np.floor(trial * inv).astype(np.int64)
            inside = ((i >= 0) & (i < shape)).all(axis=1)
            cls = np.where(inside, grid[np.where(inside, (i[:, 2] * sy + i[:, 1]) * sx + i[:, 0], 0)], EDGE)
            ok = allowed[species, cls] & mobile
            if lead.size:
                ok[lead] &= allowed[species[follow], cls[lead]]
            blocked = mobile & ~ok
            if blocked.any():
                flat_enc += np.bincount(species[blocked] * (EDGE + 1) + cls[blocked], minlength=flat_enc.size)
                if reacts:
                    stick = blocked & (cls == tgt) & (chance[k] < pb) & (partner < 0)
                    counts['binds'] += int(stick.sum()); bound |= stick
                if kin and hop is not None:                         # membrane transport: a stopped move crosses with probability hop[species, class]
                    for j in np.flatnonzero(blocked & (partner < 0) & ~bound & (fate[k] < hop[species, cls])):
                        gate = int(cls[j]); sides = far.get((int(species[j]), gate))
                        if not sides:
                            continue
                        here = int(grid[(int(x[j, 2] * inv[2]) * sy + int(x[j, 1] * inv[1])) * sx + int(x[j, 0] * inv[0])])
                        landing = beyond(trial[j], sides, here)
                        if landing is None:
                            counts['thick'] += 1                   # the boundary is thicker than the crossing reach here
                        else:
                            x[j] = landing; crossings[species[j], gate] += 1; kinlog.append((step, 'cross', int(j), *landing))
            x[ok] = trial[ok]
            if lead.size:
                x[follow] = x[lead]
            changed = False
            if kin:
                if dying:
                    for j in np.flatnonzero(alive & (fate[k] > 1.0 - p_decay)):
                        remove(j, step, 'decay'); counts['died'] += 1; changed = True
                for src, dst, p_conv in convert:
                    cand = np.flatnonzero(alive & (species == src) & (partner < 0) & ~bound)
                    if cand.size:
                        for j in cand[rng.random(cand.size) < p_conv]:
                            free = np.flatnonzero(~alive & (species == dst))
                            if not free.size:
                                counts['saturated'] += 1; continue
                            pos = x[j].copy(); remove(j, step, 'convert'); q = free[0]
                            x[q] = pos; alive[q] = True; bound[q] = False; partner[q] = -1
                            counts['converted'] += 1; kinlog.append((step, 'appear', int(q), *pos)); changed = True
                for sp_i, rate, voxels in births:
                    for _ in range(rng.poisson(rate)):
                        free = np.flatnonzero(~alive & (species == sp_i))
                        if not free.size:
                            counts['saturated'] += 1; continue
                        v = int(voxels[rng.integers(voxels.size)]); zz, rem = divmod(v, sy * sx); yy, xx = divmod(rem, sx)
                        q = free[0]; x[q] = (np.array([xx, yy, zz]) + rng.random(3)) * voxel
                        alive[q] = True; bound[q] = False; partner[q] = -1
                        counts['born'] += 1; kinlog.append((step, 'born', int(q), *x[q])); changed = True
            if pairs and step % PAIR_EVERY == 0:
                present = alive if alive is not None else True
                for pair in pairs:
                    a_free = np.flatnonzero((species == pair['a']) & (partner < 0) & ~bound & present)
                    b_free = np.flatnonzero((species == pair['b']) & (partner < 0) & ~bound & present)
                    together = np.flatnonzero((species == pair['a']) & (partner >= 0))
                    together = together[species[partner[together]] == pair['b']]
                    if together.size and pair['koff'] > 0:
                        apart = together[rng.random(together.size) < -math.expm1(-pair['koff'] * PAIR_EVERY * dt)]
                        if apart.size:
                            log += [(step, 'unbind', int(min(a, partner[a])), int(max(a, partner[a])), *x[a]) for a in apart]
                            partner[partner[apart]] = -1; partner[apart] = -1
                            counts['pairReleases'] += int(apart.size); changed = True
                    if a_free.size and b_free.size and pair['rate'] > 0:
                        d2 = ((x[a_free][:, None, :] - x[b_free][None, :, :]) ** 2).sum(axis=2)
                        ia, ib = np.nonzero(d2 < pair['reach'] ** 2)
                        if ia.size:
                            hit = rng.random(ia.size) < -math.expm1(-pair['rate'] * PAIR_EVERY * dt)
                            for j in np.argsort(d2[ia, ib]):
                                a, b = int(a_free[ia[j]]), int(b_free[ib[j]])
                                lo, hi = min(a, b), max(a, b)
                                here = class_at(classes, x[lo:lo + 1], voxel)[0]
                                if hit[j] and partner[a] < 0 and partner[b] < 0 and allowed[species[hi], here]:
                                    partner[a] = b; partner[b] = a; x[hi] = x[lo]       # the complex forms at the leading copy
                                    counts['pairBinds'] += 1; changed = True; log.append((step, 'bind', lo, hi, *x[lo]))
            if changed:
                sigma, lead, follow = refresh()
            if step % every == 0:
                frames.append((x.copy(), bound.copy(), partner.copy()) + ((alive.copy(),) if kin else ()))
    if single:
        return x, bound, [(f[0], f[1]) for f in frames], encounters[0], counts['binds'], counts['releases']
    counts['log'] = log
    if kin:
        counts.update({'alive': alive, 'crossings': crossings, 'kinlog': kinlog})
    return x, bound, frames, encounters, counts, partner


def free_control(D, dt, seed, voxel=VOXEL):
    """The same kernel on an obstacle-free grid: MSD after 64 steps against 6Dt (z-score)."""
    n, steps = 3000, 64
    grid = np.ones((64, 64, 64), np.uint8)
    centre = np.array([32 * v for v in voxel])
    x0 = np.tile(centre, (n, 1))
    allowed = np.ones(EDGE + 1, bool); allowed[EDGE] = False
    x, _, _, enc, _, _ = walk(grid, x0, np.zeros(n, bool), allowed, D, dt, steps, steps, np.random.default_rng([seed, 99991]), voxel=voxel)
    sq = ((x - x0) ** 2).sum(axis=1); expected = 6 * D * dt * steps
    z = (sq.mean() - expected) / (sq.std(ddof=1) / math.sqrt(n))
    return {'msd': float(sq.mean()), 'expected': float(expected), 'z': float(z), 'edgeHits': int(enc.sum())}


def _number(spec, source):
    out = {}
    for s in spec:
        try:
            v = float(source.get(s['key'], s['default']))
        except (TypeError, ValueError):
            raise EMError(s['description'] + ' must be a number.')
        if not math.isfinite(v) or not s['bounds'][0] <= v <= s['bounds'][1]:
            raise EMError(f"{s['description']} must be between {s['bounds'][0]:g} and {s['bounds'][1]:g} {s['unit']}.")
        out[s['key']] = int(v) if s.get('integer') else v
    return out


def _release(classes, p, n, rng, voxel=VOXEL):
    """Start positions. {'compartment': key} = uniform over that class; {'point': [x, y, z] µm} = that voxel's class,
    all copies inside one voxel. Returns positions and the home class."""
    voxel = np.asarray(voxel, float)
    if p.get('point') is not None:
        point = np.asarray(p['point'], float).reshape(1, 3)
        home = int(class_at(classes, point, voxel)[0])
        if home == EDGE:
            raise EMError('The release point is outside the imaged volume.')
        corner = np.floor(point / voxel) * voxel
        return corner + rng.random((n, 3)) * voxel, home
    key = p.get('compartment', 'cytosol')
    if key not in KEYS:
        raise EMError('Unknown compartment.')
    home = KEYS[key]
    flat = np.flatnonzero(np.asarray(classes).ravel() == home)
    if not flat.size:
        raise EMError('That compartment has no voxels in this cell.')
    z, y, xx = np.unravel_index(rng.choice(flat, n), classes.shape)
    return (np.stack([xx, y, z], axis=1) + rng.random((n, 3))) * voxel, home


def _configure(p):
    """Validated run configuration from a request. A request without `species` describes one molecule in flat keys."""
    raw = p.get('species') or [{k: p[k] for k in ('name', 'radiusNm', 'particles', 'pBind', 'koff', 'release', 'target', 'nuclearExchange', 'alsoAccessible', 'structure', 'structureSha256', 'structureName') if k in p}]
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_SPECIES:
        raise EMError(f'Choose between 1 and {MAX_SPECIES} molecules.')
    context = p.get('context') or HELA
    if context not in CONTEXTS:
        raise EMError('Unknown cell context.')
    species = []
    for i, s in enumerate(raw):
        v = _number(SPECIES_INPUTS, s)
        v.update({'name': str(s.get('name') or f'Molecule {i + 1}')[:80], 'release': s.get('release') or {'compartment': 'cytosol'}, 'target': s.get('target') or None,
                  'nuclearExchange': bool(s.get('nuclearExchange')), 'alsoAccessible': [k for k in (s.get('alsoAccessible') or []) if k in KEYS],
                  'structure': str(s['structure'])[:120] if s.get('structure') else None,
                  'structureSha256': str(s['structureSha256'])[:64] if s.get('structureSha256') else None,
                  'structureName': str(s['structureName'])[:160] if s.get('structureName') else None})
        if v['target'] is not None and v['target'] not in KEYS:
            raise EMError('Unknown binding target.')
        syn = s.get('synthesis') or {}
        k = _number(KINETIC_INPUTS, {'capacity': s.get('capacity') or v['particles'], 'synthesisRate': syn.get('rate', 0.0), 'decay': s.get('decay', 0.0)})
        if k['capacity'] < v['particles']:
            raise EMError(f"{v['name']}: the most copies that can exist must be at least the number released.")
        if k['synthesisRate'] > 0 and syn.get('compartment') not in KEYS:
            raise EMError(f"{v['name']}: choose the compartment where it is synthesised.")
        exchange = []
        for e in s.get('exchange') or []:
            if e.get('through') not in KEYS or e.get('to') not in KEYS or e['through'] == e['to']:
                raise EMError(f"{v['name']}: an exchange needs the boundary it crosses and the compartment beyond it.")
            exchange.append({'through': e['through'], 'to': e['to'], **_number([EXCHANGE_INPUT], e)})
        v.update({'capacity': k['capacity'], 'synthesis': {'rate': k['synthesisRate'], 'compartment': syn['compartment']} if k['synthesisRate'] > 0 else None, 'decay': k['decay'], 'exchange': exchange})
        species.append(v)
    if sum(s['capacity'] for s in species) > MAX_PARTICLES:
        raise EMError(f'At most {MAX_PARTICLES} copies in total.')
    pairs = []
    for q in p.get('pairs') or []:
        v = _number(PAIR_INPUTS, q)
        try:
            a, b = int(q['a']), int(q['b'])
        except (KeyError, TypeError, ValueError):
            raise EMError('A pair needs two molecules.')
        if a == b or not (0 <= a < len(species) and 0 <= b < len(species)) or any({a, b} == {r['a'], r['b']} for r in pairs):
            raise EMError('A pair must join two different molecules, once.')
        pairs.append({'a': a, 'b': b, **v})
    reactions = []
    for q in p.get('reactions') or []:
        try:
            a, b = int(q['from']), int(q['to'])
        except (KeyError, TypeError, ValueError):
            raise EMError('A conversion needs a starting molecule and a product.')
        if a == b or not (0 <= a < len(species) and 0 <= b < len(species)):
            raise EMError('A conversion turns one of your molecules into a different one.')
        reactions.append({'from': a, 'to': b, **_number([REACTION_INPUT], q)})
    parent = str(p.get('parent') or '')
    cfg = {**_number(INPUTS, {**p, 'slowdown': p.get('slowdown', context_defaults(context)['slowdown']['value'])}), 'context': context, 'species': species, 'pairs': pairs, 'reactions': reactions,
           'frameSeconds': min(0.05, max(1e-5, float(p.get('frameSeconds') or 0.004))),
           'label': str(p.get('label') or '')[:120], 'parent': parent if re.fullmatch(r'[0-9a-f]{32}', parent) else None}
    if p.get('upstream'):                                           # a quantity handed over by another model, recorded with the run
        u = p['upstream']; cfg['upstream'] = {k: str(u.get(k) or '')[:200] for k in ('model', 'run', 'quantity', 'unit', 'note')}
    return cfg


def has_kinetics(cfg):
    return bool(cfg.get('reactions')) or any(s['capacity'] > s['particles'] or s['synthesis'] or s['decay'] > 0 or s['exchange'] for s in cfg['species'])


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), default=float).encode()).hexdigest()


def simulate(service, p, classes=None):
    """One chunk of the simulation. Without `state` a new run starts; with the returned `state` it continues, so the
    interface can stream consecutive chunks. Every returned frame is a computed frame."""
    state = p.get('state')
    cfg = _configure(state['config'] if state else p)
    context = cfg['context']; info = CONTEXTS[context]
    if classes is None:
        classes, voxel, gmeta, geometry_sha = geometry(service.root, context)
    else:
        voxel, gmeta, geometry_sha = (VOXEL if context == HELA else ROD['voxel']), None, None
    voxel = tuple(voxel); cell_volume = voxel[0] * voxel[1] * voxel[2]
    sp = cfg['species']; ns = len(sp); names = [c[1] for c in CLASSES] + ['edge']
    D = np.array([diffusion_coefficient(s['radiusNm'], cfg['temperature'], cfg['slowdown']) for s in sp])
    dt = (STEP_FRACTION * min(voxel)) ** 2 / (2 * D.max())
    kinetic = has_kinetics(cfg)
    owner = np.repeat(np.arange(ns), [s['capacity'] for s in sp]); n = len(owner)
    if state:
        x = np.asarray(state['x'], float).reshape(n, 3); x0 = np.asarray(state['x0'], float).reshape(n, 3)
        bound = np.asarray(state['bound'], bool); partner = np.asarray(state['partner'], np.int64)
        alive = np.asarray(state['alive'], bool) if state.get('alive') is not None else np.ones(n, bool)
        chunk, step0 = int(state['chunk']), int(state['step'])
        homes = [int(h) for h in state['homes']]; access = [[int(a) for a in row] for row in state['accessible']]; sides = state.get('sides') or [{} for _ in sp]
        totals = np.asarray(state['encounters'], np.int64).reshape(ns, EDGE + 1); events = dict(state['events']); run_id = str(state['id'])
        cross_total = np.asarray(state.get('crossings') or np.zeros(ns * (EDGE + 1)), np.int64).reshape(ns, EDGE + 1)
        if not re.fullmatch(r'[0-9a-f]{32}', run_id) or len(homes) != ns or len(bound) != n or len(partner) != n or len(alive) != n:
            raise EMError('Invalid run state.')
    else:
        rng0 = np.random.default_rng([cfg['seed'], 0])
        parts, homes, access, present, sides = [], [], [], [], []
        for s in sp:
            xs, home = _release(classes, s['release'], s['capacity'], rng0, voxel)
            reach = {home} | {KEYS[k] for k in s['alsoAccessible']}
            if names[home] in NUCLEAR:
                reach |= {KEYS[k] for k in NUCLEAR}
            if s['nuclearExchange'] and (names[home] in NUCLEAR or home == KEYS['cytosol']):
                reach |= {KEYS[k] for k in NUCLEAR} | {KEYS['cytosol'], KEYS['ne']}
            near = set(reach); beyond_ = {}
            for e in s['exchange']:
                if KEYS[e['through']] in reach:
                    raise EMError(f"{s['name']}: {e['through']} is already open to it; a permeable boundary must be one it cannot enter.")
                other = {KEYS[e['to']]} | ({KEYS[k] for k in NUCLEAR} if e['to'] in NUCLEAR else set())
                if other & near:
                    raise EMError(f"{s['name']}: it can already reach {e['to']} without crossing {e['through']}.")
                beyond_[KEYS[e['through']]] = sorted(other); reach |= other
            sides.append({str(g): [sorted(near), o] for g, o in beyond_.items()})
            if s['target'] is not None and KEYS[s['target']] in reach:
                raise EMError(f"{s['name']}: the binding target must be a compartment the molecule cannot enter.")
            if s['synthesis'] and KEYS[s['synthesis']['compartment']] not in reach:
                raise EMError(f"{s['name']}: it is synthesised in a compartment it cannot occupy.")
            parts.append(xs); homes.append(home); access.append(set(reach)); present.append(np.arange(s['capacity']) < s['particles'])
        for _ in cfg['reactions']:                                  # a product can exist wherever it is made
            for q in cfg['reactions']:
                access[q['to']] |= access[q['from']]
        for i, s in enumerate(sp):
            if s['target'] is not None and KEYS[s['target']] in access[i]:
                raise EMError(f"{s['name']}: it is made in its own binding target; choose a target it cannot enter.")
        access = [sorted(a) for a in access]
        x = np.concatenate(parts); x0 = x.copy(); bound = np.zeros(n, bool); partner = np.full(n, -1, np.int64); alive = np.concatenate(present)
        chunk = step0 = 0; totals = np.zeros((ns, EDGE + 1), np.int64); cross_total = np.zeros((ns, EDGE + 1), np.int64)
        events = {'binds': 0, 'releases': 0, 'pairBinds': 0, 'pairReleases': 0}; run_id = uuid.uuid4().hex
        if kinetic:
            events.update({'born': 0, 'died': 0, 'converted': 0, 'saturated': 0, 'thick': 0, 'crossings': 0})
    allowed = np.zeros((ns, EDGE + 1), bool)
    for i, row in enumerate(access):
        allowed[i, row] = True
    every = max(1, round(cfg['frameSeconds'] / dt))
    if every * FRAMES > MAX_STEPS:
        every = MAX_STEPS // FRAMES
    every = max(PAIR_EVERY, every // PAIR_EVERY * PAIR_EVERY) if cfg['pairs'] else every     # pair checks fall on frame boundaries
    steps = every * FRAMES
    pairs = [{'a': q['a'], 'b': q['b'], 'reach': q['reachNm'] / 1000.0, 'rate': q['rate'], 'koff': q['koff']} for q in cfg['pairs']]
    kin = None
    if kinetic:
        hop = np.zeros((ns, EDGE + 1)); far = {}
        for i, s in enumerate(sp):
            for e in s['exchange']:
                pr = e['permeabilityUmS'] * math.sqrt(math.pi * dt / D[i])   # a stopped move crosses with P = κ·√(πΔt/D): flux κ·c through a wall met at rate c·√(D/πΔt)
                if pr > MAX_HOP:
                    raise EMError(f"{s['name']}: a permeability of {e['permeabilityUmS']:g} µm/s is too high for this time step (crossing probability {pr:.2f}). Above {MAX_HOP * math.sqrt(D[i] / (math.pi * dt)):.3g} µm/s, open the boundary instead.")
                g = KEYS[e['through']]; hop[i, g] = pr; far[(i, g)] = tuple(set(v) for v in sides[i][str(g)])
        flat = np.asarray(classes).ravel()
        kin = {'alive': alive, 'decay': [-math.expm1(-s['decay'] * dt) for s in sp], 'hop': hop, 'far': far,
               'births': [(i, s['synthesis']['rate'] * dt, np.flatnonzero(flat == KEYS[s['synthesis']['compartment']])) for i, s in enumerate(sp) if s['synthesis']],
               'convert': [(q['from'], q['to'], -math.expm1(-q['rate'] * dt)) for q in cfg['reactions']]}
        for i, _, vox in kin['births']:
            if not vox.size:
                raise EMError(f"{sp[i]['name']}: its synthesis compartment has no voxels in this cell.")
    if p.get('preview') and not state:                               # placement preview: start positions only, nothing advanced or saved
        return {'preview': True, 'owner': owner.tolist(), 'frames': [np.round(x, 4).ravel().tolist()], 'absent': [np.flatnonzero(~alive).tolist()],
                'species': [{'name': s['name'], 'home': names[homes[i]], 'accessible': [names[a] for a in access[i]], 'particles': s['particles']} for i, s in enumerate(sp)]}
    began = time.perf_counter()
    before = np.array([int(alive[owner == i].sum()) for i in range(ns)])
    x, bound, frames, enc, counts, partner = walk(classes, x, bound, allowed, D, dt, steps, every, np.random.default_rng([cfg['seed'], chunk + 1]),
                                                  [KEYS[s['target']] if s['target'] else -1 for s in sp], [s['pBind'] if s['target'] else 0.0 for s in sp],
                                                  [s['koff'] for s in sp], owner, partner, pairs, voxel, kin)
    elapsed = time.perf_counter() - began
    totals = totals + enc
    log = counts.pop('log'); kinlog = counts.pop('kinlog', [])
    if kinetic:
        alive = counts.pop('alive'); crossed = counts.pop('crossings'); cross_total = cross_total + crossed; counts['crossings'] = int(crossed.sum())
    events = {k: int(events.get(k, 0)) + int(v) for k, v in counts.items()}
    history = list((state or {}).get('log') or [])
    frame_of = lambda st: min(FRAMES - 1, max(0, -(-st // every) - 1))
    where_is = lambda pos: names[int(class_at(classes, np.array([pos]), voxel)[0])]
    fresh_events = [{'time': round((step0 + st) * dt, 7), 'frame': frame_of(st), 'kind': kind, 'a': a, 'b': b, 'species': [sp[owner[a]]['name'], sp[owner[b]]['name']],
                     'position': [round(float(v), 4) for v in pos], 'compartment': where_is(pos)} for st, kind, a, b, *pos in log]
    history = (history + [{k: e[k] for k in e if k != 'frame'} for e in fresh_events])[:MAX_EVENTS]
    kin_events = [{'time': round((step0 + st) * dt, 7), 'frame': frame_of(st), 'kind': kind, 'a': a, 'species': [sp[owner[a]]['name']], 'position': [round(float(v), 4) for v in pos], 'compartment': where_is(pos)}
                  for st, kind, a, *pos in kinlog if kind != 'appear'][:MAX_KIN_EVENTS]
    where = class_at(classes, x, voxel)
    violations = int((~allowed[owner, where] & alive).sum())
    split = int((np.abs(x[partner[partner >= 0]] - x[partner >= 0]) > 1e-9).any(axis=1).sum()) if (partner >= 0).any() else 0
    times = [(step0 + (i + 1) * every) * dt for i in range(FRAMES)]
    volumes = np.bincount(np.asarray(classes).ravel(), minlength=EDGE + 1) * cell_volume
    per = []
    for i, s in enumerate(sp):
        mine = owner == i
        here = [fr[3][mine] if kinetic else np.ones(int(mine.sum()), bool) for fr in frames]
        steady = alive[mine] if kinetic else here[0]
        occ = np.array([np.bincount(class_at(classes, fr[0][mine][h], voxel), minlength=EDGE + 1) for fr, h in zip(frames, here)])
        used = [c for c in range(EDGE + 1) if occ[:, c].any()]
        mean = lambda values, h: float(values[h].mean()) if h.any() else 0.0
        per.append({'name': s['name'], 'structure': s['structure'], 'radiusNm': s['radiusNm'], 'particles': s['particles'], 'capacity': s['capacity'], 'D': float(D[i]), 'home': names[homes[i]],
                    'accessible': [names[a] for a in access[i]], 'target': s['target'],
                    'msd': [round(mean(((fr[0][mine] - x0[mine]) ** 2).sum(axis=1), h), 5) for fr, h in zip(frames, here)], 'msdFromRelease': not kinetic,
                    'boundFraction': [mean(fr[1][mine], h) for fr, h in zip(frames, here)], 'complexFraction': [mean(fr[2][mine] >= 0, h) for fr, h in zip(frames, here)],
                    'present': [int(h.sum()) for h in here],
                    'occupancySeries': {names[c]: occ[:, c].tolist() for c in used}, 'compartmentVolumeUm3': {names[c]: float(volumes[c]) for c in used if c < EDGE},
                    'encounters': {names[c]: int(totals[i, c]) for c in range(EDGE + 1) if totals[i, c]}, 'crossings': {names[c]: int(cross_total[i, c]) for c in range(EDGE + 1) if cross_total[i, c]},
                    'occupancy': {names[c]: int(k) for c, k in enumerate(np.bincount(where[mine][steady], minlength=EDGE + 1)) if k}})
    checks = [{'name': 'Confinement', 'passed': violations == 0 and split == 0, 'applicable': True, 'value': {'violations': violations, 'splitComplexes': split}, 'threshold': '0',
               'detail': 'Particles outside their accessible classes, or complexes whose two copies are apart, after this chunk.'},
              {'name': 'Step length', 'passed': True, 'applicable': True, 'value': {'rmsStepNm': math.sqrt(2 * D.max() * dt) * 1000, 'voxelNm': min(voxel) * 1000}, 'threshold': f'≤ {STEP_FRACTION:g} voxel',
               'detail': 'Δt is derived from the fastest molecule so the rms step per axis stays below the voxel edge.'}]
    if kinetic:                                                 # the logged events must account for every change in the number of copies
        gained = np.zeros(ns, np.int64)
        for _, kind, a, *_ in kinlog:
            gained[owner[a]] += 1 if kind in ('born', 'appear') else -1 if kind in ('decay', 'convert') else 0
        after = np.array([int(alive[owner == i].sum()) for i in range(ns)])
        balance = (after - before - gained).tolist()
        checks.append({'name': 'Counts agree with events', 'passed': not any(balance), 'applicable': True, 'value': {'unexplainedChange': balance, 'copiesNow': after.tolist()}, 'threshold': '0',
                       'detail': 'Copies present after the chunk = copies before + synthesised and converted in − decayed and converted out, per molecule, from the event log.'})
    if state:                                                   # the kernel control ran once, on the first chunk
        checks = [c for c in state.get('checks') or [] if c['name'] == 'Free-diffusion control'] + checks
    else:
        c = free_control(float(D.max()), dt, cfg['seed'], voxel)
        checks.insert(0, {'name': 'Free-diffusion control', 'passed': abs(c['z']) < 4 and c['edgeHits'] == 0, 'applicable': True, 'value': c, 'threshold': '|z| < 4',
                          'detail': 'Same kernel, obstacle-free grid, 3000 particles, 64 steps, against 6Dt.'})
    passed = all(c['passed'] for c in checks) and bool((state or {}).get('passed', True))
    t_end = times[-1]
    summary = {'time': t_end, 'timeUnit': 's', 'lengthUnit': 'µm', 'events': events, 'pairEvents': history, 'pairEventsTruncated': events['pairBinds'] + events['pairReleases'] > len(history),
               'species': {s['name']: {'msd': s['msd'][-1], 'apparentD': s['msd'][-1] / (6 * t_end), 'boundFraction': s['boundFraction'][-1], 'complexFraction': s['complexFraction'][-1],
                                       'encounters': s['encounters'], 'occupancy': s['occupancy'], **({'present': s['present'][-1], 'crossings': s['crossings']} if kinetic else {})} for s in per},
               'apparentDNote': 'MSD(t)/(6t) from the release positions; falls below D as walls and binding confine the molecule'}
    hypothetical = {'provenance': {'kind': 'hypothetical', 'note': 'User assumption; not measured or predicted for any specific molecule.'}}
    slow = context_defaults(context)['slowdown']
    inputs = {s['key']: {'value': cfg[s['key']], 'unit': s['unit'], 'description': s['description'],
                         **(({'provenance': slow['provenance']} if cfg['slowdown'] == slow['value'] else hypothetical) if s['key'] == 'slowdown' else {})} for s in INPUTS}
    for i, s in enumerate(sp):
        for spec in SPECIES_INPUTS:
            inputs[f"{i + 1}.{spec['key']}"] = {'value': s[spec['key']], 'unit': spec['unit'], 'description': f"{s['name']}: {spec['description']}", **(hypothetical if spec['key'] in ('pBind', 'koff') else {})}
        if kinetic:
            inputs[f'{i + 1}.capacity'] = {'value': s['capacity'], 'unit': 'copies', 'description': f"{s['name']}: most copies that can exist at once"}
            if s['synthesis']:
                inputs[f'{i + 1}.synthesis'] = {'value': s['synthesis']['rate'], 'unit': 'copies s⁻¹', 'description': f"{s['name']}: synthesis in {s['synthesis']['compartment']}", **hypothetical}
            if s['decay']:
                inputs[f'{i + 1}.decay'] = {'value': s['decay'], 'unit': 's⁻¹', 'description': f"{s['name']}: decay rate", **hypothetical}
            for e in s['exchange']:
                inputs[f"{i + 1}.exchange.{e['through']}"] = {'value': e['permeabilityUmS'], 'unit': 'µm s⁻¹', 'description': f"{s['name']}: permeability of {e['through']} towards {e['to']}", **hypothetical}
    for q in cfg['pairs']:
        for spec in PAIR_INPUTS:
            inputs[f"{q['a'] + 1}+{q['b'] + 1}.{spec['key']}"] = {'value': q[spec['key']], 'unit': spec['unit'], 'description': f"{sp[q['a']]['name']} + {sp[q['b']]['name']}: {spec['description']}", **hypothetical}
    for q in cfg['reactions']:
        inputs[f"{q['from'] + 1}>{q['to'] + 1}.rate"] = {'value': q['rate'], 'unit': 's⁻¹', 'description': f"{sp[q['from']]['name']} → {sp[q['to']]['name']}: conversion rate", **hypothetical}
    solver = {'D': [float(d) for d in D], 'DUnit': 'µm²/s', 'dt': dt, 'dtUnit': 's', 'stepsPerFrame': every, 'pairCheckEverySteps': PAIR_EVERY if pairs else None,
              'waterViscosityPaS': water_viscosity(cfg['temperature']), 'species': [{k: s[k] for k in ('name', 'structure', 'home', 'accessible', 'target')} for s in per],
              'release': [s['release'] for s in sp], 'dataset': DATASET['id'] if context == HELA else None, 'level': LEVEL if context == HELA else None, 'geometrySha256': geometry_sha,
              'context': context, 'geometry': info['geometry'], 'voxelUm': list(voxel), 'kinetics': kinetic,
              'crossingProbability': {f"{sp[i]['name']}·{names[c]}": float(kin['hop'][i, c]) for i in range(ns) for c in range(EDGE + 1) if kin['hop'][i, c]} if kinetic else None}
    created = (state or {}).get('created') or datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    measured = context == HELA
    record = {'schema': 'fold-studio.research-record', 'schemaVersion': 1, 'id': run_id, 'kind': 'cell_em.brownian',
              'experiment': {'label': cfg['label'], 'parent': cfg['parent'], 'config': cfg, 'chunks': chunk + 1, 'context': context,
                             'rerun': 'Send `config` to cell_em_simulate, then the returned `state` for each further chunk; the same seed and chunk sequence reproduce every frame.'},
              'engine': {k: ENGINE[k] for k in ('id', 'name', 'version', 'numericalMethod')},
              'evidence': {'category': 'B', 'name': 'Physics simulation', 'statement': ('Computed Brownian motion of idealised point particles inside the segmented geometry of one fixed HeLa cell imaged by FIB-SEM. The geometry is measured; molecule sizes come from the stated radii and every binding parameter is an assumption.'
                                                                                         if measured else 'Computed Brownian motion of idealised point particles inside an illustrative rod-shaped cell. The geometry is drawn from typical E. coli dimensions and is not an image; the diffusion slowdown is calibrated to a published measurement and every other rate is an assumption.')},
              'created': created, 'inputs': inputs, 'solver': solver, 'outputs': summary, 'benchmark': {'checks': checks, 'passed': passed},
              'assumptions': ENGINE['assumptions'], 'limitations': ENGINE['limits']}
    record['reproducibility'] = {'deterministic': False, 'seed': cfg['seed'], 'runtime': 'Python ' + platform.python_version() + ' · NumPy ' + np.__version__,
                                 'contentSha256': _sha({k: record[k] for k in ('inputs', 'solver', 'outputs')}),
                                 'note': 'Stochastic; repeatable with the same seed, chunk sequence, NumPy version and platform. The record holds the latest cumulative summary of a streamed run.'}
    if service is not None and getattr(service, 'root', None):
        runs_dir = pathlib.Path(service.root) / 'cell_em' / 'runs'; runs_dir.mkdir(parents=True, exist_ok=True)
        (runs_dir / (run_id + '.json')).write_text(json.dumps(record, default=float))
    return {'id': run_id, 'context': context, 'time': [round(t, 7) for t in times], 'owner': owner.tolist(), 'frames': [np.round(fr[0], 4).ravel().tolist() for fr in frames],
            'bound': [np.flatnonzero(fr[1]).tolist() for fr in frames], 'paired': [[[int(i), int(fr[2][i])] for i in np.flatnonzero(fr[2] >= 0) if i < fr[2][i]] for fr in frames],
            'absent': [np.flatnonzero(~fr[3]).tolist() for fr in frames] if kinetic else None,
            'species': per, 'events': events, 'pairEvents': fresh_events, 'kinEvents': kin_events, 'summary': summary, 'solver': solver, 'checks': checks, 'passed': passed,
            'computeSeconds': round(elapsed, 3), 'sha256': record['reproducibility']['contentSha256'],
            'state': {'id': run_id, 'config': cfg, 'x': np.round(x, 6).ravel().tolist(), 'x0': np.round(x0, 6).ravel().tolist(), 'bound': bound.astype(int).tolist(),
                      'partner': partner.tolist(), 'alive': alive.astype(int).tolist() if kinetic else None, 'chunk': chunk + 1, 'step': step0 + steps, 'homes': homes, 'accessible': access, 'sides': sides,
                      'encounters': totals.ravel().tolist(), 'crossings': cross_total.ravel().tolist(),
                      'events': events, 'log': history, 'created': created, 'checks': checks, 'passed': passed}}


# ------------------------------------------------------------------ structures

ELEMENT_MASS = {'H': 1.008, 'C': 12.011, 'N': 14.007, 'O': 15.999, 'S': 32.06, 'P': 30.974, 'SE': 78.97, 'FE': 55.845, 'ZN': 65.38, 'MG': 24.305, 'CA': 40.078, 'NA': 22.99, 'CL': 35.45, 'K': 39.098, 'MN': 54.938, 'CU': 63.546}
MAX_ATOMS = 120_000


def parse_atoms(text, fmt, labels=None):
    """Atoms of the first model of a PDB or mmCIF file: (xyz Å, element, chain, hetero flag). Hydrogens and waters are dropped.
    `labels`, when a list, receives (atom name, residue name, residue number) per kept atom."""
    xyz, element, chain, hetero = [], [], [], []

    def add(x, y, z, el, ch, het, res, atom='', seq=''):
        el = (el or '').strip().upper()
        if el in ('H', 'D') or res in ('HOH', 'WAT', 'DOD'):
            return
        if labels is not None:
            labels.append((atom.strip().strip('"'), res.strip(), str(seq).strip()))
        xyz.append((float(x), float(y), float(z))); element.append(el or 'C'); chain.append(ch.strip() or '_'); hetero.append(het)
    if fmt in ('mmcif', 'cif'):
        cols, rows, in_loop = [], False, False
        first_model = None
        for line in text.splitlines():
            t = line.strip()
            if t.startswith('_atom_site.'):
                cols.append(t.split('.', 1)[1].split()[0]); rows = True; continue
            if rows and cols and t and not t.startswith(('#', 'loop_', '_', 'data_')):
                v = t.split()
                if len(v) < len(cols):
                    continue
                r = dict(zip(cols, v))
                model = r.get('pdbx_PDB_model_num', '1')
                first_model = model if first_model is None else first_model
                if model != first_model or r.get('label_alt_id', '.') not in ('.', '?', 'A', '1'):
                    continue
                add(r['Cartn_x'], r['Cartn_y'], r['Cartn_z'], r.get('type_symbol', ''), r.get('auth_asym_id') or r.get('label_asym_id', '_'), r.get('group_PDB') == 'HETATM', r.get('label_comp_id', ''),
                    r.get('label_atom_id', ''), r.get('auth_seq_id') or r.get('label_seq_id', ''))
            elif rows and cols and (t.startswith('#') or t.startswith('loop_')):
                break
    else:
        for line in text.splitlines():
            if line.startswith('ENDMDL'):
                break
            if line.startswith(('ATOM', 'HETATM')) and len(line) >= 54 and line[16] in ' A1':
                el = line[76:78].strip() if len(line) >= 78 and line[76:78].strip() else ''.join(c for c in line[12:14] if c.isalpha())[:1]
                add(line[30:38], line[38:46], line[46:54], el, line[21], line.startswith('HETATM'), line[17:20].strip(), line[12:16], line[22:27])
    if len(xyz) < 4:
        raise EMError('No atoms could be read from that structure.')
    if len(xyz) > 20 * MAX_ATOMS:
        raise EMError(f'That structure has more than {20 * MAX_ATOMS} heavy atoms.')
    return np.array(xyz), element, chain, hetero


def structure(service, p):
    """A saved library structure for display in the cell: centred heavy-atom coordinates, elements, chains, size."""
    name = str(p.get('asset', ''))
    if pathlib.Path(name).name != name or not re.fullmatch(r'[\w.-]+\.(pdb|cif|mmcif|ent)', name):
        raise EMError('Invalid structure file.')
    path = pathlib.Path(service.root) / 'assets' / name
    if not path.is_file() or path.stat().st_size > 60_000_000:
        raise EMError('That structure file is missing or too large.')
    fmt = 'mmcif' if name.endswith(('.cif', '.mmcif')) else 'pdb'
    labels = []
    xyz, element, chain, hetero = parse_atoms(path.read_text(errors='replace'), fmt, labels)
    centre = xyz.mean(axis=0); rel = xyz - centre
    rg = float(np.sqrt((rel ** 2).sum(axis=1).mean()))
    mass = sum(ELEMENT_MASS.get(e, 12.0) for e in element); total = len(xyz)
    stride = -(-total // MAX_ATOMS)                                 # very large assemblies are drawn with every n-th atom
    if stride > 1:
        rel, element, chain, hetero, labels = rel[::stride], element[::stride], chain[::stride], hetero[::stride], labels[::stride]
    elements = sorted(set(element)); chains = list(dict.fromkeys(chain))
    residues, residue_of, seen = [], [], {}
    for c, (_, res, seq) in zip(chain, labels):
        key = (c, res, seq)
        if key not in seen:
            seen[key] = len(residues); residues.append([c, res, seq])
        residue_of.append(seen[key])
    atom_names = sorted({a for a, _, _ in labels})
    polymer = sum(1 for a, _, _ in labels if a == 'CA'), sum(1 for a, _, _ in labels if a == 'P')
    return {'asset': name, 'residues': residues, 'residueOf': residue_of, 'atomNames': atom_names, 'atomName': [atom_names.index(a) for a, _, _ in labels],
            'kind': ('protein–nucleic acid assembly' if min(polymer) > 0.2 * max(polymer) else 'nucleic acid' if polymer[1] > polymer[0] else 'protein' if polymer[0] else 'other'), 'residueCount': len(residues), 'atoms': total, 'drawnAtoms': len(rel), 'drawnEvery': stride, 'chains': chains, 'elements': elements, 'rgNm': rg / 10, 'radiusNm': math.sqrt(5 / 3) * rg / 10,
            'extentNm': float(np.sqrt((rel ** 2).sum(axis=1).max())) / 10, 'heavyAtomMassKDa': mass / 1000,
            'radiusNote': 'Sphere with the same radius of gyration, R = √(5/3)·Rg, from heavy atoms; an estimate for a compact particle, not a measured hydrodynamic radius.',
            'xyz': np.round(rel, 2).ravel().tolist(), 'element': [elements.index(e) for e in element], 'chain': [chains.index(c) for c in chain], 'hetero': [int(h) for h in hetero],
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


# ------------------------------------------------------------------ Cell Painting (forward model)

def paint(service, p):
    """Synthetic Cell Painting-style image of the installed cell: PAINT class weights integrated along y and blurred
    with a Gaussian point spread function. `molecules` (µm positions, optional) adds a probe channel."""
    from scipy import ndimage as ndi
    from PIL import Image
    classes = np.asarray(_grid(service.root, 'classes_u8.npy'))
    psf = float(p.get('psfNm', 250.0))
    if not 100.0 <= psf <= 2000.0:
        raise EMError('The point spread function must be between 100 and 2000 nm (full width at half maximum).')
    sigma = psf / 2.355 / 1000.0
    lut = np.zeros((len(PAINT), EDGE + 1), np.float32)
    for i, ch in enumerate(PAINT.values()):
        for key, w in ch['weights'].items():
            lut[i, KEYS[key]] = w
    channels, images = {}, {}
    rgb = np.zeros((classes.shape[0], classes.shape[2], 3), np.float32)

    def finish(name, img, color, stain, weights):
        img = ndi.gaussian_filter(img, (sigma / VOXEL[2], sigma / VOXEL[0]))
        top = float(np.percentile(img, 99.9)) or 1.0
        img = np.clip(img / top, 0, 1)
        c = np.array([int(color[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255
        rgb[...] += img[..., None] * c
        buf = io.BytesIO(); Image.fromarray((img[..., None] * c * 255).astype(np.uint8)).save(buf, 'PNG')
        images[name] = base64.b64encode(buf.getvalue()).decode()
        channels[name] = {'stain': stain, 'color': color, 'weights': weights, 'scaledTo': '99.9th percentile'}
    for i, (name, ch) in enumerate(PAINT.items()):
        finish(name, lut[i][classes].sum(axis=1) * VOXEL[1], ch['color'], ch['stain'], ch['weights'])
    mol = p.get('molecules')
    if mol:
        pts = np.asarray(mol, float).reshape(-1, 3)
        if len(pts) > 4 * MAX_PARTICLES:
            raise EMError('Too many molecule positions.')
        img, _, _ = np.histogram2d(pts[:, 2], pts[:, 0], bins=(classes.shape[0], classes.shape[2]), range=((0, classes.shape[0] * VOXEL[2]), (0, classes.shape[2] * VOXEL[0])))
        finish('Probe', img.astype(np.float32), '#ffffff', 'Simulated molecules (labelled probe)', {'molecule positions': 1.0})
    buf = io.BytesIO(); Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(buf, 'PNG')
    body = {'schema': 'fold-studio.cell-painting-model/1', 'id': uuid.uuid4().hex, 'created': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'dataset': DATASET['id'], 'psfFwhmNm': psf, 'pixelUm': [VOXEL[0], VOXEL[2]], 'size': [classes.shape[2], classes.shape[0]], 'channels': channels,
            'evidence': {'category': 'D', 'name': 'Parameterised hypothesis', 'statement': 'A forward model of the Cell Painting stains from the EM segmentation of one HeLa cell. Stain weights are assumptions; this is not a fluorescence measurement.'},
            'limitations': ['Actin and cytoplasmic RNA granules are not segmented and are missing from the AGP and RNA channels', 'Widefield sum projection with a Gaussian PSF; no noise, bleed-through, illumination or camera model',
                            'Stain weights per compartment are fixed assumptions, not fitted to any image'],
            'engine': {'name': 'EM-derived Cell Painting model', 'version': VERSION}}
    out = pathlib.Path(service.root) / 'cell_em' / 'paintings'; out.mkdir(parents=True, exist_ok=True)
    (out / (body['id'] + '.png')).write_bytes(buf.getvalue()); (out / (body['id'] + '.json')).write_text(json.dumps(body, indent=1))
    return {**body, 'composite': base64.b64encode(buf.getvalue()).decode(), 'images': images}


def catalog(service):
    m = meta(service.root)
    contexts = []
    for cid, c in CONTEXTS.items():
        gm = m if cid == HELA else geometry(service.root, cid)[2]
        contexts.append({'id': cid, **{k: c[k] for k in ('name', 'short', 'species', 'cell', 'geometry', 'geometryLabel', 'resolution')}, 'installed': gm is not None, 'meta': gm,
                         'defaults': context_defaults(cid), 'hasImage': cid == HELA, 'painting': cid == HELA})
    return {'engine': ENGINE, 'dataset': DATASET, 'installed': m is not None, 'outdated': m is None and (folder(service.root) / 'derived' / 'meta.json').is_file(), 'meta': m,
            'inputs': INPUTS, 'speciesInputs': SPECIES_INPUTS, 'pairInputs': PAIR_INPUTS, 'kineticInputs': KINETIC_INPUTS, 'exchangeInput': EXCHANGE_INPUT, 'reactionInput': REACTION_INPUT,
            'molecules': MOLECULES, 'limits': {'species': MAX_SPECIES, 'particles': MAX_PARTICLES},
            'painting': PAINT, 'contexts': contexts, 'regions': regions(service) if m else [], 'regionLevels': [{'id': k, 'voxelNm': [round(v * 1000 / f, 2) for v in VOXEL]} for k, f in REGION['levels'].items()],
            'classes': [{'id': c[0], 'key': c[1], 'name': c[2], 'color': c[4]} for c in CLASSES]}


def runs(service):
    d = pathlib.Path(service.root) / 'cell_em' / 'runs'
    out = []
    for f in sorted(d.glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)[:40] if d.is_dir() else []:
        r = json.loads(f.read_text()); ex = r.get('experiment') or {}; cfg = ex.get('config') or {}
        out.append({'id': r['id'], 'created': r['created'], 'passed': r['benchmark'].get('passed'), 'time': r['outputs'].get('time'), 'sha256': r['reproducibility']['contentSha256'],
                    'label': ex.get('label') or '', 'parent': ex.get('parent'), 'species': [s['name'] for s in cfg.get('species', [])], 'events': r['outputs'].get('events'), 'replayable': bool(cfg),
                    'context': cfg.get('context') or HELA})
    return out


def run_get(service, p):
    """A saved run with the configuration needed to replay it."""
    rid = str(p.get('id', ''))
    f = pathlib.Path(service.root) / 'cell_em' / 'runs' / (rid + '.json')
    if not re.fullmatch(r'[0-9a-f]{32}', rid) or not f.is_file():
        raise EMError('That saved run no longer exists.')
    r = json.loads(f.read_text())
    if not (r.get('experiment') or {}).get('config'):
        raise EMError('That run was saved by an earlier version and cannot be replayed.')
    return r


DYNAMIC_KEYS = ('radiusNm', 'particles', 'pBind', 'koff', 'release', 'target', 'nuclearExchange', 'alsoAccessible', 'capacity', 'synthesis', 'decay', 'exchange')


def _differences(a, b):
    """What differs between two configurations, and whether any difference can change the simulated dynamics."""
    changed = []
    for key in ('slowdown', 'temperature', 'seed', 'frameSeconds'):
        if a[key] != b[key]:
            changed.append({'what': key, 'baseline': a[key], 'variant': b[key], 'affectsDynamics': True})
    for i in range(max(len(a['species']), len(b['species']))):
        x = a['species'][i] if i < len(a['species']) else None; y = b['species'][i] if i < len(b['species']) else None
        if x is None or y is None:
            changed.append({'what': f'molecule {i + 1}', 'baseline': x and x['name'], 'variant': y and y['name'], 'affectsDynamics': True}); continue
        for key in ('name', 'structure', 'structureSha256') + DYNAMIC_KEYS:
            if x.get(key) != y.get(key):
                changed.append({'what': f"molecule {i + 1} · {key}", 'baseline': x.get(key), 'variant': y.get(key), 'affectsDynamics': key in DYNAMIC_KEYS})
    if a['pairs'] != b['pairs']:
        changed.append({'what': 'pair interactions', 'baseline': a['pairs'], 'variant': b['pairs'], 'affectsDynamics': True})
    if (a.get('reactions') or []) != (b.get('reactions') or []):
        changed.append({'what': 'conversions', 'baseline': a.get('reactions') or [], 'variant': b.get('reactions') or [], 'affectsDynamics': True})
    return changed


class _Rerun:
    """A configuration recomputed without saving, chunk by chunk, with its series joined."""

    def __init__(self, cfg, classes):
        self.cfg = cfg; self.classes = classes; self.quiet = type('Quiet', (), {'root': None})()
        self.r = simulate(self.quiet, dict(cfg), classes); self.n = 1
        self.time = list(self.r['time']); self.log = list(self.r['pairEvents']); self.passed = bool(self.r['passed'])
        self.species = [{'msd': list(s['msd']), 'bound': list(s['boundFraction']), 'complex': list(s['complexFraction']), 'present': list(s['present'])} for s in self.r['species']]

    def more(self):
        self.r = simulate(self.quiet, {'state': self.r['state']}, self.classes); self.n += 1
        self.time += self.r['time']; self.log += self.r['pairEvents']; self.passed = self.passed and bool(self.r['passed'])
        for t, s in zip(self.species, self.r['species']):
            t['msd'] += s['msd']; t['bound'] += s['boundFraction']; t['complex'] += s['complexFraction']; t['present'] += s['present']

    def at(self, T):
        """Outcomes at the last computed frame not after T."""
        k = max(0, int(np.searchsorted(np.array(self.time), T + 1e-12, side='right')) - 1); t = self.time[k]
        return {'label': self.cfg.get('label', ''), 'time': float(t), 'chunks': self.n, 'passed': self.passed,
                'events': {'pairBinds': sum(1 for e in self.log if e['kind'] == 'bind' and e['time'] <= t), 'pairReleases': sum(1 for e in self.log if e['kind'] == 'unbind' and e['time'] <= t),
                           **{k2: int(v) for k2, v in self.r['events'].items() if k2 in ('born', 'died', 'converted', 'crossings')}},
                'series': {'time': self.time[:k + 1], 'species': [{'name': m['name'], 'complex': s['complex'][:k + 1], 'msd': s['msd'][:k + 1], 'bound': s['bound'][:k + 1], 'present': s['present'][:k + 1]} for m, s in zip(self.r['species'], self.species)]},
                'species': [{'name': m['name'], 'structure': m['structure'], 'radiusNm': m['radiusNm'], 'particles': m['particles'], 'D': m['D'], 'apparentD': s['msd'][k] / (6 * t),
                             'boundFraction': s['bound'][k], 'complexFraction': s['complex'][k], 'complexes': int(round(s['complex'][k] * s['present'][k])), 'present': s['present'][k]} for m, s in zip(self.r['species'], self.species)]}


def _saved_config(service, p):
    if p.get('id'):
        return run_get(service, {'id': p['id']})['experiment']['config']
    return _configure(p.get('config') or {})


def compare(service, p, classes=None):
    """Rerun a baseline and a variant from their saved configurations for the same simulated time and report both.

    Nothing is read from the earlier live runs except their configurations, so the two results are matched in duration,
    geometry and engine version. When no changed input enters the dynamics the two reruns are identical by construction
    and the result says so: a different structure with the same radius and the same rules cannot change the outcome."""
    cfgs = [run_get(service, {'id': p.get(k)})['experiment']['config'] for k in ('baseline', 'variant')]
    contexts = [c.get('context') or HELA for c in cfgs]
    if contexts[0] != contexts[1]:
        raise EMError('These two runs were made in different cell contexts and cannot be compared as baseline and variant.')
    classes = geometry(service.root, contexts[0])[0] if classes is None else classes
    chunks = int(p.get('chunks', 4))
    if not 1 <= chunks <= 12:
        raise EMError('Compare between 1 and 12 chunks.')
    both = [_Rerun(c, classes) for c in cfgs]
    for side in both:
        for _ in range(chunks - 1):
            side.more()
    target = max(side.time[-1] for side in both)                    # the time step follows the fastest molecule, so one side may need more chunks
    for side in both:
        while side.time[-1] < target - 1e-12 and side.n < 16:
            side.more()
    common = min(side.time[-1] for side in both)
    sides = [side.at(common) for side in both]
    changed = _differences(*cfgs)
    dynamic = any(c['affectsDynamics'] for c in changed)
    frame = max(cfgs[0]['frameSeconds'], cfgs[1]['frameSeconds'])
    matched = bool(abs(sides[0]['time'] - sides[1]['time']) <= 2 * frame)
    return {'baseline': sides[0], 'variant': sides[1], 'changed': changed, 'identicalDynamics': not dynamic, 'matchedTime': matched, 'chunks': chunks, 'context': contexts[0],
            'note': ('The variant changes no input that enters the simulation (only names or structure files differ), so both reruns are identical. '
                     'A structure affects this engine only through the radius and the rules you set.') if not dynamic else
                    ('Both sides were rerun from their saved configurations' + (' and are compared at the same simulated time (within one frame).' if matched else '; their simulated times differ.') +
                     ' Differences come from the changed inputs and, where the seed or particle numbers changed, from sampling noise of single runs.'),
            'engine': {k: ENGINE[k] for k in ('id', 'name', 'version')}}


def replicates(service, p, classes=None):
    """The same experiment under several random seeds: how much of an outcome is the experiment and how much is chance.
    This is run-to-run variation of one simulated cell, not variation between cells."""
    cfg = _saved_config(service, p); n = int(p.get('seeds', 5)); chunks = int(p.get('chunks', 3))
    if not 2 <= n <= 8 or not 1 <= chunks <= 6:
        raise EMError('Choose 2 to 8 seeds and 1 to 6 chunks.')
    classes = geometry(service.root, cfg.get('context') or HELA)[0] if classes is None else classes
    runs_ = []
    for k in range(n):
        side = _Rerun({**cfg, 'seed': (cfg['seed'] + 7919 * k) % (2 ** 31 - 1)}, classes)
        for _ in range(chunks - 1):
            side.more()
        runs_.append(side)
    frames = min(len(r.time) for r in runs_); time_ = runs_[0].time[:frames]
    out = []
    for i, s in enumerate(runs_[0].r['species']):
        row = {'name': s['name']}
        for key in ('complex', 'bound', 'present', 'msd'):
            a = np.array([r.species[i][key][:frames] for r in runs_], float)
            row[key] = {'mean': a.mean(axis=0).tolist(), 'sd': a.std(axis=0, ddof=1).tolist(), 'min': a.min(axis=0).tolist(), 'max': a.max(axis=0).tolist(), 'final': a[:, -1].tolist()}
        out.append(row)
    return {'seeds': [r.cfg['seed'] for r in runs_], 'time': time_, 'species': out, 'chunks': chunks, 'passed': all(r.passed for r in runs_),
            'pairBinds': [sum(1 for e in r.log if e['kind'] == 'bind') for r in runs_],
            'note': 'Each seed is a full rerun of the saved configuration. The spread is the sampling noise of this stochastic simulation in one fixed geometry; it is not a measurement of cell-to-cell variation.'}


SWEEPABLE = {'slowdown': ('Cytoplasmic slowdown', '×'), 'temperature': ('Temperature', 'K'), 'radiusNm': ('Hydrodynamic radius', 'nm'), 'particles': ('Copies released', 'copies'), 'pBind': ('Binding probability per encounter', ''),
             'koff': ('Release rate', 's⁻¹'), 'decay': ('Decay rate', 's⁻¹'), 'synthesisRate': ('Synthesis rate', 'copies s⁻¹'), 'permeabilityUmS': ('Boundary permeability', 'µm s⁻¹'),
             'pair.rate': ('Pair binding rate', 's⁻¹'), 'pair.reachNm': ('Pair reach', 'nm'), 'pair.koff': ('Complex dissociation rate', 's⁻¹'), 'reaction.rate': ('Conversion rate', 's⁻¹')}


def _with(cfg, key, index, value):
    """A copy of a configuration with one input replaced."""
    c = json.loads(json.dumps(cfg))
    if key in ('slowdown', 'temperature'):
        c[key] = value
    elif key.startswith('pair.'):
        c['pairs'][index][key[5:]] = value
    elif key == 'reaction.rate':
        c['reactions'][index]['rate'] = value
    elif key == 'synthesisRate':
        c['species'][index]['synthesis'] = {**(c['species'][index]['synthesis'] or {'compartment': c['species'][index]['release'].get('compartment', 'cytosol')}), 'rate': value}
    elif key == 'permeabilityUmS':
        c['species'][index]['exchange'][0]['permeabilityUmS'] = value
    else:
        c['species'][index][key] = value
        if key == 'particles':
            c['species'][index]['capacity'] = max(c['species'][index]['capacity'], int(value))
    return c


def sweep(service, p, classes=None):
    """One input varied over a few values, each a full rerun to the same number of chunks, outcomes read at a common time."""
    cfg = _saved_config(service, p); key = p.get('parameter'); index = int(p.get('index', 0)); values = p.get('values') or []; chunks = int(p.get('chunks', 2))
    if key not in SWEEPABLE or not 2 <= len(values) <= 8 or not 1 <= chunks <= 4:
        raise EMError('Sweep one supported input over 2 to 8 values, for 1 to 4 chunks.')
    classes = geometry(service.root, cfg.get('context') or HELA)[0] if classes is None else classes
    sides = []
    for v in values:
        try:
            side = _Rerun(_configure(_with(cfg, key, index, float(v))), classes)
        except (IndexError, KeyError, TypeError):
            raise EMError('That input does not exist in this experiment.')
        for _ in range(chunks - 1):
            side.more()
        sides.append(side)
    common = min(s.time[-1] for s in sides)
    return {'parameter': key, 'label': SWEEPABLE[key][0], 'unit': SWEEPABLE[key][1], 'index': index, 'values': [float(v) for v in values], 'time': common, 'rows': [{'value': float(v), **s.at(common)} for v, s in zip(values, sides)],
            'note': 'Single runs with the saved seed: neighbouring values differ by sampling noise as well as by the input. Time steps follow the fastest molecule, so outcomes are read at the last frame every run reached.'}


def crowding(service, p):
    """Benchmarked capability: a tracer diffusing among fixed spherical crowders in a periodic box.

    The long-time diffusion coefficient is measured from the mean squared displacement and compared with Maxwell's
    obstruction result for fixed spheres, D/D₀ = 1/(1 + φ/2), where φ is the volume fraction the tracer centre cannot
    enter. The measured ratio can be handed to the whole-cell engine as its slowdown factor."""
    try:
        phi = float(p.get('volumeFraction', 0.1)); rc = float(p.get('crowderRadiusNm', 5.0)); rt = float(p.get('tracerRadiusNm', 2.8)); seed = int(p.get('seed', 7))
    except (TypeError, ValueError):
        raise EMError('Volume fraction, radii and seed must be numbers.')
    if not 0.0 < phi <= 0.25 or not 1.0 <= rc <= 100.0 or not 0.2 <= rt <= 60.0:
        raise EMError('Choose a crowder volume fraction up to 0.25, crowder radius 1–100 nm and tracer radius 0.2–60 nm.')
    rng = np.random.default_rng([seed, 31337]); ex = rc + rt                    # exclusion radius for the tracer centre, nm
    count = 160; side = (count * 4 / 3 * math.pi * rc ** 3 / phi) ** (1 / 3)      # box that holds `count` crowders at this fraction, nm
    centres = np.empty((0, 3))
    for _ in range(200000):                                                 # random sequential addition without overlap
        c = rng.random(3) * side
        if not len(centres) or (((np.abs(centres - c) + side / 2) % side - side / 2) ** 2).sum(axis=1).min() >= (2 * rc) ** 2:
            centres = np.vstack([centres, c])
            if len(centres) == count:
                break
    if len(centres) < count:
        raise EMError('Could not place the crowders without overlap; lower the volume fraction.')
    sigma = 0.15 * ex; tracers = 1500; warm, lag, windows = 800, 1000, 3; steps = warm + lag * windows
    free = lambda pts: ((((pts[:, None, :] - centres[None, :, :]) + side / 2) % side - side / 2) ** 2).sum(axis=2).min(axis=1) >= ex ** 2
    x = np.empty((0, 3))
    while len(x) < tracers:
        cand = rng.random((tracers, 3)) * side; x = np.vstack([x, cand[free(cand)]])
    x = x[:tracers]; mark = None; per_window = []
    for k in range(1, steps + 1):
        trial = x + rng.standard_normal(x.shape) * sigma
        ok = free(trial); x[ok] = trial[ok]
        if k >= warm and (k - warm) % lag == 0:                             # displacement over each window after the transient
            if mark is not None:
                per_window.append(float(((x - mark) ** 2).sum(axis=1).mean()) / (3 * sigma ** 2 * lag))
            mark = x.copy()
    ratio = float(np.mean(per_window)); se = float(np.std(per_window, ddof=1) / math.sqrt(len(per_window)))     # per-step MSD of a free walker is 3σ²
    excluded = min(1.0, len(centres) * 4 / 3 * math.pi * ex ** 3 / side ** 3)
    theory = 1 / (1 + excluded / 2)
    tol = max(0.04, 3 * se)
    return {'volumeFraction': phi, 'crowderRadiusNm': rc, 'tracerRadiusNm': rt, 'excludedFraction': excluded, 'crowders': count, 'boxNm': side, 'tracers': tracers, 'steps': steps, 'seed': seed,
            'relativeD': ratio, 'standardError': se, 'theory': theory, 'difference': ratio - theory, 'slowdown': 1 / ratio,
            'check': {'name': 'Crowding against Maxwell obstruction', 'passed': bool(abs(ratio - theory) < tol), 'threshold': f'|difference| < {tol:.3f}', 'detail': 'Long-time D/D₀ of a tracer centre among fixed spheres, from its mean squared displacement over three windows after the initial transient.'},
            'evidence': {'category': 'B', 'statement': 'Hard, immobile, non-overlapping spherical crowders in a periodic box. Real cytoplasm is polydisperse, mobile and interacting; this capability gives the obstruction effect only.'},
            'handover': {'quantity': 'slowdown', 'unit': '×', 'value': 1 / ratio, 'to': ENGINE['id'], 'note': 'Multiply the whole-cell slowdown by this factor to add obstruction by crowders of this size and fraction. Hydrodynamic and binding effects of crowding are not included.'}}


def dispatch(service, action, p):
    p = p or {}
    if action == 'cell_em_catalog': return catalog(service)
    if action == 'cell_em_install': return install(service, p)
    if action == 'cell_em_volume': return volume(service, p)
    if action == 'cell_em_simulate': return simulate(service, p)
    if action == 'cell_em_structure': return structure(service, p)
    if action == 'cell_em_paint': return paint(service, p)
    if action == 'cell_em_runs': return runs(service)
    if action == 'cell_em_run_get': return run_get(service, p)
    if action == 'cell_em_compare': return compare(service, p)
    if action == 'cell_em_replicates': return replicates(service, p)
    if action == 'cell_em_sweep': return sweep(service, p)
    if action == 'cell_em_crowding': return crowding(service, p)
    if action == 'cell_em_region': return region(service, p)
    if action == 'cell_em_registration': return registration(service)
    raise ValueError('Unsupported cell EM action.')
