"""Assay summary arithmetic, independent-unit handling and actual persistence."""
import copy,hashlib,json,math,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from assay_statistics import summarize,T975
from test_research_cinema import ResearchCinemaTests as Fixture

def assay():
    rows=[]
    for bio,values in [('b1',[0,2]),('b2',[9,11]),('b3',[18,22])]:
        for i,response in enumerate(values):rows.append({'concentration':10,'response':response,'biologicalReplicate':bio,'technicalReplicate':str(i+1),'sampleGroup':'candidate'})
    return {'name':'Arithmetic fixture, not experimental data','endpoint':'Test response at fixed time','responseUnit':'RU','concentrationUnit':'nM','replicateDesign':'explicit_biological_technical','rows':rows}

class AssayArithmetic(unittest.TestCase):
    def test_technical_repeats_are_collapsed_before_biological_statistics(self):
        original=assay();before=copy.deepcopy(original);result=summarize(original);group=result['groups'][0]
        means=[1,10,20];mean=sum(means)/3;sd=math.sqrt(sum((v-mean)**2 for v in means)/2)
        self.assertEqual(group['biologicalUnits'],3);self.assertEqual(group['rawReadings'],6)
        self.assertAlmostEqual(group['mean'],mean);self.assertAlmostEqual(group['sampleSD'],sd)
        half=4.302652729749462*sd/math.sqrt(3)
        self.assertAlmostEqual(group['confidenceInterval95'][0],mean-half,places=12);self.assertAlmostEqual(group['confidenceInterval95'][1],mean+half,places=12);self.assertEqual(original,before)
    def test_unbalanced_technical_replication_does_not_reweight_biological_units(self):
        data=assay();data['rows']=[{'concentration':1,'response':v,'biologicalReplicate':bio,'technicalReplicate':str(i),'sampleGroup':'candidate'} for bio,values in [('b1',[0]*20),('b2',[10])] for i,v in enumerate(values)]
        result=summarize(data)['groups'][0];self.assertEqual(result['mean'],5);self.assertEqual(result['biologicalUnits'],2);self.assertEqual(result['rawReadings'],21)
    def test_one_biological_unit_has_no_inferred_interval(self):
        data=assay();data['rows']=data['rows'][:2];result=summarize(data)['groups'][0]
        self.assertEqual(result['mean'],1)
        for field in ['sampleSD','standardError','confidenceInterval95']:self.assertIsNone(result[field])
    def test_doses_and_control_groups_are_not_pooled(self):
        data=assay();data['rows']+=[{**data['rows'][0],'concentration':0,'sampleGroup':'vehicle'},{**data['rows'][0],'concentration':20}]
        result=summarize(data);self.assertEqual(len(result['groups']),3)
        self.assertEqual(sorted(group['biologicalUnits'] for group in result['groups']),[1,1,3])
    def test_ambiguous_duplicate_and_mixed_endpoint_rows_are_refused(self):
        for change in ['legacy','duplicate','endpoint','unit','missing','nonfinite']:
            data=assay()
            if change=='legacy':data.pop('replicateDesign')
            elif change=='duplicate':data['rows'].append(data['rows'][0])
            elif change=='endpoint':data['rows'][0]['endpoint']='another endpoint'
            elif change=='unit':data['rows'][0]['responseUnit']='percent'
            elif change=='missing':data['rows'][0].pop('biologicalReplicate')
            elif change=='nonfinite':data['rows'][0]['response']=float('nan')
            with self.subTest(change=change),self.assertRaises(ValueError):summarize(data)
    def test_large_biological_sample_uses_explicit_conservative_df_cap(self):
        data=assay();data['rows']=[{'concentration':1,'response':i,'biologicalReplicate':str(i),'technicalReplicate':'1','sampleGroup':'candidate'} for i in range(40)]
        result=summarize(data)['groups'][0];self.assertEqual(result['intervalDegreesOfFreedom'],30);self.assertTrue(result['intervalIsConservative'])
    def test_t_critical_table_matches_scipy_reference_when_available(self):
        try:from scipy.stats import t
        except ImportError:self.skipTest('SciPy is only needed for the independent numerical reference')
        for df,critical in enumerate(T975,1):self.assertAlmostEqual(critical,float(t.ppf(.975,df)),places=10)
        result=summarize(assay())['groups'][0]
        interval=t.interval(.95,2,loc=result['mean'],scale=result['standardError'])
        for expected,actual in zip(interval,result['confidenceInterval95']):self.assertAlmostEqual(float(expected),actual,places=10)

class AssayPersistence(unittest.TestCase):
    setUp=Fixture.setUp
    tearDown=Fixture.tearDown
    call=Fixture.call
    def test_summary_uses_exact_saved_source_and_is_idempotent(self):
        saved=self.call('research_assay_save',**assay());summary=self.call('research_assay_summary',assayId=saved['id'])
        self.assertEqual(summary['data']['groups'][0]['biologicalUnits'],3)
        self.assertEqual(summary['data']['sourceSha256'],self.hash)
        expected=hashlib.sha256(json.dumps(saved['data'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        self.assertEqual(summary['data']['assaySha256'],expected)
        self.assertEqual(summary['data']['summarySourceSha256'],hashlib.sha256((pathlib.Path(__file__).resolve().parents[1]/'scientific/assay_statistics.py').read_bytes()).hexdigest())
        self.assertEqual(self.call('research_assay_summary',assayId=saved['id'])['id'],summary['id'])
        self.assertEqual(next(e for e in self.call('research_candidate')['evidence'] if e['id']==saved['id'])['data'],saved['data'])
        with self.assertRaises(ValueError):self.s.dispatch('research_assay_summary',{**self.p,'projectId':'another','assayId':saved['id']})
    def test_legacy_records_remain_raw_and_unmodified(self):
        saved=self.call('research_assay_save',name='Legacy fixture',concentrationUnit='nM',responseUnit='RU',rows=[{'concentration':1,'response':1,'replicate':'1'}])
        with self.assertRaisesRegex(ValueError,'Legacy'):self.call('research_assay_summary',assayId=saved['id'])
        self.assertEqual(saved['data']['rows'],[{'concentration':1,'response':1,'replicate':'1'}])
    def test_changed_assay_source_identity_is_not_silently_rebound(self):
        saved=self.call('research_assay_save',**assay());changed={**saved['data'],'sourceSha256':'0'*64}
        self.s.db.execute('UPDATE research_evidence SET data=? WHERE id=?',(json.dumps(changed),saved['id']));self.s.db.commit()
        with self.assertRaisesRegex(ValueError,'source identity'):self.call('research_assay_summary',assayId=saved['id'])

del Fixture
if __name__=='__main__':unittest.main()
