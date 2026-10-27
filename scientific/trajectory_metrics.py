"""Explicit population Cα motion metrics; no equilibrium or stability inference."""

def coordinate_metrics(frames,align=True):
 import numpy as np
 if type(align) is not bool:raise ValueError('Alignment must be an explicit boolean.')
 points=np.asarray(frames,dtype=np.float64)
 if points.ndim!=3 or points.shape[0]<2 or points.shape[1]<1 or points.shape[2]!=3 or not np.isfinite(points).all():raise ValueError('Motion analysis needs at least two finite frames with matching XYZ atoms.')
 if points.shape[0]*points.shape[1]>200000:raise ValueError('Motion analysis supports at most 200,000 selected atom/frame pairs.')
 # All selected sites are carbon Cα atoms, so equal mass and equal site weights coincide.
 gyration=np.sqrt(np.mean(np.sum((points-points.mean(axis=1,keepdims=True))**2,axis=2),axis=1))
 reference=points[0];center=reference.mean(axis=0);centered=reference-center;determinants=[];coordinates=[]
 if align and (points.shape[1]<3 or np.linalg.matrix_rank(centered,tol=1e-10)<2):raise ValueError('Rigid alignment needs at least three noncollinear reference atoms. Disable alignment for raw displacement.')
 for frame in points:
  if align:
   shifted=frame-frame.mean(axis=0)
   if np.linalg.matrix_rank(shifted,tol=1e-10)<2:raise ValueError('A frame has degenerate geometry; rigid alignment is ambiguous.')
   u,_,vt=np.linalg.svd(shifted.T@centered);correction=np.eye(3);correction[2,2]=1. if np.linalg.det(u@vt)>=0 else -1.;rotation=u@correction@vt;determinants.append(float(np.linalg.det(rotation)));coordinates.append(shifted@rotation+center)
  else:coordinates.append(frame.copy())
 coordinates=np.asarray(coordinates);rmsd=np.sqrt(np.mean(np.sum((coordinates-reference)**2,axis=2),axis=1));mean=coordinates.mean(axis=0);rmsf=np.sqrt(np.mean(np.sum((coordinates-mean)**2,axis=2),axis=0))
 return {'alignment':'proper rigid least-squares fit to first saved frame' if align else 'none; includes whole-body translation and rotation','referenceFrameIndex':0,'units':'Å','rmsdAngstrom':rmsd.tolist(),'rmsfAngstrom':rmsf.tolist(),'radiusOfGyrationAngstrom':gyration.tolist(),'radiusOfGyrationMethod':'Root mean-square distance of observed canonical protein Cα sites from their per-frame centroid; equal Cα mass weights. Computed before alignment; excludes solvent, side chains, other atoms and unobserved sites.','rotationDeterminants':determinants,'averaging':'Equal frame weights; population mean-square fluctuations divided by N, not N−1. RMSF uses the mean of the analyzed coordinates.','limitations':['Frame motion alone does not establish equilibration, flexibility in solution, stability, binding or statistical uncertainty.']}

def run(request_path,output_path):
 import hashlib,json,pathlib,sys,time
 import numpy as np
 sys.path.insert(0,str(pathlib.Path(__file__).parent))
 from coordinate_ensemble import inspect
 from intelligence import CODES
 request_path=pathlib.Path(request_path);request=json.loads(request_path.read_text());source=pathlib.Path(request['input']);started=time.monotonic()
 if not source.is_file() or source.stat().st_size>100*1024**2:raise ValueError('Choose a saved ensemble below 100 MB.')
 data=source.read_bytes();sha=hashlib.sha256(data).hexdigest()
 if sha!=request['inputSha256']:raise ValueError('Trajectory source checksum changed.')
 ensemble=inspect(data);frames=[];labels=None;current=[];identities=[]
 for line in data.decode('utf8').splitlines():
  kind=line[:6].strip()
  if kind=='MODEL':current=[];identities=[]
  elif kind in ('ATOM','HETATM') and line[12:16].strip()=='CA' and line[76:78].strip().upper()=='C' and line[17:20].strip() in CODES:
   current.append([float(line[start:start+8]) for start in (30,38,46)]);identities.append({'chain':line[21:22].strip(),'residue':int(line[22:26]),'insertion':line[26:27].strip(),'residueName':line[17:20].strip(),'atom':'CA'})
  elif kind=='ENDMDL':
   if labels is None:labels=identities
   elif labels!=identities:raise ValueError('Selected Cα atom identities changed across frames.')
   frames.append(current)
 if not labels:raise ValueError('This ensemble contains no canonical protein Cα atoms.')
 result=coordinate_metrics(frames,request['align']);result.update(state='measured',selection='All observed canonical protein Cα atoms; no missing sites inferred',frameIds=ensemble['frameIds'],atoms=labels,inputSha256=sha,runnerSha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),numpyVersion=np.__version__,seconds=time.monotonic()-started)
 if hashlib.sha256(source.read_bytes()).hexdigest()!=sha:raise ValueError('Trajectory source changed during analysis.')
 pathlib.Path(output_path).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result
if __name__=='__main__':
 import sys
 sys.dont_write_bytecode=True
 run(sys.argv[1],sys.argv[2])
