"""Compare real original-model and SSD-checkpoint outputs without new inference."""
import argparse
import hashlib
import json
import pathlib
import numpy as np

p = argparse.ArgumentParser()
p.add_argument('--reference', required=True)
p.add_argument('--offloaded', required=True)
p.add_argument('--output', required=True)
p.add_argument('--policy', choices=['ssd','rematerialized_subbatches'], default='ssd')
a = p.parse_args()
paths = [pathlib.Path(a.reference), pathlib.Path(a.offloaded)]
reference, actual = [json.loads(path.read_text()) for path in paths]
assert reference['state'] == actual['state'] == 'full_gradient_passed'
for field in ('source', 'settingsSha256', 'targetSha256', 'parameterSha256', 'seed',
              'precision', 'actualGradientStatePaddedResidues', 'backend'):
    assert reference[field] == actual[field], field
assert reference['backend'] == 'cpu'
assert not reference.get('ssdOffload')
if a.policy=='ssd':
    assert actual['ssdOffload']['checkpoints'] > 0
    assert actual['ssdOffload']['bytesWritten'] > 0 and actual['ssdOffload']['bytesRead'] > 0
else:
    assert actual['amme']['policy']==a.policy and actual['amme']['tracedSubbatchCalls']>0
np.testing.assert_allclose(actual['loss'], reference['loss'], rtol=1e-4, atol=1e-5)
arrays = {}
with np.load(paths[0].with_suffix('.npz'), allow_pickle=False) as left, np.load(paths[1].with_suffix('.npz'), allow_pickle=False) as right:
    assert left.files == right.files
    assert any(name.startswith('gradient_') for name in left.files)
    assert any(name.endswith('_positions') for name in left.files)
    for name in left.files:
        assert np.isfinite(left[name]).all() and np.isfinite(right[name]).all()
        np.testing.assert_allclose(right[name], left[name], rtol=1e-4, atol=1e-5)
        arrays[name] = {'shape': list(left[name].shape), 'exactEqual': bool(np.array_equal(left[name], right[name])),
                        'maximumAbsoluteDifference': float(np.abs(left[name].astype(float) - right[name].astype(float)).max(initial=0))}
report = {'state': 'passed', 'scope': 'Single genuine model gradient parity for the saved case; not complete campaign or biological acceptance.',
          'reference': str(paths[0]), 'offloaded': str(paths[1]), 'lossAbsoluteDifference': abs(reference['loss'] - actual['loss']),
          'tolerance': {'rtol': 1e-4, 'atol': 1e-5}, 'arrays': arrays, 'executionPolicy':a.policy,'ssd': actual.get('ssdOffload'),'amme':actual.get('amme'),
          'referenceFootprintBytes': reference['observedParentPeakFootprintBytes'],
          'offloadedFootprintBytes': actual['observedParentPeakFootprintBytes'],
          'evidenceSha256': {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths + [path.with_suffix('.npz') for path in paths]}}
pathlib.Path(a.output).write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
print(json.dumps({'state': report['state'], 'exactEqual': all(row['exactEqual'] for row in arrays.values()), 'ssd': report['ssd']}))
