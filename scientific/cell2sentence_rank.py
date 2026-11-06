"""Extracted unchanged from vandijklab/cell2sentence @ 6599c9d5629cc22863d8f187e851637fd533790f / src/cell2sentence/utils.py.
License and attribution: vendor/cell-ai/c2s-LICENSE and c2s-NOTICE.
Only this numerical helper is reused; this is not the complete upstream model.
"""
import sys
import numpy as np
from scipy import sparse
from sklearn.utils import shuffle
from tqdm import tqdm

def generate_sentences(adata, vocab, delimiter=' ', random_state=42):
    """
    Transform expression matrix to sentences. Sentences contain gene "words"
    denoting genes with non-zero expression. Genes are ordered from highest
    expression to lowest expression.

    Arguments:
        adata: an AnnData object to generate cell sentences from. Expects that
            `obs` correspond to cells and `vars` correspond to genes
        vocab: an OrderedDict which as feature names as keys and counts as values
        random_state: sets the numpy random state for splitting ties
    
    Returns:
        a `numpy.ndarray` of sentences, split by delimiter.
    """
    np.random.seed(random_state)

    if len(adata.var) > len(adata.obs):
        print(
            (
                "WARN: more variables ({}) than observations ({}), "
                + "did you mean to transpose the object (e.g. adata.T)?"
            ).format(len(adata.var), len(adata.obs)),
            file=sys.stderr,
        )

    mat = sparse.csr_matrix(adata.X)
    enc_map = list(vocab.keys())

    sentences = []
    for i in tqdm(range(mat.shape[0])):
        # for row i, [indptr[i]:indptr[i+1]] returns the indices of elements to take from 
        #  data and indices corresponding to row i
        cols = mat.indices[mat.indptr[i] : mat.indptr[i + 1]]
        vals = mat.data[mat.indptr[i] : mat.indptr[i + 1]]
        cols, vals = shuffle(cols, vals)
        sentences.append(delimiter.join([enc_map[x] for x in cols[np.argsort(-vals, kind="stable")]]))

    return sentences
