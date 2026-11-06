#!/usr/bin/env python3
"""Offline bounded pilot; compatible checkpoint must already exist locally."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
sys.dont_write_bytecode=True
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1';os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--checkpoint',required=True,type=Path);p.add_argument('--data',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path);p.add_argument('--metadata',required=True,type=Path)
    p.add_argument('--steps',type=int,default=30);p.add_argument('--maximum-seconds',type=int,default=900)
    p.add_argument('--device',choices=['mps','cpu'],default='mps');p.add_argument('--teacher-weight',type=float,default=0.)
    p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS);a=p.parse_args()
    if not 1<=a.steps<=30 or not 1<=a.maximum_seconds<=900:p.error('First pilot: at most 30 steps / 900 seconds.')
    if a.worker:
        from qwen_cell_training import run
        print(run(a.checkpoint,a.data,a.out,a.metadata,a.steps,a.maximum_seconds,a.device,a.teacher_weight));return 0
    # Independent supervisor bounds native-library calls as well as Python code.
    child=subprocess.Popen([sys.executable,'-B',__file__,*sys.argv[1:],'--worker'],start_new_session=True)
    def stopped(*_):raise KeyboardInterrupt('Stop requested.')
    previous=signal.signal(signal.SIGTERM,stopped)
    try:return child.wait(timeout=a.maximum_seconds)
    except (subprocess.TimeoutExpired,KeyboardInterrupt) as error:
        try:os.killpg(child.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait()
        print('Local pilot stopped; no automatic retry.',flush=True)
        return 130 if isinstance(error,KeyboardInterrupt) else 124
    finally:signal.signal(signal.SIGTERM,previous)


if __name__=='__main__':raise SystemExit(main())
