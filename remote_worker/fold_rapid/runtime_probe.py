"""Import the actual scientific entry points without loading any checkpoint.

Run with the relevant isolated interpreter. Successful imports are not CUDA
qualification and do not establish model execution or prediction accuracy.
"""
import argparse
import importlib
import importlib.metadata
import json
import platform


def probe(engine):
    modules={
        'bindcraft2':['jax','bindcraft.af2','bindcraft.proteinmpnn'],
        'boltzgen':['torch','boltzgen.cli.boltzgen','boltzgen.task.predict.predict','boltzgen.task.filter.filter','boltzgen.task.esmfold2.score'],
        'esmfold2':['torch','esm.models.esmfold2','esm.models.esmc'],
    }[engine]
    for name in modules:importlib.import_module(name)
    packages={
        'bindcraft2':['bindcraft','jax','jaxlib','jax-cuda13-plugin'],
        'boltzgen':['boltzgen','torch','numpy','numba'],
        'esmfold2':['esm','torch','numpy'],
    }[engine]
    return {'state':'imports_passed','engine':engine,'platform':platform.system(),'architecture':platform.machine(),'versions':{name:importlib.metadata.version(name) for name in packages},'modulesImported':modules,'checkpointsLoaded':False,'cudaScientificExecution':'NOT RUN','cudaQualified':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine',required=True,choices=['bindcraft2','boltzgen','esmfold2'])
    args=parser.parse_args()
    print(json.dumps(probe(args.engine)))
