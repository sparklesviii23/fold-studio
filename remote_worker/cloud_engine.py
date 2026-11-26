"""Standalone cloud engine deployment, independent of the macOS application.

Python CLI: --configuration profile.json --release release/ --approve-cpu-build
--max-approved-usd 1. Uses official Modal credentials; never accepts tokens as
arguments. Import with FOLD_MODAL_CONFIG/FOLD_RAPID_RELEASE for SDK inspection.
"""
import argparse
import json
import os
import pathlib
from fold_rapid.modal_provider import build_app,deploy_app


def construct(configuration,release):return build_app(configuration,worker_source=pathlib.Path(release)/'worker')


def main():
    parser=argparse.ArgumentParser(description='fold RAPID Cloud Engine — source-only CPU deployment; no molecular job or GPU starts')
    parser.add_argument('--configuration',type=pathlib.Path,required=True);parser.add_argument('--release',type=pathlib.Path,required=True)
    parser.add_argument('--approve-cpu-build',action='store_true');parser.add_argument('--max-approved-usd',type=float,required=True)
    args=parser.parse_args()
    if not args.approve_cpu_build or not 0<args.max_approved_usd<=1:parser.error('Explicit source-only build/deployment approval with an allowance up to $1 is required. Actual provider billing is separate.')
    cfg=json.loads(args.configuration.read_text());app=construct(cfg,args.release);deploy_app(app)
    import modal
    health=modal.Function.from_name(cfg['appName'],'unified_control').remote('inventory',{})
    print(json.dumps({'appId':app.app_id,'health':health,'gpuStarted':False,'maximumApprovedUSD':args.max_approved_usd,'actualBilledUSD':None,'scientificCloudQualified':False},allow_nan=False))


if __name__=='__main__':main()
elif os.environ.get('FOLD_MODAL_CONFIG') and os.environ.get('FOLD_RAPID_RELEASE'):
    app=construct(json.loads(pathlib.Path(os.environ['FOLD_MODAL_CONFIG']).read_text()),os.environ['FOLD_RAPID_RELEASE'])
