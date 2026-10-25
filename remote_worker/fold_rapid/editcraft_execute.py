"""Fixed private subprocess entry point for bounded EditCraft cloud calculations."""
import json,os,pathlib,sys
from .editcraft_core import run_plan

def main(folder):
 if os.environ.get('FOLD_ENGINE_ROLE')!='editcraft_cloud':raise RuntimeError('Production scientific execution requires the selected EditCraft cloud runtime.')
 folder=pathlib.Path(folder);os.environ['FOLD_EDITCRAFT_JOB_DIR']=str(folder);plan=json.loads((folder/'plan.json').read_text())
 def checkpoint(event):
  with (folder/'events.jsonl').open('a') as log:log.write(json.dumps(event)+'\n')
 try:
  result=run_plan(plan,checkpoint)
  (folder/'result.pending').write_text(json.dumps(result,allow_nan=False));(folder/'result.pending').replace(folder/'result.json')
 except BaseException as exc:
  # Do not print raw genomic inputs or source-specific private error messages.
  (folder/'failure.json').write_text(json.dumps({'errorType':type(exc).__name__,'error':'Scientific operation failed; inspect its input requirements.'}));return 1
 return 0
if __name__=='__main__':sys.exit(main(sys.argv[1]))
