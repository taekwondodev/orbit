# Delivery policy

- Default mode: `direct`.
- Integration target and PR base: `origin` (`taekwondodev/orbit`), branch `main`. Use a PR only when explicitly requested.
- PR source: a branch pushed to `origin`.
- Required verification: `tox -e py3` (configured in `tox.ini`); also `tox -e genconfig` when configuration options change, and `tox -e dashboard` when the Horizon panel in `orbit/dashboard` changes. Run these locally before delivery.

Before selecting the route or preparing a branch, read the shared delivery reference supplied by `implement` (`references/delivery.md`).
