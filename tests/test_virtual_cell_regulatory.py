"""Synthetic artifact checks only; these fixtures do not qualify Borzoi inference."""
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import virtual_cell_regulatory as R
import biological_model_runner as runner


def fixture(root):
    run = 'a' * 32; folder = pathlib.Path(root) / 'gpu_tasks' / run; out = folder / 'outputs'; out.mkdir(parents=True)
    task = {'id': run, 'recipe': 'bio_borzoi', 'state': 'done', 'inputsSha256': 'input', 'inputs': {'chromosome': 'chr2', 'start': 100, 'track': 6226}, 'outputs': []}
    task['inputsSha256'] = hashlib.sha256(json.dumps(task['inputs'], sort_keys=True).encode()).hexdigest()
    result = {'schema': 'fold-studio.biological-model-result.v1', 'recipe': 'bio_borzoi', 'inputsSha256': task['inputsSha256'],
              'reference': {'assembly': 'hg38', 'chromosome': 'chr2', 'start': 100, 'end': 524388},
              'bins': 2, 'binSize': 32, 'outputStart': 200, 'trackIndex': 6226, 'trackMetadata': {'identifier': 'test+', 'description': 'RNA:HepG2'}, 'checkpointSha256': 'b'*64}
    for name, raw in [('result.json', json.dumps(result).encode()), ('regulatory-track.csv', b'chromosome,start_0based,end_exclusive,raw_model_value\nchr2,200,232,1.0\nchr2,232,264,2.0\n')]:
        (out / name).write_bytes(raw); task['outputs'].append({'path': name, 'sha256': hashlib.sha256(raw).hexdigest()})
    (folder / 'task.json').write_text(json.dumps(task))
    return run, folder, result, task


class RegulatoryTests(unittest.TestCase):
    def test_matching_assay_and_coordinates_are_required(self):
        with tempfile.TemporaryDirectory() as temp:
            run, folder, result, task = fixture(temp)
            r = R.get(temp, run, 'CVCL_0027')
            self.assertTrue(r['supported']); self.assertEqual(r['end'], 264); self.assertEqual(r['preview'][1]['mean'], 2.)
            self.assertFalse(R.get(temp, run, 'CVCL_1098')['supported'])
            self.assertFalse(R.get(temp, run, 'CVCL_0004')['supported'])
            self.assertEqual(len(R.listing(temp, 'CVCL_0027')['runs']), 1)
            task['state'] = 'running'; (folder / 'task.json').write_text(json.dumps(task))
            self.assertIsNone(R.get(temp, run, 'CVCL_0027')['values'])

    def test_artifact_tampering_cannot_reach_viewer(self):
        with tempfile.TemporaryDirectory() as temp:
            run, folder, _, _ = fixture(temp)
            (folder / 'outputs/regulatory-track.csv').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'checksum'): R.get(temp, run, 'CVCL_0027')
            with self.assertRaises(ValueError): R.get(temp, '../a', 'CVCL_0027')

    def test_assembly_mismatch_is_refused_after_valid_checksum(self):
        with tempfile.TemporaryDirectory() as temp:
            run, folder, result, task = fixture(temp); result['reference']['assembly'] = 'hg19'
            raw = json.dumps(result).encode(); (folder / 'outputs/result.json').write_bytes(raw)
            task['outputs'][0]['sha256'] = hashlib.sha256(raw).hexdigest(); (folder / 'task.json').write_text(json.dumps(task))
            with self.assertRaisesRegex(ValueError, 'assembly'): R.get(temp, run, 'CVCL_0027')

    def test_cached_checkpoint_with_wrong_size_fails_without_download(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp) / 'predictive-cell-borzoi/ef83ad59b43765413f73767d87a717df'; folder.mkdir(parents=True)
            (folder / 'model0_best.h5').write_bytes(b'not a checkpoint')
            with patch.object(runner.urllib.request, 'urlopen', side_effect=AssertionError('No download permitted')):
                with self.assertRaisesRegex(ValueError, 'size'): runner.borzoi_checkpoint(temp)


if __name__ == '__main__': unittest.main()
