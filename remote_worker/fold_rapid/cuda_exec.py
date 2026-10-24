"""Probe CUDA and run the trusted prepared entry point in one supervised process.

This avoids importing/initializing the framework twice. The ordinary runner owns
startup timeout, cancellation, process-group termination and scientific deadline.
No public manifest may supply an arbitrary command through this entry point.
"""
import json
import os
import pathlib
import runpy
import sys
import time
from .hardware import numerical_probe

def entry(command):
    if len(command)<2:raise ValueError('Missing prepared scientific entry point.')
    if command[1]=='-m':
        if len(command)<3:raise ValueError('Missing prepared module.')
        sys.argv=command[2:]
        return runpy.run_module(command[2],run_name='__main__',alter_sys=True)
    if command[1].startswith('-'):raise ValueError('Unsupported scientific interpreter option.')
    script=pathlib.Path(command[1]).resolve()
    sys.path.insert(0,str(script.parent));sys.argv=[str(script),*command[2:]]
    return runpy.run_path(str(script),run_name='__main__')

def main(folder):
    folder=pathlib.Path(folder)
    prepared=json.loads((folder/'cuda-entry.json').read_text())
    print('RAPID CUDA startup · '+prepared['engine'],flush=True)
    started=time.monotonic()
    try:
        probe=numerical_probe(prepared['engine'])
    except BaseException as exc:
        receipt={'passed':False,'errorType':type(exc).__name__,'seconds':time.monotonic()-started}
        (folder/'cuda-probe.json').write_text(json.dumps(receipt))
        raise
    receipt={'passed':True,'probe':probe,'seconds':time.monotonic()-started,'sameProcessAsModel':True}
    temporary=folder/'cuda-probe.json.partial';temporary.write_text(json.dumps(receipt));os.replace(temporary,folder/'cuda-probe.json')
    print('RAPID CUDA numerical check passed; starting original model entry point',flush=True)
    return entry(prepared['command'])

if __name__=='__main__':main(sys.argv[1])
