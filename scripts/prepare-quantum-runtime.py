#!/usr/bin/env python3
"""Prepare only pinned, verified CPU wheels in disposable runtime staging."""
import argparse,hashlib,json,pathlib,platform,subprocess,tempfile,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=pathlib.Path,default=ROOT/'vendor/quantum-runtime.json');p.add_argument('--runtime',required=True,type=pathlib.Path);p.add_argument('--wheel-dir',type=pathlib.Path);p.add_argument('--allow-download',action='store_true');args=p.parse_args()
 spec=json.loads(args.manifest.read_text());python=args.runtime/'bin/python3.12';site=args.runtime/'lib/python3.12/site-packages';expected={**spec['requiredExisting'],**{r['package']:r['version'] for r in spec['packages']}}
 probe="import importlib.metadata as m,json,platform,sys;names="+repr(list(expected))+";print(json.dumps({'architecture':platform.machine(),'python':str(sys.version_info.major)+'.'+str(sys.version_info.minor),'versions':{n:(m.version(n) if list(m.distributions(name=n)) else None) for n in names}}))"
 result=json.loads(subprocess.run([str(python),'-I','-B','-c',probe],check=True,capture_output=True,text=True).stdout)
 if result['architecture']!=spec['architecture'] or result['python']!=spec['pythonVersion']:raise ValueError('Pinned CPU wheels require the pinned macOS arm64 CPython 3.12 runtime.')
 for name,version in spec['requiredExisting'].items():
  if result['versions'][name]!=version:raise ValueError('Preserve the tested scientific runtime; qualify dependency changes explicitly: '+name)
 missing=[r for r in spec['packages'] if result['versions'][r['package']] is None]
 for row in spec['packages']:
  actual=result['versions'][row['package']]
  if actual is not None and actual!=row['version']:raise ValueError('Do not silently replace a differently versioned CPU library: '+row['package'])
 if missing:
  with tempfile.TemporaryDirectory(prefix='quantum-wheels-',dir=args.runtime.parent) as tmp:
   wheels=[]
   for row in missing:
    cached=args.wheel_dir/row['filename'] if args.wheel_dir else None
    if cached and cached.is_file():path=cached
    else:
     if not args.allow_download:raise ValueError('Pinned CPU runtime missing. Supply verified wheels or explicitly authorize the manifest library download through its build flag; no trained models.')
     if not row['url'].startswith('https://files.pythonhosted.org/'):raise ValueError('Unexpected package source.')
     with urllib.request.urlopen(row['url'],timeout=45) as response:raw=response.read(row['bytes']+1)
     if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('CPU wheel failed its pinned source checksum.')
     path=pathlib.Path(tmp)/row['filename'];path.write_bytes(raw)
    if path.stat().st_size!=row['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Cached quantum wheel differs from the reviewed artifact.')
    wheels.append(str(path))
   subprocess.run([str(python),'-I','-m','pip','install','--no-index','--no-deps','--disable-pip-version-check','--target',str(site),*wheels],check=True)
 check="import importlib,json;names="+repr(list(expected))+";print(json.dumps({n:importlib.import_module(n).__version__ for n in names}))"
 actual=json.loads(subprocess.run([str(python),'-I','-B','-c',check],check=True,capture_output=True,text=True).stdout)
 if actual!=expected:raise ValueError('CPU runtime versions differ after preparation.')
 print('Pinned CPU libraries verified; no model downloads or scientific calculation started.')
if __name__=='__main__':main()
