"""Trained-model exact upstream parity for site masks, chain ties and log biases.

Duplicated structural fragments are technical QA geometry, not a biological dimer.
"""
import argparse, hashlib, json, os, pathlib, subprocess, sys, time, zipfile
os.environ['JAX_PLATFORMS'] = 'cpu'
sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--engine-root', default=str(ROOT))
parser.add_argument('--directory', default=str(ROOT.parent/'validation/mpnn-residue-ties'))
parser.add_argument('--report', default=str(ROOT/'reports/mpnn-constraints-validation.json'))
args=parser.parse_args()
ENGINE=pathlib.Path(args.engine_root).resolve()
app=ENGINE.parents[1] if ENGINE.name=='Resources' and ENGINE.parent.name=='Contents' else None
def verify_seal():
    if app:subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True)
verify_seal()
sys.path[:0] = [str(ENGINE/'scientific'), str(ENGINE/'vendor/bindcraft2')]
import jax
import jax.numpy as jnp
import numpy as np
import intelligence as mi
from mpnn_constraints import prepare
from mpnn_runner import execute
from bindcraft.protein import Protein, ResidueFlags, AMINO_ACIDS
from bindcraft.proteinmpnn import ProteinMPNNSequenceModel

folder = pathlib.Path(args.directory).resolve()
folder.mkdir(parents=True, exist_ok=True)
source = ENGINE/'vendor/bindcraft2/settings/target/structures/hPDL1.pdb'
numbers, selected = [], []
for line in source.read_text().splitlines():
    if line.startswith('ATOM  ') and line[21] == 'A':
        number = int(line[22:26])
        if number not in numbers:
            numbers.append(number)
        if numbers.index(number) < 12:
            selected.append(line)
text = 'REMARK Duplicated technical target fragments, not biological assembly.\n'
text += '\n'.join(selected) + '\nTER\n'
for line in selected:
    text += line[:21] + 'B' + line[22:30] + f'{float(line[30:38])+50:8.3f}' + line[38:] + '\n'
text += 'END\n'
path = folder/'TECHNICAL_duplicated_fragments.pdb'
path.write_text(text)
st = mi.parse_structure(text, 'pdb')
seq = lambda p: ''.join(AMINO_ACIDS[int(i)] for i in np.asarray(p.sequence).argmax(-1))
proteins = Protein.from_structure(str(path))
sites = [r['id'] for r in st['residues'] if r['num'] in numbers[:5]]
constraints = prepare(st, ['A','B'], {'designResidues': sites, 'tiedChains': [['A','B']],
                                    'omitAminoAcids': 'C', 'aminoAcidBias': {'Y': .5, 'W': -.25}})
request = {'input': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
           'sequences': {ch: seq(p) for ch,p in proteins.items()}, 'designChains': ['A','B'],
           'constraints': constraints, 'count': 2, 'seed': 2718, 'temperature': .1, 'variant': 'neutral'}
actual = execute(request)
# Build the original decoder directly from source residue numbers, independently
# of the adapter's saved design-mask arrays.
flagged = {ch: p.replace(flags=jnp.asarray([int(ResidueFlags.DESIGN) if int(n) in numbers[:5] else 0
                                           for n in p.residue_index], dtype=jnp.uint8))
           for ch,p in proteins.items()}
model = ProteinMPNNSequenceModel(str(ENGINE/'vendor/bindcraft2/bindcraft/weights/proteinmpnn/weights_neutral'),
                                key=jax.random.PRNGKey(2718), temperature=.1, length_bucket_size=1,
                                multi_chain_binders=(('A','B'),), omitted_amino_acids='C',
                                amino_acid_bias={'Y': .5, 'W': -.25})
reference = model.predict_candidates({'reference': flagged}, candidate_count=2)
for output, expected in zip(actual['candidates'], reference):
    expected = expected['reference']
    assert output['chains'] == {ch: seq(p) for ch,p in expected.protein_complex.items()}
    assert output['metrics'] == {k: float(v) for k,v in expected.metrics.items()}
    assert output['chains']['A'] == output['chains']['B']
    for ch, sequence in output['chains'].items():
        assert sequence[5:] == request['sequences'][ch][5:]
        assert 'C' not in sequence[:5]
assert execute(request)['candidates'] == actual['candidates']
assert hashlib.sha256(path.read_bytes()).hexdigest() == request['sha256']
from worker import Service
service = Service(folder/'library')
statefile = folder/'shared-job.json'
if statefile.exists():
    state = json.loads(statefile.read_text())
else:
    project = service.project_create({'name': 'Constrained ProteinMPNN technical QA'})
    record = service.import_structure({'projectId': project['id'], 'path': str(path)})
    if not app:os.environ['FOLD_BINDCRAFT_PYTHON'] = os.path.abspath(sys.executable)
    job = service.dispatch('mpnn_start', {'projectId': project['id'], 'structureId': record['id'],
                                          'designChains': ['A','B'], 'designResidues': sites,
                                          'tiedChains': [['A','B']], 'omitAminoAcids': 'C',
                                          'aminoAcidBias': {'Y': .5, 'W': -.25},
                                          'count': 2, 'seed': 2718, 'temperature': .1})
    state = {'projectId': project['id'], 'recordId': record['id'], 'jobId': job['id']}
    statefile.write_text(json.dumps(state, indent=2)+'\n')
deadline = time.monotonic()+180
while True:
    job = service.job(state['jobId'])
    if job['state'] not in ('queued','running'):
        break
    if time.monotonic()>deadline:
        raise TimeoutError('Shared job remains active; inspect recorded job instead of resubmitting.')
    time.sleep(1)
assert job['state']=='completed', job
if app:assert job['data']['runtime']==str(ENGINE/'runtime/bin/python3.12')
assert len(job['data']['outputs'])==4
records = {r['id']:r for r in service.library({})['records']}
for index, id in enumerate(job['data']['outputs']):
    data = records[id]['data']
    assert data['sequence']==actual['candidates'][index//2]['chains'][data['chain']]
    assert data['constraints']==constraints
archive = folder/'constrained-project.zip'
service.export_project({'id':state['projectId'],'path':str(archive)})
with zipfile.ZipFile(archive) as z:
    saved_request = json.loads(z.read('jobs/'+job['id']+'/request.json'))
    assert saved_request['constraints']==constraints
    assert hashlib.sha256(z.read('jobs/'+job['id']+'/input.pdb')).hexdigest()==request['sha256']
service.db.close()
verify_seal()
report = {'state': 'passed', 'scope': 'Full trained upstream CPU ProteinMPNN constrained decoder parity on 24-residue technical geometry, not a design/folding/binding validation.',
          'engineRoot':str(ENGINE), 'signatureAfterInference':'passed' if app else 'not_applicable',
          'source': str(path), 'sourceSha256': request['sha256'], 'constraints': constraints,
          'directUpstreamParity': 'exact sequences and scores', 'freshModelRepeatability': 'exact',
          'fixedPositions': 'unchanged', 'tiedSequences': 'identical', 'omissions': 'enforced only at editable sites',
          'sharedJobId': job['id'], 'savedSequenceRecords':len(job['data']['outputs']),
          'projectArchiveConstraintsAndSource': 'passed', 'result': actual}
pathlib.Path(args.report).write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('result','constraints')}, indent=2))
