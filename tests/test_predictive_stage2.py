"""Software invariants only; authentic benchmark evidence is saved separately."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))
import borzoi_panel as P
import virtual_cell_gene_explorer as G
import virtual_cell_state as S
import virtual_cell_response_research as RR


class PanelTests(unittest.TestCase):
    def test_missing_reference_is_not_zero_filled(self):
        a=np.arange(30,dtype=float); b=a.copy(); b[:12]=np.nan
        self.assertEqual(P.score(a,b)['status'],'insufficient_reference')
        s=P.score(a,b,minimum=10)
        self.assertEqual(s['n'],18); self.assertAlmostEqual(s['spearman'],1)
        self.assertEqual(P.score(np.ones(30),a)['status'],'constant_signal')

    def test_invalid_shapes_and_negative_values_are_refused(self):
        with self.assertRaisesRegex(ValueError,'shape'): P.score([1,2],[1])
        with self.assertRaisesRegex(ValueError,'Negative'): P.score(np.arange(30)-1,np.arange(30))

    def test_locus_intervals_and_failed_counts(self):
        rows=[{'status':'scored','pearson':v,'spearman':v} for v in (.1,.3,.5)]+[{'status':'insufficient_reference'}]
        result=P.aggregate(rows)
        self.assertEqual((result['attempted'],result['scored'],result['failed']),(4,3,1))
        self.assertEqual(result,P.aggregate(rows)); self.assertAlmostEqual(result['spearman']['mean'],.3)
        self.assertIsNone(P.aggregate([])['pearson']['ci95'])

    def test_ensemble_comparison_uses_paired_loci_only(self):
        rows=[{'cohort':'heldout','track':1,'symbol':str(i),'model':m,'status':'scored','spearman':i+d}
              for i in range(4) for m,d in [('f0',0),('ensemble',.1)]]
        rows[0]['status']='constant_signal'
        r=P.paired_comparison(rows,1,'f0','spearman')
        self.assertEqual(r['n'],3); self.assertAlmostEqual(r['meanDifference'],.1)

    def stored(self,root):
        run='a'*32; folder=Path(root)/'virtualcell/borzoi-panels'/run; folder.mkdir(parents=True)
        output=Path(root)/'gpu_tasks'/run/'outputs'; output.mkdir(parents=True)
        artifacts=[]
        for name in ('predictions-f0.npz','predictions-f1.npz'):
            (output/name).write_bytes(b'software-fixture')
            artifacts.append({'path':name,'sha256':P.file_hash(output/name)})
        report={'schema':'fold.borzoi.panel-evaluation/1','run':run,'artifacts':artifacts,
                'geneResults':[{'symbol':'G','cellosaurus':'CVCL_0027','geneId':'ENSG1.1','region':['chr1',10,30]}]}
        report['sha256']=P._hash(report); (folder/'evaluation.json').write_text(json.dumps(report))
        return run,folder,output,report

    def test_reader_requires_exact_context_gene_and_coordinate_overlap(self):
        with tempfile.TemporaryDirectory() as root:
            self.stored(root); region={'chromosome':'chr1','start':15,'end':20}
            self.assertEqual(len(P.for_gene(root,'G','CVCL_0027',region,'ENSG1.2')),1)
            for symbol,rrid,reg,gene in [('G','CVCL_1098',region,'ENSG1'),('X','CVCL_0027',region,'ENSG1'),('G','CVCL_0027',{**region,'start':40,'end':50},'ENSG1'),('G','CVCL_0027',region,'ENSG2')]:
                self.assertEqual(P.for_gene(root,symbol,rrid,reg,gene),[])

    def test_missing_manifest_and_artifact_tampering_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            run,folder,output,report=self.stored(root)
            (output/'predictions-f0.npz').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'artifact integrity'): P.load(root,run)
            report['artifacts']=[]; report.pop('sha256'); report['sha256']=P._hash(report)
            (folder/'evaluation.json').write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,'manifest incomplete'): P.load(root,run)
            with self.assertRaises(ValueError): P.load(root,'../escape')


class GeneExplorerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=self.tmp.name
        self.ref=SimpleNamespace(cellosaurus='CVCL_0027'); self.cell={'id':'b'*32,'sha256':'cell-hash','name':'C','history':[],'reference':None}
        self.protein={'resolution':{'status':'resolved'},'symbol':'G','context':'Hep G2','identifiers':{'ensembl':['ENSG1.3']},
                      'expression':{'gene':'G','baseline':2.,'unit':'log2(TPM+1)','inPanel':True,'baselineSource':'measured source','change':9.,'current':11.}}
        self.tx={'geneId':'ENSG1.1','chrom':'chr1','start':16,'end':20,'transcripts':[{}]}
        self.patches=[patch.object(G.V,'protein',return_value=self.protein),patch.object(G.V,'context_info',return_value={'name':'Hep G2','cellosaurus':'CVCL_0027'}),
                      patch.object(G.T,'available',return_value=True),patch.object(G.T,'gene',return_value=self.tx),patch.object(G.R,'listing',return_value={'runs':[]})]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def test_measured_block_excludes_modelled_current_values(self):
        report=G.explore(SimpleNamespace(root=self.root),self.ref,self.cell,'G')
        self.assertNotIn('change',report['observedRNA']['baseline']); self.assertNotIn('current',report['observedRNA']['baseline'])
        self.assertEqual(report['gene']['region']['start'],15)
        self.assertEqual(report['regulatory']['predictions'],[])
        self.assertEqual(report['regulatory']['message'],'Prediction not available for this biological context.')
    def test_transcript_mismatch_is_refused(self):
        self.tx['geneId']='ENSG2'
        with self.assertRaisesRegex(ValueError,'identifier mismatch'): G.explore(SimpleNamespace(root=self.root),self.ref,self.cell,'G')
    def test_parental_transcripts_never_transfer_to_c3a(self):
        self.ref.cellosaurus='CVCL_1098'
        with patch.object(G.T,'gene') as tx:
            report=G.explore(SimpleNamespace(root=self.root),self.ref,self.cell,'G')
            tx.assert_not_called(); self.assertIsNone(report['observedRNA']['transcripts'])
    def test_snapshot_export_roundtrip_preserves_evidence_and_context(self):
        result=G.snapshot(SimpleNamespace(root=self.root),self.ref,self.cell,'G')
        saved=result['snapshot']; bundle=S.export(self.root,self.cell['id'],saved['id'])
        restored=S.validate_bundle(json.loads(json.dumps(bundle)),{'name':'Hep G2','cellosaurus':'CVCL_0027'})
        self.assertEqual(restored['blocks']['observedRNA']['category'],'measured')
        self.assertEqual(restored['blocks']['geneIdentity']['provenance'],result['report'])
        self.assertEqual(self.cell['history'],[])


class DiagnosticTests(unittest.TestCase):
    def test_wald_bh_handles_missing_and_empty_values(self):
        self.assertEqual(RR.bh_count(np.array([np.nan])),0)
        self.assertEqual(RR.bh_count(np.array([0.,10.,-10.,np.nan])),2)
    def test_diagnostics_cannot_save_an_unverified_report(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,'checksum'): RR.save_diagnostics(root,{'sourceRun':'a'*32,'sha256':'wrong'})

if __name__=='__main__':unittest.main()
