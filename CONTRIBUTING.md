# Contributing to OMERTAOS

Thank you for contributing. OMERTAOS is an architecture-sensitive research
prototype; changes should preserve the canonical request path:

```text
Console -> Gateway -> Control -> Runtime Daemon
```

Read [ARCHITECTURE.md](ARCHITECTURE.md), [STRUCTURE.md](STRUCTURE.md), and
[ADR 0001](docs/adr/0001-canonical-aion-ownership.md) before changing service
boundaries.
Use the canonical `OMERTA_*` namespace from
[ADR 0002](docs/adr/0002-omerta-configuration-namespace.md) for new
product-owned configuration.

## Contribution principles

- keep pull requests focused, reviewable, and backward-compatible;
- place behavior in its canonical owner;
- add positive and negative tests for changed behavior;
- do not bypass Gateway, Control, Runtime, data, policy, or schema boundaries;
- do not commit secrets, generated credentials, private research data, or
  manuscript correspondence;
- do not claim performance, security, or production readiness without
  reproducible evidence;
- update public documentation when behavior, configuration, contracts,
  deployment, or evidence status changes.

## Development setup

Reference versions are Python 3.11, Node.js 22.23.2, npm 10.9.8, pnpm 11.13.1
for Console, Rust stable, and Docker Compose v2. The repository `.node-version`
and `.nvmrc` files are authoritative for Node.js.

```bash
git clone --branch CAPO https://github.com/Hamedghz/OMERTAOS.git
cd OMERTAOS

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[control,dev]"

npm ci --prefix gateway
corepack enable
corepack prepare pnpm@11.13.1 --activate
pnpm --dir console install --frozen-lockfile
```

On Windows PowerShell, activate the virtual environment with
`.venv\Scripts\Activate.ps1`.

Create the local environment file, then render deployment configuration before
starting any stack. The checked-in credentials are development placeholders.

```bash
cp dev.env .env
docker compose --project-directory . -f deploy/docker/compose/quickstart.yml config
```

Do not use development credentials outside an isolated local environment.

## Targeted validation

Run the smallest relevant checks first:

```bash
# Architecture and Python
python -m pytest tests/architecture -q

# Gateway
npm run build --prefix gateway
npm test --prefix gateway

# Console
pnpm --dir console test --config vitest.config.mts
pnpm --dir console build

# Runtime
cargo fmt --manifest-path runtime-daemon/Cargo.toml --check
cargo test --locked --manifest-path runtime-daemon/Cargo.toml --all-targets
```

Report commands, exit codes, pass/fail/skip counts, warnings, and environmental
blockers. A blocked dependency download or unsupported host must not be
reported as a passing runtime test.

## Documentation and research claims

- link design statements to the canonical architecture document;
- link implementation claims to source and tests;
- tie validation results to a commit and environment;
- update [Evidence and claims](docs/research/evidence-and-claims.md) when the
  maturity of a major claim changes;
- keep migration reports historical; do not rewrite past evidence as if it were
  a current run.

## Commit and pull-request style

Use Conventional Commits, for example:

```text
docs(research): add reproducibility protocol
fix(runtime): reject expired capability grants
test(architecture): prohibit direct control health access
```

A pull request should state:

- motivation and scope;
- changed owners and boundaries;
- tests and exact results;
- security, migration, and rollback implications;
- documentation and research-claim impact;
- known limitations.

Architecture, public API, schema, authentication, Runtime isolation, and
production-topology changes require focused human review. Contributors must not
auto-merge or deploy changes.

## Security reports

Do not open public issues for vulnerabilities. Follow [SECURITY.md](SECURITY.md).
All participants must follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
