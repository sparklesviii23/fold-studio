"""Run authentic pinned upstream filter/rank on a private immutable snapshot."""
import hashlib,importlib.metadata,json,os,pathlib,sys
sys.dont_write_bytecode=True;os.environ['JAX_PLATFORMS']='cpu'
BASE=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE/'vendor/bindcraft2'))
def run(request_path):
 from bindcraft.rank import rerank_campaign
 from bindcraft.campaign_filter import refilter_campaign
 from bindcraft.campaign_output import write_csv_rows
 request_path=pathlib.Path(request_path);folder=request_path.parent;request=json.loads(request_path.read_text());snapshot=folder/'snapshot';output=folder/'review.csv'
 if request['operation']=='rank':
  _,rows,directions=rerank_campaign(str(snapshot),request['metrics'],request['table'],output=str(output));result={'rows':rows,'directions':directions}
 else:
  rows,rejected,report,_=refilter_campaign(str(snapshot),table=request['table'],output=str(output));write_csv_rows(rejected,str(folder/'rejected.csv'),list(dict.fromkeys(k for row in rejected for k in row)));result={'rows':rows,'rejected':rejected,'report':report}
 result.update(operation=request['operation'],table=request['table'],state='reviewed',requestSha256=hashlib.sha256(request_path.read_bytes()).hexdigest(),runnerSha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),runtime={'jax':importlib.metadata.version('jax'),'jaxlib':importlib.metadata.version('jaxlib')},csv=output.read_text(),rejectedCsv=(folder/'rejected.csv').read_text() if (folder/'rejected.csv').is_file() else None,scope='Post-hoc upstream table filtering/ranking on saved computations. This does not generate, refold or grant original scientific acceptance to a candidate. Missing recorded filters are explicitly reported by upstream.')
 (folder/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result
if __name__=='__main__':run(sys.argv[1])
