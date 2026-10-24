"""Deployment-source integrity and SDK hydration order; no cloud calls."""
import io,json,pathlib,sys,tarfile,tempfile,unittest
from unittest.mock import Mock
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'remote_worker'))
from fold_rapid.cloud_image import prepare_release,verify_release
from fold_rapid.modal_provider import configuration,deploy_app

class CloudImageTests(unittest.TestCase):
    def test_recipe_requires_explicit_known_name(self):
        cfg={'appName':'fold-fixture','gpu':'A100-80GB','maxSeconds':600,'hourlyEstimateUSD':2.4984}
        with self.assertRaises(ValueError):configuration(cfg)
        value=configuration({**cfg,'imageRecipe':'rapid-cuda13-core-v1'});self.assertIn('@sha256:',value['imageDigest'])
        with self.assertRaises(ValueError):configuration({**cfg,'imageRecipe':'unreviewed-build'})
    def test_unsafe_source_archive_cannot_overwrite_existing_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'source';path.mkdir();(path/'preserved').write_text('keep')
            data=io.BytesIO()
            with tarfile.open(fileobj=data,mode='w:gz') as archive:
                entry=tarfile.TarInfo('release/../../escape');entry.size=1;archive.addfile(entry,io.BytesIO(b'x'))
            with self.assertRaises(ValueError):prepare_release(path,data.getvalue())
            self.assertEqual((path/'preserved').read_text(),'keep')
    def test_durable_resources_hydrated_before_function_serialization(self):
        order=[];app=Mock();resource=Mock();resource.hydrate.side_effect=lambda:order.append('hydrate');app._fold_resources=(resource,);app.deploy.side_effect=lambda:order.append('deploy')
        deploy_app(app);self.assertEqual(order,['hydrate','deploy'])

if __name__=='__main__':unittest.main()
