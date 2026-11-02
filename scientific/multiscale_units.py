"""Physical units and dimensional analysis for multiscale coupling.

A quantity's dimension is an exponent vector over (amount, count, mass, length,
time). Amount (mol) and count (molecules) are deliberately separate dimensions:
converting between them needs Avogadro's constant and, for concentrations, a
volume, so it can only happen through the explicit functions below and is
always recorded as a transformation, never silently.
"""
import math

AVOGADRO = 6.02214076e23  # 1/mol, exact (SI 2019)
DIMS = ('amount', 'count', 'mass', 'length', 'time')


class UnitError(ValueError):
    pass


def _d(**e):
    return tuple(e.get(k, 0) for k in DIMS)


# unit -> (factor to SI-like base: mol, molecule, kg, m, s ; dimension)
UNITS = {
    'mol': (1.0, _d(amount=1)), 'mmol': (1e-3, _d(amount=1)), 'umol': (1e-6, _d(amount=1)), 'nmol': (1e-9, _d(amount=1)),
    'molecule': (1.0, _d(count=1)),
    'kg': (1.0, _d(mass=1)), 'g': (1e-3, _d(mass=1)), 'mg': (1e-6, _d(mass=1)), 'Da': (1.66053906660e-27, _d(mass=1)),
    'm': (1.0, _d(length=1)), 'mm': (1e-3, _d(length=1)), 'um': (1e-6, _d(length=1)), 'nm': (1e-9, _d(length=1)),
    'm3': (1.0, _d(length=3)), 'L': (1e-3, _d(length=3)), 'dL': (1e-4, _d(length=3)), 'mL': (1e-6, _d(length=3)), 'fL': (1e-18, _d(length=3)), 'um3': (1e-18, _d(length=3)),
    's': (1.0, _d(time=1)), 'min': (60.0, _d(time=1)), 'h': (3600.0, _d(time=1)), 'day': (86400.0, _d(time=1)),
    'M': (1e3, _d(amount=1, length=-3)), 'mM': (1.0, _d(amount=1, length=-3)), 'uM': (1e-3, _d(amount=1, length=-3)), 'nM': (1e-6, _d(amount=1, length=-3)),
    'mol/m3': (1.0, _d(amount=1, length=-3)),
    'g/L': (1.0, _d(mass=1, length=-3)), 'g/dL': (10.0, _d(mass=1, length=-3)), 'mg/mL': (1.0, _d(mass=1, length=-3)),
    'g/day': (1e-3 / 86400.0, _d(mass=1, time=-1)),
    'molecule/s': (1.0, _d(count=1, time=-1)), 'molecule/h': (1 / 3600.0, _d(count=1, time=-1)),
    'mol/s': (1.0, _d(amount=1, time=-1)),
    '1/s': (1.0, _d(time=-1)), '1/h': (1 / 3600.0, _d(time=-1)), '1/day': (1 / 86400.0, _d(time=-1)),
    'um2/s': (1e-12, _d(length=2, time=-1)), 'um/s': (1e-6, _d(length=1, time=-1)), 'mm/s': (1e-3, _d(length=1, time=-1)),
    'codon/s': (1.0, _d(time=-1)),
    'g/mol': (1e-3, _d(mass=1, amount=-1)),
    '1': (1.0, _d()), 'cell': (1.0, _d()), 'fraction': (1.0, _d()),
}


def dimension(unit):
    if unit not in UNITS:
        raise UnitError('Unknown unit: ' + str(unit))
    return UNITS[unit][1]


def convert(value, source, target):
    """Convert between units of the same dimension; refuses anything else."""
    fs, ds = UNITS.get(source, (None, None)); ft, dt = UNITS.get(target, (None, None))
    if fs is None or ft is None:
        raise UnitError(f'Unknown unit: {source if fs is None else target}')
    if ds != dt:
        raise UnitError(f'Cannot convert {source} to {target}: dimensions differ ({_show(ds)} vs {_show(dt)}).')
    v = float(value) * fs / ft
    if not math.isfinite(v):
        raise UnitError('Conversion produced a non-finite value.')
    return v


def _show(d):
    return '·'.join(f'{n}^{e}' for n, e in zip(DIMS, d) if e) or 'dimensionless'


# Explicit cross-dimension transformations: each returns (value, description) so the step is recorded.
def count_to_amount(n, unit_in='molecule', unit_out='mol'):
    v = convert(convert(n, unit_in, 'molecule') / AVOGADRO, 'mol', unit_out)
    return v, f'divide by Avogadro constant {AVOGADRO:.8e} /mol'


def _require(unit, dims):
    if dimension(unit) != _d(**dims):
        raise UnitError(f'{unit} is not a unit of {_show(_d(**dims))}.')


def count_rate_to_mass_rate(rate, rate_unit, molar_mass_g_per_mol, out='g/day'):
    """Molecules per time → mass per time via Avogadro and molar mass."""
    _require(out, {'mass': 1, 'time': -1})
    kg_per_s = convert(rate, rate_unit, 'molecule/s') / AVOGADRO * molar_mass_g_per_mol * 1e-3
    return kg_per_s / UNITS[out][0], f'(molecules/s) ÷ N_A × {molar_mass_g_per_mol:.1f} g/mol'


def mass_to_concentration(mass, mass_unit, volume, volume_unit, out='g/L'):
    """Mass in a volume → mass concentration."""
    _require(out, {'mass': 1, 'length': -3})
    V = convert(volume, volume_unit, 'm3')
    if V <= 0:
        raise UnitError('Volume must be positive.')
    return convert(mass, mass_unit, 'kg') / V / UNITS[out][0], f'mass ÷ volume ({volume:g} {volume_unit})'


def molar_from_mass_concentration(c, c_unit, molar_mass_g_per_mol, out='uM'):
    """Mass concentration → molar concentration via molar mass."""
    mol_per_m3 = convert(c, c_unit, 'g/L') / (molar_mass_g_per_mol * 1e-3)
    return convert(mol_per_m3, 'mol/m3', out), f'(g/L) ÷ {molar_mass_g_per_mol:.1f} g/mol'
