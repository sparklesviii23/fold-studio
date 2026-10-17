import hashlib, json, pathlib, struct, sys, tempfile, unittest, zipfile
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scientific'))
from worker import Service
from observatory import Observatory
from confidence import read_array, local_confidence

def npz(path,key,values,shape,dtype='<f4',version=1,fortran=False):
    header=repr({'descr':dtype,'fortran_order':fortran,'shape':shape}).encode()+b'\n'
    raw=b'\x93NUMPY'+bytes((version,0))+struct.pack('<H' if version==1 else '<I',len(header))+header
    raw+=struct.pack(dtype[0]+('f' if dtype[-1]=='4' else 'd')*len(values),*values) if dtype[-1] in '48' else b''
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:z.writestr(key+'.npy',raw)

class ConfidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);self.path=self.root/'pae.npz'
        self.s=Service(self.root);self.project=self.s.project_create({'name':'Confidence'});self.o=Observatory(self.s)
    def tearDown(self):self.s.db.close();self.temp.cleanup()
    def test_float_endianness_and_versions_preserve_asymmetric_values(self):
        for dtype in ('<f4','>f4','<f8','>f8'):
            for version in (1,2):
                npz(self.path,'pae',[0.25,1.5,7.75,0.25],(2,2),dtype,version)
                self.assertEqual(read_array(self.path,'pae',2,1000),[[0.25,1.5],[7.75,0.25]])
    def test_objects_and_fortran_arrays_are_refused(self):
        npz(self.path,'pae',[],(2,2),'|O')
        with self.assertRaisesRegex(ValueError,'object arrays'):read_array(self.path,'pae',2,1000)
        npz(self.path,'pae',[1]*4,(2,2),fortran=True)
        with self.assertRaisesRegex(ValueError,'C-order'):read_array(self.path,'pae',2,1000)
    def test_nonfinite_negative_and_out_of_range_values_are_refused(self):
        for value in (float('nan'),float('inf'),-1,1001):
            npz(self.path,'pae',[value]*4,(2,2))
            with self.assertRaisesRegex(ValueError,'out-of-range'):read_array(self.path,'pae',2,1000)
        npz(self.path,'plddt',[1.1],(1,))
        with self.assertRaises(ValueError):read_array(self.path,'plddt',1,1)
    def test_bad_shape_truncation_and_members_are_refused(self):
        for shape,values in [((2,3),[1]*6),((2001,2001),[]),((2,2),[1]),((True,True),[1])]:
            npz(self.path,'pae',values,shape)
            with self.assertRaises(ValueError):read_array(self.path,'pae',2,1000)
        npz(self.path,'pae',[1]*4,(2,2))
        with zipfile.ZipFile(self.path,'a') as z:z.writestr('unexpected.npy',b'junk')
        with self.assertRaisesRegex(ValueError,'members'):read_array(self.path,'pae',2,1000)
    def output(self):
        job=self.s.job_new({'projectId':self.project['id'],'name':'Actual files','chains':[{'sequence':'AG'}]},'boltz2','running')
        folder=self.root/'jobs'/job['id']/'output'/'predictions'/'input';folder.mkdir(parents=True)
        coordinate=folder/'input_model_0.pdb';coordinate.write_text('ATOM      1  CA  ALA A   1       1.000   2.000   3.000  1.00 95.00           C\n')
        record=self.s.import_structure({'projectId':self.project['id'],'path':str(coordinate),'confidenceKind':'Boltz-2 pLDDT','metadata':{'jobId':job['id']}})
        for key in ('pae','pde'):npz(folder/(key+'_input_model_0.npz'),key,[0.25,1.5,7.75,0.25],(2,2))
        npz(folder/'plddt_input_model_0.npz','plddt',[0.5,1],(2,))
        (folder/'confidence_input_model_0.json').write_text(json.dumps({'ptm':0.4,'iptm':0,'complex_ipae':None,'chains_ptm':{'0':0.4}}))
        self.s.job_update(job['id'],'completed',{'outputs':[record['id']]})
        return job,record,folder
    def test_exact_job_and_coordinate_confidence_provenance(self):
        job,record,folder=self.output();before=(self.root/'assets'/record['data']['asset']).read_bytes()
        result=self.o.confidence_fetch({'structureId':record['id']})
        self.assertEqual(result['matrix'],[[0.25,1.5],[7.75,0.25]]);self.assertEqual(result['plddt'],[0.5,1]);self.assertEqual(result['inputSequence'],'AG');self.assertEqual(result['jobId'],job['id'])
        self.assertEqual(result['files'][0]['sha256'],hashlib.sha256((folder/'pae_input_model_0.npz').read_bytes()).hexdigest())
        self.assertEqual(before,(self.root/'assets'/record['data']['asset']).read_bytes());self.assertEqual(self.o.confidence_fetch({'structureId':record['id'],'kind':'pde'})['kind'],'pde')
    def test_missing_or_ambiguous_output_never_substitutes(self):
        job,record,folder=self.output();(folder/'input_model_1.pdb').write_bytes((folder/'input_model_0.pdb').read_bytes())
        with self.assertRaisesRegex(ValueError,'ambiguous'):local_confidence(self.s,record)
        (folder/'input_model_1.pdb').unlink();(folder/'input_model_0.pdb').unlink()
        with self.assertRaisesRegex(ValueError,'missing'):local_confidence(self.s,record)
    def test_changed_coordinate_or_wrong_job_output_is_refused(self):
        job,record,folder=self.output();self.s.job_update(job['id'],'completed',{'outputs':[]})
        with self.assertRaisesRegex(ValueError,'not a completed output'):local_confidence(self.s,record)
        self.s.job_update(job['id'],'completed',{'outputs':[record['id']]});(self.root/'assets'/record['data']['asset']).write_text('changed')
        with self.assertRaisesRegex(ValueError,'checksum changed'):local_confidence(self.s,record)
    def test_missing_arrays_and_disagreeing_tokens_are_refused(self):
        job,record,folder=self.output();(folder/'pae_input_model_0.npz').unlink()
        with self.assertRaisesRegex(ValueError,'No matrix was synthesized'):local_confidence(self.s,record)
        npz(folder/'plddt_input_model_0.npz','plddt',[0.5],(1,))
        with self.assertRaisesRegex(ValueError,'token counts disagree'):local_confidence(self.s,record,'pde')
    def test_multichain_arrays_have_no_inferred_residue_map(self):
        job,record,folder=self.output();self.s.job_update(job['id'],'completed',{'chains':[{'sequence':'A'},{'sequence':'G'}]})
        self.assertIsNone(local_confidence(self.s,record)['selectionMapping'])
    def test_symlink_escape_is_refused(self):
        job,record,folder=self.output();external=self.root/'outside.npz';npz(external,'pae',[1]*4,(2,2));path=folder/'pae_input_model_0.npz';path.unlink();path.symlink_to(external)
        with self.assertRaisesRegex(ValueError,'outside'):local_confidence(self.s,record)
    def test_invalid_summary_is_refused(self):
        job,record,folder=self.output();(folder/'confidence_input_model_0.json').write_text('{"ptm": NaN}')
        with self.assertRaisesRegex(ValueError,'unsupported values'):local_confidence(self.s,record)
    def test_large_export_reads_verified_files_without_a_large_request(self):
        job,record,folder=self.output();values=[1.234567]*460**2
        npz(folder/'pae_input_model_0.npz','pae',values,(460,460));npz(folder/'plddt_input_model_0.npz','plddt',[0.8]*460,(460,))
        target=self.root/'confidence-export.json'
        result=self.s.dispatch('confidence_export',{'structureId':record['id'],'kind':'pae','path':str(target)})
        self.assertEqual(result,str(target));self.assertGreater(target.stat().st_size,2*1024**2)
        saved=json.loads(target.read_text());self.assertEqual(len(saved['matrix']),460);self.assertEqual(saved['sourceSha256'],record['data']['sha256'])
    def test_comparison_rejects_same_source_and_other_project_before_native_calls(self):
        job,record,folder=self.output();other=self.s.project_create({'name':'Other'});copy=self.s.import_structure({'projectId':other['id'],'path':str(folder/'input_model_0.pdb')})
        with patch.object(self.o,'chimerax_open') as opened:
            with self.assertRaisesRegex(ValueError,'distinct'):self.o.comparison_run({'projectId':self.project['id'],'structureId':record['id'],'referenceId':record['id']})
            with self.assertRaisesRegex(ValueError,'selected project'):self.o.comparison_run({'projectId':self.project['id'],'structureId':record['id'],'referenceId':copy['id']})
            opened.assert_not_called()

if __name__=='__main__':unittest.main()
