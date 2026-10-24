"""Read-only client audit and saved cloud evidence; never schedules science."""
import pathlib
ACTIONS={'cloud_engine_audit'}
def dispatch(s,action,p):
 if action not in ACTIONS:raise ValueError('Unsupported audit action.')
 candidates=[s.root/'cloud-qualification/engine-audit.md',pathlib.Path(__file__).resolve().parents[1]/'docs/RAPID_COMPLETE_ENGINE_AUDIT.md',pathlib.Path(__file__).with_name('RAPID_COMPLETE_ENGINE_AUDIT.md')]
 path=next((f for f in candidates if f.is_file()),None)
 if path is None:return {'components':[],'document':'Scientific audit is not yet available.','fullEngineComplete':False,'readOnly':True}
 if path.stat().st_size>256*1024:raise ValueError('Audit document exceeds the display limit.')
 doc=path.read_text();section=doc.split('## Implementation matrix',1)[-1].split('## Seven strategies',1)[0];rows=[]
 for line in section.splitlines():
  if not line.startswith('|'):continue
  cells=[v.strip().replace('`','') for v in line.strip('|').split('|')]
  if len(cells)!=6 or cells[0]=='Component' or not cells[0].strip('-: '):continue
  rows.append(dict(zip(('name','code','cloud','evidence','integration','remaining'),cells)))
 return {'components':rows,'document':doc,'fullEngineComplete':False,'readOnly':True,'source':'Saved scientific implementation audit','modelExecutionIsNotBiologicalValidation':True}
