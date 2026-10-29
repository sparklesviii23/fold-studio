"""Bounded supplied compound-table analysis through RDKit; no activity model."""
import base64,csv,hashlib,io,json,pathlib,subprocess,sys
ACTIONS={'chemical_screen','chemical_screens'}
def dispatch(s,action,p):
 s.project(p['projectId'])
 rows=lambda:[{**r,'data':json.loads(r['data'])} for r in s.rows("SELECT * FROM records WHERE project_id=? AND kind='analysis' AND json_extract(data,'$.domain')='chemical_screen' ORDER BY created DESC",(p['projectId'],))]
 if action=='chemical_screens':return rows()
 if set(p)-{'projectId','csvText','querySmiles','smarts','name'}:raise ValueError('Unsupported compound-table field.')
 text=p.get('csvText')
 if not isinstance(text,str) or not text or len(text.encode())>256*1024:raise ValueError('Supply at most 256 KiB of CSV with id,smiles columns.')
 reader=csv.DictReader(io.StringIO(text,newline=''))
 if reader.fieldnames!=['id','smiles']:raise ValueError('CSV header must be exactly id,smiles.')
 records=list(reader)
 if not 1<=len(records)<=250:raise ValueError('Supply 1–250 compounds; no partial table will be saved.')
 ids=set()
 for row in records:
  if set(row)!={'id','smiles'} or not isinstance(row['id'],str) or not 1<=len(row['id'])<=100 or row['id'] in ids or any(ord(c)<32 for c in row['id']) or not isinstance(row['smiles'],str) or not 1<=len(row['smiles'])<=2048:raise ValueError('Every compound requires a unique printable identity and one bounded SMILES; malformed rows are not skipped.')
  ids.add(row['id'])
 query=p.get('querySmiles','');smarts=p.get('smarts','')
 if not isinstance(query,str) or len(query)>2048 or not isinstance(smarts,str) or len(smarts)>512:raise ValueError('Query SMILES/SMARTS exceeds its bounded input limit.')
 request={'rows':records,'querySmiles':query,'smarts':smarts};execution=subprocess.run([s.engine_python(),'-I','-B',str(pathlib.Path(__file__).resolve())],input=json.dumps(request),capture_output=True,text=True,timeout=30)
 if execution.returncode:raise ValueError('RDKit compound analysis failed: '+execution.stderr.strip()[-1000:])
 result=json.loads(execution.stdout);data={'domain':'chemical_screen','result':result,'source':{'csvTextBase64':base64.b64encode(text.encode()).decode(),'sha256':hashlib.sha256(text.encode()).hexdigest(),'encoding':'UTF-8','bytes':len(text.encode())},'request':request,'runnerSha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()}
 identity=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest();data['inputSha256']=identity
 existing=next((row for row in rows() if row['data']['inputSha256']==identity),None)
 return existing or s.record_save({'projectId':p['projectId'],'kind':'analysis','name':str(p.get('name') or 'Supplied compound-table analysis')[:200],'data':data})

if __name__=='__main__':
 from rdkit import Chem,DataStructs,rdBase
 from rdkit.Chem import Descriptors,rdMolDescriptors,rdFingerprintGenerator,Lipinski
 p=json.load(sys.stdin)
 def molecule(smiles):
  if any(c.isspace() for c in smiles):raise ValueError('Supply a single SMILES without a trailing name or annotations.')
  mol=Chem.MolFromSmiles(smiles)
  if mol is None or not 1<=mol.GetNumHeavyAtoms()<=200 or len(Chem.GetMolFrags(mol))!=1:raise ValueError('Every query/compound must sanitize as one connected molecule with 1–200 heavy atoms; salts are not stripped.')
  return mol
 generator=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=2048,includeChirality=True);query=molecule(p['querySmiles']) if p['querySmiles'] else None;fingerprint=generator.GetFingerprint(query) if query else None;pattern=Chem.MolFromSmarts(p['smarts']) if p['smarts'] else None
 if p['smarts'] and pattern is None:raise ValueError('Supplied SMARTS could not be parsed.')
 result=[]
 for index,row in enumerate(p['rows']):
  mol=molecule(row['smiles']);matches=mol.GetSubstructMatches(pattern,uniquify=True,useChirality=True,maxMatches=101) if pattern is not None else None
  result.append({'id':row['id'],'sourceRow1Based':index+2,'inputSmiles':row['smiles'],'canonicalIsomericSmiles':Chem.MolToSmiles(mol,isomericSmiles=True),'formula':rdMolDescriptors.CalcMolFormula(mol),'molecularWeightDa':Descriptors.MolWt(mol),'exactMassDa':rdMolDescriptors.CalcExactMolWt(mol),'formalCharge':Chem.GetFormalCharge(mol),'heavyAtoms':mol.GetNumHeavyAtoms(),'HBD':Lipinski.NumHDonors(mol),'HBA':Lipinski.NumHAcceptors(mol),'TPSAAngstromSquared':rdMolDescriptors.CalcTPSA(mol),'WildmanCrippenLogP':Descriptors.MolLogP(mol),'rotatableBonds':rdMolDescriptors.CalcNumRotatableBonds(mol,strict=True),'MorganTanimoto':float(DataStructs.TanimotoSimilarity(fingerprint,generator.GetFingerprint(mol))) if fingerprint is not None else None,'SMARTSMatchesAtomIndices0Based':[list(m) for m in matches[:100]] if matches is not None else None,'SMARTSMatchEnumerationTruncated':len(matches)>100 if matches is not None else False})
 if fingerprint is not None:result.sort(key=lambda row:(-row['MorganTanimoto'],row['sourceRow1Based']))
 print(json.dumps({'rows':result,'rdkitVersion':rdBase.rdkitVersion,'queryCanonicalIsomericSmiles':Chem.MolToSmiles(query,isomericSmiles=True) if query is not None else None,'SMARTS':p['smarts'] or None,'fingerprint':{'algorithm':'Morgan','radius':2,'bits':2048,'includeChirality':True,'metric':'binary Tanimoto'} if fingerprint is not None else None,'scope':'Descriptors and optional structural similarity/substructure matches for the exact supplied graphs. No protonation/tautomer standardization, salt stripping, stereochemical completion, 3D preparation, docking, ADMET/toxicity inference or activity ranking. Similarity is not evidence of binding or safety; descriptor values are not experimental measurements. All valid input rows are retained, sorted by similarity only when a query is supplied.'},allow_nan=False))
