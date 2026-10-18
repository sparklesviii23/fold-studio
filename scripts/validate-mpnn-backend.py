"""Execute genuine ProteinMPNN on an explicit backend using a saved source request."""
import argparse,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'))
p=argparse.ArgumentParser();p.add_argument('--request',required=True);p.add_argument('--backend',choices=['cpu','metal'],required=True);p.add_argument('--output',required=True);p.add_argument('--variant',choices=['neutral','negative','positive'],default='negative');a=p.parse_args()
from mpnn_runner import execute
request=json.loads(pathlib.Path(a.request).read_text());request['variant']=a.variant
result=execute(request,backend=a.backend)
pathlib.Path(a.output).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:result[k] for k in ('execution','devices','timing','checkpointSha256')},indent=2))
