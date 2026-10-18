"""Promote only scoped, successful live checks to the compatibility inventory."""
import csv,hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1];report=ROOT/'reports/chimerax-current-acceptance.json';data=json.loads(report.read_text());checks={c['name']:c for c in data['checks']}
if not data['passed'] or len(checks)!=25 or not all(c['passed'] for c in checks.values()):raise SystemExit('Expected complete successful live acceptance; no evidence promoted.')
scopes={
 'version':('Native: version','Installed interpreter version query',False),
 'select':('Native: select #1/A:20@CA','Exact model/author-chain/residue/atom selection and native selection reflection',False),
 'color':('Native: color sel orange','Native selected-atom orange coloring; broad palette/visual material parity unverified',False),
 'style':('Native: style sel stick','Native selected-atom stick style; complete representation parity unverified',False),
 'info atoms':('Native: info atoms #1/A:20','Selected author-residue atom information',False),
 'distance':('Real Cα distance','Two observed Cα atoms: native value agrees with expected 3.7908803727 Å within 1e-5 Å',True),
 'build start':('Installed build bundle command executes','Canonical ACDE peptide creation with explicit torsions; structure quality/activity unvalidated',False),
 'move':('Changed native coordinates invalidate mapping fingerprint','1 Å x translation invalidates coordinate correspondence and stale selection is refused',False),
 'open':('Exact source checksum and model mapping','Bundled ANGPTL3 mmCIF source import with source/model mapping',False),
 'matchmaker':('Native all-pair RMSD agrees with returned residuals','Known rigid transform plus single 5 Å Cα perturbation: all-pair RMSD residual agreement and pruning to 459 fitted pairs',True)}
evidence={'schemaVersion':1,'scope':'Scoped live acceptance on installed GUI-free ChimeraX 1.12; not comprehensive command or GUI equivalence','reportSha256':hashlib.sha256(report.read_bytes()).hexdigest(),'checksPassed':len(checks),'completeParityVerified':False,'capabilities':[]}
for name,(check,scope,scientific) in scopes.items():
 if check not in checks:raise SystemExit('Missing evidence: '+check)
 evidence['capabilities'].append({'kind':'command','name':name,'status':'Partial','functionalityTested':True,'scientificOutputValidated':scientific,'validationScope':scope,'limitations':'Only the stated fixture, syntax and output assertions were tested. Other arguments and full visual equivalence remain unverified.','evidenceCheck':check})
native_report=ROOT/'reports/native-hbonds-validation.json'
if native_report.exists():
 native=json.loads(native_report.read_text())
 if native.get('state')!='passed' or not native.get('pairs') or not native.get('sourceAssetUnchanged') or native.get('sharedAnalysisJob')!='completed':raise SystemExit('Native hydrogen-bond report is incomplete; evidence not promoted.')
 evidence['additionalReports']={native_report.name:{'sha256':hashlib.sha256(native_report.read_bytes()).hexdigest(),'state':'passed','scope':native['scope']}}
 evidence['capabilities'].append({'kind':'command','name':'hbonds','status':'Partial','functionalityTested':True,'scientificOutputValidated':True,'validationScope':native['scope'],'limitations':'Only the stated artificial fixture, strict criteria, cross-partner selection and output/export assertions were tested. Other arguments and full visual equivalence remain unverified.','evidenceCheck':'Strict native donor/acceptor identity and 2.8 Å geometry; shared job and exports','evidenceReport':native_report.name})
(ROOT/'scientific/validation-evidence-current.json').write_text(json.dumps(evidence,indent=2)+'\n')
baseline=json.loads((ROOT/'scientific/pinned-capabilities-1.12.json').read_text());by_name={r['name']:r for r in evidence['capabilities']}
with open(ROOT/'docs/CHIMERAX_COMMAND_COMPATIBILITY.csv','w',newline='') as file:
 writer=csv.DictWriter(file,lineterminator='\n',fieldnames=['command','status','nativeFunctionTested','scientificOutputChecked','scope','source']);writer.writeheader()
 for row in sorted((r for r in baseline['capabilities'] if r['kind']=='command'),key=lambda r:r['name']):
  verified=by_name.get(row['name']);writer.writerow({'command':row['name'],'status':'TESTED (scoped)' if verified else 'NOT VALIDATED','nativeFunctionTested':bool(verified),'scientificOutputChecked':verified['scientificOutputValidated'] if verified else False,'scope':verified['validationScope'] if verified else 'Registered inventory only; no command-specific acceptance evidence','source':row.get('source','')})
print(f"{len(by_name)} scoped command entries; {sum(r['scientificOutputValidated'] for r in evidence['capabilities'])} numerical output checks; no complete parity claim")
