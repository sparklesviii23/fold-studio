"""NCI Genomic Data Commons (open access) → the cohort layout used by Patient genomics, so every analysis runs unchanged.

    python gdc.py <library root> <GDC project id>

What is imported: open-access somatic mutation calls (GDC "Masked Somatic Mutation" pipeline, canonical-transcript consequences)
for the same gene panel as the cBioPortal cohorts, and case-level survival (vital status, days to death or last follow-up, age at
diagnosis). Not imported: copy number (no open gene-level calls on this route) and expression. Cohort id: gdc_<project id>.
Licence: GDC open-access data (NIH Genomic Data Sharing policy); controlled-access data are never requested.
"""
import hashlib
import json
import math
import pathlib
import re
import sys
import time
import urllib.request

API = 'https://api.gdc.cancer.gov'
SO = {'missense_variant': 'Missense_Mutation', 'stop_gained': 'Nonsense_Mutation', 'frameshift_variant': 'Frame_Shift_Del', 'splice_acceptor_variant': 'Splice_Site',
      'splice_donor_variant': 'Splice_Site', 'inframe_deletion': 'In_Frame_Del', 'inframe_insertion': 'In_Frame_Ins', 'start_lost': 'Translation_Start_Site',
      'stop_lost': 'Nonstop_Mutation', 'protein_altering_variant': 'Missense_Mutation', 'synonymous_variant': 'Silent', 'splice_region_variant': 'Splice_Region'}


def study_id(project):
    return 'gdc_' + re.sub(r'[^a-z0-9]+', '_', project.lower()).strip('_')


def _post(path, body, digest):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
    raw = urllib.request.urlopen(req, timeout=300).read(); digest.update(raw)
    return json.loads(raw)['data']


def _all(path, filters, fields, digest, log, size=5000):
    out, start = [], 0
    while True:
        d = _post(path, {'filters': filters, 'fields': ','.join(fields), 'size': size, 'from': start, 'format': 'JSON'}, digest)
        out += d['hits']; total = d['pagination']['total']; start += size
        log(f'{path}: {len(out)} of {total}')
        if start >= total:
            return out


def projects():
    raw = urllib.request.urlopen(f'{API}/projects?size=200&fields=project_id,name,primary_site,program.name,summary.case_count&sort=summary.case_count:desc', timeout=60).read()
    return [{'id': h['project_id'], 'name': h.get('name'), 'program': (h.get('program') or {}).get('name'), 'site': h.get('primary_site'), 'cases': (h.get('summary') or {}).get('case_count')}
            for h in json.loads(raw)['data']['hits']]


def install(root, project, log=print):
    import types
    import cancer_genomics as G
    s = types.SimpleNamespace(root=root); sid = study_id(project); d = G._dir(s, sid); raw = d / 'raw'; raw.mkdir(exist_ok=True); h = hashlib.sha256()
    proj = {'op': 'in', 'content': {'field': 'cases.project.project_id', 'value': [project]}}
    genes = G.genes_for(s); (d / 'genes.json').write_text(json.dumps(genes))
    files = _all('/files', {'op': 'and', 'content': [proj, {'op': 'in', 'content': {'field': 'data_type', 'value': ['Masked Somatic Mutation']}},
                                                      {'op': 'in', 'content': {'field': 'access', 'value': ['open']}}]}, ['cases.case_id', 'cases.submitter_id'], h, log)
    profiled = sorted({c['submitter_id'] for f in files for c in f.get('cases', [])})
    if not profiled:
        raise SystemExit(f'{project} has no open-access mutation calls in GDC.')
    cases = _all('/cases', proj, ['submitter_id', 'demographic.vital_status', 'demographic.days_to_death', 'diagnoses.days_to_last_follow_up', 'diagnoses.age_at_diagnosis',
                                  'diagnoses.primary_diagnosis', 'diagnoses.tumor_stage', 'diagnoses.ajcc_pathologic_stage', 'follow_ups.days_to_follow_up'], h, log)
    occ = _all('/ssm_occurrences', {'op': 'and', 'content': [{'op': 'in', 'content': {'field': 'case.project.project_id', 'value': [project]}},
                                                             {'op': 'in', 'content': {'field': 'ssm.consequence.transcript.gene.symbol', 'value': sorted(genes)}}]},
               ['case.submitter_id', 'ssm.ssm_id', 'ssm.consequence.transcript.gene.symbol', 'ssm.consequence.transcript.consequence_type', 'ssm.consequence.transcript.aa_change',
                'ssm.consequence.transcript.is_canonical'], h, log)
    muts, kept = [], 0
    for o in occ:
        cid = o['case']['submitter_id']; sample = cid + '-gdc'
        for c in o['ssm'].get('consequence', []):
            tr = c.get('transcript') or {}; g = (tr.get('gene') or {}).get('symbol')
            if not tr.get('is_canonical') or g not in genes:
                continue
            aa = tr.get('aa_change') or ''; m = re.search(r'(\d+)', aa)
            muts.append({'sampleId': sample, 'patientId': cid, 'entrezGeneId': genes[g], 'gene': {'hugoGeneSymbol': g, 'entrezGeneId': genes[g]}, 'proteinChange': aa,
                         'proteinPosStart': int(m.group(1)) if m else None, 'mutationType': SO.get(tr.get('consequence_type'), tr.get('consequence_type') or 'Unknown'),
                         'ncbiBuild': 'GRCh38', 'ssmId': o['ssm']['ssm_id']}); kept += 1
    samples = [p + '-gdc' for p in profiled]
    (raw / 'mutations.json').write_text(json.dumps(muts)); (raw / 'cna.json').write_text('[]')
    (raw / 'sample_lists.json').write_text(json.dumps([{'sampleListId': f'{sid}_sequenced', 'sampleIds': samples}, {'sampleListId': f'{sid}_cna', 'sampleIds': samples}]))
    (raw / 'clinical_sample.json').write_text(json.dumps([{'sampleId': p + '-gdc', 'patientId': p, 'clinicalAttributeId': 'SOURCE', 'value': 'GDC'} for p in profiled]))
    pcl = []
    for c in cases:
        dem, dx = c.get('demographic') or {}, (c.get('diagnoses') or [{}])[0]
        fu = [f.get('days_to_follow_up') for f in c.get('follow_ups') or [] if f.get('days_to_follow_up') is not None]   # GDC keeps follow-up here
        last = max(fu + ([dx['days_to_last_follow_up']] if dx.get('days_to_last_follow_up') is not None else []), default=None)
        dead = dem.get('vital_status') == 'Dead'; days = dem.get('days_to_death') if dead else last
        rows = {'OS_STATUS': '1:DECEASED' if dead else '0:LIVING' if dem.get('vital_status') == 'Alive' else None, 'OS_MONTHS': None if days is None else f'{days / 30.4375:.2f}',
                'AGE': None if dx.get('age_at_diagnosis') is None else f'{dx["age_at_diagnosis"] / 365.25:.1f}', 'STAGE': dx.get('ajcc_pathologic_stage') or dx.get('tumor_stage'), 'DIAGNOSIS': dx.get('primary_diagnosis')}
        pcl += [{'patientId': c['submitter_id'], 'clinicalAttributeId': k, 'value': v} for k, v in rows.items() if v not in (None, 'not reported', 'Not Reported')]
    (raw / 'clinical_patient.json').write_text(json.dumps(pcl))
    manifest = {'source': 'NCI GDC (open access)', 'study': sid, 'project': project, 'name': f'{project} (GDC, mutations only)', 'citation': 'Grossman RL et al. Toward a shared vision for cancer genomic data. N Engl J Med 2016;375:1109.',
                'genes': len(genes), 'geneSource': 'same panel as the cBioPortal cohorts', 'sampleLists': {f'{sid}_sequenced': len(samples)}, 'mutations': kept, 'cases': len(cases),
                'notImported': 'copy number and expression (no open gene-level calls on this route); copy-number alterations therefore never count as altered',
                'sha256': h.hexdigest(), 'licence': 'GDC open-access data; controlled-access data are not requested', 'installed': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (d / 'manifest.json').write_text(json.dumps(manifest, indent=1)); log(f'{sid} ready: {len(samples)} profiled cases, {kept} panel mutations')
    return manifest


if __name__ == '__main__':
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    install(sys.argv[1], sys.argv[2])
