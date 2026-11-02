"""CellFlux inference in its own PyTorch runtime (runtimes/gbcell + plugin deps on PYTHONPATH); called by
virtual_cell_cellflux.py as `python cellflux_runner.py request.json`. Nothing here is modified from the published model:
the UNet / EMA classes come from the pinned CellFlux source, the ODE solver from flow_matching 1.0.10, and the sampling
settings are the authors' cpg0000 evaluation settings (scripts/slurm_eval_cpg0000.sh): EMA weights, Heun (2nd order),
50 function evaluations on the EDM time grid, classifier-free guidance scale 0.2, start = control image + N(0, 1.0²)
(use_initial=2, noise_level=1.0). Only the evaluation wrapper (CFGScaledModel) is re-implemented, because the original
module imports training-only packages (torchvision, torchmetrics)."""
import json, sys, time


def main(req_path):
    req = json.load(open(req_path))
    sys.path[:0] = [req['src'], req['deps']]
    import numpy as np, torch
    from flow_matching.solver.ode_solver import ODESolver
    from flow_matching.utils import ModelWrapper
    from models.model_configs import instantiate_model
    from training.edm_time_discretization import get_time_discretization

    device = req.get('device') or ('mps' if torch.backends.mps.is_available() else 'cpu')
    torch.manual_seed(int(req.get('seed', 0)))
    model = instantiate_model('cpg0000', is_discrete=False, use_ema=True)
    ck = torch.load(req['checkpoint'], map_location='cpu', weights_only=False)
    missing, unexpected = model.load_state_dict(ck['model'], strict=True), None
    model.to(device).train(False)

    class CFGScaledModel(ModelWrapper):                    # same arithmetic as CellFlux training/eval_loop.CFGScaledModel
        def forward(self, x, t, cfg_scale, extra):
            t = torch.zeros(x.shape[0], device=x.device) + t
            with torch.no_grad():
                if cfg_scale != 0.0:
                    return (1.0 + cfg_scale) * self.model(x, t, extra=extra) - cfg_scale * self.model(x, t, extra={})
                return self.model(x, t, extra=extra)

    import pandas as pd
    emb = pd.read_csv(req['embeddings'], index_col=0)
    if req['perturbation'] not in emb.index:
        raise SystemExit(json.dumps({'error': f"Perturbation {req['perturbation']} has no embedding in this checkpoint's table."}))
    z = torch.tensor(emb.loc[[req['perturbation']]].values, dtype=torch.float32, device=device)

    x = torch.tensor(np.load(req['inputs']), dtype=torch.float32)               # (N, 5, 96, 96) uint8 counts
    x = ((x + torch.rand_like(x)) / 255.0 - 0.5) / 0.5                          # CustomTransform: dequantise, [0,1], Normalize(0.5, 0.5)
    x = x.to(device); n = x.shape[0]
    # 'control' (authors' setting) starts from the supplied cells + noise; 'noise' starts from N(0, 1), used only to inspect
    # what the model generates for a perturbation without any input cells.
    x0 = torch.randn_like(x) if req.get('start') == 'noise' else x + torch.randn_like(x) * float(req.get('noiseLevel', 1.0))
    solver = ODESolver(velocity_model=CFGScaledModel(model))
    grid = get_time_discretization(nfes=int(req.get('nfe', 50))).to(torch.float32).to(device)   # MPS has no float64
    t0 = time.time()
    out = solver.sample(time_grid=grid, x_init=x0, method='heun2', step_size=None, cfg_scale=float(req.get('cfg', 0.2)),
                        extra={'concat_conditioning': z.expand(n, -1)})
    out = torch.clamp(out * 0.5 + 0.5, 0.0, 1.0).float().cpu().numpy()
    np.save(req['output'], out)
    json.dump({'device': device, 'seconds': round(time.time() - t0, 2), 'n': int(n), 'torch': torch.__version__, 'checkpointEpoch': ck.get('epoch'),
               'perturbation': req['perturbation'], 'nfe': int(req.get('nfe', 50)), 'cfg': float(req.get('cfg', 0.2)), 'noiseLevel': float(req.get('noiseLevel', 1.0)),
               'start': req.get('start', 'control'), 'method': 'heun2', 'timeGrid': 'EDM (get_time_discretization)', 'seed': int(req.get('seed', 0))}, open(req['output'] + '.json', 'w'))


if __name__ == '__main__':
    main(sys.argv[1])
