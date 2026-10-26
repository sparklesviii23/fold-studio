#!/usr/bin/env python3
"""Extend the authoritative clause manifest without replacing its original IDs.
Acceptance adjudications live in the manifest, never inferred from test counts.
Unreviewed clauses are explicitly excluded from verified completion counts.
"""
import collections,datetime,hashlib,json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[1]
PATH=ROOT/'docs/EDITCRAFT_FULL_COMPLETION_AUDIT.json'
ORIGINAL_CLAUSE_SHA256='2e4f10c11540bcac4228eecf4c9014e00b2a1f6692ca3d4b8ee0a94638001328'
SOURCES={'VII':'/Users/vii/.codex/attachments/27596cbd-ccf0-470b-8c06-ce8c82a8c881/Pasted text.txt','VIII':'/Users/vii/.codex/attachments/47f58c32-62c4-46ee-a6ea-622ac8e07e15/Pasted text.txt'}
STATES=['not_started','partially_implemented','implemented','offline_tested','real_scientific_execution_tested','independently_validated','native_workflow_verified','fully_accepted','externally_blocked']
def markdown(audit,summary):
 def cell(value):return str(value).replace('|','\\|').replace('\n',' ')
 lines=['# EditCraft requirement closure','', '**The complete specification remains unfinished.** Installed software, real execution, independent validation and native acceptance are tracked separately.','',f"The audit retains all {summary['originalAcceptanceParagraphs']:,} original acceptance paragraphs and appends Directives VII and VIII: {summary['sections']} sections and {summary['totalAcceptanceParagraphs']:,} paragraphs in total. {summary['reviewedParagraphs']} paragraphs have an explicit clause review; {summary['pendingClauseReview']:,} still need that review. {summary['fullyAcceptedParagraphs']} narrow paragraphs and {summary['fullyAcceptedSections']} whole sections are fully accepted.",'','Unreviewed `not_started` entries describe acceptance-review progress, not proof that all related implementation is absent. Grouped lists and qualifications remain intact in the JSON; no subjective platform percentage is calculated. Accepted source/evidence hashes cannot be silently refreshed after changes.','', '## Actual execution evidence','', '- Pinned Rule Set 3, BE-DICT and PRIDICT2 public CPU inference: `reports/editcraft/model-validation.json`. Only the recorded Rule Set 3 examples reproduce published numeric reference values; independent held-out qualification remains.','- Real public 1EHZ ViennaRNA calculation, parent-base mapping and native diagram/stem/probability selection: `reports/editcraft/rna-3d-validation.json` and associated `native-rna-*` receipts. Chemical modification thermodynamics are not modeled.','- DNA, RNA and complete 146,921-atom ribosome coordinate preservation: `reports/editcraft/native-coordinate-preservation.json`; representation/visibility and source receipts are separate.','- Cas-OFFinder implementation, source hash, exact reference contracts and CPU qualification status: `reports/editcraft/offtarget-validation.json` when present. A pending or failed run is not scientific acceptance.','', '## Section matrix','', '| ID | Requirement section | Implementation state | Clause review | Fully accepted | Remaining |','|---|---|---|---|---|---|']
 for feature in audit['features']:
  clauses=feature['requirements'];reviewed=sum(c['assessmentState']=='reviewed' for c in clauses);accepted=sum(c['status']=='fully_accepted' for c in clauses)
  lines.append('| '+' | '.join(map(cell,[feature['id'],feature.get('feature',feature['id']),feature.get('status','unreviewed'),f'{reviewed}/{len(clauses)}',f'{accepted}/{len(clauses)}',feature.get('remaining','Detailed review remains.')]))+' |')
 lines+=['','## Sources','']
 for source in audit['sources']:lines.append('- '+source['id']+': `'+source['path']+'`, SHA-256 `'+source['sha256']+'`.')
 lines+=['','## Next outstanding scientific requirements','', 'Remaining work includes the other CRISPR/editor/RNA/foundation methods, human genome search qualification, experimental sequencing analysis, single-cell/perturbation and systems biology engines, trained-model independent benchmarks, original Intelligence Core, full workflow graph/replay, publishing and complete end-to-end acceptance. Their specific clauses remain in the authoritative JSON. No catalogue entry or passing test suite accepts these requirements.','']
 return '\n'.join(lines)
def update():
 audit=json.loads(PATH.read_text());original=[(r['id'],r['acceptanceCriterion']) for f in audit['features'] if f['sourceDocument'] in ('EC','LAB','MC') for r in f['requirements']]
 if hashlib.sha256(json.dumps(original,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()!=ORIGINAL_CLAUSE_SHA256:raise ValueError('Original acceptance text or IDs changed; use an explicit new specification revision.')
 if len(original)!=1349 or len({id for id,text in original})!=1349:raise ValueError('Original 1,349 clause identities must be preserved.')
 for namespace,filename in SOURCES.items():
  path=ROOT/'docs/specifications'/('EDITCRAFT-'+namespace+'.md')
  if not path.is_file():path=pathlib.Path(filename)
  text=path.read_text();checksum=hashlib.sha256(path.read_bytes()).hexdigest();source=next((s for s in audit['sources'] if s['id']==namespace),None)
  if source and source['sha256']!=checksum:raise ValueError('A directive changed; reconcile its existing clauses explicitly.')
  if not source:audit['sources'].append({'id':namespace,'path':str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),'sha256':checksum,'lines':len(text.splitlines())})
  headings=list(re.finditer(r'^# (\d+)\. (.+)$',text,re.M))
  for i,heading in enumerate(headings):
   id=namespace+'-'+heading[1].zfill(2)
   if any(f['id']==id for f in audit['features']):continue
   body=text[heading.end():headings[i+1].start() if i+1<len(headings) else len(text)]
   paragraphs=[p.strip() for p in re.split(r'\n\s*\n',body) if p.strip() and p.strip()!='---']
   audit['features'].append({'id':id,'feature':heading[2],'scientificPurpose':heading[2],'sourceDocument':namespace,'sourceLine':text[:heading.start()].count('\n')+1,'group':'molecular_observatory' if namespace=='VIII' else 'full_closure','status':'partially_implemented','sourceFiles':['scientific/molecular_observatory.py','scientific/polymer_identity.py','scientific/scene_bridge.py','src/components/MolecularBiologyPanel.tsx','src/components/StructureDiscovery.tsx'] if namespace=='VIII' else [],'executionEvidence':[],'testFiles':['tests/test_molecular_observatory.py','src/lib/polymerMapping.test.ts'] if namespace=='VIII' else [],'remaining':'Clause-level acceptance review and remaining functionality are required. Existing implementation and native evidence do not accept the entire section.','externalBlockers':[],'acceptanceComplete':False,'requirements':[{'id':id+'-C'+str(j).zfill(3),'acceptanceCriterion':p} for j,p in enumerate(paragraphs,1)]})
 for feature in audit['features']:
  for clause in feature['requirements']:
   clause.setdefault('status','not_started');clause.setdefault('assessmentState','unreviewed')
   clause.setdefault('sourceFiles',list(feature.get('sourceFiles',[])));clause.setdefault('implementationEvidence',[]);clause.setdefault('executionEvidence',[])
   clause.setdefault('missingWork','Perform clause-specific source and evidence review, then implement and verify every requested subitem. Section-level evidence is context only, not clause acceptance.')
   clause.setdefault('scientificDependencies',[]);clause.setdefault('uiDependencies',[]);clause.setdefault('cloudDependencies',[])
   clause.setdefault('requiredTests',list(feature.get('testFiles',[])));clause.setdefault('resourceRequirements',{'newPaidWorkApproved':False,'note':'Local source development and bounded offline checks are authorized. A fresh concrete approval is required for paid scientific execution.'})
   if clause['status'] not in STATES:raise ValueError('Unsupported acceptance state: '+clause['id'])
   if clause['status']=='fully_accepted' and (clause['assessmentState']!='reviewed' or not clause['executionEvidence']):raise ValueError('Full acceptance needs reviewed, applicable execution evidence: '+clause['id'])
   for evidence in clause['executionEvidence']:
    path=ROOT/evidence['path']
    if not path.is_file():raise ValueError('Missing acceptance evidence: '+evidence['path'])
    checksum=hashlib.sha256(path.read_bytes()).hexdigest()
    if evidence.get('sha256',checksum)!=checksum:raise ValueError('Acceptance evidence changed; explicitly re-review '+clause['id']+': '+evidence['path'])
    evidence['sha256']=checksum
   if clause['status']=='fully_accepted':
    snapshots=clause.setdefault('acceptedSourceSha256',{})
    for filename in clause['sourceFiles']:
     path=ROOT/filename
     if not path.is_file():raise ValueError('Missing accepted source: '+filename)
     checksum=hashlib.sha256(path.read_bytes()).hexdigest()
     if snapshots.get(filename,checksum)!=checksum:raise ValueError('Accepted source changed; revalidate '+clause['id']+': '+filename)
     snapshots[filename]=checksum
  feature['acceptanceComplete']=all(c['status']=='fully_accepted' for c in feature['requirements'])
 after=[(r['id'],r['acceptanceCriterion']) for f in audit['features'] if f['sourceDocument'] in ('EC','LAB','MC') for r in f['requirements']]
 if original!=after:raise ValueError('The original acceptance text or identity changed.')
 clauses=[r for f in audit['features'] for r in f['requirements']];reviewed=[r for r in clauses if r['assessmentState']=='reviewed']
 summary={'sections':len(audit['features']),'originalAcceptanceParagraphs':1349,'totalAcceptanceParagraphs':len(clauses),'reviewedParagraphs':len(reviewed),'pendingClauseReview':len(clauses)-len(reviewed),'fullyAcceptedParagraphs':sum(r['status']=='fully_accepted' for r in clauses),'fullyAcceptedSections':sum(f['acceptanceComplete'] for f in audit['features']),'statusCounts':dict(collections.Counter(r['status'] for r in reviewed)),'complete':all(f['acceptanceComplete'] for f in audit['features']),'countingPolicy':'Original paragraphs and qualifiers retained. Headings and grouped lists are not silently removed. Unreviewed clauses carry not_started for their acceptance review, which does not assert absence of all implementation; inherited feature source references are context, not evidence. No subjective completion percentage.'}
 audit.update(schemaVersion=2,updated=datetime.datetime.now(datetime.timezone.utc).isoformat(),complete=summary['complete'],closure=summary)
 PATH.write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n')
 (ROOT/'reports/editcraft/requirement-closure.json').write_text(json.dumps(summary,indent=2)+'\n')
 (ROOT/'docs/EDITCRAFT_FULL_COMPLETION_AUDIT.md').write_text(markdown(audit,summary))
 print(json.dumps(summary,indent=2))
if __name__=='__main__':update()
