"""Write a content manifest for a clean, unmodified local upstream checkout."""
import hashlib, json, pathlib, subprocess, sys
repo=pathlib.Path(__file__).resolve().parents[1];source=pathlib.Path(sys.argv[1]).expanduser().resolve();vendor=repo/'vendor'/'bindcraft2'
revision=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
if subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip():raise SystemExit('Upstream must be clean.')
files=subprocess.check_output(['git','-C',str(source),'ls-files','-z']).decode().strip('\0').split('\0')
manifest={'repository':subprocess.check_output(['git','-C',str(source),'remote','get-url','origin'],text=True).strip(),'revision':revision,'modified':False,'files':{}}
for name in sorted(files):
    original=(source/name).read_bytes();copied=(vendor/name).read_bytes()
    if original!=copied:raise SystemExit('Vendor copy differs: '+name)
    manifest['files'][name]=hashlib.sha256(original).hexdigest()
(repo/'vendor'/'bindcraft2-source.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(f'Pinned {len(files)} files at {revision}')
