"""Observed/predicted gene dossier on the existing Virtual Cell context and history."""
import json
from pathlib import Path

import virtual_cell as V
import virtual_cell_state as S
import virtual_cell_registry as C
import virtual_cell_transcripts as T
import virtual_cell_regulatory as R


def explore(service, ref, cell, query):
    protein=V.protein(service.root,ref,cell,query)
    if protein['resolution']['status']!='resolved': return {'supported':False,'resolution':protein['resolution'],'values':None}
    symbol=protein['symbol']; context=V.context_info(ref); rrid=getattr(ref,'cellosaurus',None) or 'CVCL_0004'
    tx=T.gene(service.root,symbol) if rrid=='CVCL_0027' and T.available(service.root) else None
    consistency=[]
    if tx and tx.get('transcripts'):
        gene_ids={x.split('.')[0] for x in protein['identifiers']['ensembl']}
        if gene_ids and tx['geneId'].split('.')[0] not in gene_ids: raise ValueError('Transcript-to-gene identifier mismatch; report refused.')
        region={'assembly':'GRCh38','chromosome':tx['chrom'],'start':tx['start']-1,'end':tx['end'],'coordinateConvention':'zero-based half-open'}
        consistency.append({'check':'transcript_gene_identity','status':'matched_ensembl' if gene_ids else 'symbol_match_only_ensembl_link_unavailable'})
    else: region=None; consistency.append({'check':'transcript_gene_identity','status':'not_available'})
    predictions=[]
    for job in R.listing(service.root,rrid)['runs']:
        if job['jobState']!='done' or region is None: continue
        result=R.get(service.root,job['run'],rrid)
        if result['supported'] and result['reference']['chromosome']==region['chromosome'] and result['start']<region['end'] and result['end']>region['start']:
            predictions.append({'provider':'bio_borzoi','result':result,'scope':'reference-DNA assay prediction; not cellular expression',
                                'fullGeneCovered':result['start']<=region['start'] and region['end']<=result['end']})
    # The panel reader is optional until an approved panel has actually completed.
    from borzoi_panel import for_gene
    if region: predictions.extend(for_gene(service.root,symbol,rrid,region,tx['geneId']))
    report={'schema':'fold.virtualcell.gene-explorer/1','created':S.now(),'supported':True,'cellId':cell['id'],'cellSha256':cell['sha256'],
            'context':context,'gene':{'symbol':symbol,'identifiers':protein['identifiers'],'region':region},
            'observedRNA':{'category':'measured','baseline':{k:v for k,v in protein['expression'].items() if k in ('gene','baseline','unit','inPanel','baselineSource','evidenceBaseline','depmapBulk')},'transcripts':tx,
                           'note':'Transcript TPM is measured per replicate. Gene TPM sums and replicate means are computed summaries, not additional measurements.'},
            'protein':protein,'regulatory':{'category':'prediction','predictions':predictions,
                'message':None if predictions else 'Prediction not available for this biological context.'},
            'predictiveResponse':{'category':'unsupported','message':'Prediction not available for this biological context.',
                                  'reason':'No independently validated response predictor is recommended for this gene/cell request.'+(' Parental HepG2 is not the Tahoe HepG2/C3A derivative.' if rrid=='CVCL_0027' else ' Retrospective benchmark scores are not calibrated predictions for an unspecified new condition.')},
            'consistency':consistency+[{'check':'cell_identity','status':'preserved','cellosaurus':rrid},
                                      {'check':'units','status':'kept_separate','note':'Genomic coverage, RNA TPM, protein ppm, localization calls and structural confidence are distinct quantities.'}],
            'limitations':['Reference datasets come from separate experiments, samples and years.', 'Reactome membership is curated annotation, not measured pathway activity.',
                           'Protein abundance is not inferred from RNA or Borzoi.', 'Saved structures retain their own experimental/predicted origin and confidence semantics.']}
    report['sha256']=V._sha(report); return report


def snapshot(service,ref,cell,query):
    report=explore(service,ref,cell,query)
    if not report['supported']: raise ValueError('Resolve an unambiguous gene before saving.')
    g=report['gene']['symbol']; p=report['protein']; blocks={}
    e=p['expression']
    if e.get('inPanel'):
        blocks['observedRNA']=S.block('measured',{g:e['baseline']},e.get('baselineSource') or 'DepMap 24Q4',unit=e['unit'],context=p['context'])
    blocks['geneIdentity']=S.block('annotation',{'symbol':g},'UniProt/HPA identifiers',context=p['context'])
    blocks['geneIdentity']['provenance']=report
    saved=S.create(service.root,cell,V.context_info(ref),f'{g} · observed versus predicted','imported',blocks)
    folder=Path(service.root)/'virtualcell/gene-reports'; folder.mkdir(parents=True,exist_ok=True)
    (folder/f'{saved["id"]}.json').write_text(json.dumps(report,indent=1,allow_nan=False))
    return {'snapshot':saved,'report':report}
