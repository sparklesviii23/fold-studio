"""Living Cell physics action names, kept free of NumPy/SciPy imports.

The worker routes these without importing the engine (some interpreters that run
worker.py have no scientific stack); `cell_physics` is imported only on use.
"""
ACTIONS = {'cell_physics_catalog', 'cell_physics_diffusion', 'cell_physics_binding', 'cell_physics_sweep', 'cell_physics_runs'}
