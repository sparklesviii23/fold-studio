"""Blood & Circulation Laboratory action names, kept free of NumPy/SciPy imports.

The worker routes these without importing the engine; `blood_transport` is imported only when one of them runs.
"""
ACTIONS = {'blood_transport_describe', 'blood_transport_run', 'blood_transport_validate'}
