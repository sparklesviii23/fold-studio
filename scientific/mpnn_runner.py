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
 constraints=request.get('constraints');masks={}
 for ch,p in proteins.items():
  if constraints:
   positions=constraints['residues'][ch]
   if len(positions)!=len(p) or [r['number'] for r in positions]!=np.asarray(p.residue_index).tolist() or ''.join(r['aminoAcid'] for r in positions)!=expected[ch]:raise ValueError('Source residue constraint correspondence differs.')
   masks[ch]=np.asarray([r['design'] for r in positions],dtype=bool)
   if ch not in request['designChains'] and masks[ch].any():raise ValueError('Fixed context cannot acquire design positions.')
  else:masks[ch]=np.full(len(p),ch in request['designChains'],dtype=bool)
 proteins={ch:p.replace(flags=jnp.asarray(masks[ch].astype(np.uint8)*int(ResidueFlags.DESIGN))) for ch,p in proteins.items()}
 weights=BASE/'vendor/bindcraft2/bindcraft/weights/proteinmpnn/weights_neutral'
 checkpoint=pathlib.Path(mpnn_variant_directory(str(weights),request['variant']))/'v_48_020.npz'
 model=ProteinMPNNSequenceModel(str(weights),variant=request['variant'],key=jax.random.PRNGKey(request['seed']),temperature=request['temperature'],length_bucket_size=1,**({'multi_chain_binders':tuple(tuple(group) for group in constraints['tiedChains']),'omitted_amino_acids':constraints['omitAminoAcids'],'amino_acid_bias':constraints['aminoAcidBias']} if constraints else {}))
 loaded=time.perf_counter();print('Running full upstream encoder and autoregressive decoder; compilation may take time.',flush=True)
 if constraints and any('excluded' in r or 'preferred' in r for rows in constraints['residues'].values() for r in rows):
  from bindcraft.sequence_optimization import OMITTED_AMINO_ACID_LOGIT
  positions=[r for ch in sorted(proteins) for r in constraints['residues'][ch]]
  bias=jnp.broadcast_to(model.redesigned_amino_acid_bias,(len(positions),20))
  for i,r in enumerate(positions):
   for aa in r.get('preferred',''):bias=bias.at[i,AMINO_ACIDS.index(aa)].add(1.)
   for aa in r.get('excluded',''):bias=bias.at[i,AMINO_ACIDS.index(aa)].set(OMITTED_AMINO_ACID_LOGIT)
  model.redesigned_amino_acid_bias=bias
 predictions=model.predict_candidates({'source':proteins},candidate_count=request['count']);results=[]
 for prediction in predictions:
  output=prediction['source'];chains={ch:sequence(p) for ch,p in output.protein_complex.items()}
  for ch,p in output.protein_complex.items():
   if any(actual!=original for actual,original,editable in zip(chains[ch],expected[ch],masks[ch]) if not editable):raise ValueError('Fixed source residue sequence changed.')
   if constraints and any(aa in constraints['omitAminoAcids'] for aa,editable in zip(chains[ch],masks[ch]) if editable):raise ValueError('Omitted amino acid appeared at a redesigned residue.')
   if constraints and any(aa in r.get('excluded','') for aa,r in zip(chains[ch],constraints['residues'][ch]) if r['design']):raise ValueError('Position-specific excluded amino acid appeared.')
   if not np.array_equal(before[ch],np.asarray(p.atoms)):raise ValueError('Source coordinates changed.')
  if constraints:
   for group in constraints['tiedChains']:
    if len({chains[ch] for ch in group})!=1:raise ValueError('Tied chain sequences differ.')
  metrics={k:float(v) for k,v in output.metrics.items()}
  if not all(np.isfinite(v) for v in metrics.values()):raise ValueError('Nonfinite model output.')
  results.append({'chains':chains,'metrics':metrics})
 finish=time.perf_counter()
 return {'schemaVersion':1,'engine':'ProteinMPNN via pinned BindCraft2','execution':backend,'devices':[str(d) for d in jax.devices()],'jax':jax.__version__,'checkpointSha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),'sourceSha256':request['sha256'],'settings':request,'candidates':results,'timing':{'loadSeconds':loaded-start,'inferenceIncludingCompilationSeconds':finish-loaded,'totalSeconds':finish-start},'peakProcessRSSBytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'limitations':['Fixed-backbone sequence redesign only; no new coordinates, folding validation or binding prediction.','Scores are upstream sequence-model metrics, not affinity or experimental validation.','Backend is reported explicitly; this output alone does not establish cross-backend parity.']}
if __name__=='__main__':
 request=json.loads(pathlib.Path(sys.argv[1]).read_text());result=execute(request);pathlib.Path(sys.argv[2]).write_text(json.dumps(result,indent=2,allow_nan=False));print('ProteinMPNN inference finished.',flush=True)
