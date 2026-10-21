"""Seed the genuine BoltzGen pipeline in one explicitly recorded process."""
import sys
from pytorch_lightning import seed_everything
from boltzgen.cli.boltzgen import main

if __name__=='__main__':
    seed=int(sys.argv.pop(1));seed_everything(seed,workers=True)
    # All stages inherit the explicit RNG initialization. No unseeded child
    # process is allowed to silently replace this reproducibility contract.
    sys.argv.append('--no_subprocess')
    main()
