"""Virtual Cell action names, kept free of NumPy/SciPy so the worker can route them anywhere."""
ACTIONS = {'vcell_catalog', 'vcell_reference_build', 'vcell_list', 'vcell_create', 'vcell_get', 'vcell_perturb', 'vcell_branch',
           'vcell_delete', 'vcell_observe', 'vcell_design', 'vcell_protein', 'vcell_pathway', 'vcell_enrichment', 'vcell_annotations_install',
           'vcell_registry', 'vcell_transcripts_build', 'vcell_coverage', 'vcell_transcripts', 'vcell_cycle_run', 'vcell_snapshot_save', 'vcell_snapshot_list',
           'vcell_snapshot_get', 'vcell_snapshot_compare', 'vcell_snapshot_export', 'vcell_snapshot_import', 'vcell_snapshot_delete',
           'vcell_structures', 'vcell_structure_compare', 'vcell_results_list', 'vcell_result_get', 'vcell_rna_protein', 'vcell_microscopy_list', 'vcell_microscopy_view', 'vcell_report',
           'vcell_cellflux_status', 'vcell_cellflux_perturbations', 'vcell_cellflux_run', 'vcell_cellflux_job',
           'vcell_benchmarks', 'vcell_benchmark_get', 'vcell_benchmark_run', 'vcell_regulatory_runs', 'vcell_regulatory_track'}
