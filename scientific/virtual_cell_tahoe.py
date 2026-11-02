"""Stream Tahoe-100M pseudobulk drug responses into a compact, resumable matrix (runtime: NumPy + PyArrow).

    python virtual_cell_tahoe.py <library root> [max files]          # local, resumable
    python virtual_cell_tahoe.py parallel <work dir> <out dir> [workers]   # Modal CPU container (gpu_tasks recipe tahoe_atlas)

Source: tahoebio/Tahoe-100M, config pseudobulk_differential_expression (CC0 1.0): DESeq2 log2 fold changes of drug-treated
versus DMSO cells, per cell line × drug × concentration × plate, 1,026 Parquet files (≈ 89 GB). Each file is downloaded,
filtered to the gene panel, written into memory-mapped matrices and deleted, so disk use stays at a few GB.

Gene panel: DepMap 24Q4 protein-coding genes ∪ the virtual cell's K-562 expression panel.
Output <library>/virtualcell/data/tahoe100m/: lfc.f16 and se.f16 (conditions × genes, NaN = not tested),
conditions.json, genes.json, progress.json (files done; rerun to resume), manifest.json.
"""
import json
import pathlib
import subprocess
import sys
import time

import numpy as np

BASE = 'https://huggingface.co/datasets/tahoebio/Tahoe-100M/resolve/refs%2Fconvert%2Fparquet/pseudobulk_differential_expression/train/{:04d}.parquet'
FILES = 1026
MAX_CONDITIONS = 90000
COLS = ['gene_name', 'log2FoldChange', 'lfcSE', 'Cell_ID_Cellosaur', 'Cell_ID_DepMap', 'Cell_Name_Vevo', 'drug', 'concentration', 'concentration_unit', 'plate', 'n_cells_trt', 'n_cells_ctrl']


def panel(root):
    dm = json.loads((root / 'oncology' / 'depmap' / '24Q4' / 'expression.json').read_text())['genes']
    z = np.load(root / 'virtualcell' / 'reference' / 'k562' / 'pack.npz')
    return sorted(set(dm) | {str(g) for g in z['genes']})


def run(root, limit=None):
    import pyarrow.parquet as pq
    import pyarrow.compute as pc
    root = pathlib.Path(root); out = root / 'virtualcell' / 'data' / 'tahoe100m'; out.mkdir(parents=True, exist_ok=True)
    t0 = time.time(); log = lambda m: print(f'[{time.time() - t0:7.0f}s] {m}', flush=True)
    gfile = out / 'genes.json'
    if not gfile.is_file():
        gfile.write_text(json.dumps(panel(root)))
    genes = json.loads(gfile.read_text()); gi = {g: i for i, g in enumerate(genes)}
    shape = (MAX_CONDITIONS, len(genes)); mode = 'r+' if (out / 'lfc.f16').is_file() else 'w+'
    lfc = np.memmap(out / 'lfc.f16', np.float16, mode, shape=shape); se = np.memmap(out / 'se.f16', np.float16, mode, shape=shape)
    if mode == 'w+':
        lfc[:] = np.nan; se[:] = np.nan
    prog = json.loads((out / 'progress.json').read_text()) if (out / 'progress.json').is_file() else {'done': []}
    conds = json.loads((out / 'conditions.json').read_text()) if (out / 'conditions.json').is_file() else []
    index = {(c['cellosaurus'], c['drug'], c['concentration'], c['plate']): i for i, c in enumerate(conds)}
    gset = __import__('pyarrow').array(genes)
    todo = [i for i in range(FILES) if i not in set(prog['done'])][:limit]
    log(f'{len(genes)} genes; {len(prog["done"])} files already done; {len(todo)} to process')
    tmp = out / 'download.parquet'
    for k, fi in enumerate(todo):
        for attempt in range(4):
            r = subprocess.run(['curl', '-sL', '--fail', '--retry', '3', '-o', str(tmp), BASE.format(fi)])
            if r.returncode == 0:
                break
            time.sleep(10 * (attempt + 1))
        else:
            raise RuntimeError(f'download of file {fi} failed')
        t = pq.read_table(tmp, columns=COLS)
        t = t.filter(pc.is_in(t['gene_name'], value_set=gset))
        g = np.array([gi[x] for x in t['gene_name'].to_pylist()], np.int64)
        keys = list(zip(t['Cell_ID_Cellosaur'].to_pylist(), t['drug'].to_pylist(), t['concentration'].to_pylist(), t['plate'].to_pylist()))
        first = {}
        for row, key in enumerate(keys):
            key = (key[0], key[1].strip(), round(float(key[2]), 6), str(key[3]))
            if key not in index:
                index[key] = len(conds); first[key] = row
                conds.append({'cellosaurus': key[0], 'drug': key[1], 'concentration': key[2], 'plate': key[3], 'unit': t['concentration_unit'][row].as_py(),
                              'depmap': t['Cell_ID_DepMap'][row].as_py(), 'cellLine': t['Cell_Name_Vevo'][row].as_py(),
                              'cellsTreated': t['n_cells_trt'][row].as_py(), 'cellsControl': t['n_cells_ctrl'][row].as_py()})
            keys[row] = index[key]
        if len(conds) > MAX_CONDITIONS:
            raise RuntimeError('More conditions than allocated; raise MAX_CONDITIONS and restart.')
        c = np.array(keys, np.int64)
        lfc[c, g] = t['log2FoldChange'].to_numpy(zero_copy_only=False).astype(np.float16)
        se[c, g] = t['lfcSE'].to_numpy(zero_copy_only=False).astype(np.float16)
        tmp.unlink()
        prog['done'].append(fi)
        if k % 5 == 0 or k == len(todo) - 1:
            lfc.flush(); se.flush()
            (out / 'conditions.json').write_text(json.dumps(conds)); (out / 'progress.json').write_text(json.dumps(prog))
            log(f'file {fi}: {len(prog["done"])}/{FILES} done, {len(conds)} conditions')
    lfc.flush(); se.flush()
    (out / 'conditions.json').write_text(json.dumps(conds)); (out / 'progress.json').write_text(json.dumps(prog))
    (out / 'manifest.json').write_text(json.dumps({'source': 'https://huggingface.co/datasets/tahoebio/Tahoe-100M', 'config': 'pseudobulk_differential_expression',
                                                   'licence': 'CC0 1.0', 'filesDone': len(prog['done']), 'files': FILES, 'conditions': len(conds), 'genes': len(genes),
                                                   'complete': len(prog['done']) == FILES, 'updated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, indent=1))
    log('finished' if len(prog['done']) == FILES else 'stopped early')




def _filter(fi, genes):
    """Download one file, keep panel genes; returns (condition keys + metadata, gene index, lfc, se). Runs in a worker."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    tmp = pathlib.Path(f'/tmp/tahoe-{fi}.parquet')
    for attempt in range(5):
        if subprocess.run(['curl', '-sL', '--fail', '--retry', '3', '-o', str(tmp), BASE.format(fi)]).returncode == 0:
            break
        time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError(f'download of file {fi} failed')
    t = pq.read_table(tmp, columns=COLS); tmp.unlink()
    t = t.filter(pc.is_in(t['gene_name'], value_set=pa.array(genes)))
    gi = {g: i for i, g in enumerate(genes)}
    g = np.array([gi[x] for x in t['gene_name'].to_pylist()], np.int32)
    meta = list(zip(t['Cell_ID_Cellosaur'].to_pylist(), t['drug'].to_pylist(), t['concentration'].to_pylist(), t['plate'].to_pylist(),
                    t['concentration_unit'].to_pylist(), t['Cell_ID_DepMap'].to_pylist(), t['Cell_Name_Vevo'].to_pylist(),
                    t['n_cells_trt'].to_pylist(), t['n_cells_ctrl'].to_pylist()))
    return fi, meta, g, t['log2FoldChange'].to_numpy(zero_copy_only=False).astype(np.float16), t['lfcSE'].to_numpy(zero_copy_only=False).astype(np.float16)


def run_parallel(work, out, workers=12):
    """Remote mode (Modal CPU container): all files in parallel, written as compact matrices with exactly one row per
    condition. work/genes.json holds the panel; out receives lfc.f16, se.f16, conditions.json, genes.json, progress.json."""
    from multiprocessing import Pool
    work, out = pathlib.Path(work), pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
    genes = json.loads((work / 'genes.json').read_text()); t0 = time.time()
    shape = (MAX_CONDITIONS, len(genes)); scratch = pathlib.Path('/tmp/tahoe-out'); scratch.mkdir(exist_ok=True)
    lfc = np.memmap(scratch / 'lfc.f16', np.float16, 'w+', shape=shape); se = np.memmap(scratch / 'se.f16', np.float16, 'w+', shape=shape)
    lfc[:] = np.nan; se[:] = np.nan
    conds, index, done = [], {}, []
    with Pool(workers) as pool:
        for fi, meta, g, l, s in pool.imap_unordered(lambda_filter, [(i, genes) for i in range(FILES)]):
            rows = np.empty(len(meta), np.int64)
            for r, m in enumerate(meta):
                key = (m[0], m[1].strip(), round(float(m[2]), 6), str(m[3]))
                if key not in index:
                    index[key] = len(conds)
                    conds.append({'cellosaurus': key[0], 'drug': key[1], 'concentration': key[2], 'plate': key[3], 'unit': m[4], 'depmap': m[5], 'cellLine': m[6],
                                  'cellsTreated': m[7], 'cellsControl': m[8]})
                rows[r] = index[key]
            lfc[rows, g] = l; se[rows, g] = s; done.append(fi)
            if len(done) % 50 == 0:
                print(f'[{time.time() - t0:6.0f}s] {len(done)}/{FILES} files, {len(conds)} conditions', flush=True)
    n = len(conds)
    for name, m in (('lfc.f16', lfc), ('se.f16', se)):
        m.flush(); np.asarray(m[:n]).tofile(out / name)            # trimmed to exactly n rows
    (out / 'conditions.json').write_text(json.dumps(conds)); (out / 'genes.json').write_text(json.dumps(genes))
    (out / 'progress.json').write_text(json.dumps({'done': sorted(done)}))
    print(f'[{time.time() - t0:6.0f}s] finished: {n} conditions × {len(genes)} genes', flush=True)


def lambda_filter(args):
    return _filter(*args)


if __name__ == '__main__':
    if sys.argv[1] == 'parallel':
        run_parallel(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 12)
    else:
        run(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None)
