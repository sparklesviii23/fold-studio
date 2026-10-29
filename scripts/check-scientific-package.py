"""Check the actual bundled service before signing or replacing the current app."""
import ast
import json
import pathlib
import subprocess
import sys


def check_sources():
    repo = pathlib.Path(__file__).resolve().parents[1]
    source = repo / 'scientific'
    configured = json.loads((repo / 'src-tauri/tauri.conf.json').read_text())['bundle']['resources']
    pending, visited = ['worker'], set()
    while pending:
        name = pending.pop()
        if name in visited:continue
        visited.add(name)
        if configured.get('../scientific/' + name + '.py') != 'scientific/' + name + '.py':
            raise RuntimeError('Scientific source is absent or misplaced in packaging resources: ' + name)
        for node in ast.walk(ast.parse((source / (name + '.py')).read_text())):
            names = [item.name for item in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            for imported in names:
                local = imported.split('.')[0]
                if (source / (local + '.py')).is_file():pending.append(local)
    print('Pre-build scientific resource closure passed:', len(visited), 'local modules.')


def check(app):
    resources = pathlib.Path(app).resolve() / 'Contents/Resources'
    scientific = resources / 'scientific'
    source = pathlib.Path(__file__).resolve().parents[1] / 'scientific'
    pending, visited = ['worker'], set()
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        module = scientific / (name + '.py')
        if not module.is_file():
            raise RuntimeError('Missing packaged scientific module: ' + name)
        tree = ast.parse(module.read_text())
        for node in ast.walk(tree):
            names = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            for imported in names:
                local = imported.split('.')[0]
                if (source / (local + '.py')).is_file():
                    pending.append(local)
    python = resources / 'runtime/bin/python3'
    subprocess.run([str(python), '-B', '-c', 'import sys;sys.path.insert(0,sys.argv[1]);import worker;assert worker.research.ACTIONS and worker.cinema.ACTIONS', str(scientific)], check=True, timeout=60)
    print('Packaged scientific service imports successfully; checked', len(visited), 'local modules.')
    provider=source.parents[1]/'runtimes/biology-services/bin/python'
    if provider.is_file():
        # Exercise the actual supervisor -> isolated parser route with a private
        # disposable synthetic library. No network request or model computation.
        code="""import sys,pathlib,tempfile,json
sys.path.insert(0,sys.argv[1])
from worker import Service
with tempfile.TemporaryDirectory(prefix='fold-package-cloud-review-') as tmp:
 s=Service(pathlib.Path(tmp));project=s.project_create({'name':'Synthetic packaged control test'})['id']
 with s.db:s.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('biologyServicesPython',json.dumps(sys.argv[2])))
 rows=[];n=1
 for i,name in enumerate(['ALA','CYS','ASP','GLU'],1):
  for atom,d,element in [('N',-.8,'N'),('CA',0,'C'),('C',.8,'C'),('O',1.3,'O')]:
   rows.append(f'ATOM  {n:5d} {atom:^4s} {name:3s} A{i:4d}    {i*3+d:8.3f}{0:8.3f}{0:8.3f}  1.00 50.00          {element:>2s}');n+=1
 target=pathlib.Path(tmp)/'fixture.pdb';target.write_text('\\n'.join(rows)+'\\nEND\\n')
 record=s.import_structure({'projectId':project,'path':str(target)})
 s.dispatch('biology_modal_configure',{'projectId':project,'configuration':{'appName':'package-fixture','imageDigest':'example.org/fixture@sha256:'+'a'*64,'gpu':'A100-80GB','maxSeconds':600,'hourlyEstimateUSD':2.4984}})
 value=s.dispatch('biology_unified_prepare',{'projectId':project,'structureId':record['id'],'targetChains':['A'],'binderChains':[],'strategy':'de_novo','generators':[{'engine':'bindcraft2','design':{'modality':'peptide','lengths':[20],'count':1,'attempts':1}}],'workflow':{'redesign':[],'predictors':['af2_multimer'],'rosetta':False,'count':1},'stageSeconds':60,'seconds':600,'maxEstimatedUSD':2,'seed':43})
 assert value['state']=='prepared' and value['configuration']['gpu']=='A100-80GB'
 assert 'contentBase64' not in value['manifest']['target'] and not value['blockers']
 assert not any(row.get('campaignId') for row in s.dispatch('biology_modal_jobs',{'projectId':project}))
 s.db.close()
print('Packaged native cloud review passed; no upload or GPU allocation.')
"""
        subprocess.run([str(python),'-B','-c',code,str(scientific),str(provider)],check=True,timeout=60)


if __name__ == '__main__':
    check_sources() if sys.argv[1] == '--sources' else check(sys.argv[1])
