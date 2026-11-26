#!/usr/bin/env python3
"""Lossless audit migration. Source occurrences are not invented requirements.

Original stable IDs and criteria are preserved. Exact textual matches may link
an Ultimate paragraph to old IDs; all other overlaps need human semantic review.
No keyword match or test-count percentage is treated as scientific acceptance.
"""
import copy,datetime,hashlib,json,pathlib,re

ROOT=pathlib.Path(__file__).resolve().parents[1]
DEST=ROOT/'docs/FOLD_ULTIMATE_COMPLETION_AUDIT'

def sha(raw):return hashlib.sha256(raw).hexdigest()
def normalized(text):return ' '.join(text.split())

def inventory():
 legacy_path=ROOT/'docs/EDITCRAFT_FULL_COMPLETION_AUDIT.json'
 legacy=json.loads(legacy_path.read_text());requirements=[];matches={}
 for feature in legacy['features']:
  for clause in feature['requirements']:
   matches.setdefault(normalized(clause['acceptanceCriterion']),[]).append(clause['id'])
   requirements.append({
    'id':clause['id'],'parentSpecification':feature['sourceDocument'],'parentFeatureId':feature['id'],
    'researchDomain':feature['group'],'scientificPurpose':feature['scientificPurpose'],
    'expectedFunctionality':clause['acceptanceCriterion'],'acceptanceCriteria':clause['acceptanceCriterion'],
    'acceptanceCriterionSha256':sha(clause['acceptanceCriterion'].encode()),
    'existingSourceFiles':clause.get('sourceFiles',[]),'implementationState':clause['status'],
    'uiState':'Clause-specific review pending; inherited section context is not acceptance.',
    'scientificComputationState':'See original clause evidence; no new qualification inferred.',
    'modalDeploymentState':'Not reverified by this audit migration.',
    'validationState':clause.get('assessmentState','unreviewed'),
    'tests':clause.get('requiredTests',[]),
    'evidenceArtifacts':clause.get('implementationEvidence',[])+clause.get('executionEvidence',[]),
    'remainingWork':clause.get('missingWork',feature.get('remaining','')),
    'externalDependencies':{key:clause.get(key,[]) for key in ('scientificDependencies','uiDependencies','cloudDependencies')},
    'licensingConstraints':'Verify applicable source, checkpoint and data terms before redistribution/deployment.',
    'estimatedImplementationComplexity':'Pending clause-specific assessment.',
    'resourceRequirements':clause.get('resourceRequirements',{'newPaidWorkApproved':False}),
    'historicalAssessment':copy.deepcopy(clause),
    'architectureOverride':'Full Fab execution is now cloud-only. Any earlier local Fab engineering obligation is historical and superseded; evidence is retained.'})
 raw=(ROOT/'docs/specifications/FOLD_ULTIMATE.md').read_bytes();lines=raw.decode().splitlines()
 sections=[];occurrences=[];current=None;pending=[];start=None
 def flush():
  nonlocal pending,start
  if pending:
   text='\n'.join(pending)
   occurrences.append({'sourceAnchor':f'ULT:L{start}', 'section':current,'sourceLine':start,
                       'sourceEndLine':start+len(pending)-1,'text':text,'sha256':sha(text.encode()),
                       'requirementIds':matches.get(normalized(text),[]),
                       'reconciliationState':'exact_legacy_text_match' if normalized(text) in matches else 'semantic_mapping_pending'})
  pending=[];start=None
 for number,line in enumerate(lines,1):
  heading=re.match(r'^## (\d+)\. (.+)$',line)
  if heading:
   flush();current=int(heading[1]);sections.append({'number':current,'title':heading[2],'sourceLine':number,'status':'Scope retained; section acceptance not established.'})
  if not line.strip():flush()
  else:
   if start is None:start=number
   pending.append(line)
 flush()
 if [s['number'] for s in sections]!=list(range(1,101)):raise ValueError('Ultimate directive section coverage differs.')
 requirements.append({
  'id':'UL-FAB-CLOUD-001','parentSpecification':'ULT','parentFeatureId':'ULT-02','researchDomain':'full_fab',
  'scientificPurpose':'Prevent further native full-Fab computation while preserving research history.',
  'expectedFunctionality':'Reject local full Fab generation, recovery, repeat and known Fab heavy downstream jobs before spawn; retain configuration/view/export; prepare original complete scaffold cloud campaigns.',
  'acceptanceCriteria':'Backend admission cannot be bypassed by local backend selection, legacy profile, direct native runner, candidate-only launch or queued worker. No historical data mutation. Original full chains and scientific preset preserved in approved cloud transport.',
  'existingSourceFiles':['scientific/scientific_capabilities.py','scientific/execution_policy.py','scientific/bindcraft_runner.py','scientific/biology_pipeline.py','remote_worker/fold_rapid/fab.py','remote_worker/fold_rapid/contracts.py','remote_worker/fold_rapid/unified.py','src/components/ModalComputePanel.tsx'],
  'implementationState':'Software-contract tested','uiState':'Native Fab format, local-execution refusal presentation, direct cloud handoff and real-target local campaign review verified; complete scientific run/import UI not yet validated.',
  'scientificComputationState':'A separately approved real cloud Fab attempt is running (reports/ultimate/fab-qualification.json); no complete scientific outcome yet. Prior cancelled five-update native attempt remains historical.',
  'modalDeploymentState':'Approved $1 CPU deployment verified; remote source checksum and full-Fab contract match. No GPU qualification.','validationState':'Local admission and original cloud asset/coordinate transport tests; not full Fab scientific qualification.',
  'tests':['tests/test_fab_cloud_policy.py','tests/test_fab_cloud_transport.py','tests/test_fab_campaign.py','src/components/FabCampaignControls.test.tsx'],
  'evidenceArtifacts':['reports/ultimate/fab-policy-tests.log','reports/ultimate/backend-tests.log','reports/ultimate/interface-tests.log','reports/ultimate/cloud-deployment.json','reports/ultimate/native-fab-review.json','reports/ultimate/build.log','reports/ultimate/fab-qualification.json','reports/ultimate/fab-startup-provider-log.json'],
  'remainingWork':'Authentic complete full-Fab trajectory or scientific rejection, independent redesign/refolding and original-framework/domain/disulfide/model-pool evidence.',
  'externalDependencies':{'cloud':['Approved qualified GPU runtime and original verified checkpoints']},
  'licensingConstraints':'Pinned BindCraft2 source and model terms; preserve notices and verify hosting rights.',
  'estimatedImplementationComplexity':'Admission implemented; scientific qualification requires a separately bounded cloud campaign.',
  'resourceRequirements':{'localFullFabAllowed':False,'maximumApprovedCloudQualificationUSD':7,'qualificationLocalId':'fb621be777fd47ba962c550e810de7e0','noAutomaticGpuUpgrade':True}})
 # Reviewed genuinely new domain: none of the five legacy EditCraft source
 # documents contains materials/periodic/crystal/ASE/LAMMPS scope. Retain each
 # materials paragraph as its own unimplemented requirement, not a menu claim.
 material_numbers={62,63,64,65,66,68,69};counters={}
 for occurrence in occurrences:
  if occurrence['section']==2:occurrence['requirementIds'].append('UL-FAB-CLOUD-001')
  if occurrence['section'] in material_numbers and not occurrence['requirementIds']:
   text=occurrence['text']
   if text.strip()=='---' or text.startswith('# PART ') or text.startswith('## '):continue
   number=occurrence['section'];counters[number]=counters.get(number,0)+1
   id=f'UL-MAT-{number:03d}-C{counters[number]:03d}'
   requirements.append({
    'id':id,'parentSpecification':'ULT','parentFeatureId':f'ULT-{number:02d}',
    'sourceAnchor':occurrence['sourceAnchor'],'researchDomain':'materials_science',
    'scientificPurpose':next(section['title'] for section in sections if section['number']==number),
    'expectedFunctionality':text,'acceptanceCriteria':text,'acceptanceCriterionSha256':occurrence['sha256'],
    'existingSourceFiles':[],'implementationState':'Not implemented',
    'uiState':'Not implemented; no empty workspace added.',
    'scientificComputationState':'No materials-specific qualified execution.',
    'modalDeploymentState':'No materials-specific qualified deployment.',
    'validationState':'Not validated','tests':[],'evidenceArtifacts':[],
    'remainingWork':'Implement the scoped real data model, computation where applicable, native workflow and reference acceptance; preserve periodic source coordinates and category memberships.',
    'externalDependencies':{'scientific':'Select appropriate original engine/data and independently validate this specific material class.'},
    'licensingConstraints':'Review engine, dataset and scientific-model terms before installation/distribution.',
    'estimatedImplementationComplexity':'Domain implementation and reference qualification required; detailed estimate pending.',
    'resourceRequirements':{'newPaidWorkApproved':False,'scope':'Separate approval before new paid work, model/data downloads or GPU allocation.'}})
   occurrence['requirementIds'].append(id);occurrence['reconciliationState']='reviewed_new_materials_requirement'

 legacy_ids={c['id'] for f in legacy['features'] for c in f['requirements']}
 assert len(requirements)==len(legacy_ids)+1+sum(counters.values()) and len(legacy_ids)==1933
 source={'id':'ULT','path':'docs/specifications/FOLD_ULTIMATE.md','sha256':sha(raw),'lines':len(lines)}
 return {'schemaVersion':1,'updated':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'complete':False,'scientificCertification':False,'completionPercentage':None,
  'inventoryReconciliationComplete':False,
  'scope':'All 1,933 original clauses retained with unchanged stable IDs and criteria, plus the new cloud-only Fab architecture and reviewed new materials-domain requirements. All 100 Ultimate sections and every nonempty source paragraph retained as source occurrences. Unmapped overlaps/new expanded domains require semantic reconciliation; these source anchors are not falsely counted as new accepted requirements.',
  'sources':legacy['sources']+[source,{'id':'legacy-audit','path':str(legacy_path.relative_to(ROOT)),'sha256':sha(legacy_path.read_bytes())}],
  'legacyRequirementCount':len(legacy_ids),'newRequirementCount':len(requirements)-len(legacy_ids),'requirements':requirements,
  'ultimateSections':sections,'ultimateSourceOccurrences':occurrences,
  'sourceReconciliation':{'exactLegacyTextMatches':sum(bool(o['requirementIds']) and o['section']!=2 for o in occurrences),
                         'pendingSemanticMapping':sum(o['reconciliationState']=='semantic_mapping_pending' for o in occurrences),
                         'missingOlderProteinSpecificationCoverage':'Earlier Project Metal/RAPID/Research/Cinema directives and broader source-level feature evidence must be reconciled into stable requirements. Existing implementation audit retained as context, not silently represented as complete clause coverage.'},
  'architecture':{'fullFab':'cloud_only','localFabEngineering':'retired; preserve original evidence and numerical drift limitation','historicalDataPreserved':True,'notarization':'deferred_local_use'},
  'releaseTrains':[{'number':i,'state':'in_progress' if i==1 else 'remaining','fullyAccepted':False} for i in range(1,11)],
  'externalGates':['Fresh explicit paid-work approval','Licensed Rosetta runtime and validation','Additional official model/data permissions and downloads','Real model/reference qualification','Legitimate SDK access for speculative PS5 work'],
  'evidenceContext':['docs/FOLD_IMPLEMENTATION_AUDIT.md','reports/fold-implementation-audit.json','docs/EDITCRAFT_FULL_COMPLETION_AUDIT.json','reports/editcraft/requirement-closure.json']}

def render(value):
 lines=['# fold ultimate completion audit','',
  'The platform is unfinished. This audit preserves prior scope and separates tested software contracts from scientific qualification. No completion percentage is assigned.','',
  '## Architectural change','',
  'Full Fab is cloud-only. Native launch, recovery, repeat, direct-runner and known Fab downstream entry points reject before computation. Local history, cancelled attempts, model assets and read-only molecular workflows remain available. The independent-trajectory numerical drift limitation remains historical evidence.','',
  'The cloud form supports the original complete upstream Fab scaffold without a free binder-length control. Cloud source/transport checks do not establish a validated complete Fab campaign. The approved source update is deployed on Modal: CPU inventory, remote source hash and Fab-contract checks passed. Native handoff and a full 115-residue hPDL1 local review passed. One separately approved cloud-only full-Fab campaign is running; its real source preflight retains the original model pools and filters. No complete scientific outcome is claimed.','',
  '## Scope accounting','',
  f"- {value['legacyRequirementCount']:,} original clauses retained with unchanged identifiers and acceptance text.",
  f"- {value['newRequirementCount']} reviewed new requirements: UL-FAB-CLOUD-001 and the materials-domain paragraphs, absent from the five legacy EditCraft specifications.",
  '- All 100 Ultimate sections and every nonempty source paragraph are retained with source anchors and hashes.',
  f"- {value['sourceReconciliation']['pendingSemanticMapping']} source paragraphs still need semantic reconciliation. An exact-text match is traceability only.",
  '- Earlier protein/cloud/cinema directives still need full stable-ID reconciliation; the prior implementation audit remains evidence context.',
  '- Materials categories, life-science categories, infrastructure, speculative extensions and required demonstrations remain visible below. None is accepted merely because its heading is inventoried.','',
  '## Feature-by-feature source coverage','',
  '| Section | Required scope | Acceptance |','|---|---|---|']
 lines += [f"| {s['number']} | {s['title']} | Not established |" for s in value['ultimateSections']]
 lines += ['', '## Next acceptance gates','',
  '1. Complete semantic mapping and clause-specific source/evidence review, preserving stable identifiers and distinguishing superseded local Fab obligations.',
  '2. Native build and the approved CPU deployment checks passed. The approved $7 full-Fab qualification is running on the deployed A100 40 GB; no automatic retry or upgrade. Further paid work requires fresh approval.',
  '3. Run a genuine complete full-Fab attempt with original full target/heavy/light chains, model pools, settings and reproducibility; record acceptance or scientific rejection honestly.',
  '4. Complete downstream two-chain redesign/refolding, independent model evidence and native import/inspection. Single-chain seeded Fab refinement remains refused.',
  '5. Continue the ten release trains in dependency order. BoltzGen/ESM/RFdiffusion/Rosetta, advanced EditCraft, materials and fresh-machine acceptance remain incomplete.','',
  '## Evidence and limitations','',
  'The companion JSON contains each original criterion, its unmodified historical assessment, source/test/evidence context, remaining work, dependencies, licensing, resource and acceptance fields. Missing clause-specific validation is explicit; the audit migration does not promote historical statuses. Existing scientific results are described in FOLD_IMPLEMENTATION_AUDIT.md. Notarization remains deferred for local use.']
 return '\n'.join(lines)+'\n'

if __name__=='__main__':
 value=inventory();DEST.with_suffix('.json').write_text(json.dumps(value,indent=2)+'\n');DEST.with_suffix('.md').write_text(render(value))
 print(json.dumps({key:value[key] for key in ('complete','legacyRequirementCount','newRequirementCount','inventoryReconciliationComplete')}))
