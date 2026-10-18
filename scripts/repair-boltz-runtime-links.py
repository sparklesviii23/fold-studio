"""Repair only known absolute OpenMP dependencies in an owned staged Boltz runtime.
Original environments remain unchanged. Mathematical libraries/weights are not
replaced; extension load paths become relative to the retained internal libomp.
"""
import argparse,hashlib,json,os,pathlib,subprocess
p=argparse.ArgumentParser();p.add_argument('--runtime',required=True);p.add_argument('--audit',required=True);p.add_argument('--report',required=True);a=p.parse_args();root=pathlib.Path(a.runtime).resolve();audit=json.loads(pathlib.Path(a.audit).read_text())
if root.name!='python-boltz' or root.parent.name!='runtime-build':raise SystemExit('Repairs require the dedicated owned runtime-build/python-boltz staging directory.')
if pathlib.Path(audit['runtime'])!=root:raise SystemExit('Audit/runtime mismatch.')
target=root/'lib/python3.12/site-packages/torch/lib/libomp.dylib'
if not target.is_file():raise SystemExit('Internal OpenMP library missing.')
repairs=[]
for item in audit['externalDependencies']:
 file=(root/item['file']).resolve();old=item['dependency']
 if not file.is_relative_to(root) or pathlib.Path(old).name!='libomp.dylib':raise SystemExit('Unreviewed external dependency: '+json.dumps(item))
 new='@loader_path/'+os.path.relpath(target,file.parent);before=hashlib.sha256(file.read_bytes()).hexdigest()
 subprocess.run(['/usr/bin/install_name_tool','-change',old,new,str(file)],check=True,capture_output=True)
 subprocess.run(['/usr/bin/codesign','--force','--sign','-',str(file)],check=True,capture_output=True)
 repairs.append({'file':item['file'],'previousDependency':old,'relativeDependency':new,'beforeSha256':before,'afterSha256':hashlib.sha256(file.read_bytes()).hexdigest()})
manifest_path=root/'fold-runtime-manifest.json';manifest=json.loads(manifest_path.read_text())
for item in repairs:manifest['files'][item['file']]=item['afterSha256']
manifest['relocationRepairs']=repairs;manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
pathlib.Path(a.report).write_text(json.dumps({'state':'relinked_private_staging_copy','runtime':str(root),'internalOpenMPSha256':hashlib.sha256(target.read_bytes()).hexdigest(),'repairs':repairs,'scope':'Loader paths and ad hoc signatures only; library algorithms and model parameters unchanged. Requires subsequent audit and actual relocation/inference validation.'},indent=2)+'\n');print(len(repairs),'extension load paths repaired')
