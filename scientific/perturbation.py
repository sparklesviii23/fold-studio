"""Perturbation lab: one experiment, every engine that can speak to it, each answer labelled by what kind of evidence it is.

    python perturbation.py <library root> <experiment id>     (experiment read from oncology/perturbation/<id>/experiment.json)

An experiment is a system (cancer lineage, patient cohort) plus up to four perturbations applied together:
  gene         inhibit a gene's product by a stated fraction (1 = complete loss)
  interaction  scale one protein–protein interaction (0 = abolished, 1 = unchanged, > 1 = strengthened)
  compound     a GDSC compound, assumed to inhibit its annotated targets by a stated fraction (exposure is not modelled)
  immune       scale effector immune-cell influx into the tumor

Engines and what they are
  Simulators (Mechanistic simulation): EGFR signalling (Kholodenko 1999), MAPK cascade with feedback (Kholodenko 2000),
    tumor–immune effector dynamics (Kuznetsov 1994), Human-GEM flux balance. They compute consequences from mechanism,
    only for what their equations contain; a gene's mapping onto model terms is stated with each run.
  Measured data (Experimental observation): DepMap CRISPR knockout effects, GDSC measured drug responses.
  Statistical association: survival by naturally occurring alteration in a patient cohort.
  AI prediction: the expression ridge model's response prediction, scored on the held-out lineage before it is shown.
  Curated evidence: the evidence graph's CIViC / Open Targets links.
Engines never feed numbers into each other: each readout stands alone so its evidence class is never blurred.
"""
import json
import math
import pathlib
import re
import sys
import time
import types

import numpy as np

ALIASES = {'MEK1': 'MAP2K1', 'MEK2': 'MAP2K2', 'ERK1': 'MAPK3', 'ERK2': 'MAPK1', 'HER2': 'ERBB2', 'ERBB1': 'EGFR', 'C-RAF': 'RAF1', 'CRAF': 'RAF1', 'B-RAF': 'BRAF',
           'PI3KALPHA': 'PIK3CA', 'MTORC1': 'MTOR', 'MTORC2': 'MTOR', 'CDK4/6': 'CDK4', 'PARP1': 'PARP1', 'BCL-2': 'BCL2', 'BCL-XL': 'BCL2L1'}

# Explicit, stated mappings from human genes onto the terms of published models. Kind 'rate' scales parameters
# (catalytic activity); 'amount' scales initial amounts of a species (and its modified forms).
MODELS = {
    'egfr': {'name': 'EGFR receptor signalling (Kholodenko 1999, BIOMD0000000048)', 'demo': 'receptor', 'tEnd': 120, 'unit': 'nM', 'time': 's',
             'outputs': {'RP': 'phosphorylated EGFR dimer', 'PLCgP': 'phospho-PLCγ', 'RShP': 'receptor–phospho-Shc', 'RGS': 'receptor–Grb2–SOS'},
             'context': 'rat hepatocytes; 0–120 s after EGF; parameters from the paper',
             'genes': {'EGFR': ('rate', ['v3.k3f'], 'receptor autophosphorylation rate'), 'PLCG1': ('amount', ['PLCg'], 'PLCγ amount'), 'GRB2': ('amount', ['Grb'], 'Grb2 amount'),
                       'SOS1': ('amount', ['SOS'], 'SOS amount'), 'SHC1': ('amount', ['Shc'], 'Shc amount')},
             'interactions': {'EGF–EGFR': ['v1.k1f'], 'EGFR–PLCG1': ['v5.k5f'], 'EGFR–GRB2': ['v9.k9f'], 'EGFR–SHC1': ['v13.k13f'],
                              'GRB2–SOS1': ['v10.k10f', 'v19.k19f', 'v22.k22f', 'v12.k12b'], 'SHC1–GRB2': ['v17.k17f', 'v21.k21f']}},
    'mapk': {'name': 'MAPK cascade with negative feedback (Kholodenko 2000, BIOMD0000000010)', 'demo': 'cascade', 'readout': 'oscillation', 'tEnd': 9000, 'unit': 'nM', 'time': 's',
             'outputs': {'MAPK_PP': 'doubly phosphorylated ERK', 'MKK_PP': 'doubly phosphorylated MEK', 'MKKK_P': 'active MAPKKK'},
             'context': 'generic three-tier cascade parameterised for Xenopus oocytes (Mos–Mek1–Erk2); RAS genes are mapped onto its input rate and RAF genes onto the MAPKKK slot, both by analogy',
             'genes': {'KRAS': ('rate', ['J0.V1'], 'upstream activation of the MAPKKK (Ras input, by analogy)'), 'NRAS': ('rate', ['J0.V1'], 'upstream activation of the MAPKKK (by analogy)'),
                       'HRAS': ('rate', ['J0.V1'], 'upstream activation of the MAPKKK (by analogy)'), 'BRAF': ('rate', ['J2.k3', 'J3.k4'], 'MAPKKK catalytic rate (RAF on the Mos slot, by analogy)'), 'RAF1': ('rate', ['J2.k3', 'J3.k4'], 'MAPKKK catalytic rate (by analogy)'),
                       'MAP2K1': ('rate', ['J6.k7', 'J7.k8'], 'MEK catalytic rate'), 'MAP2K2': ('rate', ['J6.k7', 'J7.k8'], 'MEK catalytic rate'),
                       'MAPK1': ('amount', ['MAPK', 'MAPK_P', 'MAPK_PP'], 'ERK amount'), 'MAPK3': ('amount', ['MAPK', 'MAPK_P', 'MAPK_PP'], 'ERK amount')},
             'interactions': {'RAF–MEK': ['J2.k3', 'J3.k4'], 'MEK–ERK': ['J6.k7', 'J7.k8'], 'ERK⊣RAF feedback': ['J0.Ki~inverse']}},
}
# Published BioModels bundled under fixtures/biomodels (CC0), run unmodified. Gene → species maps follow each model's UniProt
# annotations; where a model lacks or mis-states an annotation the mapping is curated and the note says so. 'amount' scales
# a protein's starting pool (knockdown-like: a catalytic inhibitor that leaves protein in place is approximated this way).
AMOUNT_NOTE = 'reduces the starting pool of the protein (knockdown-like); an inhibitor that leaves the protein in place is approximated this way'
MODELS.update({
    'schoeberl': {'name': 'EGF → RAS → ERK signalling (Schoeberl 2002, BIOMD0000000019)', 'biomodels': 'BIOMD0000000019', 'tEnd': 60, 'unit': 'molecules/cell', 'time': 'model time units',
                  'outputs': {'x59': 'doubly phosphorylated ERK', 'x51': 'doubly phosphorylated MEK', 'x28': 'Ras-GTP', 'x5': 'active EGFR dimer'},
                  'context': 'human HeLa cells stimulated with EGF; parameters from the paper; RAS isoforms and paralogs mapped onto the single pools the model has; the cascade is strongly ultrasensitive, so ERK output falls steeply with upstream knockdown (25 % less Ras → about half the peak ERK-PP)',
                  'genes': {'EGFR': ('amount', ['x2'], 'EGFR pool'), 'GRB2': ('amount', ['x22'], 'Grb2 pool'), 'SOS1': ('amount', ['x24'], 'SOS pool'), 'RASA1': ('amount', ['x14'], 'RasGAP pool'),
                            'HRAS': ('amount', ['x26'], 'Ras-GDP pool'), 'KRAS': ('amount', ['x26'], 'Ras-GDP pool (model has one Ras)'), 'NRAS': ('amount', ['x26'], 'Ras-GDP pool (model has one Ras)'),
                            'SHC1': ('amount', ['x31'], 'Shc pool (annotated SHC2 in the model)'), 'RAF1': ('amount', ['x41'], 'Raf pool'), 'BRAF': ('amount', ['x41'], 'Raf pool (model has one Raf)'),
                            'MAP2K1': ('amount', ['x47'], 'MEK pool'), 'MAP2K2': ('amount', ['x47'], 'MEK pool'), 'MAPK1': ('amount', ['x55'], 'ERK pool'), 'MAPK3': ('amount', ['x55'], 'ERK pool')},
                  'interactions': {'EGF–EGFR': ['k1'], 'GRB2–SOS1': ['k17'], 'RAS–RAF': ['k28'], 'RAF–MEK': ['k44'], 'MEK–ERK': ['k52']}},
    'hatakeyama': {'name': 'Heregulin → ErbB → PI3K/AKT and ERK (Hatakeyama 2003, BIOMD0000000146)', 'biomodels': 'BIOMD0000000146', 'tEnd': 1800, 'unit': 'model units', 'time': 's',
                   'outputs': {'ERKPP': 'doubly phosphorylated ERK', 'AktPIPP': 'doubly phosphorylated AKT', 'RasGTP': 'Ras-GTP'},
                   'context': 'heregulin-stimulated MCF-7 breast cancer cells; the model is barely annotated, so genes are mapped by species name (curated)',
                   'genes': {'ERBB3': ('amount', ['R'], 'ErbB receptor pool'), 'ERBB4': ('amount', ['R'], 'ErbB receptor pool'), 'SHC1': ('amount', ['Shc'], 'Shc pool'),
                             'GRB2': ('amount', ['GS'], 'Grb2–SOS pool'), 'SOS1': ('amount', ['GS'], 'Grb2–SOS pool'), 'HRAS': ('amount', ['RasGDP'], 'Ras pool'), 'KRAS': ('amount', ['RasGDP'], 'Ras pool (model has one Ras)'),
                             'NRAS': ('amount', ['RasGDP'], 'Ras pool (model has one Ras)'), 'RAF1': ('amount', ['Raf'], 'Raf pool'), 'BRAF': ('amount', ['Raf'], 'Raf pool'), 'MAP2K1': ('amount', ['MEK'], 'MEK pool'),
                             'MAP2K2': ('amount', ['MEK'], 'MEK pool'), 'MAPK1': ('amount', ['ERK'], 'ERK pool'), 'MAPK3': ('amount', ['ERK'], 'ERK pool'), 'PIK3CA': ('amount', ['PI3K'], 'PI3K pool'),
                             'AKT1': ('amount', ['Akt'], 'AKT pool')},
                   'interactions': {'ERBB–SHC1': ['k5'], 'SHC1–GRB2·SOS1': ['k7'], 'ERBB–PI3K': ['k23'], 'PIP3–AKT': ['k29']}},
    'albeck': {'name': 'TRAIL-induced extrinsic apoptosis (Albeck 2008, BIOMD0000000220)', 'biomodels': 'BIOMD0000000220', 'tEnd': 21600, 'unit': 'molecules/cell', 'time': 's',
               'outputs': {'CPARP': 'cleaved PARP (death marker)', 'tBid': 'truncated Bid', 'CytoC': 'cytosolic cytochrome c', 'C3': 'active caspase-3'},
               'threshold': ('CPARP', 5e5, 'time to 50 % PARP cleavage (cell death)'),
               'context': 'human HeLa cells treated with TRAIL (3000 ligand molecules); parameters from the paper; PARP is only the death reporter here (PARP inhibitors act on DNA repair, which this model lacks), so PARP1 is deliberately not mapped',
               'genes': {'TNFSF10': ('amount', ['L'], 'TRAIL ligand'), 'TNFRSF10B': ('amount', ['R'], 'death receptor DR5'), 'CFLAR': ('amount', ['flip'], 'FLIP'), 'CASP8': ('amount', ['pC8'], 'procaspase-8'),
                         'CASP3': ('amount', ['pC3'], 'procaspase-3'), 'BID': ('amount', ['Bid'], 'Bid'), 'CASP6': ('amount', ['pC6'], 'procaspase-6'), 'XIAP': ('amount', ['XIAP'], 'XIAP'),
                         'BCL2': ('amount', ['Bcl2c', 'Bcl2'], 'Bcl-2 (cytosolic and mitochondrial)'), 'BAX': ('amount', ['Bax'], 'Bax'),
                         'DIABLO': ('amount', ['Smacm'], 'mitochondrial Smac'), 'CYCS': ('amount', ['CytoCm'], 'mitochondrial cytochrome c'), 'APAF1': ('amount', ['Apaf'], 'Apaf-1'), 'CASP9': ('amount', ['pC9'], 'procaspase-9')},
               'interactions': {'TRAIL–DR5': ['k1'], 'DR5–FLIP': ['k2'], 'DR5–CASP8': ['k3'], 'BID–BCL2': ['k11'], 'BID–BAX': ['k12'], 'BAX–BCL2': ['k14', 'k16', 'k18'], 'XIAP–CASP3': ['k8'],
                                'XIAP–SMAC': ['k28'], 'CYCS–APAF1': ['k23']}},
    'lee': {'name': 'Wnt / β-catenin destruction complex (Lee 2003, BIOMD0000000658)', 'biomodels': 'BIOMD0000000658', 'tEnd': 500, 'unit': 'nM', 'time': 'min',
            'outputs': {'B_catenin_0': 'free β-catenin', 'B_catenin_TCF': 'β-catenin–TCF (transcriptionally active)'},
            'context': 'Xenopus egg extract with a transient Wnt signal (model without the regulatory loop); human genes mapped to the Xenopus orthologs annotated in the model',
            'genes': {'APC': ('amount', ['APC'], 'APC pool'), 'AXIN1': ('amount', ['Axin'], 'Axin pool'), 'GSK3B': ('amount', ['GSK3'], 'GSK3 pool'), 'CTNNB1': ('amount', ['B_catenin_0'], 'β-catenin pool'),
                      'DVL2': ('amount', ['Dsh_i'], 'Dishevelled pool')},
            'interactions': {'APC–AXIN1': ['k7'], 'GSK3B–APC·AXIN1': ['k6'], 'destruction complex–CTNNB1': ['k8'], 'CTNNB1–TCF': ['k16'], 'APC–CTNNB1': ['k17']}},
    'zi': {'name': 'TGF-β → SMAD signalling (Zi 2007, BIOMD0000000163)', 'biomodels': 'BIOMD0000000163', 'tEnd': 300, 'unit': 'model units', 'time': 'min',
           'outputs': {'Smads_Complex_n': 'nuclear SMAD2–SMAD4 complex', 'Smad2n': 'nuclear SMAD2'},
           'context': 'TGF-β receptor trafficking and SMAD shuttling; the type-I receptor is annotated ACVR1C in the model but is TGFBR1 (ALK5) in the paper, so TGFBR1 is mapped (curated)',
           'genes': {'TGFB1': ('amount', ['TGF_beta'], 'TGF-β ligand'), 'TGFBR1': ('amount', ['T1R_Surf', 'T1R_Cave', 'T1R_EE'], 'type-I receptor pools'),
                     'TGFBR2': ('amount', ['T2R_Surf', 'T2R_Cave', 'T2R_EE'], 'type-II receptor pools'), 'SMAD2': ('amount', ['Smad2c', 'Smad2n'], 'SMAD2 pools'), 'SMAD4': ('amount', ['Smad4c', 'Smad4n'], 'SMAD4 pools')},
           'interactions': {'SMAD2–SMAD4': ['k_Smads_Complex_c']}},
    'yamada': {'name': 'Interferon → JAK → STAT1 signalling (Yamada 2003, BIOMD0000000093)', 'biomodels': 'BIOMD0000000093', 'tEnd': 3600, 'unit': 'model units', 'time': 's',
               'outputs': {'STAT1n_star_STAT1n_star': 'nuclear phospho-STAT1 dimer', 'STAT1c_star_STAT1c_star': 'cytoplasmic phospho-STAT1 dimer'},
               'context': 'mouse JAK–STAT model with SOCS1 and SHP2 feedback; human genes mapped to the annotated mouse orthologs; the receptor is annotated Cntfr but is the interferon receptor, so IFNGR1 is mapped (curated)',
               'genes': {'IFNGR1': ('amount', ['R'], 'receptor pool'), 'JAK1': ('amount', ['JAK'], 'JAK pool'), 'JAK2': ('amount', ['JAK'], 'JAK pool (model has one JAK)'), 'STAT1': ('amount', ['STAT1c'], 'STAT1 pool'),
                         'PTPN11': ('amount', ['SHP2'], 'SHP2 pool')},
               'interactions': {'JAK1–receptor': ['v1.kf'], 'receptor–STAT1': ['v5.kf'], 'receptor–SHP2': ['v9.kf'], 'receptor–SOCS1': ['v29.kf'], 'STAT1–STAT1': ['v15.kf']}},
})

# Models that need SBML events (stimulus pulses) or delays; runnable since the engine supports both.
MODELS.update({
    'hoffmann': {'name': 'TNF → IKK → NF-κB oscillations (Hoffmann 2002, BIOMD0000000140)', 'biomodels': 'BIOMD0000000140', 'tEnd': 2600, 'unit': 'µM', 'time': 'min',
                 'outputs': {'Total_NFkBn': 'nuclear NF-κB', 'Total_IkBalpha': 'total IκBα'},
                 'context': 'mouse fibroblasts; the model equilibrates for 2000 min, then an event switches IKK on (TNF-like stimulus), so the response is the last 600 min; human genes mapped to the annotated mouse orthologs',
                 'genes': {'RELA': ('amount', ['NFkB'], 'NF-κB pool'), 'NFKB1': ('amount', ['NFkB'], 'NF-κB pool'), 'NFKBIA': ('rate', ['tr2a', 'tr2'], 'IκBα transcription (basal and NF-κB-induced)'),
                           'NFKBIB': ('rate', ['tr2b'], 'IκBβ transcription'), 'NFKBIE': ('rate', ['tr2e'], 'IκBε transcription'),
                           'IKBKB': ('rate', ['r1', 'r2', 'r3', 'r4', 'r5', 'r6'], 'IKK-catalysed IκB degradation'), 'CHUK': ('rate', ['r1', 'r2', 'r3', 'r4', 'r5', 'r6'], 'IKK-catalysed IκB degradation'),
                           'IKBKG': ('rate', ['r1', 'r2', 'r3', 'r4', 'r5', 'r6'], 'IKK-catalysed IκB degradation')},
                 'interactions': {'NFKBIA–RELA': ['a4'], 'IKK–NFKBIA': ['a1', 'a7']}},
    'proctor': {'name': 'DNA damage → ATM → p53/MDM2 (Proctor & Gray 2008, BIOMD0000000188)', 'biomodels': 'BIOMD0000000188', 'tEnd': 43200, 'unit': 'molecules', 'time': 's',
                'outputs': {'totp53': 'total p53', 'p53_P': 'phosphorylated p53', 'totMdm2': 'total MDM2'},
                'context': 'human p53–MDM2 circuit; events deliver 1 min of ionising radiation at 1 h; 12 h simulated',
                'genes': {'TP53': ('rate', ['ksynp53mRNA'], 'p53 mRNA synthesis'), 'MDM2': ('rate', ['ksynMdm2'], 'MDM2 translation'), 'ATM': ('amount', ['ATMI'], 'ATM pool')},
                'interactions': {'MDM2–TP53': ['kbinMdm2p53'], 'ATM→TP53 phosphorylation': ['kphosp53']}},
    'zatorsky': {'name': 'p53–MDM2 delayed negative feedback (Geva-Zatorsky 2006 model 6, BIOMD0000000155)', 'biomodels': 'BIOMD0000000155', 'tEnd': 30, 'unit': 'dimensionless', 'time': 'h',
                 'outputs': {'x': 'p53', 'y': 'MDM2'}, 'readout': 'oscillation',
                 'context': 'minimal model of p53 pulses in single MCF-7 cells after damage, with an explicit delay (τ = 0.9 h) in MDM2 production; dimensionless levels',
                 'genes': {'TP53': ('rate', ['beta_x'], 'p53 production'), 'MDM2': ('rate', ['beta_y'], 'MDM2 production')},
                 'interactions': {'MDM2–TP53': ['alpha_xy']}},
})

# Immune checkpoint signalling inside the T cell (directive §39); integrated through the same SBML engine.
MODELS.update({
    'theinmozhi': {'name': 'PD-1 → SHP2 inhibition of TCR and CD28 signalling (Theinmozhi 2018, BIOMD0000000724)', 'biomodels': 'BIOMD0000000724', 'tEnd': 3600, 'unit': 'molecules', 'time': 's',
                   'outputs': {'PI3Kb': 'CD28-bound PI3K (costimulation)', 'CPactive': 'active PD-1–SHP2', 'LAT_phosphorylated': 'phosphorylated LAT (TCR signal; saturated at baseline in this model)'},
                   'context': 'T-cell-intrinsic model: PD-1 phosphorylated by LCK recruits SHP2, which dephosphorylates CD3, CD28 and LCK; PD-L1 is not in the model (PD-1 is taken as engaged), so a PD-1 or PD-L1 antibody is represented as less PD-1 available or a weaker PD-1–SHP2 interaction',
                   'genes': {'PDCD1': ('amount', ['PD1'], 'PD-1 available'), 'PTPN11': ('amount', ['SHP2'], 'SHP2 pool'), 'LCK': ('amount', ['LCKi', 'LCKyi', 'LCKya', 'LCKyiya'], 'LCK pool'),
                             'CD28': ('amount', ['CD28i'], 'CD28 pool'), 'PIK3CA': ('amount', ['PI3K'], 'PI3K pool'), 'PIK3R1': ('amount', ['PI3K'], 'PI3K pool'), 'ZAP70': ('amount', ['ZAP70'], 'ZAP70 pool'),
                             'LAT': ('amount', ['LATi'], 'LAT pool')},
                   'interactions': {'PD1–SHP2': ['Ka_shp'], 'CD28–PI3K': ['Ka_pi3k'], 'CD3–ZAP70': ['Ka_zap']}},
})

IMMUNE = {'name': 'Tumor–effector cell dynamics (Kuznetsov, Makalkin, Taylor & Perelson 1994)',
          'params': {'sigma': 0.1181, 'rho': 1.131, 'eta': 20.19, 'mu': 0.00311, 'delta': 0.3743, 'alpha': 1.636, 'beta': 0.002},
          'context': 'dimensionless ODE fitted to BCL1 lymphoma in mouse spleen; tumor in units of 10⁶ cells; effector influx σ scaled by the infiltration factor'}
KINDS = ('gene', 'interaction', 'compound', 'immune')


def _gene(g):
    g = str(g).strip().upper()
    return ALIASES.get(g, g)


def _norm_perturbations(perts, drugs=None):
    out = []
    for p in perts[:4]:
        k = p.get('kind')
        if k == 'gene':
            g = _gene(p.get('gene', ''))
            if not re.fullmatch(r'[A-Z0-9-]{2,15}', g):
                raise ValueError('Give a gene symbol (e.g. EGFR).')
            out.append({'kind': k, 'gene': g, 'strength': min(1.0, max(0.0, float(p.get('strength', 1.0))))})
        elif k == 'interaction':
            names = {n for m in MODELS.values() for n in m['interactions']}
            if p.get('pair') not in names:
                raise ValueError('Choose an interaction from the list.')
            out.append({'kind': k, 'pair': p['pair'], 'factor': min(10.0, max(0.0, float(p.get('factor', 0.5))))})
        elif k == 'compound':
            if drugs is not None and p.get('drug') not in drugs:
                raise ValueError('Choose a GDSC compound.')
            q = {'kind': k, 'drug': p.get('drug'), 'strength': min(1.0, max(0.0, float(p.get('strength', 0.9))))}
            if p.get('conc') not in (None, ''):
                c = float(p['conc'])
                if not 1e-4 <= c <= 1000:
                    raise ValueError('Concentration must be between 0.0001 and 1000 µM.')
                q['conc'] = c
            out.append(q)
        elif k == 'immune':
            out.append({'kind': k, 'factor': min(5.0, max(0.0, float(p.get('factor', 2.0))))})
        else:
            raise ValueError('Perturbation kind must be gene, interaction, compound or immune.')
    if not out:
        raise ValueError('Add at least one perturbation.')
    return out


def describe(p, drugs=None):
    if p['kind'] == 'gene':
        return f'inhibit {p["gene"]} by {p["strength"]:.0%}'
    if p['kind'] == 'interaction':
        return f'{p["pair"]} interaction × {p["factor"]:g}'
    if p['kind'] == 'compound':
        d = (drugs or {}).get(p['drug'], {})
        if 'conc' in p:
            return f'{d.get("name", p["drug"])} at {p["conc"]:g} µM (inhibition from ChEMBL potency)'
        return f'{d.get("name", p["drug"])} ({d.get("target", "?")}), assumed {p["strength"]:.0%} target inhibition'
    return f'effector immune influx × {p["factor"]:g}'


def targets(p, drugs):
    """Genes a perturbation acts on: the gene itself, or a compound's annotated targets (with aliases resolved)."""
    if p['kind'] == 'gene':
        return [(p['gene'], p['strength'])]
    if p['kind'] == 'compound' and 'engagement' in p:                          # concentration mode: every target ChEMBL says is ≥ 20 % inhibited
        return sorted(p['engagement'].items(), key=lambda x: -x[1])
    if p['kind'] == 'compound':
        t = drugs.get(p['drug'], {}).get('target') or ''
        return [(_gene(x), p['strength']) for x in re.split(r'[,;/]\s*', t) if x.strip()]
    return []


def engine(eid, name, kind, evidence):
    return {'id': eid, 'name': name, 'kind': kind, 'evidence': evidence, 'represented': [], 'ignored': [], 'status': 'not applicable', 'metrics': [], 'caveats': [], 'summary': ''}


# ---------------------------------------------------------------- simulators
def _terms(M, perts, drugs, base_p, base_y):
    """Model parameter and initial-value changes for a set of perturbations. Different perturbations act independently
    (factors multiply), except compounds given as concentrations that share a target: they compete for one site, so the
    occupancy is Σ(C/IC50) / (1 + Σ(C/IC50)) applied once."""
    conc = [p for p in perts if p['kind'] == 'compound' and p.get('ic50')]
    comp, owner = {}, {}
    for g in set().union(*[set(p['ic50']) for p in conc]) if len(conc) > 1 else ():
        users = [p for p in conc if g in p['ic50']]
        if len(users) > 1:
            r = sum(p['conc'] / p['ic50'][g] for p in users); comp[g] = r / (1 + r); owner[g] = users[0]
    over, init, rep, ign = {}, {}, [], []
    for p in perts:
        hits, factor = [], {}
        if p['kind'] in ('gene', 'compound'):
            for g, s in targets(p, drugs):
                if g in comp:
                    if owner[g] is not p:
                        if g in M['genes']:
                            hits.append(f'{g}: shares its site with another compound (combined occupancy applied once)')
                        continue
                    s = comp[g]
                if g in M['genes']:
                    kind, terms, what = M['genes'][g]
                    for t in terms:                        # paralogs sharing one model term (MEK1/MEK2) count once per perturbation
                        factor[(kind, t)] = min(factor.get((kind, t), 1.0), 1 - s)
                    hits.append(f'{g}: {what} × {1 - s:.2f}' + (' (competitive occupancy of the compounds sharing this target)' if g in comp else ''))
            for (kind, t), f in factor.items():
                if kind == 'rate':
                    over[t] = over.get(t, base_p[t]) * f
                else:
                    init[t] = init.get(t, base_y[t]) * f
        elif p['kind'] == 'interaction' and p['pair'] in M['interactions']:
            for t in M['interactions'][p['pair']]:
                t, inv = t.split('~')[0], t.endswith('~inverse')
                f = p['factor']; over[t] = over.get(t, base_p[t]) * ((1 / f if f > 0 else 1e6) if inv else f)
            hits.append(f'{p["pair"]}: ' + ', '.join(t.split('~')[0] for t in M['interactions'][p['pair']]) + f' × {p["factor"]:g}' + (' (Ki ÷ factor: below 1 weakens the feedback, 0 removes it, above 1 strengthens it)' if p['pair'].endswith('feedback') else ''))
        (rep if hits else ign).append(describe(p, drugs) + (' → ' + '; '.join(hits) if hits else ''))
    return over, init, rep, ign


def ode_model(mid, perts, drugs):
    import mechanistic_demos as demos
    import mechanistic_sbml as sbml
    import mechanistic_sim as sim
    M = MODELS[mid]; e = engine('ode_' + mid, M['name'], 'simulator', 'Mechanistic simulation (published ODE model, SciPy integration)')
    model = demos.load(M['demo']) if 'demo' in M else sbml.Model((demos.FIXTURES / (M['biomodels'] + '.xml')).read_text(), {'kind': 'biomodels', 'id': M['biomodels'], 'bundled': True})
    y0, p0 = model.prepare(); base_p = dict(zip(model.param_ids, map(float, p0))); base_y = {s['id']: float(v) for s, v in zip(model.state, y0)}
    over, init, e['represented'], e['ignored'] = _terms(M, perts, drugs, base_p, base_y)
    if not e['represented']:
        return e
    b = sim.simulate(model, M['tEnd'], 600); q = sim.simulate(model, M['tEnd'], 600, overrides=over, initial=init)
    half = len(b['time']) // 2
    for sid, label in M['outputs'].items():
        xb, xq = (np.where(np.abs(np.array(v['series'][sid])) < 1e-9, 0.0, v['series'][sid]) for v in (b, q))     # solver round-off below 1e-9 nM is zero
        if M.get('readout') == 'oscillation':
            e['metrics'].append([f'{label} · mean, second half ({M["unit"]})', xb[half:].mean(), xq[half:].mean()])
            e['metrics'].append([f'{label} · oscillation amplitude ({M["unit"]})', np.ptp(xb[half:]), np.ptp(xq[half:])])
        else:
            e['metrics'].append([f'{label} · peak ({M["unit"]})', xb.max(), xq.max()])
            e['metrics'].append([f'{label} · at {M["tEnd"]} {M["time"]} ({M["unit"]})', xb[-1], xq[-1]])
    acting = [p for p in perts if any(r.startswith(describe(p, drugs)) for r in e['represented'])]
    if len(acting) > 1:                                  # interaction in the model: combined output vs Bliss independence of the singles
        sid = next(iter(M['outputs'])); key = (lambda r: float(np.mean(r['series'][sid][len(r['time']) // 2:]))) if M.get('readout') == 'oscillation' else (lambda r: float(np.max(r['series'][sid])))
        base, both = key(b), key(q); fr = []
        for p in acting:
            o, i, _, _ = _terms(M, [p], drugs, base_p, base_y); fr.append(key(sim.simulate(model, M['tEnd'], 600, overrides=o, initial=i, check=False)) / base if base else float('nan'))
        exp = base * float(np.prod(fr))
        e['interaction'] = {'output': M['outputs'][sid], 'baseline': base, 'singles': [b_ * base for b_ in fr], 'combined': both, 'blissExpected': exp,
                            'ratio': both / exp if exp else None}
        e['metrics'].append([f'{M["outputs"][sid]} · combined vs Bliss-independent expectation from the single perturbations', exp, both])
        e['caveats'].append('Interaction readout: a combined output below the Bliss expectation means the perturbations reinforce each other in this model (synergy on this readout); above it, they offset each other. It is a statement about this signalling readout, not about cell viability.')
    if M.get('threshold'):
        sid, level, label = M['threshold']
        cross = lambda r: next((tt for tt, v in zip(r['time'], r['series'][sid]) if v >= level), None)
        e['metrics'].insert(0, [f'{label} ({M["time"]}; blank = not reached by {M["tEnd"]})', cross(b), cross(q)])
    e['series'] = {'time': b['time'][::4], 'unit': f'{M["unit"]} vs {M["time"]}', 'baseline': {k: b['series'][k][::4] for k in M['outputs']}, 'perturbed': {k: q['series'][k][::4] for k in M['outputs']}}
    e['status'] = 'ran'; e['reliable'] = bool(b['diagnostics'].get('reliable') and q['diagnostics'].get('reliable'))
    rel = lambda m: abs(m[2] - m[1]) / abs(m[1]) if isinstance(m[1], (int, float)) and isinstance(m[2], (int, float)) and m[1] else 0.0
    m0 = max((m for m in e['metrics'] if ' · ' in m[0]), key=rel)          # lead with the readout that moved most
    e['summary'] = f'{m0[0].split(" (")[0]}: {m0[1]:.3g} → {m0[2]:.3g} {M["unit"]} ({_pct(m0[1], m0[2])}).'
    po = next(m for m in e['metrics'] if m[0].startswith(M['outputs'][next(iter(M['outputs']))]))   # the model's main pathway output
    e['primary'] = f'{po[0].split(" (")[0]}: {po[1]:.3g} → {po[2]:.3g} ({_pct(po[1], po[2])})'
    if not e['summary'].startswith(e['primary'].split(':')[0]):
        e['summary'] = f'{e["primary"]}. Largest change elsewhere in the model: {e["summary"]}'
    if M.get('threshold'):                                                   # an event time is the headline: end-point levels after death mislead
        tb, tq = e['metrics'][0][1:]
        e['summary'] = f'{M["threshold"][2][0].upper() + M["threshold"][2][1:]}: ' + ' → '.join('not reached' if v is None else f'{v / 3600:.1f} h' if M['time'] == 's' else f'{v:.3g}' for v in (tb, tq)) + '.'
        e['primary'] = e['summary'].rstrip('.')
    e['caveats'] = [f'Model context: {M["context"]}.', 'Gene-to-term mapping is stated above; ' + (AMOUNT_NOTE if any(v[0] == 'amount' for v in M['genes'].values()) else 'a fractional rate change stands in for inhibitor occupancy, which is not modelled') + '.',
                    'Numerical reliability (tolerance and conservation checks): ' + ('passed' if e['reliable'] else 'NOT passed — treat with caution') + '.']
    return e


def engagement(root, perts, drugs):
    """Concentration mode: fetch ChEMBL potency and compute per-target inhibition; attaches 'engagement' to each compound perturbation."""
    import chembl_potency as C
    e = engine('chembl', 'Target engagement from ChEMBL potency', 'measured data', 'Experimental observation (ChEMBL biochemical potency) → calculated fraction inhibited')
    for p in perts:
        if p['kind'] != 'compound' or 'conc' not in p:
            e['ignored'].append(describe(p, drugs)); continue
        name = drugs.get(p['drug'], {}).get('name', p['drug']); annotated = {g for g, _ in targets({'kind': 'compound', 'drug': p['drug'], 'strength': 1}, drugs)}   # GDSC annotation
        try:
            pot = C.potency(root, name)
        except Exception as x:
            p['engagement'] = {}; e['ignored'].append(f'{name}: ChEMBL unreachable ({type(x).__name__}); not simulated'); continue
        if pot.get('error'):
            p['engagement'] = {}; e['ignored'].append(f'{name}: {pot["error"]}'); continue
        inh = C.inhibition(pot, p['conc']); p['engagement'] = {g: v for g, v in inh.items() if v >= 0.2}
        p['ic50'] = {g: pot['targets'][g]['ic50_uM'] for g in p['engagement']}
        e['represented'].append(f'{describe(p, drugs)} → ChEMBL {pot["molecule"]["id"]} ({pot["activities"]} biochemical activities, {len(pot["targets"])} human targets)')
        for g, v in sorted(inh.items(), key=lambda x: -x[1])[:12]:
            tt = pot['targets'][g]
            e['metrics'].append([f'{name} · {g} ({"annotated target" if g in annotated else "off-target"}) · median IC50 {tt["ic50_uM"] * 1000:.3g} nM, n = {tt["n"]}', None, v])
        try:                                             # independent source: BindingDB, for the annotated targets
            for g, b in C.bindingdb(root, pot, sorted(annotated & set(pot['targets']))).items():
                e['metrics'].append([f'{name} · {g} · BindingDB cross-check: median {b["median_nM"]:.3g} nM over {b["n"]} measurements (ChEMBL {pot["targets"][g]["ic50_uM"] * 1000:.3g} nM)', None, f'{b["median_nM"] / (pot["targets"][g]["ic50_uM"] * 1000):.2g}× ChEMBL'])
            e['caveats'].append('BindingDB and ChEMBL import each other\'s curated literature values, so agreement between them is partly by construction, not independent replication.') if 'BindingDB and ChEMBL' not in ' '.join(e['caveats']) else None
        except Exception as x:
            e['caveats'].append(f'BindingDB cross-check unavailable ({type(x).__name__}).')
        missing = sorted(annotated - set(pot['targets']))
        if missing:
            e['caveats'].append(f'{name}: no ChEMBL potency for annotated target(s) {", ".join(missing)}; they are not simulated.')
    if e['represented']:
        e['status'] = 'ran'; e['summary'] = 'Fraction of each target inhibited at the stated concentration; targets ≥ 20 % go to the other engines.'
        e['caveats'] += ['C / (C + IC50) with Hill slope 1 at the stated free concentration; ignores cell permeability, intracellular ATP, protein binding and tumor exposure.',
                         'Off-targets are included when the calculation says they are engaged; that they matter biologically is not implied.']
    return e


def almanac(root, perts, drugs):
    """Measured interaction of a two-compound perturbation in NCI ALMANAC, scored with the Synergy demo's own code per NCI-60 line."""
    import synergy as Y
    e = engine('almanac', 'NCI ALMANAC measured combination', 'measured data', 'Experimental observation (NCI-60 combination screen; scores relative to Bliss and Loewe reference models)')
    comps = [p for p in perts if p['kind'] == 'compound']
    for p in perts:
        if p['kind'] != 'compound':
            e['ignored'].append(describe(p, drugs))
    if len(comps) != 2:
        if comps:
            e['ignored'] += [describe(p, drugs) + ' (needs exactly two compounds)' for p in comps]
        return e
    try:
        A, idx, _ = Y._load(types.SimpleNamespace(root=root))
    except ValueError as x:
        e['status'] = 'unavailable'; e['summary'] = str(x); return e
    nsc = {_norm_drug(n): int(k) for k, n in idx['names'].items()}
    ids = [nsc.get(_norm_drug(drugs.get(p['drug'], {}).get('name', ''))) for p in comps]
    if None in ids:
        e['ignored'] += [describe(p, drugs) + ' (not in ALMANAC)' for p, i in zip(comps, ids) if i is None]; return e
    a, b = ids; on = ((A['nsc1'] == a) & (A['nsc2'] == b)) | ((A['nsc1'] == b) & (A['nsc2'] == a))
    cells = [idx['cells'][c] for c in np.unique(A['cell'][on])]
    if not cells:
        e['ignored'].append('This pair was not screened together in ALMANAC.'); return e
    scores = {'Bliss': [], 'Loewe': []}; calls = {'Bliss': {}, 'Loewe': {}}
    for c in cells:
        try:
            r = Y.analyse(types.SimpleNamespace(root=root), c, a, b)
        except ValueError:
            continue
        for k in scores:
            if k in r['scores'] and r['scores'][k]['mean'] is not None:
                scores[k].append(r['scores'][k]['mean']); calls[k][r['scores'][k]['call']] = calls[k].get(r['scores'][k]['call'], 0) + 1
    e['represented'] = [f'{describe(comps[0], drugs)} + {describe(comps[1], drugs)} → ALMANAC pair NSC {a} × NSC {b}, {len(scores["Bliss"])} NCI-60 cell lines (ALMANAC doses, not the concentrations above)']
    for k, v in scores.items():
        if v:
            v = np.array(v); h = 1.96 * v.std(ddof=1) / math.sqrt(len(v)) if len(v) > 1 else float('nan')
            e['metrics'] += [[f'{k} score, mean over cell lines (percentage points)', 0.0, float(v.mean())], [f'{k} · 95 % CI over cell lines', None, f'{v.mean() - h:+.1f} to {v.mean() + h:+.1f}'],
                             [f'{k} · per-line calls', None, ', '.join(f'{n} {c}' for c, n in sorted(calls[k].items(), key=lambda x: -x[1]))]]
    if e['metrics']:
        e['status'] = 'ran'; bl = e['metrics'][0][2]; lo = next((m[2] for m in e['metrics'] if m[0].startswith('Loewe score')), None)
        e['summary'] = f'Measured: Bliss {bl:+.1f} pp' + (f', Loewe {lo:+.1f} pp' if lo is not None else '') + f' on average across {len(scores["Bliss"])} cell lines.'
        e['caveats'] = ['48 h growth in NCI-60 lines at the screen\'s own doses. Same-target pairs are expected near Loewe additivity (≈ 0).', 'Compare its sign with the simulators\' interaction readout; they measure different things (growth vs signalling).']
    return e


def _norm_drug(n):
    n = re.sub(r'\b(hydrochloride|dihydrochloride|mesylate|dimesylate|tosylate|ditosylate|maleate|malate|citrate|sulfate|phosphate|sodium|acetate|hcl|monohydrate|hydrate|free base)\b', '', n.lower())
    return re.sub(r'[^a-z0-9]', '', n)


def kuznetsov(perts):
    from scipy.integrate import solve_ivp
    e = engine('ode_immune', IMMUNE['name'], 'simulator', 'Mechanistic simulation (published phenomenological ODE)')
    f = 1.0
    for p in perts:
        if p['kind'] == 'immune':
            f *= p['factor']; e['represented'].append(describe(p) + f' → σ × {p["factor"]:g}')
        else:
            e['ignored'].append(describe(p))
    if not e['represented']:
        return e
    P = IMMUNE['params']
    def run(sig):
        rhs = lambda t, z: [sig + P['rho'] * z[0] * z[1] / (P['eta'] + z[1]) - P['mu'] * z[0] * z[1] - P['delta'] * z[0], P['alpha'] * z[1] * (1 - P['beta'] * z[1]) - z[0] * z[1]]
        return solve_ivp(rhs, (0, 150), [P['sigma'] / P['delta'], 10.0], method='LSODA', rtol=1e-8, atol=1e-10, t_eval=np.linspace(0, 150, 300))
    b, q = run(P['sigma']), run(P['sigma'] * f)
    e['metrics'] = [['tumor cells at t = 150 (×10⁶)', b.y[1, -1], q.y[1, -1]], ['effector cells at t = 150 (×10⁶)', b.y[0, -1], q.y[0, -1]], ['peak tumor (×10⁶)', b.y[1].max(), q.y[1].max()]]
    e['series'] = {'time': b.t.tolist(), 'unit': '×10⁶ cells vs dimensionless time', 'baseline': {'tumor': b.y[1].tolist(), 'effector': b.y[0].tolist()}, 'perturbed': {'tumor': q.y[1].tolist(), 'effector': q.y[0].tolist()}}
    e['status'] = 'ran'; e['summary'] = f'Tumor at end of run: {b.y[1, -1]:.3g} → {q.y[1, -1]:.3g} ×10⁶ cells ({_pct(b.y[1, -1], q.y[1, -1])}).'
    e['caveats'] = [f'{IMMUNE["context"]}.', 'Two populations, well mixed: no space, no exhaustion, no antigen loss, no suppression by other cells. Starting tumor 10 × 10⁶ cells, effectors at their tumor-free level.']
    return e


def fba(root, perts, drugs):
    e = engine('fba', 'Human-GEM flux balance (genome-scale metabolism)', 'simulator', 'Mechanistic simulation (stoichiometric constraint model)')
    genes = [(g, s, p) for p in perts for g, s in targets(p, drugs)]
    for p in perts:
        if p['kind'] not in ('gene', 'compound'):
            e['ignored'].append(describe(p))
    if not genes:
        return e
    try:
        import cobra
    except ImportError:
        e['status'] = 'unavailable'; e['summary'] = 'Needs the science runtime with COBRApy.'; return e
    import csv
    import metabolism as MB
    d = pathlib.Path(root) / 'oncology' / 'metabolism' / 'Human-GEM-v2.1.1'
    if not (d / 'Human-GEM.json').is_file():
        e['status'] = 'unavailable'; e['summary'] = 'Install Human-GEM in the Metabolism tab.'; return e
    with open(d / 'genes.tsv') as fh:
        rows = [(row['genes'], (row.get('geneSymbols') or '').split(';')[0].upper()) for row in csv.DictReader(fh, delimiter='\t')]
    if not {g for g, _, _ in genes} & {s for _, s in rows}:              # no metabolic target: skip the 8 s model load
        e['ignored'] += [f'{g} (not a metabolic gene in Human-GEM)' for g, _, _ in genes]; return e
    m = cobra.io.load_json_model(str(d / 'Human-GEM.json')); sym = {}
    for gid, s in rows:
        if s and gid in m.genes:
            sym.setdefault(s, []).append(m.genes.get_by_id(gid))
    MB.set_medium(m, MB.HAMS + MB.SERUM); m.objective = MB.BIOMASS; wt = m.slim_optimize(error_value=0.0)
    with m:
        for g, s, p in genes:
            if g not in sym:
                continue
            with m:                                              # reactions that lose every catalyst when the gene is lost
                before = {r.id: r.bounds for r in m.reactions}
                for gene in sym[g]:
                    gene.knock_out()
                rx = [m.reactions.get_by_id(rid) for rid, b in before.items() if b != (0.0, 0.0) and m.reactions.get_by_id(rid).bounds == (0.0, 0.0)]
            for r in rx:
                r.bounds = (r.lower_bound * (1 - s), r.upper_bound * (1 - s))
            e['represented'].append(f'{describe(p, drugs)} → {g}: {len(rx)} reaction(s) lose {s:.0%} capacity' + ('' if rx else ' (isoenzymes or complexes keep every reaction running)'))
        ko = m.slim_optimize(error_value=0.0)
    for g, s, p in genes:
        if g not in sym:
            e['ignored'].append(f'{g} (not a metabolic gene in Human-GEM)')
    if not e['represented']:
        return e
    e['metrics'] = [["relative growth in Ham's F-12 (biomass flux)", wt, ko]]; e['status'] = 'ran'
    e['summary'] = f'Biomass {wt:.4f} → {ko:.4f} ({_pct(wt, ko)}).'
    e['caveats'] = ['Steady-state stoichiometry: no regulation, kinetics or enzyme capacity. Partial inhibition scales the bounds of reactions that lose all catalysts.',
                    "Medium: Ham's F-12 plus serum vitamins, glucose ≤ 1 (relative units)."]
    return e


# ---------------------------------------------------------------- measured data, statistics, AI, curated
def depmap(s, system, perts, drugs):
    import oncology_data as D
    import oncology_stats as S
    e = engine('depmap', 'DepMap CRISPR knockout screen', 'measured data', 'Experimental observation (Chronos-corrected CRISPR gene effect)')
    genes = [(g, st, p) for p in perts for g, st in targets(p, drugs)]
    for p in perts:
        if p['kind'] not in ('gene', 'compound'):
            e['ignored'].append(describe(p))
    if not genes:
        return e
    try:
        rel = D.Release(s)
    except ValueError as x:
        e['status'] = 'unavailable'; e['summary'] = str(x); return e
    lin = system.get('lineage')
    for g, st, p in genes:
        try:
            prof = S.gene_profile(rel, g)
        except ValueError:
            e['ignored'].append(f'{g} (not in the screen)'); continue
        row = next((l for l in prof['lineages'] if l['lineage'] == lin), None)
        rank = next((i + 1 for i, l in enumerate(prof['lineages']) if l['lineage'] == lin), None)
        e['represented'].append(f'{describe(p, drugs)} → {g} knockout (complete loss; the {st:.0%} strength is not representable here)')
        if row:
            e['metrics'].append([f'{g} · median gene effect in {lin} (n = {row["n"]})', 0.0, row['median']])
            e['metrics'].append([f'{g} · share of {lin} models dependent (< −0.5)', None, row['fracDependent']])
        e['metrics'].append([f'{g} · median gene effect, all models (n = {prof["n"]})', 0.0, float(np.median([q["effect"] for q in prof['points']]))])
        if rank:
            e['metrics'].append([f'{g} · {lin} rank among {len(prof["lineages"])} lineages (1 = most dependent)', None, rank])
    if e['represented']:
        e['status'] = 'ran'; first = e['metrics'][0]
        e['summary'] = f'{first[0]}: {first[2]:.2f} (0 = no effect, −1 ≈ common essential).'
        e['caveats'] = [f'DepMap {rel.release}: measured in cancer cell lines in culture, one model per patient. A knockout is not a drug: no partial inhibition, no time course, no tumor environment.']
    return e


def gdsc(s, system, perts, drugs):
    import drug_response as R
    from scipy.stats import mannwhitneyu
    e = engine('gdsc', 'GDSC measured drug response', 'measured data', 'Experimental observation (fitted LN_IC50 from viability assays)')
    ai = engine('ridge', 'Expression → response model (ridge)', 'AI model', 'AI prediction (regularised regression), validated on the held-out lineage')
    comps = [p for p in perts if p['kind'] == 'compound']
    for p in perts:
        if p['kind'] != 'compound':
            e['ignored'].append(describe(p)); ai['ignored'].append(describe(p))
    if not comps:
        return [e, ai]
    try:
        d = R.Data(s)
    except ValueError as x:
        e['status'] = ai['status'] = 'unavailable'; e['summary'] = ai['summary'] = str(x); return [e, ai]
    lin = system.get('lineage')
    for p in comps:
        ids, y, *_ = d.table(p['drug']); inl = np.array([d.meta(m, 'OncotreeLineage') == lin for m in ids]); name = d.drugs[p['drug']]['name']
        e['represented'].append(describe(p, drugs) + ' → measured responses (doses fixed by the assay; this perturbation\'s strength or concentration is not used)')
        if inl.sum() >= 3:
            pv = mannwhitneyu(y[inl], y[~inl]).pvalue
            e['metrics'] += [[f'{name} · median LN_IC50 in {lin} (n = {int(inl.sum())})', float(np.median(y[~inl])), float(np.median(y[inl]))], [f'{name} · {lin} vs other lineages, Mann–Whitney p', None, pv]]
        else:
            e['metrics'].append([f'{name} · lines from {lin} screened', None, int(inl.sum())])
        try:
            r = R.held_out_lineage(s, p['drug'], lin)
            rr = r['results']['ridge']
            ai['represented'].append(f'{describe(p, drugs)} → {name}: trained on other lineages, predicted for {lin}')
            ai['metrics'] += [[f'{name} · predicted vs measured in {lin}, Pearson', None, rr.get('pearson')], [f'{name} · RMSE (LN_IC50), ridge vs predicting the training mean', r['results']['mean']['rmse'], rr['rmse']],
                              [f'{name} · 90 % interval coverage', None, rr.get('coverage90')]]
        except ValueError as x:
            ai['ignored'].append(f'{name}: {x}')
    if e['metrics']:
        e['status'] = 'ran'; e['summary'] = '; '.join(f'{m[0].split(" · ")[0]}: median LN_IC50 {m[2]:.2f} in {lin} vs {m[1]:.2f} elsewhere' for m in e['metrics'] if 'median' in m[0]) or e['metrics'][0][0]
        e['caveats'] = ['72 h viability of cell lines in culture at GDSC concentrations; says nothing about patients, exposure or the tumor environment.']
    if ai['metrics']:
        ai['status'] = 'ran'; ai['summary'] = 'How well the model transfers to this lineage, measured before any prediction is trusted: ' + '; '.join(f'{m[0].split(" · ")[0]} r = {m[2]:.2f}' for m in ai['metrics'] if 'Pearson' in m[0] and m[2] is not None)
        ai['caveats'] = ['A prediction is only as good as its held-out score; a low Pearson means the model does not know this lineage.']
    return [e, ai]


def cohort(s, system, perts, drugs):
    import cancer_genomics as G
    e = engine('cohort', 'Patient cohort (cBioPortal)', 'statistical', 'Statistical association (naturally occurring alterations, retrospective)')
    study = system.get('study'); genes = [(g, p) for p in perts for g, _ in targets(p, drugs)]
    for p in perts:
        if p['kind'] not in ('gene', 'compound'):
            e['ignored'].append(describe(p))
    if not genes or not study:
        return e
    if not (pathlib.Path(s.root) / 'oncology' / 'cbioportal' / study / 'manifest.json').is_file():
        e['status'] = 'unavailable'; e['summary'] = f'{study} is not installed.'; return e
    for g, p in genes:
        try:
            r = G.survival(s, study, g)
        except ValueError as x:
            e['ignored'].append(f'{g}: {x}'); continue
        c = r['cox'][0]
        e['represented'].append(f'{describe(p, drugs)} → patients whose tumors have {g} altered (not an inhibition)')
        e['metrics'] += [[f'{g} · altered patients', None, f'{r["altered"]} of {r["patients"]}'], [f'{g} · OS hazard ratio, altered vs not (age-adjusted)', 1.0, c['hr']], [f'{g} · 95 % CI', None, f'{c["ci"][0]:.2f}–{c["ci"][1]:.2f}']]
    if e['metrics']:
        e['status'] = 'ran'; e['summary'] = '; '.join(f'{m[0].split(" · ")[0]} HR {m[2]:.2f}' for m in e['metrics'] if 'hazard' in m[0])
        e['caveats'] = [f'{study}: an alteration that tumors acquired is the opposite direction to inhibiting a gene and is confounded by stage and treatment; this is association, not a predicted effect.']
    return e


def curated(s, perts, drugs):
    e = engine('evidence', 'Evidence graph (CIViC, Open Targets, STRING, literature)', 'curated knowledge', 'Curated evidence (expert-reviewed clinical and database records)')
    names = {d['name'].lower() for d in drugs.values()}
    for p in perts:
        genes = [g for g, _ in targets(p, drugs)]
        if not genes:
            e['ignored'].append(describe(p)); continue
        for g in genes:
            f = pathlib.Path(s.root) / 'oncology' / 'evidence' / g / 'graph.json'
            if not f.is_file():
                e['ignored'].append(f'{g}: no evidence graph built (Evidence graph tab covers KRAS)'); continue
            gr = json.loads(f.read_text()); e['represented'].append(f'{describe(p, drugs)} → evidence graph for {g}')
            drug_edges = [x for x in gr['edges'] if x['target'].startswith('drug:') and x['origin'] == 'curated']
            for x in drug_edges[:8]:
                e['metrics'].append([f'{x["source"].split(":")[1]} → {x["target"].split(":")[1]} · {x["relation"]}', None, f'{x.get("strength", "")} · {x["database"]} · {x.get("context", "")}'])
            e['metrics'].append([f'{g} · links by origin', None, ', '.join(f'{k} {v}' for k, v in sorted({o: sum(1 for x in gr['edges'] if x['origin'] == o) for o in {x['origin'] for x in gr['edges']}}.items()))])
    if e['represented']:
        e['status'] = 'ran'; e['summary'] = f'{sum(1 for m in e["metrics"] if "→" in m[0])} curated drug–response records shown.'
        e['caveats'] = ['Curated records describe what was observed in patients or trials under their own conditions; they are not computed for this experiment.']
    return e


OUTSIDE = {
    'gene': ['effects in normal tissue and organism-level toxicity', 'adaptive resistance over weeks (no engine models selection)'],
    'interaction': ['the structural cause of a changed interaction: Boltz-2 can predict a mutant complex (Boltz workspace, GPU), but its confidence is not a binding affinity'],
    'compound': ['pharmacokinetics and tumor exposure', 'off-target activity beyond the annotated targets', 'patient benefit'],
    'immune': ['spatial infiltration: run the 3D PhysiCell tumor–immune model in the Tumor microenvironment tab with immune cells × your factor (GPU run on your server, needs cost approval)', 'immune suppression, exhaustion and checkpoint biology'],
}


def _pct(a, b):
    return '—' if not a else f'{(b - a) / abs(a):+.0%}'


def run(root, exp):
    s = types.SimpleNamespace(root=root); t0 = time.time()
    try:
        import drug_response as R
        drugs = {k: v for k, v in R.Data(s).drugs.items()}
    except Exception:
        drugs = {}
    perts = _norm_perturbations(exp['perturbations']); system = exp.get('system') or {}
    engines = [engagement(root, perts, drugs)]
    sims = [(MODELS[k]['name'], (lambda k=k: ode_model(k, perts, drugs))) for k in MODELS]
    for label, f in (*sims, ('Tumor–immune model', lambda: kuznetsov(perts)),
                     ('Human-GEM', lambda: fba(root, perts, drugs)), ('DepMap', lambda: depmap(s, system, perts, drugs)), ('GDSC', lambda: gdsc(s, system, perts, drugs)),
                     ('NCI ALMANAC', lambda: almanac(root, perts, drugs)), ('Patient cohort', lambda: cohort(s, system, perts, drugs)), ('Evidence graph', lambda: curated(s, perts, drugs))):
        try:
            r = f(); engines += r if isinstance(r, list) else [r]
        except Exception as x:                                   # one engine failing never hides the others
            engines.append({**engine('error-' + label, label, 'error', ''), 'status': 'error', 'summary': f'{type(x).__name__}: {x}'})
        print(f'[{time.time() - t0:5.1f}s] {engines[-1]["name"]}: {engines[-1]["status"]}', flush=True)
    matrix = [{'perturbation': describe(p, drugs), 'engines': {e['id']: ('ran' if any(r.startswith(describe(p, drugs)) for r in e['represented']) else 'not applicable' if e['status'] != 'unavailable' else 'unavailable') for e in engines}} for p in perts]
    return {'title': ' + '.join(describe(p, drugs) for p in perts) + (f' · {system.get("lineage")}' if system.get('lineage') else ''), 'system': system, 'perturbations': perts,
            'engines': engines, 'matrix': matrix, 'outside': sorted({x for p in perts for x in OUTSIDE[p['kind']]}), 'seconds': round(time.time() - t0, 1),
            'created': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'rule': 'Engines never pass numbers to each other. Simulations show what a stated mechanism implies; measurements, associations and predictions are reported beside them, not merged.'}


def catalog():
    return {'interactions': sorted({n for m in MODELS.values() for n in m['interactions']}),
            'mappedGenes': sorted({g for m in MODELS.values() for g in m['genes']}),
            'models': [{'id': k, 'name': m['name'], 'context': m['context'], 'genes': {g: v[2] for g, v in m['genes'].items()}, 'interactions': list(m['interactions'])} for k, m in MODELS.items()]
            + [{'id': 'immune', 'name': IMMUNE['name'], 'context': IMMUNE['context'], 'genes': {}, 'interactions': []}]}


def main(root, eid):
    import warnings; warnings.filterwarnings('ignore')
    d = pathlib.Path(root) / 'oncology' / 'perturbation' / eid
    r = run(root, json.loads((d / 'experiment.json').read_text()))
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    from insilico import _clean
    (d / 'result.json').write_text(json.dumps(_clean({**r, 'id': eid})))
    print(f'done in {r["seconds"]} s', flush=True)


if __name__ == '__main__':
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    main(*sys.argv[1:3])
