# Delivery policy

- Default mode: `direct`.
- Integration target: `origin` (`taekwondodev/orbit`), branch `main`.
- PR base: `origin` (`taekwondodev/orbit`), branch `main`, used only when a PR is requested explicitly.
- PR source: a branch pushed to `origin`.
- Required verification: `tox -e py3` (configured in `tox.ini`); also `tox -e genconfig` when configuration options change, and `tox -e dashboard` (Python 3.11 or later) when the Horizon panel in `orbit/dashboard` changes. There is no CI, so these run locally before delivery.

Before selecting the route or preparing a branch, read the shared delivery reference supplied by `implement` (`references/delivery.md`).
