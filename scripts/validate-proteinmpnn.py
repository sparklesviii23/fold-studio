"""Real checkpoint inference, direct-upstream parity, fixed context and repeatability."""
import hashlib,json,os,pathlib,sys,time
os.environ['JAX_PLATFORMS']='cpu';sys.dont_write_bytecode=True
BASE=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(BASE/'scientific'),str(BASE/'vendor/bindcraft2')]
from mpnn_runner import execute
from bindcraft.protein import Protein,ResidueFlags,AMINO_ACIDS
from bindcraft.proteinmpnn import ProteinMPNNSequenceModel
import jax,jax.numpy as jnp,numpy as np
report={'scope':'Full-model upstream ProteinMPNN integration parity on CPU; not binding/structure prediction validation','cases':[]}
for name,variant in [('hPDL1','neutral'),('hIL2R_beta_gamma','negative')]:
 path=BASE/f'vendor/bindcraft2/settings/target/structures/{name}.pdb';proteins=Protein.from_structure(str(path));seq=lambda p:''.join(AMINO_ACIDS[int(i)] for i in np.asarray(p.sequence).argmax(-1));chains=sorted(proteins);design=[chains[0]]
 request={'input':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'sequences':{ch:seq(p) for ch,p in proteins.items()},'count':2,'seed':2718,'temperature':0.1,'variant':variant,'designChains':design}
 result=execute(request)
 flagged={ch:p.replace(flags=jnp.full(p.flags.shape,int(ResidueFlags.DESIGN) if ch in design else 0,dtype=jnp.uint8)) for ch,p in proteins.items()}
 direct=ProteinMPNNSequenceModel(str(BASE/'vendor/bindcraft2/bindcraft/weights/proteinmpnn/weights_neutral'),variant=variant,key=jax.random.PRNGKey(2718),temperature=.1,length_bucket_size=1)
 outputs=direct.predict_candidates({'reference':flagged},candidate_count=2)
 for actual,reference in zip(result['candidates'],outputs):
  expected=reference['reference'];assert actual['chains']=={ch:seq(p) for ch,p in expected.protein_complex.items()}
  for k,v in expected.metrics.items():assert actual['metrics'][k]==float(v)
  for ch in chains:
   if ch not in design:assert actual['chains'][ch]==request['sequences'][ch]
 # New model same seed yields identical samples; raw metrics must also match.
 again=execute(request);assert again['candidates']==result['candidates']
 report['cases'].append({'fixture':path.name,'variant':variant,'designChains':design,'fixedContextChains':chains[1:],'residues':sum(len(p) for p in proteins.values()),'candidates':result['candidates'],'checkpointSha256':result['checkpointSha256'],'timing':result['timing'],'peakProcessRSSBytes':result['peakProcessRSSBytes'],'devices':result['devices'],'directUpstreamParity':'exact','freshModelRepeatability':'exact'})
report['state']='passed';(BASE/'reports/proteinmpnn-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
