"""Standalone Modal application: no Fold Studio macOS installation required.

Set FOLD_MODAL_CONFIG to a reviewed JSON profile and FOLD_RAPID_RELEASE to the
verified source-only release root. Deploy through the official Modal SDK after
explicit cost approval; merely importing this file does not deploy or run GPUs.
"""
import json
import os
import pathlib
from fold_rapid.modal_provider import build_app

configuration=json.loads(pathlib.Path(os.environ['FOLD_MODAL_CONFIG']).read_text())
release=pathlib.Path(os.environ['FOLD_RAPID_RELEASE'])
app=build_app(configuration,worker_source=release/'worker')
