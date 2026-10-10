# agents-chronicle is now interlatch

Chronicle was renamed **Interlatch**, and its PyPI package is now [`interlatch`](https://pypi.org/project/interlatch/).
This package installs `interlatch` at the same version and keeps the `chronicle` and `interlatch` commands, so an
existing install keeps updating with `uv tool upgrade agents-chronicle` (or the dashboard's **Update** button).

For a new install, use the new name:

```bash
uv tool install --python 3.13 interlatch
```

To move an existing install to it, list the extras you have in the brackets (`app`, `team`, `postgres`), or none:

```bash
uv tool uninstall agents-chronicle
uv tool install --python 3.13 'interlatch[app]'
```

With pipx, `pipx uninstall agents-chronicle` and `pipx install interlatch`. With pip, both packages share one
environment and the same files, so put interlatch's back after removing this one:
`pip uninstall -y agents-chronicle && pip install --force-reinstall --no-deps interlatch`.

Your archive, settings and hub connection stay where they are. Docs: <https://interlatch.com/docs/>
