"""Narrow optimizer-output comparison. Diagnostic gates never establish binder quality."""
import argparse,hashlib,json,pathlib
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--cpu',required=True);p.add_argument('--metal',required=True);p.add_argument('--output',required=True);a=p.parse_args()
cpu=pathlib.Path(a.cpu);metal=pathlib.Path(a.metal)
c=json.loads((cpu/'result.json').read_text());m=json.loads((metal/'result.json').read_text())
for key in ('upstreamRevision','precision','sourceSha256','diagnosticAllStages'):
 if c[key]!=m[key]:raise ValueError('Input profile mismatch: '+key)
for key in c['settings']:
 if key=='targets':continue
 if c['settings'][key]!=m['settings'][key]:raise ValueError('Settings mismatch: '+key)
if c['execution']!='cpu' or m['execution']!='metal' or c['failedStage'] or m['failedStage']:raise ValueError('Both complete backend trajectories are required.')
x=np.load(cpu/'outputs.npz',allow_pickle=False);y=np.load(metal/'outputs.npz',allow_pickle=False)
if set(x.files)!=set(y.files):raise ValueError('Outputs differ.')
checks={};passed=True
for key in x.files:
 left=x[key].astype(np.float64);right=y[key].astype(np.float64)
 if left.shape!=right.shape or not np.isfinite(left).all() or not np.isfinite(right).all():raise ValueError('Invalid output: '+key)
 delta=right-left;rms=float(np.sqrt(np.mean(delta**2)));maximum=float(np.max(np.abs(delta)))
 if key.endswith('__atoms'):
  mask=x[key.removesuffix('__atoms')+'__mask'].astype(bool);delta=delta[mask];rms=float(np.sqrt(np.mean(delta**2)));maximum=float(np.max(np.abs(delta)));ok=rms<=.1
 elif key.endswith(('__mask','__sequence')):ok=np.array_equal(x[key],y[key])
 else:ok=maximum<=.01
 passed=passed and bool(ok);checks[key]={'rmsError':rms,'maxAbsError':maximum,'passed':bool(ok)}
report={'state':'passed' if passed else 'failed','scope':'Technical target fragment and designed chains (lengths in source reports), one real optimizer update per screen/refine/anneal/harden stage, permissive diagnostic gates. No research-quality acceptance or full campaign parity claim.','thresholds':{'resolvedCoordinateRmsAngstrom':.1,'metricMaxAbs':.01,'sequenceAndMask':'identical'},'checks':checks,'cpu':c,'metal':m,'artifactSha256':{str(folder):hashlib.sha256((folder/'outputs.npz').read_bytes()).hexdigest() for folder in (cpu,metal)}}
pathlib.Path(a.output).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps({'state':report['state'],'checks':checks},indent=2))
if not passed:raise SystemExit(1)
