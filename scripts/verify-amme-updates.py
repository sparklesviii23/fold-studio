"""Keep independent-trajectory and matched-input numerical claims distinct."""
import argparse
import hashlib
import json
import pathlib
import numpy as np

p=argparse.ArgumentParser()
p.add_argument('--reference',required=True);p.add_argument('--optimized',required=True)
p.add_argument('--output',required=True);p.add_argument('--protocol',choices=['independent','matched'],required=True)
a=p.parse_args();paths=[pathlib.Path(a.reference),pathlib.Path(a.optimized)]
r,o=[json.loads(path.read_text()) for path in paths]
anchored=bool(r.get('referenceInputReanchoring') or o.get('referenceInputReanchoring'))
if a.protocol=='independent' and anchored:raise SystemExit('Re-anchored inputs cannot certify an independent trajectory.')
if a.protocol=='matched' and not anchored:raise SystemExit('Matched-input comparison requires an explicit input replay receipt.')
for key in ('source','targetSha256','selection','seed','optimizerUpdates','originalOptimizerIterations'):
    assert r[key]==o[key],key
assert r['optimizerUpdates']==2
assert [step['keyAfterSelection'] for step in r['steps']]==[step['keyAfterSelection'] for step in o['steps']]
checks={}
with np.load(paths[0].with_suffix('.npz'),allow_pickle=False) as expected,np.load(paths[1].with_suffix('.npz'),allow_pickle=False) as actual:
    assert set(expected.files)==set(actual.files),'Different recorded outputs'
    for name in expected.files:
        left,right=expected[name],actual[name]
        finite=bool(np.isfinite(left).all() and np.isfinite(right).all())
        if a.protocol=='matched' and name.startswith('input_'):
            assert np.array_equal(left,right),'Matched-input operands must be bitwise identical: '+name
        checks[name]={'shape':list(left.shape),'finite':finite,
            'maxAbsoluteDifference':float(np.max(abs(right.astype(np.float64)-left.astype(np.float64)))) if left.size else 0.,
            'exactEqual':bool(np.array_equal(left,right)),
            'passed':finite and bool(np.allclose(right,left,rtol=1e-4,atol=1e-5))}
loss_pass=bool(np.allclose([s['loss'] for s in o['steps']],[s['loss'] for s in r['steps']],rtol=1e-4,atol=1e-5))
passed=loss_pass and all(check['passed'] for check in checks.values())
report={'state':'passed' if passed else 'failed','protocol':a.protocol,
    'scope':'Two local derivatives and original optimizer calculations at bitwise identical source inputs; does not certify a continuous trajectory.' if a.protocol=='matched' else 'Two independently propagated original optimizer updates on a small technical input; not full Fab.',
    'reference':str(paths[0]),'optimized':str(paths[1]),'tolerance':{'rtol':1e-4,'atol':1e-5},
    'lossesPassed':loss_pass,'arrays':checks,'referenceInputReanchoring':anchored,
    'evidenceSha256':{str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in (*paths,*(path.with_suffix('.npz') for path in paths))}}
pathlib.Path(a.output).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
print(json.dumps({'state':report['state'],'protocol':a.protocol,'failedArrays':[name for name,check in checks.items() if not check['passed']]}))
raise SystemExit(0 if passed else 1)
