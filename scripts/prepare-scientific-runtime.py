"""Assemble a relocatable CPython/JAX runtime from an existing tested environment.
No system installs are modified. Output must be new. Original package licenses,
dist-info and Python LICENSE remain present. Verify relocation before bundling.
"""
import argparse,hashlib,json,pathlib,shutil,subprocess,sys,os
p=argparse.ArgumentParser();p.add_argument('--python',required=True);p.add_argument('--output',required=True);p.add_argument('--resume',action='store_true');a=p.parse_args()
metadata=json.loads(subprocess.check_output([a.python,'-c','import sys,sysconfig,json;print(json.dumps({"base":sys.base_prefix,"site":sysconfig.get_path("purelib"),"version":sys.version.split()[0]}))'],text=True))
base=pathlib.Path(metadata['base']);site=pathlib.Path(metadata['site']);dest=pathlib.Path(a.output).absolute()
if dest.exists() and not a.resume:raise SystemExit('Runtime output must be new unless --resume is explicit.')
if shutil.disk_usage(dest.parent if dest.parent.exists() else dest.parent.parent).free<3*1024**3:raise SystemExit('At least 3 GiB free is required for runtime staging.')
def ignore(path,names):return [n for n in names if n in ('site-packages','__pycache__') or n.endswith('.pyc')]
if not a.resume:shutil.copytree(base,dest,symlinks=True,ignore=ignore)
target=dest/'lib'/('python'+'.'.join(metadata['version'].split('.')[:2]))/'site-packages';None if a.resume else shutil.copytree(site,target,symlinks=True,ignore=lambda path,names:[n for n in names if n=='__pycache__' or n.endswith('.pyc')])
for file in dest.rglob('*'):
 if file.is_symlink() and not file.resolve().is_relative_to(dest.resolve()):
  # The source runtime has three stale absolute build-directory links in docs/pkgconfig.
  # Repoint only to an existing same-directory counterpart; no external files copied.
  if file.name not in ('python3.1','python3.pc','python3-embed.pc'):raise RuntimeError('External runtime symlink: '+str(file))
  sibling=file.parent/pathlib.Path(os.readlink(file)).name
  if not sibling.is_file():raise RuntimeError('Missing internal symlink target: '+str(sibling))
  file.unlink();file.symlink_to(sibling.name)
python=dest/'bin/python3.12'
check=subprocess.run([str(python),'-I','-B','-c','import sys,jax,numpy,haiku,biotite,optax;print(sys.prefix);print(jax.__version__,jax.devices());print(jax.grad(lambda x:jax.numpy.sin(x))(1.0))'],text=True,capture_output=True,timeout=45)
if check.returncode:raise RuntimeError(check.stderr)
manifest={'schemaVersion':1,'pythonVersion':metadata['version'],'initialIsolatedProbe':check.stdout,'files':{str(f.relative_to(dest)):hashlib.sha256(f.read_bytes()).hexdigest() for f in dest.rglob('*') if f.is_file() and not f.is_symlink() and '__pycache__' not in f.parts}}
(dest/'fold-runtime-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(check.stdout)
