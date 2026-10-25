"""Method-specific scientific contracts; trained inference occurs only on Modal.

No scores are synthesized when a runtime or checkpoint is missing. Upstream source
is unmodified and content checked before importing pickle-based trained models.
"""
import contextlib,hashlib,json,math,os,pathlib,re,subprocess,sys,tempfile,urllib.request
ROOT=pathlib.Path(__file__).parent
MANIFEST=json.loads((ROOT/'editcraft_assets.json').read_text())
OPERATIONS={'rs3_activity':'rs3','bedict_per_base':'bedict','pridict2_design':'pridict2'}
VENV={'rs3':'/opt/rs3-runtime/bin/python','bedict':'/opt/bedict-runtime/bin/python','pridict2':'/opt/pridict2-runtime/bin/python'}

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
def manifest_sha():return hashlib.sha256(canonical(MANIFEST).encode()).hexdigest()
def cloud_only():
 if os.environ.get('FOLD_ENGINE_ROLE')!='editcraft_cloud':raise RuntimeError('Trained scientific models execute on the EditCraft Modal service only.')
def model_root():return pathlib.Path('/research/models/editcraft')
def blob_sha(raw):return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
def verify_bytes(raw,asset):
 if len(raw)!=asset['bytes'] or blob_sha(raw)!=asset['gitBlobSha1']:raise ValueError('Pinned upstream source or checkpoint checksum mismatch.')
 return hashlib.sha256(raw).hexdigest()

def verify_model(model,root=None):
 folder=(root or model_root())/model;spec=MANIFEST['models'][model];receipt_path=folder/'receipt.json'
 if not receipt_path.is_file():raise ValueError('Model is not installed. Approve the separate cloud preparation first.')
 receipt=json.loads(receipt_path.read_text())
 if receipt.get('manifestSha256')!=manifest_sha():raise ValueError('Model preparation belongs to another pinned manifest.')
 hashes={}
 for asset in spec['assets']:
  path=folder/'source'/asset['path']
  if not path.is_file() or path.is_symlink():raise ValueError('Pinned model asset is missing or linked outside its store.')
  actual=verify_bytes(path.read_bytes(),asset)
  if receipt.get('files',{}).get(asset['path'])!=actual:raise ValueError('Model receipt checksum mismatch.')
  hashes[asset['path']]=actual
 return {'model':model,'repository':spec['repository'],'revision':spec['revision'],'license':spec['license'],'manifestSha256':manifest_sha(),'files':hashes,'scientificBenchmarkComplete':False}

def install_models(models,root=None):
 cloud_only()
 if not isinstance(models,list) or not models or len(set(models))!=len(models) or set(models)-set(VENV):raise ValueError('Select explicit supported model identifiers.')
 base=root or model_root();receipts={}
 for model in models:
  folder=base/model;spec=MANIFEST['models'][model];hashes={}
  for asset in spec['assets']:
   path=folder/'source'/asset['path'];path.parent.mkdir(parents=True,exist_ok=True)
   if path.is_file():
    try:hashes[asset['path']]=verify_bytes(path.read_bytes(),asset);continue
    except ValueError:raise ValueError('Existing model asset differs; preserve it for inspection rather than overwrite it.') from None
   url='https://raw.githubusercontent.com/'+spec['repository']+'/'+spec['revision']+'/'+asset['path']
   with urllib.request.urlopen(url,timeout=60) as response:raw=response.read(asset['bytes']+1)
   hashes[asset['path']]=verify_bytes(raw,asset)
   tmp=path.with_suffix(path.suffix+'.pending');tmp.write_bytes(raw);tmp.replace(path)
  receipt={'manifestSha256':manifest_sha(),'files':hashes,'installed':True,'executed':False,'scientificBenchmarkComplete':False}
  folder.mkdir(parents=True,exist_ok=True);tmp=folder/'receipt.pending';tmp.write_text(canonical(receipt));tmp.replace(folder/'receipt.json')
  receipts[model]=verify_model(model,base)
 return receipts

def dna(value,length=None):
 if not isinstance(value,str):raise ValueError('DNA context must be text.')
 s=re.sub(r'\s+','',value).upper()
 if not s or set(s)-set('ACGT') or (length and len(s)!=length):raise ValueError('Provide unambiguous DNA with the required context length.')
 return s

def validate_input(operation,p):
 if not isinstance(p,dict):raise ValueError('Model parameters must be an object.')
 out=dict(p)
 if operation in ('rs3_activity','bedict_per_base'):
  rows=p.get('sequences')
  if not isinstance(rows,list) or not 1<=len(rows)<=64:raise ValueError('Provide 1–64 explicitly identified sequence contexts.')
  cleaned=[];ids=set()
  for row in rows:
   if not isinstance(row,dict) or not re.fullmatch('[A-Za-z0-9_.-]{1,60}',str(row.get('id',''))) or row['id'] in ids:raise ValueError('Sequence identifiers must be unique, bounded names.')
   ids.add(row['id']);s=dna(row.get('sequence'),30 if operation=='rs3_activity' else 20)
   if operation=='rs3_activity' and s[25:27]!='GG':raise ValueError('Rule Set 3 requires the SpCas9 NGG PAM at positions 25–27 of its 30-mer context.')
   if operation=='bedict_per_base' and ('A' if p.get('editor')=='ABEmax' else 'C') not in s:raise ValueError('Each BE-DICT sequence must contain a base supported by its editor.')
   cleaned.append({'id':row['id'],'sequence':s})
  out['sequences']=cleaned
  if operation=='rs3_activity':
   if p.get('tracrRNA') not in ('Hsu2013','Chen2013') or p.get('nuclease')!='SpCas9':raise ValueError('Rule Set 3 sequence model supports SpCas9 and the Hsu2013 or Chen2013 tracrRNA only.')
  elif p.get('editor') not in ('ABEmax','BE4max'):raise ValueError('This BE-DICT adapter supports the complete five-run ABEmax or BE4max ensemble only.')
 elif operation=='pridict2_design':
  s=str(p.get('editSequence','')).upper()
  match=re.fullmatch(r'([ACGT]{99,500})\(([ACGT]{1,40}/[ACGT]{1,40}|\+[ACGT]{1,40}|-[ACGT]{1,40})\)([ACGT]{99,500})',s)
  if not match:raise ValueError('PRIDICT2 needs one explicit edit and 99–500 unambiguous bases on each side.')
  edit=match[2]
  if '/' in edit:
   ref,alt=edit.split('/')
   if len(ref)!=len(alt) or ref[0]==alt[0] or ref[-1]==alt[-1]:raise ValueError('Use equal-length differing alleles with unchanged flanking bases outside the edit brackets, as required by upstream PRIDICT2.')
  if p.get('cellContext') not in ('HEK','K562'):raise ValueError('Inspect the published HEK or K562 model context; other cells are unsupported.')
  if p.get('folds')!=5:raise ValueError('This reproducible PRIDICT2 adapter requires all five folds of both upstream model groups.')
  out['editSequence']=s
 else:raise ValueError('Unknown trained scientific operation.')
 return out

def run_external(operation,p):
 cloud_only();p=validate_input(operation,p);model=OPERATIONS[operation];receipt=verify_model(model)
 python=VENV[model]
 if not pathlib.Path(python).is_file():raise ValueError('The isolated model runtime is unavailable; no substitute model was run.')
 with tempfile.TemporaryDirectory(prefix='editcraft-model-') as tmp:
  folder=pathlib.Path(tmp);(folder/'input.json').write_text(canonical({'operation':operation,'parameters':p}))
  # Parent scientific process owns this child's process group and hard deadline.
  logroot=pathlib.Path(os.environ.get('FOLD_EDITCRAFT_JOB_DIR',tmp));logroot.mkdir(parents=True,exist_ok=True)
  with (logroot/(operation+'.private.log')).open('w') as log:
   run=subprocess.run([python,'-B',str(ROOT/'editcraft_models.py'),'--execute',str(folder)],stdout=log,stderr=log,env={**os.environ,'OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','CUDA_VISIBLE_DEVICES':'','MPLBACKEND':'Agg'})
  if run.returncode or not (folder/'output.json').is_file():raise RuntimeError('The pinned model calculation failed. No predicted value is available; inspect its recorded scientific input requirements.')
  raw=(folder/'output.json').read_text()
  if len(raw)>3*1024**2:raise ValueError('Model result exceeds bounded transfer; no partial output was imported.')
  result=json.loads(raw)
 return {**result,'provenance':receipt,'evidence':'computational_prediction'}

def infer_rs3(p,source):
 sys.path.insert(0,str(source))
 from rs3.seq import predict_seq
 values=predict_seq([r['sequence'] for r in p['sequences']],sequence_tracr=p['tracrRNA'],n_jobs=1)
 if len(values)!=len(p['sequences']) or any(not math.isfinite(float(v)) for v in values):raise ValueError('Rule Set 3 returned invalid output dimensions or nonfinite predictions.')
 return {'method':'Rule Set 3 sequence-only','tracrRNA':p['tracrRNA'],'nuclease':'SpCas9','rows':[{'id':r['id'],'context30mer':r['sequence'],'predictedActivity':float(v)} for r,v in zip(p['sequences'],values)],'endpoint':'sequence-based sgRNA activity score','units':'upstream model score (not a probability or editing percentage)','scope':'SpCas9 knockout sequence model. No endogenous target features, genomic off-target search, functional validation or editing efficiency inferred.'}

def infer_bedict(p,source):
 sys.path.insert(0,str(source));os.chdir(source/'criscas')
 import pandas as pd,torch
 from criscas.predict_model import BEDICT_CriscasModel
 torch.set_num_threads(2);model=BEDICT_CriscasModel(p['editor'],torch.device('cpu'))
 df=pd.DataFrame([{'ID':r['id'],'seq':r['sequence']} for r in p['sequences']]);raw,_=model.predict_from_dataframe(df,batch_size=64)
 grouped=model.select_prediction(raw.copy(),'mean');rows=[];sequences={r['id']:r['sequence'] for r in p['sequences']}
 expected={(r['id'],i) for r in p['sequences'] for i,b in enumerate(r['sequence']) if b==('A' if p['editor']=='ABEmax' else 'C')};seen=set()
 for _,row in grouped.iterrows():
  id=str(row['id']);pos=int(row['base_pos']);key=(id,pos)
  if key not in expected or key in seen:raise ValueError('BE-DICT returned an unexpected or duplicate base coordinate.')
  seen.add(key);runs=raw[(raw['id']==id)&(raw['base_pos']==pos)]
  if set(runs['run_id'])!={'run_'+str(i) for i in range(5)} or len(runs)!=5:raise ValueError('Incomplete BE-DICT ensemble.')
  probs=[float(row['prob_score_class'+str(i)]) for i in range(2)]
  if any(not math.isfinite(v) or not 0<=v<=1 for v in probs) or abs(sum(probs)-1)>1e-5:raise ValueError('Invalid BE-DICT class probabilities.')
  rows.append({'id':id,'position':pos+1,'referenceBase':sequences[id][pos],'modelEditedClassProbability':probs[1],'modelUneditedClassProbability':probs[0],'runProbabilities':[{'run':str(r['run_id']),'editedClassProbability':float(r['prob_score_class1'])} for _,r in runs.iterrows()]})
 if seen!=expected:raise ValueError('BE-DICT omitted supported target bases.')
 return {'method':'BE-DICT per-base classifier','editor':p['editor'],'ensembleRuns':5,'coordinateConvention':'1-based position in supplied 20-nt protospacer; upstream zero-based coordinates converted explicitly','rows':rows,'endpoint':'per-base edited-class probability','units':'probability','scope':'Published dichotomous classifier (training editing at/above the mean versus below the mean), not a measured conversion fraction, haplotype distribution, total editing yield or calibrated success probability in another cell type. All five trained runs are preserved.'}

def infer_pridict2(p,source,folder):
 import csv
 out=folder/'predictions';out.mkdir();env={**os.environ,'CUDA_VISIBLE_DEVICES':''}
 cmd=[sys.executable,'-B',str(source/'pridict2_pegRNA_design.py'),'single','--sequence-name','editcraft_input','--sequence',p['editSequence'],'--output-dir',str(out),'--use_5folds']
 run=subprocess.run(cmd,cwd=source,env=env,stdout=sys.stderr,stderr=sys.stderr)
 path=out/'editcraft_input_pegRNA_Pridict_full.csv'
 if run.returncode or not path.is_file():raise RuntimeError('Upstream PRIDICT2 did not produce a successful prediction file.')
 with path.open() as f:rows=list(csv.DictReader(f))
 if not rows or len(rows)>5000:raise ValueError('No predictions, or result exceeds the bounded single-variant analysis.')
 columns={c:'PRIDICT2_0_editing_Score_deep_'+c for c in ('HEK','K562')}
 for row in rows:
  for context,col in columns.items():
   value=float(row[col])
   if not math.isfinite(value) or not 0<=value<=100:raise ValueError('PRIDICT2 returned an invalid model score.')
   row[col]=value
 return {'method':'PRIDICT2.0','selectedCellContext':p['cellContext'],'foldsPerModel':5,'upstreamModelGroups':['PRIDICT1_1/exp_2023-08-25_20-55-53','PRIDICT1_2/exp_2023-08-28_22-22-26'],'rows':rows,'outputCsvSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'endpoint':'prime-editing efficiency prediction in published HEK and K562 contexts','units':'upstream model score on 0–100 scale','scope':'Both original model groups and all five folds; no DeepCas9 nicking model or primer design requested. No efficacy in other cells or clinical outcome inferred.'}

def execute(folder):
 cloud_only();folder=pathlib.Path(folder);data=json.loads((folder/'input.json').read_text());op=data['operation'];p=validate_input(op,data['parameters']);model=OPERATIONS[op];verify_model(model);source=model_root()/model/'source'
 with contextlib.redirect_stdout(sys.stderr):
  value=infer_rs3(p,source) if model=='rs3' else infer_bedict(p,source) if model=='bedict' else infer_pridict2(p,source,folder)
 import importlib.metadata
 names=['numpy','pandas','scipy','scikit-learn']+(['sglearn','seqfold','lightgbm','biopython','joblib'] if model=='rs3' else ['torch'])
 packages={name:importlib.metadata.version(name) for name in names}
 value['runtime']={'python':sys.version.split()[0],'packages':packages,'gpuUsed':False}
 (folder/'output.json').write_text(canonical(value))
if __name__=='__main__':
 if len(sys.argv)!=3 or sys.argv[1]!='--execute':raise SystemExit(2)
 execute(sys.argv[2])
