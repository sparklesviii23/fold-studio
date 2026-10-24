"""Build a private, source-only deployable release; never include research/weights."""
import argparse,gzip,hashlib,json,pathlib,shutil,subprocess,tarfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--output',type=pathlib.Path,required=True);parser.add_argument('--boltzgen',type=pathlib.Path,default=ROOT.parent/'upstream/boltzgen');args=parser.parse_args()
out=args.output.absolute();out.mkdir(parents=True,exist_ok=True);release=out/'release'
if release.exists():shutil.rmtree(release)
release.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ignore(path,names):return [n for n in names if n in ('.git','__pycache__','.venv','weights','assets','tests','example','docs','dist','build') or n.endswith(('.pyc','.ipynb','.png','.jpeg','.jpg','.pt','.ckpt','.npz','.egg-info'))]
shutil.copytree(ROOT/'remote_worker',release/'worker',ignore=ignore)
analysis=release/'worker/native_analysis';analysis.mkdir(exist_ok=True)
for name in ('intelligence.py','biology_assessment.py','research.py','peptides.py','amino-acids.json'):shutil.copy2(ROOT/'scientific'/name,analysis/name)
(release/'scripts').mkdir();shutil.copy2(ROOT/'scripts/qualify-rapid-gpu.py',release/'scripts/qualify-rapid-gpu.py')
sources=release/'sources';sources.mkdir()
for name,source,revision,allowed in [('bindcraft2',ROOT/'vendor/bindcraft2','c0ee638d11bc010817c2c97ee58ed5c323e664e2',['bindcraft','settings','scaffolds','bindcraft.py','pyproject.toml','LICENSE']),('boltzgen',args.boltzgen,'a07fea1153111ef453aaea7a15697ee05de9291f',['src','pyproject.toml','LICENSE','README.md','PYPI_DESCRIPTION.md'])]:
 target=sources/name;target.mkdir()
 if name=='boltzgen':
  assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==revision
 for entry in allowed:
  src=source/entry
  if src.is_dir():shutil.copytree(src,target/entry,ignore=ignore)
  elif src.is_file():shutil.copy2(src,target/entry)
 (target/'rapid-source.json').write_text(json.dumps({'repository':name,'revision':revision,'modifications':'None; model weights excluded from deployment source.'},sort_keys=True))
 index={str(p.relative_to(target)):sha(p) for p in sorted(target.rglob('*')) if p.is_file()}
 (target/'rapid-files.json').write_text(json.dumps(index,sort_keys=True))
manifest={'version':'0.2.0','apiVersion':2,'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'sourceTreeIncludesUncommittedWorker':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),'privateResearchIncluded':False,'modelWeightsIncluded':False,'cudaQualified':False,'files':{str(p.relative_to(release)):sha(p) for p in sorted(release.rglob('*')) if p.is_file()}}
(release/'release.json').write_text(json.dumps(manifest,indent=2)+'\n')
archive=out/'fold-rapid-0.2.0.tar.gz'
def stable(info):
 info.uid=info.gid=0;info.uname=info.gname='';info.mtime=0;info.mode=0o755 if info.isdir() else 0o644
 return info
with archive.open('wb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as zipped,tarfile.open(fileobj=zipped,mode='w') as tar:tar.add(release,arcname='release',filter=stable)
(out/'release-artifact.json').write_text(json.dumps({'path':str(archive),'sha256':sha(archive),'bytes':archive.stat().st_size,'version':'0.2.0','modelsIncluded':False},indent=2)+'\n')
print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'sha256':sha(archive)}))
