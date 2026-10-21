# Local build and storage policy

- Keep exactly one installed current Fold Studio build, at `../current/FOLD STUDIO Metal Dev.app`. The current directory is a symlink to the existing app location; do not duplicate the bundle to a new release directory.
- Use `bash scripts/build-local-app.sh` for packaging. It guards running app/worker identities, replaces the existing app only when idle, verifies signatures, removes the prior bundle, and removes disposable build products. Do not create dated/versioned backup apps or automatic ZIP exports.
- Packaging runtime inputs in `../runtime-build` are disposable. The build script recreates them from the tested standalone runtimes inside the current app, then removes them. Keep independently configured development environments in `../runtimes` only when needed for scientific validation.
- Preserve source, Git history, trained model files, required runtimes, saved research, settings, and private credentials. The live research root is `../validation/bindcraft-fab-amme-native`; its name does not make it disposable test data.
- Keep one shared Boltz model store at that live root's `engine/models`. Other validation roots may link to it. Never remove a differing model on the assumption that it is a duplicate.
- GPU CUDA images and build virtual machines are optional developer artifacts, not local app dependencies. Build these only for explicit deployment/qualification work and remove temporary local images, environments and caches when finished. Do not download models or export multi-GB image archives automatically.
- Keep genuine scientific result evidence; do not claim that storage cleanup validates model accuracy or completes the unfinished GPU/Fab work.
