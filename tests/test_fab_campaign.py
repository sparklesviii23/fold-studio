"""Complete original Fab preparation; no fabricated gradients or acceptance."""
import json
import unittest
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures,w


class FabPreparation(unittest.TestCase):
    setUp=Fixtures.setUp
    tearDown=Fixtures.tearDown

    def fab_config(self):
        return {**{k:v for k,v in self.config.items() if k!='binderLengths'},'modality':'Fab'}

    def test_complete_heavy_light_scaffold_and_original_criteria_are_saved(self):
        job=self.s.dispatch('bindcraft_prepare',self.fab_config())
        prep=job['data']['preparation'];folder=self.s.root/'jobs'/job['id']
        preset=json.loads((w.fold_engine.UPSTREAM/'settings/modality/Fab.json').read_text())
        for key,value in preset.items():
            if key not in ('description','binder_scaffold'):
                self.assertEqual(prep['config'][key],value,key)
        self.assertEqual(prep['config']['design_models'],3)
        self.assertEqual(prep['config']['validation_model'],'multimer')
        raw=(folder/'scaffold.cif').read_bytes()
        self.assertEqual(raw,(w.fold_engine.UPSTREAM/'scaffolds/Fab.cif').read_bytes())
        structure=w.fold_engine.mi.parse_structure(raw.decode(),'mmcif')
        # Raw scaffold H221/L213; the original seeded editable-loop insertion
        # produces H231/L213 in the full-model seed42 experiment.
        self.assertEqual({c['id']:len(c['sequence']) for c in structure['chains']},{'H':221,'L':213})
        self.assertFalse(prep['executionReady'])

    def test_free_length_control_cannot_truncate_antibody_domains(self):
        with self.assertRaisesRegex(ValueError,'CDR edit choices'):
            self.s.dispatch('bindcraft_prepare',{**self.fab_config(),'binderLengths':[15]})

    def test_fab_cannot_fall_through_to_single_model_or_metal_profile(self):
        job=self.s.dispatch('bindcraft_prepare',self.fab_config())
        for profile in ('experimental-cpu-float32-scaffold','experimental-cpu-float32-ensemble','experimental-metal-float32-ensemble'):
            with self.subTest(profile=profile),patch.object(self.s,'spawn') as spawn:
                with self.assertRaisesRegex(ValueError,'cloud-only'):
                    self.s.dispatch('bindcraft_start',{'id':job['id'],'projectId':self.project['id'],'profile':profile})
                spawn.assert_not_called()
        self.assertEqual(self.s.job(job['id'])['state'],'prepared')

    def test_fab_is_cloud_only_even_if_the_retired_flag_is_overridden(self):
        status=self.s.dispatch('fold_engine_status',{})
        self.assertFalse(status['fabMemory']['enabled'])
        self.assertFalse(status['fabExecution']['localExecutionAllowed'])
        self.assertEqual(status['fabMemory']['historicalTaskMemoryCeilingGiB'],14)
        self.assertNotIn('experimental-cpu-fab-amme',status['engines'][0]['profiles'])
        job=self.s.dispatch('bindcraft_prepare',self.fab_config())
        with patch('amme_campaign.NATIVE_ENABLED',True),patch.object(self.s,'spawn') as spawn:
            with self.assertRaisesRegex(ValueError,'cloud-only'):
                self.s.dispatch('bindcraft_start',{'id':job['id'],'projectId':self.project['id'],'profile':'experimental-cpu-fab-amme'})
            spawn.assert_not_called()
        self.assertEqual(self.s.job(job['id'])['state'],'prepared')



del Fixtures
