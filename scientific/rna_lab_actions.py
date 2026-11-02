"""RNA-to-Protein Laboratory action names, kept free of engine imports.

`rna_lab` (and its folding/translation engines) is imported only when one of these runs.
"""
ACTIONS = {'rna_lab_catalog', 'rna_lab_fold', 'rna_lab_translate', 'rna_lab_validate', 'rna_lab_runs'}
