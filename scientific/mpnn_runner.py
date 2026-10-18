"""Isolated authentic upstream ProteinMPNN inference. No model approximations."""
import hashlib,json,os,pathlib,resource,sys,time
os.environ['JAX_PLATFORMS']='cpu'
os.environ['XLA_PYTHON_CLIENT_PREALLOCATE']='false'
sys.dont_write_bytecode=True
BASE=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'vendor/bindcraft2'))

def execute(request,backend='cpu'):
 if backend not in ('cpu','metal'):raise ValueError('Unknown execution backend.')
 os.environ['JAX_PLATFORMS']=backend
 import jax,jax.numpy as jnp,numpy as np
 from bindcraft.protein import Protein,ResidueFlags,AMINO_ACIDS
 from bindcraft.proteinmpnn import ProteinMPNNSequenceModel
 from bindcraft.model_weights import mpnn_variant_directory
 start=time.perf_counter();print('Loading source backbone and ProteinMPNN checkpoint on '+backend+'.',flush=True)
 if any(d.platform.lower()!=backend for d in jax.devices()):raise RuntimeError('Requested backend was not used.')
 path=pathlib.Path(request['input']);raw=path.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=request['sha256']:raise ValueError('Input checksum changed.')
 proteins=Protein.from_structure(str(path));expected=request['sequences']
 def sequence(p):return ''.join(AMINO_ACIDS[int(i)] for i in np.asarray(p.sequence).argmax(-1))
 if set(proteins)!=set(expected) or any(sequence(p)!=expected[ch] for ch,p in proteins.items()):raise ValueError('Upstream/source sequence correspondence differs.')
 before={ch:np.asarray(p.atoms).copy() for ch,p in proteins.items()}
 proteins={ch:p.replace(flags=jnp.full(p.flags.shape,int(ResidueFlags.DESIGN) if ch in request['designChains'] else 0,dtype=jnp.uint8)) for ch,p in proteins.items()}
 weights=BASE/'vendor/bindcraft2/bindcraft/weights/proteinmpnn/weights_neutral'
 checkpoint=pathlib.Path(mpnn_variant_directory(str(weights),request['variant']))/'v_48_020.npz'
 model=ProteinMPNNSequenceModel(str(weights),variant=request['variant'],key=jax.random.PRNGKey(request['seed']),temperature=request['temperature'],length_bucket_size=1)
 loaded=time.perf_counter();print('Running full upstream encoder and autoregressive decoder; compilation may take time.',flush=True)
 predictions=model.predict_candidates({'source':proteins},candidate_count=request['count']);results=[]
 for prediction in predictions:
  output=prediction['source'];chains={ch:sequence(p) for ch,p in output.protein_complex.items()}
  for ch,p in output.protein_complex.items():
   if ch not in request['designChains'] and chains[ch]!=expected[ch]:raise ValueError('Fixed context sequence changed.')
   if not np.array_equal(before[ch],np.asarray(p.atoms)):raise ValueError('Source coordinates changed.')
  metrics={k:float(v) for k,v in output.metrics.items()}
  if not all(np.isfinite(v) for v in metrics.values()):raise ValueError('Nonfinite model output.')
  results.append({'chains':chains,'metrics':metrics})
 finish=time.perf_counter()
 return {'schemaVersion':1,'engine':'ProteinMPNN via pinned BindCraft2','execution':backend,'devices':[str(d) for d in jax.devices()],'jax':jax.__version__,'checkpointSha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),'sourceSha256':request['sha256'],'settings':request,'candidates':results,'timing':{'loadSeconds':loaded-start,'inferenceIncludingCompilationSeconds':finish-loaded,'totalSeconds':finish-start},'peakProcessRSSBytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'limitations':['Fixed-backbone sequence redesign only; no new coordinates, folding validation or binding prediction.','Scores are upstream sequence-model metrics, not affinity or experimental validation.','Backend is reported explicitly; this output alone does not establish cross-backend parity.']}
if __name__=='__main__':
 request=json.loads(pathlib.Path(sys.argv[1]).read_text());result=execute(request);pathlib.Path(sys.argv[2]).write_text(json.dumps(result,indent=2,allow_nan=False));print('ProteinMPNN inference finished.',flush=True)
