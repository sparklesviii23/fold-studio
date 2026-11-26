"""Read-only integrity review, including actual Fold exporter output; no model work."""
import copy
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
import warnings
import zipfile
from unittest.mock import patch

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
from project_archive import inspect_archive


class ProjectArchiveReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=pathlib.Path(self.temp.name)
        self.payload=b'ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\nEND\n'
        sha=hashlib.sha256(self.payload).hexdigest()
        self.data={'format':'fold-project-v1','project':{'name':'Isolated archive fixture'},'records':[{'kind':'structure','data':{'asset':'model.pdb','sha256':sha}}],'jobs':[], 'assetManifest':[{'file':'assets/model.pdb','sha256':sha,'bytes':len(self.payload)}]}
        self.path=self.root/'fixture.zip'
    def tearDown(self):self.temp.cleanup()
    def write(self,data=None,extra=None,payload=None):
        with zipfile.ZipFile(self.path,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('project.json',json.dumps(self.data if data is None else data))
            archive.writestr('assets/model.pdb',self.payload if payload is None else payload)
            for name,value in extra or []:archive.writestr(name,value)
    def test_real_export_is_reviewed_without_import_or_job_execution(self):
        service=Service(self.root/'research')
        try:
            project=service.project_create({'name':'Exported isolated fixture'})
            source=self.root/'input.pdb';source.write_bytes(self.payload)
            service.import_structure({'projectId':project['id'],'path':str(source)})
            service.export_project({'id':project['id'],'path':str(self.path)})
            before=service.library({})
            with patch('subprocess.Popen',side_effect=AssertionError('Archive inspection must never launch a worker')):
                result=service.dispatch('project_archive_inspect',{'path':str(self.path)})
            self.assertEqual(result['state'],'integrity_reviewed')
            self.assertEqual(result['verifiedAssetCount'],1)
            self.assertEqual(result['recordCount'],1)
            self.assertEqual(result['archiveSha256'],hashlib.sha256(self.path.read_bytes()).hexdigest())
            self.assertEqual(service.library({}),before)
            self.assertFalse((self.root/'assets').exists())
        finally:service.db.close()
    def test_checksum_and_record_manifest_mismatches_fail(self):
        self.write(payload=b'x'*len(self.payload))
        with self.assertRaisesRegex(ValueError,'checksum mismatch'):inspect_archive({'path':str(self.path)})
        changed=copy.deepcopy(self.data);changed['records'][0]['data']['sha256']='b'*64;self.write(data=changed)
        with self.assertRaisesRegex(ValueError,'reference differs'):inspect_archive({'path':str(self.path)})
        changed['records'][0]['data']={'asset':'undeclared.pdb'};self.write(data=changed)
        with self.assertRaisesRegex(ValueError,'reference differs'):inspect_archive({'path':str(self.path)})
    def test_unsafe_duplicate_symlink_and_oversized_members_fail(self):
        for name in ('../escape','/escape','assets/../escape','assets\\escape','assets//escape'):
            self.write(extra=[(name,b'x')])
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'unsafe'):inspect_archive({'path':str(self.path)})
        link=zipfile.ZipInfo('assets/link');link.external_attr=0o120777<<16
        self.write(extra=[(link,b'../escape')])
        with self.assertRaisesRegex(ValueError,'unsafe'):inspect_archive({'path':str(self.path)})
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning);self.write(extra=[('project.json',b'{}')])
        with self.assertRaisesRegex(ValueError,'duplicate'):inspect_archive({'path':str(self.path)})
        self.write(extra=[('assets/MODEL.pdb',b'x')])
        with self.assertRaisesRegex(ValueError,'duplicate'):inspect_archive({'path':str(self.path)})
        self.write()
        with patch('project_archive.MAX_EXPANDED',1),self.assertRaisesRegex(ValueError,'Expanded'):inspect_archive({'path':str(self.path)})
    def test_old_archives_without_integrity_receipts_are_not_certified(self):
        data=copy.deepcopy(self.data);data.pop('assetManifest');self.write(data=data)
        with self.assertRaisesRegex(ValueError,'integrity manifest'):inspect_archive({'path':str(self.path)})
    def test_scene_references_require_their_own_saved_asset(self):
        data=copy.deepcopy(self.data)
        data['researchViews']=[{'kind':'scene','data':{'engine':'chimerax','asset':'missing.cxs','sha256':'c'*64}}]
        self.write(data=data)
        with self.assertRaisesRegex(ValueError,'reference differs'):inspect_archive({'path':str(self.path)})

if __name__=='__main__':unittest.main()
