"""Inspect bundled Mach-O absolute dependencies and loader-relative linkage.
This complements real relocation/import/inference tests; @rpath candidates are
reported, not treated as proof of dynamic-loader resolution.
"""
import argparse,json,pathlib,subprocess
p=argparse.ArgumentParser();p.add_argument('--runtime',required=True);p.add_argument('--output',required=True);a=p.parse_args();root=pathlib.Path(a.runtime).resolve()
magic={bytes.fromhex(x) for x in ('cffaedfe','feedfacf','cafebabe','bebafeca','cefaedfe','feedface')};files=[]
for file in root.rglob('*'):
 if file.is_file() and not file.is_symlink():
  with file.open('rb') as stream:header=stream.read(4)
  if header in magic:files.append(file)
by_name={}
for file in files:by_name.setdefault(file.name,[]).append(str(file.relative_to(root)))
external=[];missing=[];rpaths=[];checks=[]
for file in files:
 output=subprocess.check_output(['/usr/bin/otool','-L',str(file)],text=True)
 identifiers=subprocess.check_output(['/usr/bin/otool','-D',str(file)],text=True).splitlines()[1:]
 identifiers={line.strip() for line in identifiers if line.strip() and not line.endswith(':')}
 dependencies=[line.strip().split(' (',1)[0] for line in output.splitlines()[1:] if line[:1].isspace()]
 for dep in dependencies:
  if dep in identifiers:continue  # LC_ID_DYLIB is this file's identity, not a dependency.
  record={'file':str(file.relative_to(root)),'dependency':dep}
  if dep.startswith('/'):
   if not dep.startswith(('/usr/lib/','/System/Library/')) and not pathlib.Path(dep).is_relative_to(root):external.append(record)
  elif dep.startswith('@loader_path/'):
   resolved=(file.parent/dep[len('@loader_path/'):]).resolve()
   if not resolved.is_file():missing.append(record)
   elif not resolved.is_relative_to(root):external.append({**record,'resolved':str(resolved)})
  elif dep.startswith('@rpath/'):rpaths.append({**record,'internalCandidates':by_name.get(pathlib.Path(dep).name,[])})
 checks.append({'file':str(file.relative_to(root)),'dependencies':dependencies})
report={'state':'passed_absolute_and_loader_path_checks' if not external and not missing else 'external_or_missing_dependencies','runtime':str(root),'machOFiles':len(files),'externalDependencies':external,'missingLoaderRelativeDependencies':missing,'rpathCandidates':rpaths,'checks':checks,'scope':'Absolute and @loader_path dependency audit. @rpath entries require actual relocation/import/inference validation; this report alone is not standalone acceptance.'}
pathlib.Path(a.output).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('state','machOFiles','externalDependencies','missingLoaderRelativeDependencies')},indent=2))
if external or missing:raise SystemExit(1)
