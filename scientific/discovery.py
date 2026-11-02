"""Demo L · integrated discovery workflow: from a patient observation to candidate targets, each step a different kind of evidence.

    python discovery.py <library root> <run id>        (question read from oncology/discovery/<id>/question.json)

  1 Patients      cBioPortal cohort: how often the driver is altered, and its survival association      Experimental observation / Statistical association
  2 Dependencies  DepMap: genes more essential in lines carrying the driver, lineage-adjusted           Statistical association on measured CRISPR screens
  3 Drugs         GDSC: compounds whose response differs with the driver, lineage-adjusted              Statistical association on measured drug responses
  4 Mechanism     published ODE models: what inhibiting each candidate does, where a model contains it Mechanistic simulation
  5 Curated       evidence graph (CIViC, Open Targets) for the driver                                   Curated evidence
  6 Synthesis     candidates × lines of evidence, side by side; no composite score is computed

Steps do not pass numbers to each other; a step only proposes which genes the next step looks at. A candidate is a hypothesis
to test in the laboratory, never a recommendation.
"""
import json
import math
import pathlib
import sys
import time
import types


def step(n, title, evidence):
    return {'n': n, 'title': title, 'evidence': evidence, 'status': 'ran', 'rows': [], 'columns': [], 'notes': [], 'summary': ''}


def run(root, q, log=print):
    import cancer_genomics as G
    import drug_response as R
    import oncology_data as D
    import oncology_stats as S
    import perturbation as P
    s = types.SimpleNamespace(root=root); gene, study, lineage = q['gene'], q.get('study'), q.get('lineage')
    kind = q.get('kind') or ('hotspot' if gene in G.ONCOGENES else 'damaging'); top = int(q.get('candidates', 5)); t0 = time.time(); steps = []

    # 1 · patients
    st = step(1, 'Is the driver altered in patients, and does it track outcome?', 'Experimental observation (sequenced tumors) · Statistical association (survival)')
    if study:
        try:
            summ = G.summary(s, study); row = next((r for r in summ['genes'] if r['gene'] == gene), None)
            st['columns'] = ['measure', 'value']
            st['rows'].append(['tumors altered', f'{row["altered"]} of {summ["profiledSamples"]} ({row["freq"]:.0%})' if row else f'0 of {summ["profiledSamples"]}'])
            if row:
                st['rows'] += [['mutated / copy-number only', f'{row["mutated"]} / {row["cna"]}'], ['at recurrent positions', row['recurrent']]]
            try:
                sv = G.survival(s, study, gene); c = sv['cox'][0]
                st['rows'] += [['overall-survival hazard ratio (age-adjusted)', f'{c["hr"]:.2f} ({c["ci"][0]:.2f}–{c["ci"][1]:.2f}), p = {c["p"]:.2g}'], ['patients with follow-up', sv['patients']]]
            except ValueError as e:
                st['notes'].append(f'Survival not estimable: {e}')
            st['summary'] = f'{gene} is altered in {row["freq"]:.0%} of {summ["study"].get("name", study)} tumors.' if row else f'{gene} is not altered in this cohort.'
            st['notes'].append('Association in one retrospective cohort; not causal, unadjusted for stage and treatment.')
        except ValueError as e:
            st['status'] = 'unavailable'; st['summary'] = str(e)
    else:
        st['status'] = 'skipped'; st['summary'] = 'No cohort chosen.'
    steps.append(st); log(f'[{time.time() - t0:5.1f}s] step 1')

    # 2 · dependencies
    st = step(2, f'Which genes do {gene}-{kind} cell lines depend on more?', 'Statistical association (DepMap CRISPR gene effect, lineage fixed effects, BH-FDR)')
    cands, replicated, hits_all, rep, rel = [], None, [], None, None
    try:
        rel = D.Release(s); ms = S.mutation_scan(rel, gene, kind)
        hits = [h for h in ms['hits'] if h['q'] < 0.05 and h['beta'] < 0]
        cands = [h['gene'] for h in hits[:top]]; hits_all = hits
        st['columns'] = ['gene', 'Δ gene effect (mutant − wild type)', '95 % CI', 'q', f'median effect in {lineage}' if lineage else 'median effect']
        for h in hits[:15]:
            try:
                prof = S.gene_profile(rel, h['gene']); lin = next((l for l in prof['lineages'] if l['lineage'] == lineage), None)
                med = lin['median'] if lin else None
            except ValueError:
                med = None
            st['rows'].append([h['gene'] + (' (the driver itself)' if h['gene'] == gene else ''), h['beta'], f'{h["ci"][0]:.2f} to {h["ci"][1]:.2f}', h['q'], med])
        st['summary'] = (f'{len(hits)} genes are significantly more essential in {ms["mutant"]} {gene}-{kind} lines than in {ms["n"] - ms["mutant"]} others (q < 0.05); '
                         f'the top {len(cands)} go forward as candidates.') if hits else f'No gene is significantly more essential in {gene}-{kind} lines.'
        import sanger_score as SS
        if SS.installed(root) and hits:                  # replication in an independent screen (Sanger Project Score)
            rep = SS.replicate(root, rel, gene, [h['gene'] for h in hits[:15]], kind)
            st['columns'].append(f'Sanger Project Score Δ (p), {rep.get("mutant", 0)} mutant of {rep.get("lines", 0)} lines')
            for row, h in zip(st['rows'], hits[:15]):
                g = rep['genes'].get(h['gene']); row.append(f'{g["delta"]:.2f} (p {g["p"]:.1e}){" · replicates" if g["replicates"] else ""}' if g else (rep.get('note') or 'not screened'))
            replicated = {g for g, v in rep['genes'].items() if v['replicates']}
            st['notes'].append(f'Independent screen: {sum(c in replicated for c in cands)} of {len(cands)} candidates replicate in Sanger Project Score (Δ < 0, p < 0.05, same lineage adjustment; Behan et al. 2019).')
        else:
            replicated = None
            st['notes'].append('Install Sanger Project Score in the Data tab to test whether each dependency replicates in an independent screen.')
        st['notes'] += [f'DepMap {rel.release}, one model per patient ({ms["collapsedSamePatient"]} sister lines collapsed), adjusted for {ms["lineages"]} lineages.',
                        'A driver that is its own top hit is oncogene addiction, the expected positive control.']
    except ValueError as e:
        st['status'] = 'unavailable'; st['summary'] = str(e)
    steps.append(st); log(f'[{time.time() - t0:5.1f}s] step 2')

    # 3 · drugs
    st = step(3, f'Which compounds act differently on {gene}-{kind} lines?', 'Statistical association (GDSC measured LN_IC50, lineage fixed effects, BH-FDR)')
    drug_by_target = {}
    try:
        bs = R.biomarker_scan(s, gene, kind)
        sens = [r for r in bs['results'] if r['q'] < 0.05]
        st['columns'] = ['compound', 'annotated target', 'Δ LN_IC50 (mutant − wild type)', 'q', 'targets a candidate']
        for r in sens[:20]:
            tg = [P._gene(x) for x in r['target'].replace(';', ',').split(',') if x.strip()]
            hit = sorted(set(tg) & set(cands))
            for g in hit:
                drug_by_target.setdefault(g, []).append(r)
            st['rows'].append([r['drug'], r['target'], r['deltaLnIC50'], r['q'], ', '.join(hit) or '—'])
        more = sum(r['deltaLnIC50'] < 0 for r in sens)
        st['summary'] = f'{len(sens)} of {bs["drugsTested"]} compounds differ (q < 0.05): {more} more potent and {len(sens) - more} less potent in mutant lines.'
        st['notes'] += ['Negative Δ = mutant lines more sensitive (ln µM).', bs['caveat']]
    except ValueError as e:
        st['status'] = 'unavailable'; st['summary'] = str(e)
    steps.append(st); log(f'[{time.time() - t0:5.1f}s] step 3')

    # 4 · mechanism
    st = step(4, 'What does inhibiting each candidate do in mechanistic models?', 'Mechanistic simulation (published ODE models; 90 % knockdown or rate reduction)')
    mech, mech_rel = {}, {}
    st['columns'] = ['candidate', 'model', 'main pathway output', 'largest change anywhere in the model']
    for g in cands:
        for mid in P.MODELS:
            if g in P.MODELS[mid]['genes']:
                e = P.ode_model(mid, P._norm_perturbations([{'kind': 'gene', 'gene': g, 'strength': 0.9}]), {})
                if e['status'] == 'ran':
                    name = P.MODELS[mid]['name'].split(' (')[0]; mech_rel.setdefault(g, []).append((name, e.get('reliable'), e['metrics'][0][2] < e['metrics'][0][1] if e['metrics'] else None))
                    mech.setdefault(g, []).append(f'{name}: {e["primary"]}'); st['rows'].append([g, name, e['primary'], e['summary'] if e['summary'].rstrip('.') != e['primary'] else '—'])
    unmapped = [g for g in cands if g not in mech]
    st['summary'] = f'{len(mech)} of {len(cands)} candidates are represented in at least one model.' if cands else 'No candidates to simulate.'
    if unmapped:
        st['notes'].append('Not in any mechanistic model here: ' + ', '.join(unmapped) + '. Absence from a model says nothing about the biology.')
    st['notes'].append('A large change away from the main output is often feedback being released (e.g. Ras-GTP rising when RAF is knocked down).')
    st['notes'].append('Each model has its own cell context and parameters (see the Perturbation lab); results show what the model implies, not what a tumor does.')
    steps.append(st); log(f'[{time.time() - t0:5.1f}s] step 4')

    # 5 · curated
    st = step(5, f'What do curated clinical and database records say about {gene}?', 'Curated evidence (CIViC, Open Targets)')
    f = pathlib.Path(root) / 'oncology' / 'evidence' / gene / 'graph.json'
    if f.is_file():
        gr = json.loads(f.read_text()); st['columns'] = ['from', 'to', 'relation', 'strength', 'source', 'context']
        for x in [x for x in gr['edges'] if x['origin'] == 'curated'][:15]:
            st['rows'].append([x['source'].split(':', 1)[1], x['target'].split(':', 1)[1], x['relation'], x.get('strength', ''), x['database'], x.get('context', '')])
        st['summary'] = f'{len(st["rows"])} curated records shown from the {gene} evidence graph (built {gr["built"][:10]}).'
    else:
        st['status'] = 'unavailable'; st['summary'] = f'No evidence graph is built for {gene} (the Evidence graph tab currently covers KRAS).'
    steps.append(st)

    # 6 · synthesis
    st = step(6, 'Candidates and their independent lines of evidence', 'Synthesis (side by side; no composite score)')
    st['columns'] = ['candidate', 'dependency in mutant lines', 'replicates in Sanger screen', 'compound hitting it', 'mechanistic model', f'patients: {gene} altered']
    dep_rows = {r[0].split(' (')[0]: r for r in steps[1]['rows']}
    alt = steps[0]['rows'][0][1] if steps[0]['rows'] else '—'
    for g in cands:
        d = dep_rows.get(g); dr = sorted(drug_by_target.get(g, []), key=lambda r: r['deltaLnIC50'])
        st['rows'].append([g, f'Δ {d[1]:.2f}, q {d[3]:.1e}' if d else '—', '—' if replicated is None else 'yes' if g in replicated else 'no', f'{dr[0]["drug"]} (Δ {dr[0]["deltaLnIC50"]:.2f}, q {dr[0]["q"]:.1e})' if dr else '—',
                           '; '.join(mech.get(g, [])) or '—', alt])
    st['summary'] = 'Each column is a different kind of evidence. Agreement across columns strengthens a hypothesis; it does not make it a treatment.'
    st['notes'] = ['Not covered: normal-tissue toxicity, drug exposure in tumors, resistance, and whether the cell-line dependency holds in patients.']
    steps.append(st)
    scorecard = []
    if rel is not None and cands:
        try:
            scorecard = _scorecard(root, rel, gene, kind, cands, hits_all, rep, drug_by_target, mech_rel, steps)
        except Exception as e:                           # the scorecard never hides the steps
            scorecard = [{'candidate': '—', 'error': f'{type(e).__name__}: {e}'}]
    log(f'[{time.time() - t0:5.1f}s] scorecard')
    return {'scorecard': scorecard, 'title': f'{gene} ({kind})' + (f' · {lineage}' if lineage else '') + (f' · {study}' if study else ''), 'question': q, 'kind': kind, 'candidates': cands, 'steps': steps,
            'seconds': round(time.time() - t0, 1), 'created': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}


def _scorecard(root, rel, gene, kind, cands, hits, rep, drug_by_target, mech_rel, steps):
    """Per candidate: each dimension the directive lists, as evidence and text, never combined into a score."""
    import urllib.parse
    import urllib.request
    import numpy as np
    import oncology_stats as S
    E, em, genes, gi, keep, _ = S._rows(rel, 'gene_effect'); Mu, mm, mg, mgi, _ = rel.matrix('mut_' + kind); mrow = {m: i for i, m in enumerate(mm)}
    rows = [i for i in keep if em[i] in mrow]; x = np.array([float(Mu[mrow[em[i]], mgi[gene]] > 0) for i in rows])
    hit = {h['gene']: h for h in hits}; out = []
    for g in cands:
        h = hit.get(g); y = np.asarray(E[rows, gi[g]], float); y = np.where(np.isfinite(y), y, np.nanmean(y))
        naive = float(y[x > 0].mean() - y[x == 0].mean())                         # without lineage adjustment
        allv = np.asarray(E[keep, gi[g]], float); frac = float(np.nanmean(allv < -0.5))
        r = (rep or {}).get('genes', {}).get(g); drugs = sorted(drug_by_target.get(g, []), key=lambda d: d['deltaLnIC50'])
        mech = mech_rel.get(g, [])
        try:
            if g == gene:
                raise LookupError                        # the driver itself: co-mention counting is meaningless
            q = f'"{gene}" AND "{g}" AND cancer'
            n_lit = json.loads(urllib.request.urlopen('https://www.ebi.ac.uk/europepmc/webservices/rest/search?' + urllib.parse.urlencode({'query': q, 'format': 'json', 'pageSize': 1}), timeout=30).read())['hitCount']
        except LookupError:
            n_lit = -1
        except Exception:
            n_lit = None
        contra = []
        if r and not r['replicates']:
            contra.append(f'not significant in the Sanger screen (Δ {r["delta"]:.2f}, p {r["p"]:.2g})')
        if r and r['delta'] > 0:
            contra.append('opposite direction in the Sanger screen')
        if mech and len({m[2] for m in mech if m[2] is not None}) > 1:
            contra.append('mechanistic models disagree on the direction of the main output')
        missing = [m for m, ok in (('replication in an independent screen', r is not None), ('a compound engaging this target', bool(drugs)), ('a mechanistic model containing it', bool(mech)),
                                   ('patient outcome data for the candidate itself', False), ('normal-tissue toxicity data', False), ('in vivo or organoid validation', False)) if not ok]
        out.append({'candidate': g,
                    'support': f'DepMap Δ {h["beta"]:.2f} (q {h["q"]:.1e}) in {kind} {gene} lines' + (f'; {drugs[0]["drug"]} more potent in mutant lines (Δ LN_IC50 {drugs[0]["deltaLnIC50"]:.2f}, q {drugs[0]["q"]:.1e})' if drugs else '') if h else '—',
                    'replication': 'not installed' if rep is None else rep.get('note') or ('replicates' if r and r['replicates'] else 'does not replicate' if r else 'not screened') + (f' (Sanger Δ {r["delta"]:.2f}, p {r["p"]:.1e})' if r else ''),
                    'modelQuality': f'lineage-adjusted OLS, {int(x.sum())} mutant vs {int((1 - x).sum())} other independent models' + (f'; mechanistic runs numerically reliable: {", ".join(n for n, ok, _ in mech if ok) or "none"}' if mech else ''),
                    'plausibility': ('the driver itself (oncogene addiction)' if g == gene else '') + ('; ' if g == gene and mech else '') + (f'in the same mechanistic model(s) as the pathway: {", ".join(n for n, _, _ in mech)}' if mech else ('' if g == gene else 'no pathway model here; check the evidence graph')),
                    'alternatives': f'without lineage adjustment Δ {naive:.2f} vs {h["beta"]:.2f} adjusted' + (' (lineage explains part of the signal)' if h and abs(naive) > 1.5 * abs(h['beta']) else '') + '; cell-line growth rate and screen quality are not adjusted',
                    'normalTissue': f'{frac:.0%} of all cancer models depend on it (< −0.5)' + (' — close to pan-essential, so a therapeutic window is doubtful' if frac > 0.8 else ' — selective' if frac < 0.3 else '') + '; no normal-tissue screen is installed (proxy only)',
                    'uncertainty': f'95 % CI {h["ci"][0]:.2f} to {h["ci"][1]:.2f}' if h else '—',
                    'contradictions': '; '.join(contra) or 'none found in these data',
                    'novelty': 'the driver itself' if n_lit == -1 else 'literature not reachable' if n_lit is None else f'{n_lit} Europe PMC records mention {gene} and {g} with cancer' + (' (well studied)' if n_lit > 200 else ' (little studied)' if n_lit < 10 else ''),
                    'missing': missing})
    return out


def main(root, rid):
    import warnings; warnings.filterwarnings('ignore')
    from insilico import _clean
    d = pathlib.Path(root) / 'oncology' / 'discovery' / rid
    r = run(root, json.loads((d / 'question.json').read_text()))
    (d / 'result.json').write_text(json.dumps(_clean({**r, 'id': rid})))
    print(f'done in {r["seconds"]} s', flush=True)


if __name__ == '__main__':
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    main(*sys.argv[1:3])
