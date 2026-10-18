"""Compare authentic sampled sequences/scores on CPU and Metal for identical inputs."""
import argparse,hashlib,json,pathlib
p=argparse.ArgumentParser();p.add_argument('--cpu',required=True);p.add_argument('--metal',required=True);p.add_argument('--output',required=True);a=p.parse_args()
paths=[pathlib.Path(a.cpu),pathlib.Path(a.metal)];c,m=[json.loads(path.read_text()) for path in paths]
if c['execution']!='cpu' or m['execution']!='metal':raise ValueError('Both actual backends are required.')
for key in ('checkpointSha256','sourceSha256','settings'):
 if c[key]!=m[key]:raise ValueError('Input differs: '+key)
checks=[]
if len(c['candidates'])!=len(m['candidates']):raise ValueError('Candidate counts differ.')
for left,right in zip(c['candidates'],m['candidates']):
 errors={k:abs(v-right['metrics'][k]) for k,v in left['metrics'].items()}
 same=left['chains']==right['chains'];checks.append({'identicalSequences':same,'metricAbsoluteErrors':errors,'passed':same and max(errors.values())<=1e-4})
passed=bool(checks) and all(check['passed'] for check in checks)
report={'state':'passed' if passed else 'failed','scope':'Two fixed-backbone ProteinMPNN sequences for one 460-residue ANGPTL3 source, negative checkpoint, identical seed/settings. Numerical/sample agreement only; no fold or binding validation.','thresholds':{'sequence':'identical','scoreMaxAbsoluteError':1e-4},'checks':checks,'cpu':c,'metal':m,'artifactSha256':{str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}}
pathlib.Path(a.output).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(report['state'])
if not passed:raise SystemExit(1)
