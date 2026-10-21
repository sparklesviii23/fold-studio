# RAPID worker · scientific package v0.2.0 / API v2

The installable scientific application is now `fold_rapid/`, with metadata in
`pyproject.toml`, isolated hashed environments in `environments/`, and CUDA image
targets in `containers/Dockerfile`. See `../docs/RAPID_WORKER_REPORT.md` for actual
execution paths, deployment/test commands, evidence and outstanding NVIDIA gates.
No CUDA scientific readiness is claimed from a no-GPU build.

## Retained connection foundation · protocol v1

A dependency-free Python worker transported over authenticated OpenSSH stdin.
It opens no public network port. Supported operations: health, engine inventory,
and actual isolated Torch/JAX CUDA forward/gradient probes. It never silently
executes CPU instead of CUDA. GPU detection alone never sets Ready.

This initial worker does not install models, accept scientific campaigns, or
claim remote BindCraft2 / BoltzGen execution. Those milestones need a real GPU
server, pinned environments, approved assets and scientific reference tests.

The native Cloud Compute page transfers only this small worker after the user
confirms server identity and selects Prepare Worker. Private keys remain local.
No provider API credentials, rentals, instance changes or model downloads occur.

Official connection reference: https://docs.vast.ai/guides/instances/connect/ssh
CUDA environment reference: https://docs.jax.dev/en/latest/installation.html
