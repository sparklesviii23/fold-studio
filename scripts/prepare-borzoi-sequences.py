import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))
import borzoi_panel as P
p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--folder',required=True);a=p.parse_args()
r=P.prepare_sequences(json.loads(Path(a.plan).read_text()),a.folder)
print(json.dumps({'sha256':r['sha256'],'ready':sum(x['status']=='ready' for x in r['loci']),'unsupported':[x for x in r['loci'] if x['status']!='ready']},indent=1))
