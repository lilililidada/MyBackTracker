"""Project-local site customization.

This file intentionally shadows IDE helper sitecustomize modules so the
interpreter does not eagerly import plotting backends during startup.
That keeps the repo usable even when a system Python has NumPy 2 but an older
matplotlib is still present in the IDE helper path.
"""

