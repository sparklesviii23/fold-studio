"""Compare full-model Metal and CPU reference arrays; no biology/affinity claim."""
import argparse,json,pathlib
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--cpu',required=True);p.add_argument('--metal',required=True);p.add_argument('--output',required=True);a=p.parse_args()
cpu=pathlib.Path(a.cpu);metal=pathlib.Path(a.metal);c=json.loads(cpu.read_text());m=json.loads(metal.read_text())
for key in ('seed','residues','recycles','model','parameterSha256','precision','inputSha256','targetResidues','targetSha256'):
 if key=='targetSha256' and key not in c and key not in m:continue
 if c[key]!=m[key]:raise ValueError('Reference setting mismatch: '+key)
if m['backend']!='metal' or c['backend']!='cpu':raise ValueError('Actual backend identities required.')
x=np.load(cpu.with_suffix('.npz'),allow_pickle=False);y=np.load(metal.with_suffix('.npz'),allow_pickle=False);comparisons={}
for key in x.files:
 left=np.asarray(x[key],dtype=np.float64);right=np.asarray(y[key],dtype=np.float64)
 if left.shape!=right.shape or not np.isfinite(right).all():raise ValueError('Invalid Metal output '+key)
 delta=right-left;norm=np.linalg.norm(left);other=np.linalg.norm(right)
 comparisons[key]={'shape':list(left.shape),'maxAbsError':float(np.max(np.abs(delta))),'rmsError':float(np.sqrt(np.mean(delta**2))),'relativeL2Error':float(np.linalg.norm(delta)/max(norm,1e-12)),'cosine':float(np.sum(left*right)/max(norm*other,1e-12))}
# Explicit narrow acceptance thresholds; results beyond them remain failures.
passed=comparisons['gradient']['relativeL2Error']<=.05 and comparisons['gradient']['cosine']>=.99 and comparisons['forwardPlddt']['maxAbsError']<=.01 and comparisons['forwardPositions']['rmsError']<=.1 and comparisons['gradientPositions']['rmsError']<=.1
passed=passed and all(value['rmsError']<=.1 for key,value in comparisons.items() if 'Positions' in key)
report={'scope':f"Full {c['model']}, {c['residues']}-residue designed input plus {c['targetResidues']} target residues, {c['recycles']} recycles, same trained checkpoint and seed. Narrow numerical backend comparison; not biological validation or full BindCraft parity.",'state':'passed' if passed else 'failed','comparisons':comparisons,'cpuTiming':c,'metalTiming':m,'thresholds':{'gradientRelativeL2':.05,'gradientCosineMin':.99,'plddtMaxAbs':.01,'coordinateRmsAngstrom':.1}}
pathlib.Path(a.output).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'state':report['state'],'comparisons':comparisons},indent=2))
if not passed:raise SystemExit(1)
