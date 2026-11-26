"""Demo 12 reference molecular dynamics: Trp-cage (PDB 1L2Y) in implicit solvent with OpenMM.

Runs in the bundled OpenMM runtime as a separate process (no fold imports):
    python md_reference.py <input.json> <output.json>

Physics: Amber ff14SB (amber14-all.xml) with the GBn2 generalised-Born implicit solvent,
no cutoff, hydrogen-bond constraints, Langevin middle integrator at 300 K. Every frame
written is a real integration state; nothing is interpolated.

Checks: CPU forces against the independent Reference platform, energy minimisation,
energy conservation in a constant-energy (Verlet) segment, mean kinetic temperature,
bit-for-bit reproducibility from a seed.
"""
import json, math, platform, sys, time
import numpy as np
import openmm as mm
from openmm import app, unit

KB = 0.0083144626  # kJ/(mol·K)


def kabsch(P, Q):
    """Rotate P onto Q (both centred); returns rotated P."""
    H = P.T @ Q
    U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1, 1, d])
    return P @ (U @ D @ Vt)


def rmsd(a, b):
    a0, b0 = a - a.mean(0), b - b.mean(0)
    return float(np.sqrt(((kabsch(a0, b0) - b0) ** 2).sum(1).mean()))


def fluctuation(frames, idx):
    """Per-atom RMSF after iterative superposition onto the mean (two passes)."""
    X = np.array([f[idx] - f[idx].mean(0) for f in frames])
    ref = X[0]
    for _ in range(2):
        X = np.array([kabsch(x, ref) for x in X])
        ref = X.mean(0)
    return np.sqrt(((X - ref) ** 2).sum(2).mean(0))


def state(sim, pos=True, energy=True):
    return sim.context.getState(getPositions=pos, getEnergy=energy, getVelocities=False)


def main(inp, outp):
    cfg = json.load(open(inp))
    started = time.time()
    pdb = app.PDBFile(cfg['pdb'])
    top = pdb.topology
    ff = app.ForceField('amber14-all.xml', 'implicit/gbn2.xml')
    system = ff.createSystem(top, nonbondedMethod=app.NoCutoff, constraints=app.HBonds)
    T, dt, gamma = cfg['temperature'], cfg['timestep_fs'] / 1000.0, cfg['friction']
    seed = int(cfg['seed'])
    checks = []

    # 1. Independent implementation: CPU vs Reference platform forces on the experimental model.
    pos0 = pdb.getPositions(frame=0)
    forces = {}
    for name in ('Reference', 'CPU'):
        ctx = mm.Context(system, mm.VerletIntegrator(0.001), mm.Platform.getPlatformByName(name))
        ctx.setPositions(pos0)
        st = ctx.getState(getForces=True, getEnergy=True)
        forces[name] = (np.array(st.getForces().value_in_unit(unit.kilojoule_per_mole / unit.nanometer)), st.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole))
        del ctx
    fr, fc = forces['Reference'][0], forces['CPU'][0]
    rel = float(np.abs(fr - fc).max() / np.abs(fr).max())
    checks.append({'name': 'CPU forces agree with the Reference platform', 'passed': rel < 1e-4,
                   'detail': f'max |ΔF| / max |F| = {rel:.1e}; potential {forces["Reference"][1]:.2f} vs {forces["CPU"][1]:.2f} kJ/mol'})

    plat = mm.Platform.getPlatformByName('CPU')
    integ = mm.LangevinMiddleIntegrator(T * unit.kelvin, gamma / unit.picosecond, dt * unit.picoseconds)
    integ.setRandomNumberSeed(seed)
    # Deterministic force summation makes a seeded run repeatable across thread scheduling.
    sim = app.Simulation(top, system, integ, plat, {'DeterministicForces': 'true'})
    sim.context.setPositions(pos0)
    e_before = state(sim).getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
    sim.minimizeEnergy(tolerance=1.0, maxIterations=2000)
    e_after = state(sim).getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
    checks.append({'name': 'Energy minimisation lowers the potential energy', 'passed': e_after < e_before,
                   'detail': f'{e_before:.1f} → {e_after:.1f} kJ/mol'})
    sim.context.setVelocitiesToTemperature(T * unit.kelvin, seed)

    # 2. Reproducibility. Multithreaded CPU summation of the GB force is not bit-reproducible (differences of
    # ~1e-4 nm after 1 ps grow chaotically), so seeded determinism is checked on the single-threaded Reference platform.
    start_pos = state(sim, energy=False).getPositions()
    def segment(steps):
        ri = mm.LangevinMiddleIntegrator(T * unit.kelvin, gamma / unit.picosecond, dt * unit.picoseconds)
        ri.setRandomNumberSeed(seed)
        rc = mm.Context(system, ri, mm.Platform.getPlatformByName('Reference'))
        rc.setPositions(start_pos); rc.setVelocitiesToTemperature(T * unit.kelvin, seed)
        ri.step(steps)
        return np.array(rc.getState(getPositions=True).getPositions().value_in_unit(unit.nanometer))
    a, b = segment(100), segment(100)
    diff = float(np.abs(a - b).max())
    checks.append({'name': 'Seeded trajectory is reproducible', 'passed': diff == 0.0,
                   'detail': f'two 0.2 ps Reference-platform runs from one state and seed: max coordinate difference {diff:.1e} nm. '
                             'Production uses the multithreaded CPU platform, whose GB force summation order varies, so CPU runs agree statistically, not bit for bit.'})

    # 3. Equilibration, then production with real frames.
    sim.step(int(cfg['equilibration_ps'] / dt))
    every = int(cfg['frame_ps'] / dt)
    nframes = int(cfg['production_ps'] / cfg['frame_ps'])
    dof = 3 * system.getNumParticles() - system.getNumConstraints()
    frames, times, pot, kin, temp = [], [], [], [], []
    t0 = time.time()
    for k in range(nframes):
        sim.step(every)
        st = sim.context.getState(getPositions=True, getEnergy=True)
        frames.append(np.array(st.getPositions().value_in_unit(unit.angstrom)))
        times.append((k + 1) * cfg['frame_ps'])
        pe = st.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole); ke = st.getKineticEnergy().value_in_unit(unit.kilojoule_per_mole)
        pot.append(pe); kin.append(ke); temp.append(2 * ke / (dof * KB))
    prod_seconds = time.time() - t0
    tm, tsd = float(np.mean(temp)), float(np.std(temp))
    # Expected spread of the instantaneous kinetic temperature is T·√(2/dof); allow the sampling error of correlated frames.
    checks.append({'name': 'Mean kinetic temperature matches the thermostat', 'passed': abs(tm - T) < 4 * T * math.sqrt(2 / dof) / math.sqrt(max(nframes / 10, 1)),
                   'detail': f'{tm:.1f} ± {tsd:.1f} K over {nframes} frames (target {T} K; canonical spread {T * math.sqrt(2 / dof):.1f} K)'})

    # 4. Energy conservation in a constant-energy segment from the final state.
    vint = mm.VerletIntegrator(0.0005 * unit.picoseconds)
    ctx = mm.Context(system, vint, plat)
    st = sim.context.getState(getPositions=True, getVelocities=True)
    ctx.setPositions(st.getPositions()); ctx.setVelocities(st.getVelocities())
    ctx.applyVelocityConstraints(1e-8)
    tot, kins = [], []
    for _ in range(100):
        vint.step(40)
        s2 = ctx.getState(getEnergy=True)
        k2 = s2.getKineticEnergy().value_in_unit(unit.kilojoule_per_mole)
        tot.append(s2.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole) + k2); kins.append(k2)
    tt = np.arange(len(tot)) * 0.02
    drift = float(np.polyfit(tt, tot, 1)[0])
    ratio = float(np.std(tot) / np.std(kins))
    checks.append({'name': 'Total energy is conserved without a thermostat', 'passed': ratio < 0.05 and abs(drift) * 2.0 < 0.05 * np.mean(kins),
                   'detail': f'2 ps Verlet at 0.5 fs: σ(E_total)/σ(E_kin) = {ratio:.3f}; drift {drift:.2f} kJ/mol/ps'})

    # 5. Analysis.
    atoms = list(top.atoms())
    res_of = [a.residue.index for a in atoms]
    bb = [i for i, a in enumerate(atoms) if a.name in ('N', 'CA', 'C')]
    ca = [i for i, a in enumerate(atoms) if a.name == 'CA']
    heavy = [i for i, a in enumerate(atoms) if a.element is not None and a.element.symbol != 'H']
    nmr = [np.array(pdb.getPositions(frame=m).value_in_unit(unit.angstrom)) for m in range(pdb.getNumFrames())]
    ref = nmr[0]
    rmsd_bb = [rmsd(f[bb], ref[bb]) for f in frames]
    nmr_rmsd = [rmsd(m[bb], ref[bb]) for m in nmr]
    rmsf_md = fluctuation(frames, ca)
    rmsf_nmr = fluctuation(nmr, ca)
    rg = [float(np.sqrt(((f[heavy] - f[heavy].mean(0)) ** 2).sum(1).mean())) for f in frames]
    residues = list(top.residues())
    def centroid(rnum, names):
        r = residues[rnum - 1]
        return [a.index for a in r.atoms() if a.name in names]
    ring = ('CD1', 'CD2', 'NE1', 'CE2', 'CE3', 'CZ2', 'CZ3', 'CH2')
    pro = ('CB', 'CG', 'CD')
    tyr = ('CG', 'CD1', 'CD2', 'CE1', 'CE2', 'CZ')
    pairs = [('Trp6 ring – Pro12 ring', centroid(6, ring), centroid(12, pro)),
             ('Trp6 ring – Pro18 ring', centroid(6, ring), centroid(18, pro)),
             ('Trp6 ring – Pro19 ring', centroid(6, ring), centroid(19, pro)),
             ('Trp6 ring – Tyr3 ring', centroid(6, ring), centroid(3, tyr)),
             ('Asp9 CG – Arg16 CZ (salt bridge)', centroid(9, ('CG',)), centroid(16, ('CZ',)))]
    contacts = []
    for name, a, b in pairs:
        d = [float(np.linalg.norm(f[a].mean(0) - f[b].mean(0))) for f in frames]
        dn = [float(np.linalg.norm(m[a].mean(0) - m[b].mean(0))) for m in nmr]
        cut = 5.0 if 'salt' in name else 6.5
        contacts.append({'name': name, 'series': d, 'mean': float(np.mean(d)), 'nmrMean': float(np.mean(dn)), 'nmrRange': [float(min(dn)), float(max(dn))],
                         'cutoff': cut, 'persistence': float(np.mean(np.array(d) < cut)), 'nmrPersistence': float(np.mean(np.array(dn) < cut))})

    bonds = [[b[0].index, b[1].index] for b in top.bonds()]
    out = {
        'atoms': [{'name': a.name, 'element': a.element.symbol if a.element else '', 'residue': a.residue.name, 'resSeq': a.residue.index + 1} for a in atoms],
        'bonds': bonds, 'residues': [r.name for r in residues],
        'times': times, 'frames': [np.round(f, 3).tolist() for f in frames], 'reference': np.round(ref, 3).tolist(),
        'potential': pot, 'kinetic': kin, 'temperature': temp,
        'rmsd': rmsd_bb, 'nmrRmsd': nmr_rmsd, 'rmsfMd': rmsf_md.tolist(), 'rmsfNmr': rmsf_nmr.tolist(), 'rg': rg, 'contacts': contacts,
        'checks': checks,
        'system': {'atoms': system.getNumParticles(), 'constraints': system.getNumConstraints(), 'dof': dof, 'nmrModels': len(nmr)},
        'performance': {'productionSeconds': prod_seconds, 'nsPerDay': cfg['production_ps'] / 1000 / prod_seconds * 86400, 'totalSeconds': time.time() - started},
        'software': {'openmm': mm.__version__, 'python': platform.python_version(), 'numpy': np.__version__, 'platform': 'CPU', 'threads': plat.getPropertyDefaultValue('Threads') if 'Threads' in plat.getPropertyNames() else None},
    }
    tmp = outp + '.part'
    with open(tmp, 'w') as f:
        json.dump(out, f, default=lambda o: o.item() if isinstance(o, np.generic) else str(o))
    import os
    os.replace(tmp, outp)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
