"""Extracted unchanged from snap-stanford/GEARS @ f374e43e197b295016d80395d7a54ddb81cc6769 / gears/utils.py.
License and attribution: vendor/cell-ai/gears-LICENSE.
Only this numerical helper is reused; this is not the complete upstream model.
"""
import numpy as np

def np_pearson_cor(x, y):
    xv = x - x.mean(axis=0)
    yv = y - y.mean(axis=0)
    xvss = (xv * xv).sum(axis=0)
    yvss = (yv * yv).sum(axis=0)
    result = np.matmul(xv.transpose(), yv) / np.sqrt(np.outer(xvss, yvss))
    # bound the values to -1 to 1 in the event of precision issues
    return np.maximum(np.minimum(result, 1.0), -1.0)
