# One current local build

The 21 October 2026 cleanup removed 30 obsolete fold app bundles, old Sonora candidates/backups, redundant build products, automatic release ZIPs and the disposable `fold-rapid-build` CUDA developer virtual machine. Identical Boltz caches were verified file by file and consolidated, preserving every unique scientific result and user library. Seven immutable AF2 checkpoint files were SHA-256 compared and hard-linked to the identical bundled copies. Do not modify these checkpoints in place; acquire any replacement as a separate verified file.

The project folder now occupies approximately 16.6 GB and the Sonora project approximately 0.9 GB. Actual available disk space rose from roughly 39 GiB to 108 GiB (about 74 GB recovered). APFS shares cloned app contents, so adding all historical bundle sizes would overstate physical recovery. Exact measurements and exclusions are in `reports/storage-cleanup.json`.

Current apps:

- fold: `/Users/vii/Documents/FoldStudio-MetalPort/current/fold Metal Dev.app`. `current` links to the unchanged verified working bundle in `validation/RAPID Foundation Engine`; this is one physical app.
- Sonora: `/Users/vii/Documents/Codex/2026-10-10/files-pasted-by-the-user-project/outputs/SONORA.app`. Its former Distribution path is a compatibility symlink.

Use `npm run bundle` for fold and `Scripts/package-app.sh` for Sonora. Both refuse to replace an active app or its bundled worker. They stage a signed replacement temporarily, verify it, replace the one current app, and remove the prior bundle and build intermediates. Failed verification leaves the current app intact. They do not create automatic app archives. Sonora ZIP export and RAPID image export are explicit opt-ins.

Standalone scientific runtimes inside the current fold app are the packaging source for subsequent builds; the script materializes `runtime-build` only temporarily. Independently configured scientific development environments and all required trained weights remain available. No scientific calculation was started by cleanup, no running app was replaced, and no full NVIDIA/Fab qualification is claimed.

Keep user data separate from releases. In particular, `validation/bindcraft-fab-amme-native` is the **real active research library**, despite its directory name, and must never be pruned as a disposable test root. Sonora's Application Support library, local AI downloads, books and preferences were not deleted. Historical scientific evidence remains available; removed historical app binaries must be rebuilt from the relevant source if needed.
