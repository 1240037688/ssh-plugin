# Contributing

Thanks for improving `ssh-plugin` (Hermes SSH Deploy).

## Development workspace

- Plugin package root: this repository
- Runtime install (local): copy into `$HERMES_HOME/plugins/ssh-plugin` and enable in `config.yaml`
- Desktop half: `$HERMES_HOME/desktop-plugins/ssh-plugin/plugin.js` (or unified package `desktop/plugin.js` via Hermes package copy)

Never commit:

- `deployments.json` / any credential material
- Personal `HERMES_HOME` paths with secrets
- Real host IPs used in private infra (use examples)

## Branch layout

- `main` — stable
- `feature/*` — work branches (Compose Next style: spec under `docs/compose/spec/`)

## Before you PR

```bash
# syntax
node --check desktop/plugin.js

# unit tests (no network / no real SSH)
python -m unittest discover -s tests -v

# optional compile check
python -m py_compile deploy_paths.py security.py ssh_session.py sftp_client.py tools.py dashboard/plugin_api.py
```

## Design rules

1. Disk Desktop plugins: **no JSX** — `jsx()` / `jsxs()` only; imports limited to `@hermes/plugin-sdk`, `react`, `react/jsx-runtime`.
2. Theme via `var(--ui-*)`; no hardcoded colors.
3. Never return passwords in APIs or tool payloads; mask host/username for Agent tools by default.
4. Mutating remote files: prefer dry-run / diff; require read-before-write in Agent guidance.
5. `python_dependencies` in `plugin.yaml` is **declare-only** — document install steps; Hermes does not auto-pip-install.

## Specs

Feature work that is non-trivial should land a short spec at `docs/compose/spec/<feature>.md` with problem, design, out-of-scope, and tasks.

## Code of conduct

Be respectful. Do not submit malware, credential stealers, or code designed to evade security controls on systems you do not own.
