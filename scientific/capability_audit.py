"""FOLD coverage assessment. Registry discovery is never scientific validation."""
import pathlib, json

def assess(current):
    baseline=json.loads((pathlib.Path(__file__).parent/'pinned-capabilities-1.12.json').read_text())
    live={(r['kind'],r['name']):r for r in current['capabilities']}
    evidence_path=pathlib.Path(__file__).parent/'validation-evidence-current.json'
    if not evidence_path.exists():evidence_path=pathlib.Path(__file__).parent/'validation-evidence-4.2.json'
    evidence=json.loads(evidence_path.read_text()) if evidence_path.exists() else {'capabilities':[]}
    verified={(r['kind'],r['name']):r for r in evidence['capabilities']}
    rows=[]
    for source in [*baseline['capabilities'],*current['capabilities']]:
        key=(source['kind'],source['name'])
        if any((r['kind'],r['name'])==key for r in rows):continue
        row=dict(source);available=key in live;kind=key[0]
        row.update(upstreamAvailable=available,scientificImplementation='Original separately installed ChimeraX 1.12',
            originalChimeraXUIRequired=False,functionalityTested=False,scientificOutputValidated=False,
            status='Partial',integrationMethod='GUI-free scientific session; FOLD presentation adapter',
            foldAccess='Scientific Tools Library; Molecular Console; Scientific Python',
            limitations='Enumerated only. Complete parameter, dataset and output validation remains pending.',
            implementationPlan='Exercise the original API with a representative fixture, add FOLD controls and validate numerical and visual outputs.')
        if kind=='command':
            if available:row['metadata']=live[key].get('metadata',{})
            else:row.update(status='Blocked',originalChimeraXUIRequired=True,limitations='Not registered by the pinned GUI-free session; GUI initialization or another dependency is required.',implementationPlan='Inspect registration and isolate a non-GUI implementation. Adapt the scientific API without opening the upstream interface.')
        elif kind in ('tool','menu','preference'):
            row.update(status='Blocked',originalChimeraXUIRequired=True,foldAccess='Scientific Tools Library inventory; related commands / Python where compatible',
                limitations='Original Qt presentation is intentionally unavailable. This complete interaction has not been reconstructed.',
                implementationPlan='Inspect the upstream tool API, separate its Qt dependencies, build a FOLD panel with all parameters, then validate each operation.')
        elif kind=='representation':
            row['foldAccess']='Appearance Laboratory and Molecular Console'
            row['limitations']='Native molecular atoms, bonds, colours and surface meshes; Mol* ribbons/materials. Volume ray casting and exact upstream rendering are not implemented.'
        elif kind=='format':
            row['foldAccess']='Molecular Console native open/save; Library PDB/mmCIF import; Imaging Laboratory map import'
            row['limitations']='Format registration is confirmed. Individual reader/writer options and visual adapters require per-format tests.'
        elif kind=='bundle':
            row['limitations']='Installed bundle retained. Compatible non-GUI APIs and registered commands are accessible; its original GUI is blocked. External services, hardware and licenses may apply.'
        if key in verified:
            row.update(verified[key])
        rows.append(row)
    current.update(capabilities=rows,count=len(rows),completeParityVerified=False,integrated=False,
        scope='Pinned 1.12 GUI registry plus live GUI-free registry. Every registered entry is accounted for; workflows and scientific algorithms require additional scenario coverage.',
        validationEvidence={k:v for k,v in evidence.items() if k!='capabilities'},
        originalUIExposed=False,headlessCommandCount=sum(r['kind']=='command' and r['upstreamAvailable'] for r in rows))
    return current
