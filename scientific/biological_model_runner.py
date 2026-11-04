"""Read-only model inference inside a remote GPU container. No sequence generation."""
import hashlib
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request


def sha_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b''): h.update(b)
    return h.hexdigest()


def borzoi_checkpoint(cache):
    """Verify the official immutable GCS object before every use; serialize downloads."""
    import fcntl
    import tempfile
    expected = 'ef83ad59b43765413f73767d87a717df'
    url = 'https://storage.googleapis.com/seqnn-share/borzoi/f0/model0_best.h5'
    # Separate from the older adapter's mutable cache; directory identity is content-based.
    folder = Path(cache) / 'predictive-cell-borzoi' / expected; folder.mkdir(parents=True, exist_ok=True)
    weight = folder / 'model0_best.h5'
    def verify(path):
        if path.stat().st_size != 744112468:
            raise ValueError('Borzoi checkpoint size differs from the official object.')
        h = hashlib.md5()
        with path.open('rb') as f:
            for part in iter(lambda: f.read(8 << 20), b''): h.update(part)
        if h.hexdigest() != expected:
            raise ValueError('Borzoi checkpoint differs from the official GCS object MD5; refusing inference.')
    with (folder / 'download.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if weight.exists():
            verify(weight)
        else:
            with tempfile.NamedTemporaryFile(dir=folder, suffix='.partial', delete=False) as f:
                temp = Path(f.name)
            try:
                with urllib.request.urlopen(url, timeout=180) as response, temp.open('wb') as dest:
                    total = 0
                    while True:
                        part = response.read(8 << 20)
                        if not part: break
                        total += len(part)
                        if total > 744112468: raise ValueError('Borzoi checkpoint exceeds its declared size.')
                        dest.write(part)
                verify(temp); temp.replace(weight)
            finally:
                temp.unlink(missing_ok=True)
    return weight


def evo(inputs, out):
    import numpy as np
    import torch
    from evo2 import Evo2
    # Use the documented 7B BF16 path, not the FP8-dependent 1B/20B/40B models.
    model = Evo2('evo2_7b_base')
    sequences = [inputs['sequence']]
    if inputs.get('alternate'): sequences.append(inputs['alternate'])
    scores = [float(x) for x in model.score_sequences(sequences, prepend_bos=True, reduce_method='mean')]
    layer = 'blocks.28.mlp.l3'
    ids = torch.tensor(model.tokenizer.tokenize(sequences[0]), dtype=torch.int, device='cuda:0').unsqueeze(0)
    _, embeddings = model(ids, return_embeddings=True, layer_names=[layer])
    e = embeddings[layer].float().cpu().numpy()
    if not np.isfinite(e).all(): raise ValueError('Non-finite Evo embeddings.')
    np.save(out / 'dna-embeddings.npy', e)
    cache = Path(os.environ['HF_HOME'])
    candidates = [cache / 'evo2_7b_base.pt', *cache.glob('hub/models--arcinstitute--evo2_7b_base/snapshots/*/evo2_7b_base.pt')]
    weights = next((p for p in candidates if p.is_file()), None)
    if weights is None: raise ValueError('Cannot establish loaded Evo checkpoint identity.')
    return {'model': 'evo2_7b_base', 'checkpointSha256': sha_file(weights), 'scores': scores, 'scoreDefinition': 'Mean autoregressive log likelihood per token, BOS prepended; not pathogenicity or fitness.',
            'alternateMinusReference': scores[1] - scores[0] if len(scores) == 2 else None,
            'embeddingLayer': layer, 'embeddingShape': list(e.shape), 'note': 'Input order: reference, then optional alternate. No clinical classification.'}


def esmc(inputs, out):
    import numpy as np
    import torch
    from huggingface_hub import HfApi
    from esm.models.esmc import EsmcForMaskedLM, EsmcTokenizer
    repo = 'biohub/ESMC-300M'
    revision = HfApi().model_info(repo).sha
    model = EsmcForMaskedLM.from_pretrained(repo, revision=revision, device='cuda').eval()
    tokenizer = EsmcTokenizer()
    tokens = tokenizer([inputs['sequence']], return_tensors='pt', padding=True)
    tokens = {k: v.to(model.device) for k, v in tokens.items()}
    with torch.inference_mode(): result = model(**tokens)
    # Exclude BOS/EOS; keep one vector for every supplied residue.
    e = result.last_hidden_state[0, 1:len(inputs['sequence']) + 1].float().cpu().numpy()
    if e.shape[0] != len(inputs['sequence']) or not np.isfinite(e).all(): raise ValueError('Invalid residue embeddings.')
    np.save(out / 'protein-embeddings.npy', e)
    return {'model': repo, 'checkpointRevision': revision, 'embeddingShape': list(e.shape), 'meanEmbedding': e.mean(axis=0).tolist(),
            'note': 'Protein representations, not measured function, binding affinity or antimicrobial activity.'}


def esmfold(inputs, out):
    import torch
    from huggingface_hub import HfApi
    from esm.models.esmfold2 import ESMFold2InputBuilder, EsmFold2Model, ProteinInput, StructurePredictionInput
    repo = 'biohub/ESMFold2'; revision = HfApi().model_info(repo).sha
    model = EsmFold2Model.from_pretrained(repo, revision=revision, device='cuda').eval()
    query = StructurePredictionInput(sequences=[ProteinInput(id='A', sequence=inputs['sequence'])])
    with torch.inference_mode():
        r = ESMFold2InputBuilder().fold(model, query, num_loops=inputs['loops'], num_sampling_steps=inputs['steps'], num_diffusion_samples=1, seed=inputs['seed'])
    (out / 'prediction.cif').write_text(r.complex.to_mmcif())
    return {'model': repo, 'checkpointRevision': revision, 'pLDDTMean': float(r.plddt.mean()), 'pTM': float(r.ptm),
            'note': 'Single-chain structure prediction without supplied MSA. Confidence is not experimental validation.'}


def borzoi(inputs, out):
    import csv
    import numpy as np
    import tensorflow as tf
    from baskerville import seqnn
    if not tf.config.list_physical_devices('GPU'): raise RuntimeError('Borzoi requires a remote TensorFlow GPU; CPU fallback disabled.')
    start = inputs['start']; end = start + 524288
    url = 'https://api.genome.ucsc.edu/getData/sequence?' + urllib.parse.urlencode({'genome': 'hg38', 'chrom': inputs['chromosome'], 'start': start, 'end': end})
    with urllib.request.urlopen(url, timeout=120) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000: raise ValueError('Reference response too large.')
    dna = json.loads(body)['dna'].upper()
    if len(dna) != 524288 or set(dna) - set('ACGTN'): raise ValueError('Reference window length/alphabet mismatch; no padding or clipping applied.')
    (out / 'reference.fasta').write_text('>hg38:' + inputs['chromosome'] + ':' + str(start) + '-' + str(end) + ' zero-based-half-open\n' + dna + '\n')
    repo = Path('/opt/borzoi'); params = json.loads((repo / 'examples/params_pred.json').read_text())
    tracks = list(csv.DictReader((repo / 'examples/targets_human.txt').open(), delimiter='\t'))
    index = inputs['track']; metadata = tracks[index]
    if len(tracks) != 7611 or int(metadata['']) != index:
        raise ValueError('Borzoi track order does not match the human checkpoint.')
    weight = borzoi_checkpoint('/cache/models')
    model = seqnn.SeqNN(params['model']); model.restore(str(weight), 0); model.build_slice([index])
    # N is represented as zeros; no random bases substituted.
    sequence = np.zeros((524288, 4), dtype=np.float32)
    encoded = np.frombuffer(dna.encode(), dtype=np.uint8)
    for j, base in enumerate(b'ACGT'): sequence[:, j] = encoded == base
    result = np.asarray(model(sequence[None, ...]))
    # params_pred has 16 cropped bins at either edge; training params crop 5120.
    crop = next(b['cropping'] for b in params['model']['trunk'] if b['name'] == 'Cropping1D')
    expected_bins = 524288 // 32 - 2 * int(crop)
    if result.shape != (1, expected_bins, 1) or not np.isfinite(result).all() or (result < 0).any(): raise ValueError('Invalid Borzoi output shape or values.')
    values = result[0, :, 0].astype(float)
    offset = (524288 - len(values) * 32) // 2
    with (out / 'regulatory-track.csv').open('w') as f:
        writer = csv.writer(f); writer.writerow(['chromosome', 'start_0based', 'end_exclusive', 'raw_model_value'])
        for i, v in enumerate(values): writer.writerow([inputs['chromosome'], start + offset + 32*i, start + offset + 32*(i+1), v])
    # All bins are retained in CSV. The UI uses a bounded envelope preview.
    chunks = np.array_split(values, min(256, len(values)))
    preview = [{'min': float(c.min()), 'max': float(c.max()), 'mean': float(c.mean())} for c in chunks]
    return {'model': 'Borzoi human replicate 0', 'reference': {'assembly': 'hg38', 'chromosome': inputs['chromosome'], 'start': start, 'end': end, 'source': url, 'sequenceSha256': hashlib.sha256(dna.encode()).hexdigest()},
            'trackIndex': index, 'trackMetadata': metadata, 'bins': len(values), 'binSize': 32, 'outputStart': start + offset,
            'checkpointSha256': sha_file(weight), 'checkpointSource': 'https://storage.googleapis.com/seqnn-share/borzoi/f0/model0_best.h5',
            'checkpointObjectMd5': 'ef83ad59b43765413f73767d87a717df',
            'sourceRevision': os.environ.get('FOLD_BORZOI_REVISION'), 'baskervilleRevision': os.environ.get('FOLD_BASKERVILLE_REVISION'),
            'parametersSha256': sha_file(repo / 'examples/params_pred.json'), 'targetsSha256': sha_file(repo / 'examples/targets_human.txt'),
            'coordinateConvention': 'zero-based half-open', 'outputUnit': 'raw transformed assay coverage (see sum_stat, scale and clipping in trackMetadata)',
            'uncertainty': {'supported': False, 'reason': 'One replicate, forward strand; no calibrated predictive interval.'},
            'trainingDomain': {'assemblies': ['hg38', 'mm10'], 'head': 'human hg38', 'testFold': 'fold3', 'validationFold': 'fold4',
                               'note': 'Assay-specific genomic tracks; not a cell phenotype or calibrated transcript abundance.'},
            'preview': preview,
            'note': 'Raw transformed model output; no inverse count transform, reverse-complement averaging, ensemble or expression calibration. Human reference only; not a bacterial/phage model.'}


RUNNERS = {'bio_evo2': evo, 'bio_esmc': esmc, 'bio_esmfold2': esmfold, 'bio_borzoi': borzoi}


def main():
    if os.environ['FOLD_BIO_RECIPE'] != 'bio_borzoi':
        import torch
        if not torch.cuda.is_available(): raise RuntimeError('Remote CUDA GPU unavailable; no CPU fallback.')
    inputs = json.loads(os.environ['FOLD_INPUT']); out = Path('/cache/out') / os.environ['FOLD_TASK_ID']; out.mkdir(parents=True, exist_ok=True)
    recipe = os.environ['FOLD_BIO_RECIPE']
    print('[fold] Running ' + recipe, flush=True)
    result = RUNNERS[recipe](inputs, out)
    result.update(schema='fold-studio.biological-model-result.v1', recipe=recipe, evidence='Model prediction · not independently validated', clinicalUse=False,
                  inputsSha256=hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest())
    # Every output must be strict JSON; errors are failures, never successful NaN results.
    text = json.dumps(result, allow_nan=False, indent=2)
    (out / 'result.json').write_text(text)
    manifest = [{'path': p.name, 'bytes': p.stat().st_size, 'sha256': sha_file(p)} for p in out.iterdir() if p.is_file()]
    (out / 'artifacts.json').write_text(json.dumps(manifest, indent=2))
    print('[fold] Results saved; research predictions only.', flush=True)


if __name__ == '__main__': main()
