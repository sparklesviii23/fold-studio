import argparse
import json
import os
import pathlib
import sys
from . import API_VERSION,VERSION

def main():
    parser=argparse.ArgumentParser(description='fold RAPID scientific worker; authenticated SSH stdio API')
    parser.add_argument('--version',action='version',version=VERSION)
    parser.add_argument('--root',default=os.environ.get('RAPID_ROOT',str(pathlib.Path.home()/'.local/share/fold-rapid/data')))
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('rpc','health','recover','inventory'):sub.add_parser(name)
    sub.add_parser('run-job').add_argument('job_id')
    sub.add_parser('run-campaign').add_argument('campaign_id')
    args=parser.parse_args()
    if args.command=='run-campaign':
        from .unified import run
        run(pathlib.Path(args.root),args.campaign_id);return
    if args.command=='run-job':
        from .runner import execute
        execute(pathlib.Path(args.root),args.job_id);return
    from .api import Worker
    worker=Worker(args.root)
    if args.command=='rpc':
        try:
            raw=sys.stdin.buffer.read(4_000_001)
            if len(raw)>4_000_000:raise ValueError('Request exceeds 4 MB limit.')
            request=json.loads(raw);result=worker.dispatch(request)
        except (ValueError,KeyError,TypeError,OSError) as error:
            result={'apiVersion':API_VERSION,'error':str(error),'errorType':type(error).__name__}
    else:result={'health':worker.health,'inventory':worker.engine_inventory,'recover':worker.job_recover}[args.command]({})
    print(json.dumps(result,allow_nan=False))

if __name__=='__main__':main()
