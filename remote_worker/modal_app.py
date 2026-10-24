"""Deploy only after explicit review of the pinned RAPID image and provider cost."""
import json
import os
from fold_rapid.modal_provider import build_app

with open(os.environ['FOLD_MODAL_CONFIG']) as stream:
    app=build_app(json.load(stream))
