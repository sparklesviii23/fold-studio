"""Inventory exact pinned source imports, GPU assumptions and preset scope."""
import ast, json, pathlib, re, sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'))
from fold_engine import verify_source, UPSTREAM
report={'source':verify_source(),'declaredDependencies':(UPSTREAM/'pyproject.toml').read_text(),'imports':{},'acceleratorReferences':[],'modalities':{},'properties':{}}
for path in sorted((UPSTREAM/'bindcraft').rglob('*.py')):
 try:tree=ast.parse(path.read_text())
 except SyntaxError:continue
 names=sorted({node.names[0].name.split('.')[0] if isinstance(node,ast.Import) else (node.module or '').split('.')[0] for node in ast.walk(tree) if isinstance(node,(ast.Import,ast.ImportFrom)) and not getattr(node,'level',0)})
 for name in names:report['imports'].setdefault(name,[]).append(str(path.relative_to(UPSTREAM)))
 for num,line in enumerate(path.read_text().splitlines(),1):
  if re.search(r'cuda|cudnn|cuequivariance|nvidia|rocm|triton|\.devices\(|gpu_ids|pmap\(',line,re.I):report['acceleratorReferences'].append({'file':str(path.relative_to(UPSTREAM)),'line':num,'text':line.strip()})
for tier,key in [('modality','modalities'),('property','properties')]:
 for path in sorted((UPSTREAM/'settings'/tier).glob('*.json')):report[key][path.stem]={'preset':json.loads(path.read_text()),'configuration':'tested' if tier=='modality' and path.stem in ('binder','peptide') else 'not_started','nativeDesignExecution':'blocked'}
path=ROOT/'reports'/'bindcraft-audit.json';path.write_text(json.dumps(report,indent=2)+'\n');print(f'{len(report["imports"])} import roots, {len(report["acceleratorReferences"])} accelerator references, {len(report["modalities"])} modalities')
