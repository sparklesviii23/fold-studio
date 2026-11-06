#!/usr/bin/env python3
"""Prepare measured RNA supervision without reopening legacy test outcomes."""
import argparse
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))
from qwen_cell_data import prepare
p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
a=p.parse_args();print(prepare(a.root,a.out))
