import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))
import borzoi_panel as P

p=argparse.ArgumentParser(); p.add_argument('--library',required=True); p.add_argument('--plan',type=Path,required=True); p.add_argument('--reference-dir',type=Path,required=True); p.add_argument('--run'); args=p.parse_args()
panel=json.loads(args.plan.read_text())
if args.run:
    report=P.evaluate(args.library,args.run,args.reference_dir); print(json.dumps({'testLoci':report['testLoci'],'summary':report['summary']},indent=1))
else: print(json.dumps(P.prepare_reference(panel,args.reference_dir),indent=1))
