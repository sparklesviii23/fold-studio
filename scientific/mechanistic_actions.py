"""Mechanistic Biology Lab action names, kept free of NumPy/SciPy imports.

The worker also runs under isolated interpreters (e.g. the provider SDK runtime)
that have no scientific stack, so it must be able to route actions without
importing the engine; `mechanistic` is imported only when one of these runs.
"""
ACTIONS = {'mech_catalog', 'mech_load', 'mech_simulate', 'mech_scan', 'mech_scan2d', 'mech_uncertainty', 'mech_sensitivity', 'mech_steady', 'mech_fit',
           'mech_validate', 'mech_search', 'mech_target', 'mech_discover', 'mech_runs', 'mech_export'}
