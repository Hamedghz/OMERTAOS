# CAPO acceptance report

## P4 auxiliary UI dependency repairs - 2026-11-11

Starting clean HEAD `411f4e1`, unchanged branch `Radin/omerta-env-namespace`;
pre-edit checkpoint `checkpoint/p4-ui-patches-start-411f4e1`.
Repair `402428d` closes the two auxiliary lock-audit failures recorded below,
not the remaining Docker/Python/live gates. Each previous audit reported three
high and one moderate finding; independent lock inspection confirmed the old
versions. Root cause: stale dependency graphs, not the npm tool upgrade.

Both `console/desktop-shell` and `integrations/windows-agentic-bridge/bridge-ui`
now lock Vite 6.4.6, baseline-browser-mapping 2.11.34, Browserslist 4.29.5 and
source-map-js 1.2.2. The [upstream Vite 6 changelog](https://raw.githubusercontent.com/vitejs/vite/v6.4.6/packages/vite/CHANGELOG.md)
records the intervening security backports. Vite remains major 6; React, its
Vite plugin, Node/npm/pnpm and application runtime dependency declarations are
unchanged. Generated lock diffs contain only these four packages and four
Browserslist data/helper dependencies, all with integrity fields. No manual
lock editing, broad `audit fix`, force/legacy-peer install or audit suppression.
Console's pnpm release-age policy and all execution/auth boundaries are unchanged.

| Sequential gate | Actual result / wall seconds |
|---|---|
| Both npm lock generations | Exit 0 / 9.63s and 8.52s |
| Toolchain, packaging and integration contracts | Exit 0 / 22.60s; 32 passed in 11.71s, zero failed/skipped; includes two new UI security-floor cases covering every matching nested lock entry |
| Changed-test Ruff | Exit 0 / 2.86s |
| Desktop locked install / production web build / explicit typecheck | Exit 0 each / 32.44s, 59.93s, 20.83s |
| Desktop explicit fresh npm audit | Exit 0 / 3.61s; zero findings |
| Bridge UI locked install / production web build / explicit typecheck | Exit 0 each / 15.28s, 10.97s, 11.10s |
| Bridge UI explicit fresh npm audit | Exit 0 / 5.53s; zero findings |

Exact argv, exits, warnings, semantic lock diffs and timing are retained in
ignored `artifacts/p4/ui-compatible-patches.json`; the local sequential runner
is `ui-compatible-patches.mjs`. Minimum available RAM: 3986 MiB; free disk:
3.861 GiB. The 1 GiB RAM / 3 GiB disk guards did not fire. No image build or
persistent service was started, and no data/image/cache/volume cleanup occurred.

Reproduce for each of the two directories, sequentially:
`npm ci --prefer-offline --prefix <directory>`,
`npm run build --prefix <directory>`,
`node <directory>/node_modules/typescript/bin/tsc --noEmit --project <directory>/tsconfig.json`,
`npm audit --json --prefix <directory>`.
Architecture argv is retained in the receipt and uses the existing read-only,
network-disabled Python validation image; no system package installation.

The Desktop build retains the Tailwind missing/empty `content` warning already
present in the preceding receipt. These applications have no unit-test script;
no unit/browser/native/Tauri acceptance is claimed. Main Console, Gateway,
Python and Runtime suites were not rerun for this isolated dependency repair.
The previous image scan failures, Console disk-guard cancellation, Python wheel
access blocker and final live acceptance remain open; no new image/OS scan was
substituted by these registry audits. P4 and the full roadmap remain incomplete.

Rollback requires a reviewed reversal of this dependency patch and locked
reinstallation/rebuild of the affected web surfaces; it restores known advisory
versions and is not automatic remediation. No schema or persistent-data rollback
is needed. Local checkpoint `checkpoint/p4-ui-dependency-patches-2026-11-11`;
nothing pushed or merged, and no P5/native/benchmark approval is inferred.

## P4 transport repairs and approved npm patch - 2026-11-10/11

Branch remains `Radin/omerta-env-namespace`. Starting HEAD `46d36c5` was clean;
pre-edit tag `checkpoint/p4-images-start-46d36c5`. Local repairs:
`20eb56f` (reviewed Alpine mirror), `5e7c9da` (bounded Console fetch profile),
`882b7ed` (separately approved npm 10.9.10 alignment). No P5/push/merge approval
is implied. This section supersedes earlier statements about the active npm pin.

### Reproduced Failures

| Gate | Actual result / classification |
|---|---|
| Initial Gateway image build | Locked installation and compilation passed; publisher CDN probe timed out at 20.01s while `apk add curl` remained pending. Owned build deliberately canceled, exit 130 / 467.29s; environment transport, not a compiler defect. Console not attempted in that batch. |
| Official mirror probes | kernel.org and IUT HTTPS HEAD returned 200 in 1.71s / 0.62s, with DNS/TCP/TLS observed. Probes alone are not package acceptance. |
| Mirror-selected Gateway build, source `20eb56f` | Exit 0 / 190.13s; `omertaos-gateway:p4-major-20eb56f`, ID `sha256:6d73a7a952861afc33392daa0d7ef01523a5ef66c64c6a066e4dfb2b6a4e8a9b`. Network-disabled payload probe passed, 6.67s; still npm 10.9.8 and UID 0. |
| That Gateway image's vulnerability scan | Exit 1 / 41.21s: 1 critical, 15 high, 16 medium, 1 low. Critical: bundled tar 7.5.11, CVE-2026-59873, fixed floor 7.5.19. No findings ignored. |
| Initial mirror-selected Console build | Exit 1 / 265.68s during frozen install: registry.npmjs.org resets/timeouts, then a secondary pnpm error-message setter exception. No compiler failure observed. |
| Console retry, source `5e7c9da` | Frozen install completed (273.8s), Prisma generation passed (28.6s), Next started. Deliberately canceled after npm-upgrade approval, exit 130 / 660.96s, to avoid exporting a superseded image; no Console export claimed. |
| Initial npm-patch architecture batch | 25 passed / 2 failed, 23.12s wall: obsolete blanket `npm install` ban and concurrency-4 literal. Updated with three negative regressions; no test removed or xfailed. |
| Initial npm-patch Console full suite | 42 passed / 1 failed, 79.13s wall: Prisma fixture exceeded the unchanged 5000ms timeout under concurrent local load. Independent five-test file passed, 11.24s suite. |

`ALPINE_MIRROR=cdn|kernel` keeps the publisher CDN as default and permits only
the HTTPS kernel.org endpoint from the [official mirror list](https://mirrors.alpinelinux.org/).
Version paths and signing keys are unchanged. Actual negative Docker builds
rejected an unsupported value with expected exit 1 (7.02s / 24.05s).
No arbitrary URL, HTTP fallback, untrusted signature mode, DNS/daemon edit or
TLS relaxation was introduced. Local successful builds explicitly select
`--build-arg ALPINE_MIRROR=kernel`; default-CDN local acceptance remains blocked.

Console now uses prefer-offline cache lookup, network concurrency 2, child
concurrency 2, one retry and 120000ms fetch timeout. Frozen locks, integrity and
strict release-age policy remain enabled. The deps-stage Prisma missing-schema
warning was retained; the builder subsequently generated from the real schema.
Both canceled builds have explicit ownership/cancellation receipts and terminal
BuildKit records, not inferred completion from an observation timeout.

### npm Alignment Evidence

The user explicitly approved the host/Docker/CI/lock patch. Pre-edit tag:
`checkpoint/p4-npm-start-5e7c9da`. The downloaded npm 10.9.10 archive matched
its [publisher integrity metadata](https://registry.npmjs.org/npm/10.9.10).
Active npm/npx are 10.9.10 and actual bundled tar is 7.5.22 in the user-owned
Node prefix; the old package and npm/npx links were backed up in the protected
validation directory first. `/usr` was untouched. Node stays 22.23.2 and
canonical `corepack pnpm` stays 11.13.1; system pnpm was not replaced.

All five manifests/npm locks agree on the npm pin. Generated comparisons found
no package-set, version, artifact, integrity or dependency-edge change, only root
npm-engine metadata. All six Node Docker stages and two Node CI jobs explicitly
install the patch and assert the active version; remote CI was not executed.
Docker Gateway installation still requires audited `npm ci`. New mutation
tests reject unlocked installs, `--no-audit` and global `npm@latest`; no blanket
permission for arbitrary tool installs was added.

The host locked-install commands used `--no-audit` to separate installation
from advisory requests; those installs alone are not audit evidence. Fresh,
sequential lock audits were therefore run explicitly after the image checks.
Their results are recorded separately below, including failures; no failed
audit is converted into an install success or waived.

| Completed host gate | Actual result / wall seconds |
|---|---|
| Architecture/packaging contracts; Ruff; namespace | Exit 0 each: 30 passed / 16.06s; Ruff / 3.31s; 164 tokens and 93 reviewed legacy readers / 2.13s |
| Gateway locked install, build, tests, lint | Exit 0 each; 31 tests; 50.78 / 25.56 / 15.24 / 24.00s |
| Desktop shell locked install and web build | Exit 0 each; 40.19 / 50.32s; not native/Tauri acceptance |
| Bridge server locked install, build, tests | Exit 0 each; 4 tests; 45.59 / 15.79 / 6.65s |
| Bridge UI locked install and web build | Exit 0 each; 40.94 / 11.78s |
| Console frozen install and final full suite | Exit 0 each; 12.95s install; 43 passed / 16 files, 110.36s wall / 102.34s suite |

Node-only config/Prisma fixtures now select the actual Node environment using
the documented [Vitest per-file control](https://vitest.dev/guide/environment).
Assertions and the 5000ms timeout remain intact; the final local Console suite
used one worker, not skipped cases or a globally extended timeout. Desktop shell
and Bridge UI have no unit-test script; no test count is invented for them.
No additional host Console production build was run for this patch. In Docker,
frozen installation (208.2s), Prisma generation (30.0s), production Next build
(447.6s) and bootstrap TypeScript compilation (27.5s) all passed. This is not a
successful image export or live Console acceptance.

All builds/installations/suites were sequential. Completed host batch minimum
available RAM: 3875 MiB; Console retry: 3950 MiB. Earlier image work minimum:
3278 MiB and 7.90 GiB free disk. New builds keep 1 GiB RAM / 3 GiB disk stop
guards. The new image batch observed a minimum 3019 MiB available RAM and
2.986 GiB free disk: the disk guard fired during Console export. It was not
disabled or lowered, and no images, build cache or volumes were deleted.

### npm-Patched Image Results

| Gate at source `882b7ed` | Actual result / boundary |
|---|---|
| Compose quiet rendering | Exit 0 / 1.69s; not live acceptance |
| Gateway/Console unsupported-mirror Docker checks | Expected exit 1 / 109.11s and 18.94s; both rejection gates passed |
| Gateway build | Exit 0 / 274.66s; tag `omertaos-gateway:p4-npm-882b7ed`, ID `sha256:3e9f2337a7449730ef4def7b8be3aab3349df42af692e8ef718c6f741093c53d` |
| Gateway readonly, network-disabled payload probe | Exit 0 / 8.62s; actual Node 22.23.2, npm 10.9.10, tar 7.5.22, Zod 4.6.7 and packaged shared provider; UID remains 0 |
| Gateway fresh vulnerability scan | Exit 1 / 41.55s; 0 critical, 13 high, 13 medium, 1 low; no tar finding, but not a clean scan |
| Console build/export | Exit 130 / 1436.12s; `free disk below 3 GiB`; BuildKit record `xwm6x7p4lzdkgyzakp98815ml` is Canceled despite completed compilation and a surviving tag |
| Console surviving export identity | Tag `omertaos-console:p4-npm-882b7ed`, ID `sha256:69a84187fbf9b7820c61eb342d4ce3381f1fe3f3eebef31d75b743e821114928`; revision label verified independently; identity does not override the canceled build |
| Console surviving-export payload probe | Exit 143 / 60.11s, bounded timeout, no output; not accepted and not attributed to a proven application defect |
| Identical Console payload-probe retry after cold image access | Exit 0 / 8.06s with the same 60s limit, assertions and resources; npm 10.9.10 / tar 7.5.22, UID 1001, Next 15.5.28, Prisma 6.18.0; 96 trace manifests / 8580 references, zero missing |
| Console surviving-export vulnerability scan | Exit 1 / 151.01s; 2 critical, 63 high, 73 medium, 7 low, 2 unknown; no tar finding; both critical findings are CVE-2025-68121 in two esbuild paths bundling Go 1.23.12 |

Gateway's scan used Trivy 0.76.1 with database UpdatedAt
`2026-11-10T10:23:24.039108641Z`; no advisory/severity filtering or ignore was
used. Console used the same database. The identical probe passed after the
initial cold-access timeout; the cause of that timeout was not proven and its
failed receipt is preserved. The selected critical bundled-tar remediation is
supported for the host, this Gateway image and the independently inspected
surviving Console artifact, not the unchanged publisher base. Console's build
remains canceled: a working tagged payload and scan do not establish an exit-zero
export, live startup, health or authenticated request flow. Remaining Gateway
high findings include musl, zlib and bundled JavaScript tooling. No
production/security certification is implied.

### Separate Fresh Lock Audits

| Command | Actual result / wall seconds |
|---|---|
| `npm audit --json --prefix gateway` | Exit 0 / 8.04s; zero findings |
| `npm audit --json --prefix console` | Exit 0 / 5.16s; zero findings in the secondary lock |
| `npm audit --json --prefix console/desktop-shell` | Exit 1 / 8.66s; 3 high, 1 moderate |
| `npm audit --json --prefix integrations/windows-agentic-bridge/bridge-server` | Exit 0 / 4.63s; zero findings |
| `npm audit --json --prefix integrations/windows-agentic-bridge/bridge-ui` | Exit 1 / 5.34s; 3 high, 1 moderate |
| `corepack pnpm --dir console audit --json` | Exit 0 / 5.79s; zero findings in the canonical lock |

Desktop and Bridge UI report Vite, Browserslist and source-map-js as high,
baseline-browser-mapping as moderate. Their package graphs were unchanged by
the npm-engine patch; this patch did not repair those separate dependency
findings. No automatic `audit fix`, force install, dev-dependency exclusion or
severity suppression was used. These failures remain P4 work, not passing gates.
The final targeted batch observed 4130 MiB minimum available RAM and 3.913 GiB
minimum free disk. No complete test suite or image scan was repeated in it.

Python wheel access was last blocked on November 10 and was not retried in this
npm-only batch. pip-audit/full production
closure, Runtime refresh, OS/binary findings and final live acceptance remain
open. No native services, benchmarks or new live stack were run. P4 is open.

Exact argv, warnings, exits and durations are retained under ignored
`artifacts/p4/`: `major-image-builds.json`, `major-image-cancellation.json`,
`alpine-mirror-transport.json`, `major-image-mirror-builds.json`,
`major-image-checks.json`, `console-image-fetch-retry.json`,
`console-npm-upgrade-cancellation.json`, `npm-host-patch.json`,
`npm-patch-validation.json`, `npm-patch-final-validation.json`,
`npm-console-unit-retry.json`, `npm-patched-image-builds.json`,
`npm-patched-image-checks.json`, `npm-console-canceled-export.json`,
`npm-console-canceled-export-checks.json`, `npm-final-targeted-checks.json`.
Failed/canceled receipts were not overwritten.
Rollback is a reviewed reversal of all npm manifests/locks/CI/Docker pins plus
restoring the user-prefix backup; it restores a known vulnerable tool and is not
automatic security remediation. No schema/data rollback is needed. Existing
services, other workers' image tags, secrets and persistent volumes were preserved.
Local completion checkpoint: `checkpoint/p4-npm-alignment-2026-11-11`.
Nothing pushed or merged.

## P4 Console tracing-root repair - 2026-11-10

Starting commit `48314cd7b48703b10f6a02acab52c76a8118b9fa`, clean branch
`Radin/omerta-env-namespace`; pre-edit tag
`checkpoint/p4-tracing-root-start-48314cd`. Repair commit: `79fe192`.
This closes the workspace-root warning recorded in the preceding major batch,
not the remaining P4 image/security or Python network gates.

An independent call to the installed Next 15.5.28 config loader reproduced
`outputFileTracingRoot=/home/omerta` rather than the checkout. Previous build
metadata independently showed the same root, a worktree-specific relative app
directory and one trace reference to the host Node binary outside the checkout.
The command exited 0 despite this semantic defect. The external lockfile caused
Next's root inference; no user-owned lockfile was edited or removed.

`console/next.config.mjs` now derives the absolute repository tracing root from
its own module location, not cwd or ancestor lockfiles. This includes the two
local workspace packages without extending tracing to the home directory.
See the official [Next 15 tracing-root documentation](https://nextjs.org/docs/15/app/api-reference/config/next-config-js/output).
No dependency, API, auth, schema, security header, transpilation, privilege or
service-topology change was made. This is build reproducibility, not isolation.

The regression copies the real config into a temporary checkout beneath a
foreign lockfile, loads it with the real installed Next normalizer from another
cwd, and checks the root plus existing HSTS/strict-mode/webpack settings.
Its first run failed because Vitest/jsdom transformed a `new URL` asset reference
into a browser URL. Replacing fixture lookup with Node's `require.resolve`
fixed the test harness without weakening the assertions; the failed run is kept.

| Gate | Actual result | Wall seconds |
|---|---|---|
| Initial full Console suite | Exit 1; 42 passed, 1 failed, 0 skipped; fixture URL failure | 72.75 |
| `corepack pnpm --dir console test --config vitest.config.mts --maxWorkers=2` after repair | Exit 0; 43 passed / 16 files, 0 failed/skipped; suite 66.79s | 75.59 |
| `corepack pnpm --dir console build` | Exit 0; production compilation/typechecking/page generation; previous root warning absent | 444.36 |
| Generated `required-server-files.json` and all `.nft.json` assertions | Exit 0; checkout root, relative app `console`, 96 manifests / 8580 references, 0 outside / missing | 1.16 |
| Independent realpath probe of the same references | Exit 0; 8580 references, 0 symlink-resolved escapes; separate timing not retained | Not recorded |

The final three-gate batch used the prior bounded Node environment and
non-credential validation database URL, sequentially, with a 1 GiB available-RAM
guard. Minimum available RAM: 2763 MiB. Disk stayed at about 12 GiB free.
Reports, including exact final argv, warnings and trace assertions:
ignored `artifacts/p4/tracing-root-validation.json` (failed attempt) and
`tracing-root-final-validation.json` (successful batch); the local runner is
`tracing-validation-runner.mjs`. No test/type/lint check was disabled.

**Not run:** new application-image builds, live Docker acceptance, Python/Runtime
suites, fresh vulnerability scans, browser E2E, native services or benchmarks.
Existing Python wheel DNS and image/OS/binary advisory gates remain open and
were not retried here. Earlier Docker acceptance and source scans do not attest
this new tree. No running stack, secret, image tag or volume was modified.
Rollback is a reviewed reversal of the config/test repair; no dependency or
database rollback is needed. Checkpoint:
`checkpoint/p4-console-tracing-root-2026-11-10`. Nothing pushed or merged; P4 open.

## P4 approved dependency-major migration - 2026-11-10

The user separately approved controlled Zod, DeepmergeTS and Minimatch/Glob
major migrations after the compatible checkpoint. Starting commit:
`ec76802608f8bd4795e3a8517c2d8af0f3662ddc`; pre-edit tag:
`checkpoint/p4-major-start-ec76802`. Implementation: `f47c8ad` on unchanged
branch `Radin/omerta-env-namespace`. This section supersedes earlier statements
that these selected majors still await approval; P4 itself remains open.

### Changes And Compatibility Findings

- Gateway, Console and Bridge now lock Zod 4.6.7. Gateway/Bridge record schemas
  use explicit string keys. Gateway retains the existing validation envelope,
  dotted field paths and `invalid_enum_value` diagnostic code; default Zod
  message wording is not promised byte-identical. No route, auth, tenant or
  execution-privilege change was made, and no Zod 3 fallback was introduced.
- Console TypeScript moves from 5.4.5 to 5.9.3, within major 5, for supported
  Zod 4 typing. Node 22.23.2, npm 10.9.8 and pnpm 11.13.1 are unchanged.
- Console overrides DeepmergeTS to 8.0.2 for the actual `@prisma/config` consumer.
  Prisma/client remain 6.18.0; no database migration was run. Tests exercise
  config loading, nested merging, input preservation and selected prototype keys.
- Modern matcher owners use Minimatch 11.0.5 and Console Glob 14.0.4. ESLint 8
  and rimraf 3 retain callable Minimatch 3.1.5 / callback Glob 7.2.3 APIs. This
  is not retirement of deprecated legacy tooling or a universal Glob upgrade.

An independent brace-pattern probe initially failed with exit 1:
`TypeError: (0 , brace_expansion_1.expand) is not a function`. The old global
brace-expansion v1 override had been forced into the modern named-API matcher.
Scoping it to `<2`, retaining the existing v2 override and allowing modern v5
fixed the consumer incompatibility. Regression tests exercise actual parent-
resolved modern and legacy matchers, including braces, rather than just versions.

The initial npm secondary Console lock also retained Glob 10.5.0 despite an
exit-zero resolution command. Expanding the selector from `glob@>=10 <14` to
`glob@>=10 <15` produced Glob 14.0.4 in both locks; the generated locks were
inspected, not assumed correct from command success or edited by hand.

During initial lock generation, pnpm automatically proposed a release-age
exception for newly published Minimatch 11.0.6. It was removed **before an
installation used it**. The mature 11.0.5 release was selected instead and
`minimumReleaseAgeStrict: true` now rejects such silent policy relaxation.
No final age exception, disabled integrity check, force/legacy-peer install,
advisory ignore, dev-dependency exclusion or skipped failing test was used.

Migration references: [Zod migration guide](https://zod.dev/v4/changelog),
[DeepmergeTS changelog](https://github.com/RebeccaStevens/deepmerge-ts/blob/main/CHANGELOG.md),
[Glob changelog](https://github.com/isaacs/node-glob/blob/main/changelog.md).
Registry versions, engines and exports were also inspected before installation.

### Executed Gates

All following gates exited 0. Durations are wall seconds, not benchmark results.
Commands ran sequentially with a 1 GiB available-memory stop guard. Main-batch
minimum available RAM: 2559 MiB; final regressions: 3316 MiB; scan: 3987 MiB.
Node builds used `CIRCLE_NODE_TOTAL=2` and
`NODE_OPTIONS=--max-old-space-size=1536`. Prisma/build used the non-credential
validation URL `postgresql://127.0.0.1:5432/omerta_validation`; no DB was started.

| Command / gate | Actual result | Wall seconds |
|---|---|---|
| `npm ci --prefix gateway --no-audit --prefer-offline --fetch-retries=1 --fetch-timeout=120000` | Locked real installation | 52.12 |
| `npm ci --prefix integrations/windows-agentic-bridge/bridge-server --no-audit --prefer-offline --fetch-retries=1 --fetch-timeout=120000` | Locked real installation | 48.17 |
| `corepack pnpm --dir console install --frozen-lockfile --prefer-offline --network-concurrency=2 --child-concurrency=2` | Final canonical real installation | 12.18 |
| `npm run build --prefix gateway` | TypeScript compilation | 30.37 |
| `npm test --prefix gateway` | 31 passed / 9 files; 0 failed/skipped | 14.47 |
| `npm run lint --prefix gateway` | Actual parser/matcher consumer passed | 25.66 |
| `npm run build --prefix integrations/windows-agentic-bridge/bridge-server` | TypeScript compilation | 18.33 |
| `npm test --prefix integrations/windows-agentic-bridge/bridge-server -- --run --maxWorkers=2` | 4 passed / 2 files; 0 failed/skipped | 6.35 |
| `corepack pnpm --dir console test --config vitest.config.mts --maxWorkers=2` | 40 passed / 16 files; 0 failed/skipped | 81.62 |
| `corepack pnpm --dir console exec prisma validate` | Actual config/schema validation | 13.65 |
| `corepack pnpm --dir console prisma:generate` | Client 6.18.0 generated | 16.39 |
| `corepack pnpm --dir console build` | Production build passed, root warning below | 500.36 |
| `corepack pnpm --dir console exec vitest run tests/unit/policy-editor.test.tsx --config vitest.config.mts --maxWorkers=1` | Final strengthened test: 3 passed, 0 failed/skipped | 21.26 |
| `corepack pnpm --dir console exec tsc --noEmit` | Final typecheck | 87.70 |
| `python -m pytest tests/architecture/test_javascript_toolchain.py tests/architecture/test_quickstart_runtime.py tests/architecture/test_integration_consolidation.py -q -p no:cacheprovider` | 26 passed; 0 failed/skipped | 22.57 |
| `ruff check --no-cache tests/architecture/test_javascript_toolchain.py` | Passed | 3.08 |
| `python3 scripts/audit_environment_namespace.py --check` | 164 tokens; 93 reviewed legacy readers retained | 3.84 |

Python/Ruff used the existing `omertaos-python-validation:local` image with
read-only bind, no network, temporary `/tmp`, 1024 MiB RAM and 2 CPUs. Exact
Docker argv are retained in the artifact below. The full Console suite ran
before two additional invalid-budget cases and stronger submission assertions
were added; only that three-test subset and typecheck ran afterward. Do not
report a full 42-test Console run. The later changes were test-only.

Registry audit commands used `--json --fetch-retries=0 --fetch-timeout=30000`:
`npm audit --prefix gateway --package-lock-only` (6.82s), Bridge equivalent
(7.44s), `corepack pnpm --dir console audit` (7.53s) and secondary
`npm audit --prefix console --package-lock-only` (6.91s). Each reported zero
known advisories, including development dependencies, for its own resolved
graph. Counts from npm and pnpm are not interchangeable or evidence of images.

A manifest-only temporary copy also passed
`npm ci --prefix <temporary-copy>/console --dry-run --ignore-scripts --no-audit
--fetch-retries=0 --fetch-timeout=30000` (9.62s). This is an **811-package
install plan**, not another real installation; canonical Console uses pnpm.

Trivy 0.76.1 `fs --scanners vuln,secret --db-repository
public.ecr.aws/aquasecurity/trivy-db:2 --parallel 1 --timeout 5m --exit-code 1
--format json <snapshot>` passed in 7.08s. Snapshot: 972 tracked regular working-
tree files, including the staged new test, before this documentation update;
manifest SHA-256 `a2a55395bc35513ea4b43dd56a8862236c21158eacec20443fe7aed6509428b0`.
DB updated `2026-11-10T10:23:24.039108641Z`; zero reported vulnerabilities and
zero detected secrets in the inspected scope. Two historical broken symlinks
were excluded from the regular-file snapshot and recorded explicitly. Detected
dependency targets were six npm/pnpm locks and Runtime Cargo.lock, **not Python
requirements, container OS packages, ignored files or Git history**.

### Warnings, Deferred Gates And Rollback

- Console build inferred `/home/omerta` as workspace root because of an external
  `/home/omerta/package-lock.json`. Build passed with this warning; tracing-root
  reproducibility needs a focused config repair and rebuild in the next batch.
  The external file was not removed and no type/lint/build-error check disabled.
- Deprecated ESLint 8 and seven deprecated transitive packages remain warnings.
  Initial Prisma postinstall warned about CLI installation; explicit real
  config validation, client generation and production build later passed.
- The prior Python wheel DNS blocker was not retried in this batch. Control
  rebuild, complete Python production closure and pip-audit remain blocked.
  Existing failed base/image scans, bundled npm-tar and other OS/binary findings
  remain open; a clean application lock audit does not clear those findings.
- Application-image rebuilds and live acceptance for these new majors are
  **deferred/not run**, not passed. Earlier one-worker acceptance used older
  source/images. Full repository Python/Runtime suites, browser E2E, native
  services and benchmarks were not rerun for this dependency-only batch.

Sanitized local reports under ignored `artifacts/p4/` retain exact argv, exit
codes, durations, warnings, intermediate failures and provenance:
`major-package-contracts.json`, `major-lock-generation.json`,
`major-locked-installation.json`, `major-secondary-glob-lock.json`,
`major-scoped-override-install.json`, `major-glob-selector-sync.json`,
`major-validation-batch.json`, `major-final-regressions.json`,
`major-source-scan.json`. No service or persistent Docker data was changed.
The generated TypeScript build-info file was moved into ignored artifacts,
not committed. Evidence improves only to selected **E1** compatibility/audit
checks, not new deployed E2 acceptance or production/security certification.
Rollback is a normal reviewed reversal of this dependency/source/test commit,
restoring manifests and all locks together, followed by locked reinstall and
affected tests; no schema/data rollback or volume operation is required.
Checkpoint: `checkpoint/p4-major-migration-2026-11-10`. Nothing pushed or merged.

## P4 reviewed base-image refresh - 2026-11-10

Starting HEAD `c57dfc9a4391bfef6ee332c0f294309bfed0a5df`, clean working tree;
pre-edit tag `checkpoint/p4-base-refresh-start-c57dfc9`. Current branch remains
`Radin/omerta-env-namespace`. Scope: compatible pinned-base refresh, not major
application upgrades, final Docker acceptance or P5 synchronization.

Registry metadata and sequential Linux/amd64 digest pulls succeeded for these
publisher images. The generic Node tag was inspected only as preflight; the
canonical `alpine3.24` tag was independently inspected and returned the same
digest. No mutable `latest` reference was introduced into a Dockerfile.

| Consumer | New immutable reference |
|---|---|
| Control | `python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b` |
| Runtime final stage | `debian:bookworm-slim@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc` |
| Gateway and Console, all stages | `node:22.23.2-alpine3.24@sha256:b6f26b36c8ff49624cfdac716b8ea1138d606df02586a77d364bb5536a634f85` |

Read-only, network-disabled identity probes passed: Python 3.12.16 with pip
25.0.1 (5.46s); Debian Perl `5.36.0-7+deb12u4` and zlib
`1:1.2.13.dfsg-1` (2.89s); Node 22.23.2, npm 10.9.8, Alpine 3.24.2 (2.95s).
The Runtime Perl patch matches the fix version recorded in the earlier scan;
the old retained application image still has the older package. Node/npm
contracts, Python minor line, pnpm version, Rust builder, dependency locks,
auth, schemas, topology and volume names are unchanged by this refresh.

### Base Scans Are Still Red

Trivy 0.76.1 scanned each base sequentially with `image --image-src docker
--scanners vuln --db-repository public.ecr.aws/aquasecurity/trivy-db:2
--parallel 1 --timeout 5m --exit-code 1 --format json` and the existing private
validation cache. DB update: `2026-11-10T10:23:24.039108641Z`. No advisory/severity
filter or ignore was added. Counts are package/advisory occurrences in bases,
not application-image counts or unique CVEs.

| Base | Pull exit / seconds | Scan exit / seconds | Critical | High | Medium | Low |
|---|---|---|---|---|---|---|
| Python | 0 / 42.73 | 1 / 24.18 | 0 | 49 | 80 | 66 |
| Debian | 0 / 44.53 | 1 / 12.38 | 1 | 34 | 95 | 85 |
| Node | 0 / 48.78 | 1 / 29.58 | 1 | 15 | 16 | 1 |

Debian's critical is the previously documented zlib/minizip applicability case,
still retained without a waiver. Node's critical remains npm's bundled tar
7.5.11, CVE-2026-59873, published fix 7.5.19. Python's pip remains 25.0.1;
zero critical does not mean no vulnerabilities or a patched pip. No bundled
package was deleted to hide findings. Minimum available RAM for pulls/scans:
3939 MiB; base identity probes: 3904 MiB. Disk remained at about 12 GiB free.

### Executed Contracts And Open Build Gate

`test_quickstart_upstream_images_and_build_bases_are_digest_pinned` now checks
the reviewed final-stage baseline and identical Node references in every stage,
in addition to the existing digest-pinning requirements. These assertions guard
pin consistency and selected-baseline regression, not vulnerability absence.

| Gate | Actual result |
|---|---|
| `python -m pytest tests/architecture/test_javascript_toolchain.py tests/architecture/test_quickstart_runtime.py tests/control/test_model_client.py -q -p no:cacheprovider` | Exit 0; 25 passed, 0 failed/skipped/warnings; 5.47s suite / 16.28s wall |
| `ruff check --no-cache tests/architecture/test_javascript_toolchain.py` | Exit 0; 3.40s wall |
| `docker compose --project-directory /home/omerta/.codex/worktrees/09e8/OMERTAOS --project-name omerta-p4-validation --env-file /home/omerta/projects/OMERTAOS/.env -f deploy/docker/compose/quickstart.yml config --quiet` | Exit 0; 0.52s; rendering only |

Python gates used the existing bounded, read-only, network-disabled validation
container, with temporary data under `/tmp`; minimum available RAM 3821 MiB.
A separate probe from the **new production Python base**, with all capabilities
dropped and no-new-privileges, confirmed PyPI release metadata HTTP 200 but
`files.pythonhosted.org` DNS `gaierror` (exit 1, 45.66s). Wheel HEAD was not
attempted after failed resolution. A remote read-only DNS API lookup was also
unavailable; no usable mapping was obtained or fabricated. No DNS/TLS, host,
daemon or systemd setting was changed.

Exact argv, durations and selected package findings are retained under ignored
`artifacts/p4/`: `base-registry-preflight.json`, `node-base-preflight.json`,
`base-image-inspection.json`, `base-image-identities.json`,
`base-refresh-validation.json`, `python-base-transport.json`.

**Not executed:** application image rebuilds, new live stack, arm64 acceptance,
native deployment or benchmarks. Control rebuild/pip-audit remain network-blocked;
other application rebuilds are deferred to the consolidated image-validation
batch, not reported as network failures. Base scans and Compose rendering do
not substitute for those gates. Existing application tags, running services,
containers, volumes, credentials and keys were preserved; only the new public
base images were added to the local cache. P4 remains open. Major migrations
still require separate approval. Rollback is reversal of the four Dockerfile
pin changes and the corresponding test baseline, without data migration or
removing any image. Checkpoint: `checkpoint/p4-base-refresh-2026-11-10`.

## P4 Control provider payload repair - 2026-11-10

Starting commit `867d78288890ed1c7cce157e66257be40e7ccce2`, clean branch
`Radin/omerta-env-namespace`; pre-edit tag
`checkpoint/p4-control-provider-start-867d782`. This remains compatible P4 work,
not major-upgrade approval or a transition to P5.

An independent read-only, network-disabled probe of the retained Control image
`omertaos-control:p4-20261103` failed importing `control.clients.models` with
`ModuleNotFoundError: integrations` (exit 1, 3.90s). The inspected tag still
identifies `sha256:ce7942eebcd216c500ad3ff053cc60e6a9887439ceb096d8458bdfd819861c98`.
Root cause is an implementation/packaging defect: `control/clients/models/client.py`
imports `integrations.providers`, while the production Dockerfile omitted that
source directory. Repository-mounted unit tests had hidden this deployment gap.

`control/Dockerfile` now copies only `integrations/providers`, not the entire
integration tree or Windows Bridge tooling. Provider ownership remains in
Integrations, orchestration stays in Control, and host execution remains behind
Runtime. There is no auth, API, schema, credential, dependency or topology change
in this repair.

The regression checks the production COPY entries and imports the actual client
and provider from a temporary payload using `python -I -B`, without the checkout
on the import path. It verifies the loaded provider belongs to that payload and
that the disabled provider still fails closed. Existing model-client tests retain
bounded timeout, redirect rejection, response validation and local-key behavior.
This is **not a replacement for a production Docker build or live provider test**.

| Gate | Actual result |
|---|---|
| `python -m pytest tests/architecture/test_quickstart_runtime.py tests/control/test_model_client.py -q -p no:cacheprovider` | Exit 0; 21 passed, 0 failed/skipped/warnings; 4.72s suite / 13.16s wall |
| `ruff check --no-cache tests/architecture/test_quickstart_runtime.py` | Exit 0; 2.91s wall |

Both commands used the existing pinned validation container, read-only workspace,
no network, 1 GiB memory limit, 2 CPUs and temporary data/tmpfs. Minimum available
RAM: 4104 MiB. Exact commands and sanitized results are in ignored
`artifacts/p4/control-provider-reproduction.json` and
`artifacts/p4/control-provider-validation.json`.

Two bounded transport probes attempted documented JSON DNS-over-HTTPS endpoints
without changing host/container DNS, weakening TLS, changing indexes or installing
packages. Both failed: Cloudflare URLError (0.20s), Google URLError/OSError
(0.14s). Evidence: `python-wheel-doh-probe.json` and
`python-wheel-google-doh-probe.json` under `artifacts/p4/`.
Endpoint references: [Cloudflare](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/make-api-requests/dns-json/),
[Google](https://developers.google.com/speed/public-dns/docs/doh/json).

The full canonical Control rebuild remains blocked by wheel-host access and was
not rerun using alternate requirements or an overlay image. Existing image CVEs,
pip-audit, final live acceptance and deferred major migrations remain open.
No services, volumes, images or secrets were modified. Rollback is reversal of
this Dockerfile/test repair only; it entails no data migration. Local checkpoint:
`checkpoint/p4-control-provider-payload-2026-11-10`. Nothing pushed or merged.

## P4 scanner follow-up and dependency checkpoint - 2026-11-10

Scope remains compatible repairs first, local checkpoint, and separate human
approval for major upgrades. Starting HEAD: `e8b15d5cb112eb72a2b361a7539e6d186cf2d263`;
pre-edit tag: `checkpoint/p4-open-gates-start-e8b15d5`. Branch unchanged.
Dependency/test repair commit: `1eae3e7`.
**P4 is open. No push, merge, P5 transition or major migration was performed.**

The retained scanner artifacts below were produced on 2026-11-02 UTC; their
timestamps are preserved, not relabeled as fresh 2026-11-10 scans. They supersede
the earlier *unavailable* Trivy result, not the functional Docker evidence.
The official Aqua ECR DB endpoint unblocked the same scanner without TLS bypass,
severity filtering, advisory ignores or dropping development dependencies.
DB download: exit 0, 103.12s, minimum available RAM 4666 MiB; database update
`2026-11-02T19:15:11.074748541Z`, schema 2. See
[Trivy's publisher documentation](https://trivy.dev/docs/dev/docs/configuration/db/).

### Retained Image Findings

All scans used Trivy 0.76.1 and `image --image-src docker --scanners vuln
--db-repository public.ecr.aws/aquasecurity/trivy-db:2 --parallel 1 --timeout 6m
--exit-code 1 --format json`, with cache at
`/home/omerta/.local/share/omerta-validation/tools/p4/trivy-cache`.
The four exact image IDs are in the earlier build table and the ignored
`artifacts/p4/image-vulnerabilities.json`. Counts are package/advisory
occurrences, not unique CVEs, demonstrated exploits or current zero-finding proof.

| Retained image | Exit | Wall seconds | Critical | High | Medium | Low | Unknown |
|---|---|---|---|---|---|---|---|---|
| `omertaos-control:p4-20261103` | 1 | 22.90 | 4 | 64 | 132 | 88 | 11 |
| `omertaos-runtime:p4-20261103` | 1 | 8.80 | 4 | 40 | 107 | 83 | 6 |
| `omertaos-gateway:p4-20261103` | 1 | 30.74 | 2 | 16 | 34 | 71 | 4 |
| `omertaos-console:p4-20261103` | 1 | 88.16 | 3 | 42 | 62 | 74 | 5 |

Minimum available RAM during these sequential scans: 4566 MiB. Critical
findings include Debian Perl in Control/Runtime, Control certifi, Alpine Brotli
and npm's bundled tar in Gateway/Console, and Go stdlib in Console's bundled
`@esbuild/linux-x64@0.25.11` binary. Updating application locks alone does not
update OS packages, npm's own dependency tree or compiled Go binaries.
The earlier zero-critical npm/pnpm results covered those application audits
only, not these complete images. Runtime's final image yielded no Rust library
inventory; Cargo source audit is a separate, narrower gate.

Runtime `zlib1g` also reports CVE-2023-45853. Read-only package probes confirmed
`1:1.2.13.dfsg-1` and absence of `minizip`/`libminizip1` (expected probe exits 1).
[Debian's applicability note](https://security-tracker.debian.org/tracker/CVE-2023-45853)
explains that bookworm's zlib does not build the affected contrib/minizip code.
This is an applicability-review candidate, not an added ignore or a passed
image gate; all four raw critical counts above remain recorded.

### Compatible Repairs And Targeted Validation

- Control's Docker Requests pin now matches the existing hashed validation lock
  at 2.34.2 instead of 2.32.5. Regression tests reject both version drift and
  pre-remediation pins. The upstream
  [Requests advisory](https://github.com/psf/requests/security/advisories/GHSA-gc5v-m9x4-r6x2)
  concerns direct `extract_zipped_paths()` use, not normal requests; no exploit
  of this application's model client was demonstrated.
- Bridge lock updates stay within declared major ranges: MCP SDK 1.32.2,
  Axios 1.21.1, Hono 4.13.17, node-server 2.1.6, body-parser 2.4.0,
  fast-uri 3.1.9, follow-redirects 1.16.3, ip-address 10.7.6,
  proxy-addr 2.0.8 and qs 6.17.1. The source-scan critical proxy-addr finding
  motivated the first patch. The lock-contract test checks all ten runtime floors,
  four development-package floors and the supported Vite peer contract.
  Node/npm contract, transport API and authorization are unchanged.
- Broad `npm audit fix --package-lock-only --ignore-scripts --json` failed with
  Arborist `edgesOut` (exit 1, 58.39s), leaving the lock unchanged. Targeted
  `npm update proxy-addr --package-lock-only --ignore-scripts --no-audit` succeeded;
  a second targeted update batched the other nine affected runtime packages.
  No force or peer-validation bypass was used.
- First final `npm ci` failed fetching Axios with ETIMEDOUT (exit 1, 52.74s).
  The explicit bounded retry below succeeded; the failed attempt is retained.
  An earlier proxy-only build and three tests also passed, but are not substituted
  for the final expanded-lock validation.
- The next full npm audit exposed compatible development fixes omitted by the
  production-focused filesystem scan. Vitest now pins 4.1.12, brace-expansion
  1.1.21, js-yaml 4.3.2 and source-map-js 1.2.2. Targeted development update also
  reproduced Arborist `edgesOut` (exit 1, 30.77s). As already done for Gateway,
  explicit Vite 7.3.7 dependency/override selects Vitest 4's supported patched
  peer line instead of 8.2.1. This test-only peer-line change is disclosed; it is
  not an application Vite migration or a disabled peer/security check. Lockfile
  platform-package churn is generated by the changed Vite dependency graph.
  Zod, DeepmergeTS and Glob/Minimatch major upgrades were not implemented.

| Final gate | Result |
|---|---|
| `npm audit --prefix integrations/windows-agentic-bridge/bridge-server --package-lock-only --json --fetch-retries=0 --fetch-timeout=30000` | Exit 1; only Zod remains: 1 high, 0 critical/moderate/low; proposed fix 4.6.7 is a major; 5.29s wall |
| `npm ci --prefix integrations/windows-agentic-bridge/bridge-server --no-audit --prefer-offline --fetch-retries=1 --fetch-timeout=120000` | Exit 0; 361 packages, 48.36s wall; audit executed separately above, not suppressed |
| `npm run build --prefix integrations/windows-agentic-bridge/bridge-server` | Exit 0; 18.30s wall |
| `npm test --prefix integrations/windows-agentic-bridge/bridge-server -- --run` | Exit 0; 3 passed, 0 failed/skipped, 2 files; 2.32s suite / 6.96s wall |
| `python -m pytest tests/architecture/test_quickstart_runtime.py tests/architecture/test_integration_consolidation.py tests/control/test_model_client.py -q -p no:cacheprovider` | Exit 0; 25 passed, 0 failed/skipped, 6.17s suite / 21.38s wall |
| `ruff check --no-cache tests/architecture/test_quickstart_runtime.py tests/architecture/test_integration_consolidation.py` | Exit 0; 3.16s wall |

Python commands used `omertaos-python-validation:local`, read-only workspace,
network disabled, 1 GiB memory limit, 2 CPUs, `/tmp` tmpfs and temporary Control
data directory. Its Requests is 2.34.2. Minimum available RAM for the final
sequential validation batch: 3820 MiB. Exact argv/durations are retained in
`artifacts/p4/bridge-complete-validation.json`; its overall exit remains 1
because the audit is red, even though build/tests/lint passed. Intermediate
results are retained in `compatible-final-retry.json`, and install failures in
`compatible-final-tests.json`. Two diagnostic wrapper mistakes (wrong Runner
constructor and treating an artifact list as a mapping) exited 1 before their
intended operation, were corrected, and are not counted as validation passes.

### Fresh Source Scan

The 2026-11-10 scan refreshed the official DB rather than reusing the expired
baseline: updated `2026-11-10T10:23:24.039108641Z`, downloaded
`2026-11-10T13:11:26.428874735Z`. Initial refresh/scan took 177.79s. The final
snapshot rerun used Trivy `fs --scanners vuln,secret --db-repository
public.ecr.aws/aquasecurity/trivy-db:2 --parallel 1 --timeout 5m --exit-code 1
--format json`, the cache directory above and a new tracked-file-only snapshot.
Exit 1, 3.10s, minimum available RAM 4067 MiB:
**0 critical, 2 high, 3 medium occurrences, 0 detected secrets**.
The five occurrences are three distinct advisory IDs: DeepmergeTS in both
Console locks, Glob in both locks, and Minimatch in the pnpm lock; all published
fixes require the deferred major migrations. No findings were reported for the
Bridge lock by this scanner, but its broader npm audit still flags Zod.

There were 971 copied tracked files. Two historical broken symlinks were not
followed: `docs/migration/evidence/config-sustemd.broken-link` and
`docs/migration/evidence/process-analytics.broken-link`. Python requirements
were not dependency targets of this filesystem scan. The result is not image,
full dependency, ignored-file or Git-history acceptance. Snapshot manifest SHA-256:
`a9fd8b20abb5e5f92c767680b85017c2fd3801f0cbc2e6cb275a9080c75b4ecc`;
sanitized evidence is in `artifacts/p4/final-source-scan.json`. This manifest
identifies the working-tree snapshot before this final report wording, not an
assertion that all later document edits were scanned. Different DB baselines
mean old/new counts cannot be attributed solely to dependency patches.

### Still Open

The 2026-11-10 DNS recheck still resolves PyPI but not `files.pythonhosted.org`
(10.09s). Python wheel downloads and pip-audit installation remain blocked.
The earlier exact-version PyPI release-metadata query fetched all 34 installed
Control packages: five affected packages, 12 alias-deduplicated advisories
(23 raw entries). This is supplementary evidence, **not pip-audit acceptance**.
Affected packages include certifi, pip, Requests, setuptools and urllib3.
The Requests source repair does not repair the retained image.

No image rebuild or new Docker live acceptance was performed for this batch;
the new Control dependency is not deployed. Full pinned Python transitive
closure, OS/Brotli/Perl fixes, bundled npm/Go fixes, Bandit's five existing low
findings, and reviewed major migrations remain open. Previously passed 68
functional fresh/restart gates do not prove security acceptance. Native,
benchmark, full repository Python, and historical restore/upgrade reruns were
not executed. No running worker, volume or persistent service was changed.
Rollback is a reviewable reversal of these dependency/test changes, with no
data/schema migration; do not use an insecure old dependency for production.

Final supporting checks: `python3 scripts/audit_environment_namespace.py --check`
and `git diff --check` exited 0; 164 tokens and the same 93 reviewed legacy
readers remain. No alias retirement was performed. Local checkpoint name:
`checkpoint/p4-compatible-deps-2026-11-10`; this is not P4 closure.

## P4 compatible security repair checkpoint - 2026-11-03

Approved scope: batched dependency/security inspection, private secret storage
and constrained Docker validation. Original HEAD `3b1ef78`; clean-tree checkpoint
`checkpoint/p4-start-3b1ef78`; branch `Radin/omerta-env-namespace`. Local repairs:
`20988f8` (private atomic secret storage) and `089127b` (compatible security
patches, lockfiles, operator workflow and refreshed namespace inventory).
P4 is **not closed** and no P5 push/merge is authorized by this execution.

The local provider now creates a `0700` directory, checks owner and unsafe
permission bits on every operation, uses no-follow directory-relative I/O and
atomically replaces AES-GCM ciphertext with `0600` files. Permission failure is
no longer swallowed. Tests preserve prior ciphertext on failed permission setup,
reject directory/read symlinks, protect a symlink target from overwrite, retain
legacy plaintext migration and accept owner-controlled native `0750` directories.
No API/schema/key-format change or secret rotation was made.

Metadata-only inspection confirmed the two previously documented permission
defects. After checking ownership and running-service bind mounts, only these
owned paths were restricted, without changing contents or recursing:

| Local path | Before | After |
|---|---|---|
| `/home/omerta/projects/OMERTAOS/.env` | `0664` | `0600` |
| `/home/omerta/projects/OMERTAOS/.aion/secrets` (empty) | `0777` | `0700` |
| Current worktree `.aion/secrets` (empty) | `0775` | `0700` |

The existing worktree lease-key directory/file were already `0700`/`0600`.
No running service mounted the two checkout secret directories or environment
file. No root-owned native path or systemd setting was changed.

### Executed Gates

Test durations below are suite-reported unless marked wall time. Early commands
without a timed runner have no captured wall duration; it is not reconstructed.

| Gate / exact command | Actual result | Evidence |
|---|---|---|
| `python -m pytest tests/control -q -p no:cacheprovider` in pinned validation image, with data/secret dirs under `/tmp` | Exit 0; 117 passed, 1 skipped, 9 warnings; 18.19s | E1; includes 12 local-secret tests and Configuration/Network authorization cases |
| `ruff check control/app/network/service.py tests/control/test_network_proxy_secrets.py` | Exit 0 | E1 |
| `npm ci --prefix gateway --no-audit --fetch-retries=1 --fetch-timeout=120000` | Exit 0; 410 packages; CLI reported 54s; six deprecation warnings | Locked install, not a clean advisory result |
| `npm run build --prefix gateway` / `npm test --prefix gateway` | Both exit 0; 26 tests in 9 files; 7.84s | E1 |
| `corepack pnpm --dir console install --frozen-lockfile --prefer-offline --network-concurrency=4 --child-concurrency=2` | Exit 0; final manifest/lock synchronization reported 8.7s | Locked install; Node/npm/pnpm contract unchanged |
| `corepack pnpm --dir console test --config vitest.config.mts` | Exit 0; 36 tests in 15 files; 36.65s | E1 |
| `cargo fmt --manifest-path runtime-daemon/Cargo.toml --check` | Exit 0 | E1 |
| `cargo test --manifest-path runtime-daemon/Cargo.toml --locked --jobs 1` | Exit 0; 19 unit + 4 contract tests; compilation reported 2m51s; minimum available RAM 3807 MiB | E1; fail-closed sandbox contracts are not successful Linux isolation |
| `docker compose --project-directory /home/omerta/.codex/worktrees/09e8/OMERTAOS --project-name omerta-p4-validation --env-file /home/omerta/projects/OMERTAOS/.env -f deploy/docker/compose/quickstart.yml config --quiet` | Exit 0 | E1 rendering only, not live acceptance |
| `python3 scripts/audit_environment_namespace.py --write` | Exit 0; final 164 tokens, 85 files, 548 occurrences; same 93 reviewed compatibility readers | Refreshed stale P2/P3/test/report inventory, not a removed compatibility gate |

The Control skip is the PostgreSQL scheduler-concurrency test: no dedicated
`AION_TEST_POSTGRES_DSN` was supplied to that unit-suite container. Four existing
framework deprecations and five expected legacy-alias warnings remain.
The native host, browser UI, full Python repository suite, benchmark and
intentionally red Structure completion gate were not executed in this P4 batch.

### Dependency And Scanner Results

| Check | Before | After / actual limitation |
|---|---|---|
| Gateway `npm audit --json --package-lock-only --fetch-retries=0 --fetch-timeout=20000` | Exit 1; 25 affected packages: 7 high, 18 moderate | Exit 1; 15 affected packages: 1 high (Zod), 14 moderate propagated through lint/glob dependencies; 14.85s |
| Console `corepack pnpm audit --json --fetch-retries=0 --fetch-timeout=20000` | Exit 1; 39 advisory entries: 4 critical, 15 high, 14 moderate, 6 low | Exit 1; 4 entries: DeepmergeTS/Zod high, Minimatch/Glob moderate; zero critical; 9.50s |
| Cargo audit 0.22.2 | Initial DB fetch blocked; after CLI Git fetch, exit 0 but Tokio `RUSTSEC-2026-0386` unsound warning | Tokio 1.53.3 and minimum manifest version; exit 0, no vulnerabilities/warnings against 1402 advisories |
| CI-equivalent `bandit -r . -x ./tests -s B101,B105 -f json` | Exit 1; 5 low/high-confidence findings, no parse errors; 20.99s | Open: imports and argv-only subprocess calls in parity/encrypted-recovery harnesses. No new ignore/nosec waiver added |
| Trivy 0.76.1 tracked-source snapshot, `fs --scanners vuln,secret --parallel 1 --timeout 5m --exit-code 1 --format json` | Exit 1 before scan; DB mirror HTTP 403 | Explicit upstream `--db-repository ghcr.io/aquasecurity/trivy-db:2` also blocked, TLS timeout, 35.68s; vulnerability/image acceptance unavailable |
| Separate Trivy `fs --scanners secret --parallel 1 --timeout 3m --exit-code 1 --format json` | Independent secret-only gate, not a substitute for blocked vulnerability scanning | Exit 0; zero detected secrets in tracked-source snapshot; 2.71s. Not a Git-history, ignored-file or comprehensive credential-leak proof |
| Control installed-package audit with `pip-audit==2.10.1 -r /dev/stdin --no-deps --disable-pip --format json --progress-spinner off --timeout 20` in temporary bounded container | Exact package versions captured from existing Control image in memory | Tool install exit 1, DNS failure for files.pythonhosted.org; 148.90s; audit NOT executed |

The RustSec DB was freshly cloned with CLI Git after the scanner's own Git
transport failed; revision `263a4d951a0867d4bddc29dddd6d59427c78f9a7`, dated
2026-11-02T12:45:44+01:00. No stale/advisory-ignore mode was used. Cargo audit
and Trivy release archives matched publisher GitHub API SHA-256 digests before
execution; tools live outside Git under the operator's local validation directory.
The first broad audit wrappers printed underlying nonzero results but themselves
returned zero; subsequent audit wrappers propagate the underlying failure and
the above table records the real scanner exits, not wrapper success.

Next.js 15.5.28, Sharp >=0.35.5, DOMPurify >=3.4.17, Vitest 4.1.12 and compatible
transitive patches address the selected published advisories. Both Console
lockfiles are regenerated, with pnpm remaining canonical. Gateway raises gRPC,
compression and Fastify security floors. Vite is constrained to patched 7.3.7,
within Vitest 4's declared supported range: npm 10.9.8 crashed while traversing
newer Vite optional-devtools peers. Peer validation was NOT disabled. Gateway's
test-only Vite moves from 8.2.2 to 7.3.7, a supported Vitest peer line; it is not
a Vite-application migration. Development dependencies were not pruned to hide
findings.

Remaining major upgrades require separate compatibility work; a user question
was sent before undertaking Zod 4, DeepmergeTS 8, Minimatch 11 or Glob 14.
No application-schema major migration, direct dependency removal, `--force`, `--legacy-peer-deps`, new
scanner exclusion, security certification or production-readiness claim was made.
Upstream patch references: [Next.js](https://github.com/vercel/next.js/security/advisories/GHSA-2464-fhr4-w9xw),
[DOMPurify](https://github.com/cure53/DOMPurify/security/advisories/GHSA-cg2g-xh64-v4q7).

### Failed Attempts And Recovery

- One targeted pytest command named a nonexistent authorization test file:
  exit 4, no tests. The real Network/Configuration tests were included above.
- First network/config batch: 2 failed, 20 passed, 5 warnings, 8.96s. A supplied
  canonical directory conflicted with legacy-unit fixture environment. The unit
  fixture now clears both spelling groups before explicitly configuring each
  case; no resolver conflict check was relaxed.
- Five npm lock-update/install attempts exited 1 with Arborist `edgesOut`,
  including an independent clean scratch reproduction. Pinning only root Vite
  was insufficient because Vitest could still select a nested newer Vite.
  The compatible explicit override fixed it; locked `npm ci`, build and tests
  subsequently passed. Root tool versions and engine-strict policy are unchanged.
- Initial pnpm lock generation exited 1 with an internal error following a
  network timeout. Bounded retries with longer timeout succeeded; subsequent
  package-download timeouts are warnings on eventually successful installs.
- First architecture container: 3 failed, 139 passed, 1 deselected, 21 subtests,
  32.67s. Git worktree metadata was not mounted; a dependency traversal also
  raced Gateway installation. Second, with UID 1000 and read-only Git metadata:
  1 failed, 141 passed, 1 deselected, 21 subtests, 30.62s. The remaining failure
  identified the genuinely stale namespace inventory, regenerated above.
  No architecture assertion was removed or vendor traversal hidden.

### Docker And Final Checkpoint

Inspection found that the acceptance CLIs hardcoded old Gateway/Runtime images.
Explicit `--gateway-image`/`--runtime-image` options now reach both parity and
recovery configurations. Explicit `--fresh-only` selects one new project, retains
all original restart/request/store/fencing assertions, and records exclusions
instead of claiming backup/upgrade acceptance. The default two-project guard
and partial exit 2 are preserved. Regressions: 23 passed, 13 subtests, 3.82s;
four-file Ruff passed. No old image is silently presented as a patched build.
Final namespace/toolchain checks after inventory regeneration: 8 passed, 2.93s.

Operational sequencing deviation: this short harness pytest/Ruff pair overlapped
the single Runtime image build. No image builds overlapped and available RAM
remained above the limit; further validation waits until image builds finish.
The earlier install/architecture traversal race is separately recorded above.

The application source is `089127b`; subsequent `38c6702` changes only the
acceptance helpers/tests and operator documentation, not shipped app code.
All four patched Linux/amd64 tags were built sequentially, not simultaneously:

| Image `omertaos-<service>:p4-20261103` | Final immutable image ID | Build wall time / exit |
|---|---|---|
| control | `sha256:ce7942eebcd216c500ad3ff053cc60e6a9887439ceb096d8458bdfd819861c98` | 12.88s / 0 |
| runtime | `sha256:d2cbeb5288caacf706f1bd018b21a5560a0e18558292fd58d09b982820c92d05` | 1199.17s / 0 |
| gateway | `sha256:d1cee7b90a98a087c84caa6e7c29e8ef4e1faae6c82c0401592ef3b332e2186b` | 319.87s / 0 |
| console | `sha256:8130c7fb0cc465343177710f1d95c5595ff35059bc7a13c7bb1262f4c796eaaf` | first 1202.26s / 130; cached retry 101.82s / 0 |

Each exact build command is `docker build --progress plain --file
<service-directory>/Dockerfile --tag omertaos-<service>:p4-20261103 .`; Runtime
uses directory `runtime-daemon`. The timed runner's initial 1200s bound canceled
Console during export/unpack, after Next production build, type checking and
installer TypeScript compilation had all completed. Buildx independently
confirmed cancellation, not an application compile defect or OOM. The artifact
existed but was NOT treated as a successful build. A 2400s bounded retry reused
27 cached steps, including Next and TypeScript; it did not rerun compilation.
Memory monitoring and provenance were not disabled. Original failed metadata
remains in the first-attempt report, separate from the successful retry report.
Minimum sampled available RAM: 3238 MiB first build batch, 4460 MiB retry.
About 14 GiB disk remains; no image/volume/cache cleanup was performed.

Control reused its prior dependency-install layer. Direct Python requirements
are pinned but deployed transitive requirements are not hash-locked; the hashed
validation-image lock is NOT proof of an uncached reproducible Control install.
APT/APK/OS-image vulnerability and independent-host/multi-architecture acceptance
remain unverified. No all-green supply-chain or hermetic-build claim is made.

Read-only preflight reused the existing local-endpoint guard and verified all
configured data/worker endpoints point to their selected Compose services, with
no static external worker inventory and no preexisting fresh-project volumes.
The reused P3 harness ran explicitly with `--fresh-only` and all four image
arguments, using source `38c6702aea90328801978b4cd331a08153338503`. Its JSON retains
the P3 harness-family label, but scope is explicitly `fresh-install/restart only`:
exit **0**, `passed-in-scope`, 68 command/HTTP gates, no nonzero gate.
This is new bounded E2 evidence, not inherited acceptance of previous images.

| Patched-image live gate | Result |
|---|---|
| One-worker fresh project `omerta-p3-fresh-p4-20261103` | Ready in 94.41s; four explicitly selected image IDs above; loopback app ports |
| Authentication/canonical path | Real Console login; unauthenticated denial; Console -> Gateway -> Control -> Runtime echo and replay; all three schedule/start/success audit events match tenant/correlation/trace |
| Runtime restart | Signed claim executes once; duplicate rejected before and after normal restart while unexpired; identical persisted generation/expiry record; bounded probe 22.43s |
| Whole-stack restart | Normal stop 10.80s; startup/installer reapply 66.85s; no password reset, seed skip or migration bypass |
| Persistence | Same administrator and migration digest, original audit IDs, PostgreSQL/Mongo fixture, MinIO object and Qdrant payload retained |
| Replay after Control restart | Gateway Redis cache replay passed; separate Control gRPC replay failed closed with `RUNTIME_RESULT_REPLAY_UNAVAILABLE`; dispatch count stayed one; new authenticated request succeeded |
| Shutdown | Final normal stop 12.82s; no project container running; eleven containers and six named volumes retained; image-created anonymous store volumes also remain with their retained containers |
| Privacy | Nine distinct selected actual credential/key values absent in 202 retained lines across five application/install logs and in diff/five JSON artifacts; raw environment, keys, signed leases and logs were not persisted |
| Resources | Minimum available RAM 4018 MiB live, 4610 MiB post-run privacy check; about 14 GiB disk remains; other worker's six healthy `compose` services untouched |

Actual commands and durations are in ignored `artifacts/p4/image-builds.json`
(first attempt, with the Console failure preserved), `console-export-retry.json`,
`runtime-tests.json`, `live-preflight.json`, `fresh-recovery.json`,
`log-artifact-scan.json` and `bandit.json`. No encrypted restore or historical
upgrade was rerun in P4; the earlier bounded P3 results remain separately scoped.

Reproduce sequentially from this branch's checkpoint, without replacing old tags
or deleting any volume:

```bash
docker compose --project-directory . --env-file /home/omerta/projects/OMERTAOS/.env \
  -f deploy/docker/compose/quickstart.yml config --quiet
docker build --progress plain -f control/Dockerfile -t omertaos-control:p4-20261103 .
docker build --progress plain -f runtime-daemon/Dockerfile -t omertaos-runtime:p4-20261103 .
docker build --progress plain -f gateway/Dockerfile -t omertaos-gateway:p4-20261103 .
docker build --progress plain -f console/Dockerfile -t omertaos-console:p4-20261103 .
python3 scripts/validate_quickstart_recovery.py \
  --env-file /home/omerta/projects/OMERTAOS/.env \
  --console-image omertaos-console:p4-20261103 \
  --control-image omertaos-control:p4-20261103 \
  --runtime-image omertaos-runtime:p4-20261103 \
  --gateway-image omertaos-gateway:p4-20261103 \
  --fresh-project omerta-p3-fresh-p4-next --fresh-only --run \
  --output artifacts/p4/fresh-recovery-next.json
```

Use a new approved project suffix and image tag for subsequent repairs; the
recorded first-run project cannot be reused as a fresh installation. The command
list is operator-run: retain the harness memory monitor for long builds, bound
Console export at 2400s rather than the failed 1200s deadline, and stop workloads
below 1 GiB available RAM. All four source/lock states are committed; this is
not evidence of an independent-host or uncached Python/OS build.

Next P4 gates remain: reviewed application/schema major upgrades, working
vulnerability DB/Python audit access and hash-locked deployed Python dependencies,
and disposition of the five low Bandit subprocess findings. Existing CI already
skips B101/B105; this phase did not add exclusions or claim those omitted rules
passed. No P5 synchronization or production/native deployment is authorized.

Final Bandit rerun on the changed harness tree: exit 1, the same five low/high-
confidence findings, zero parse errors, 22.18s; 34 existing comment-parser warning
lines. This failed gate remains visible in `artifacts/p4/bandit.json`.

Final affected-helper regression, after all repairs: parity, restart recovery,
encrypted recovery, historical upgrade, namespace and JavaScript-toolchain test
files together passed **52 tests and 24 subtests**, zero fail/skip, exit 0,
9.10s, in the pinned read-only validation image with exact worktree Git metadata
mounted read-only and UID 1000. The namespace `--check` and `git diff --check`
also exited 0. The other 141 architecture checks passed in the earlier full
run; only affected checks were repeated, not every application suite/build.

Local checkpoint: `checkpoint/p4-compatible-repairs-2026-11-03`. Inspect its
complete file/commit inventory with `git diff --stat 3b1ef78
checkpoint/p4-compatible-repairs-2026-11-03` and `git log --oneline
3b1ef78..checkpoint/p4-compatible-repairs-2026-11-03`. No schema/public API or
encryption-format migration was introduced. Rollback is an operator-reviewed
source revert/selection of retained old immutable images, preserving volumes,
keys and private host modes; it was not executed and old vulnerable images must
not be treated as a certified fallback. Human review is required before merge.
No stack owned by another worker has been changed; no volume/image was removed,
and no system-wide package, native service, push or merge has been performed.

## P3 historical R6 upgrade and bounded phase closure - 2026-11-02

Baseline: `6f69b3b6e2de6be4b80ac2217e99d73dd49f05b6`; clean-tree checkpoint:
`checkpoint/p3-historical-upgrade-start-6f69b3b`; implementation and regressions:
`614b2ef`. Branch remains `Radin/omerta-env-namespace`. This continues the
approved P3 scope; P4 has NOT started and needs separate approval.

Read-only inspection found the actual retained `omertaos-r6-fixed` single-worker
dataset. All ten source containers were created/stopped on 2026-08-30 and have
not been restarted. Their immutable image IDs and timestamps were recorded,
not inferred from mutable tags. Source Control image:
`c6d6489508ccb9b991083210187e86a2f95996b79044c24fdd5ca2dfe735e8c3`;
source Console/install image:
`44cf82636036cea758b9566752387ccca242c0c121f8e70aa57dd403acc45ceb`.
The source was not reseeded or replaced with current-version fixtures.

Historical storage required more than copying the three named volumes: Redis
and Mongo configdb used anonymous volumes, while Qdrant data lived in the
stopped container writable layer at `/qdrant/storage`. All six storage sources
were signed/encrypted with the already authorized recovery key. Qdrant was
read through `docker cp` without starting it. Retained service environments
and target configuration were encrypted separately; values were never printed.

| Gate | Actual result |
|---|---|
| Source isolation | Source stopped; all five volume consumers belonged only to the stopped source project; no source service recreated or started |
| Backup/authentication | Six cold archives plus encrypted configuration, signed manifest, pinned signer and ciphertext checks, all passed |
| Clone integrity | All six decrypted inventories matched file contents, ownership and modes before store startup; archive paths/types validated |
| Genuine old schema/data | Eight existing tables; one User, one SystemState, two Prisma migration records, two Runtime node records, six task attempts and six scheduling decisions; Configuration/Proxy tables empty |
| Clone stores | Same immutable store images as source; PostgreSQL ready in 9.66s |
| Current installer | Normal forward Console migrations/bootstrap exited 0 in 16.68s with retained admin identity/password; no seed-skip or password-reset bypass |
| Current Control schema | Existing additive migration exited 0 in 10.79s; added `runtime_audit_events`, `runtime_resource_leases`, `runtime_execution_leases` |
| Pre-activation data preservation | Hash multisets over ALL old columns/rows remained present; no old column/row removed or changed; duplicate multiplicity checked |
| Upgraded stack | Current P2 image IDs, one Runtime; readiness exit 0 in 81.29s |
| Canonical path | Login with retained administrator credentials and actual Console -> Gateway -> Control -> Runtime echo, replay and audit-context assertions passed |
| Post-activation data | Original User/password hash, SystemState, migration records, attempts and decisions preserved; Runtime-node operational metadata intentionally allowed to advance with lifecycle heartbeats |
| Shutdown/source recheck | Normal stop exit 0 in 13.27s; eleven target containers and eight named target volumes retained; all five original volume inventories and the Qdrant writable-layer inventory unchanged |
| Key caches | Both dedicated GPG agents stopped after acceptance |
| Regression | Initial six new unit tests passed; final validation image: 42 passed, 21 subtests passed, 0 failed/skipped, 6.36s; Ruff and diff check exit 0 |
| Privacy | Report/new sources checked against eight selected distinct legacy credential/passphrase values; no matches; raw rows, secrets, cookies and lease tokens not persisted in reports |
| Resources | One test Runtime, sequential suites, no builds; minimum sampled available RAM 3481 MiB, about 24 GiB disk remaining |

`artifacts/p3/historical-upgrade.json` records 109 subprocess/HTTP gates and
status `passed`; the harness exited **0**, with no failed validation gate.
Read-only discovery first looked for an absent `.artifacts` directory and a
noncanonical lifecycle path, then located the actual files; these were not
substituted test results. No new application, schema or authentication repair
was necessary: the existing forward migration handled this retained dataset.

The target image IDs are the same Console `2462cb0a17ee...`, Control
`266e12e16720...`, Gateway `477ba0891a67...` and Runtime `c83cbcd5a9b5...`
recorded in full in P2. New fencing volumes were deliberately empty because
the old source predates durable fencing; the current provisioned lease key and
normal initializer were used. No unexpired historical fence was fabricated.
Extra Redis/Mongo-configdb mounts belong only to the isolated upgrade override;
the shipped canonical Compose topology was not changed.

Reproduce with a NEW backup path and clone project, the retained original R6
containers/volumes, provisioned env/lease key, existing protected recovery files
and recorded local images. The fixed historical source is never started:

```bash
stamp=$(date -u +%Y%m%d%H%M%S)
python3 scripts/validate_historical_quickstart_upgrade.py \
  --env-file /home/omerta/projects/OMERTAOS/.env \
  --key-dir "$HOME/.local/share/omerta-recovery/keys/p3-20261102a" \
  --backup-dir "$HOME/.local/share/omerta-recovery/backups/r6-upgrade-$stamp" \
  --project "omerta-p3-restore-$stamp" \
  --output "artifacts/p3/historical-upgrade-$stamp.json" --run
```

Actual execution used backup `r6-upgrade-20261102a`, target
`omerta-p3-restore-r6upgrade1`, report `artifacts/p3/historical-upgrade.json`.
Run the validation-image pytest command below with all four P3 test files,
including `tests/architecture/test_historical_quickstart_upgrade.py`.
No volume deletion, original-data mutation, push, merge, installation, systemd
change or image build occurred. Restore rollback retains the original cold
snapshot and separate clone; no database downgrade was attempted.

Together with the prior fresh-install/restart and encrypted current-state
restore runs, this closes P3's bounded local acceptance gates. It does not
prove arbitrary-version upgrade compatibility, rollback execution on old code,
old Console UI security, populated encrypted Configuration/Proxy migration,
portable logical/API restore, host-loss recovery, production isolation,
scalability, native/systemd acceptance or certification. Those boundaries were
not turned into successful gates. All original snapshots/backups remain intact.

## P3 encrypted cold backup and isolated restore - 2026-11-02

The user explicitly authorized creating and using the recovery key. Baseline:
`9622774544c3840ed34ce97e0052ecd66ae18c05`; checkpoint:
`checkpoint/p3-encrypted-backup-start-9622774`. Implementation: `3415359`;
restore-specific logical-export retention repair: `76a5477`. Branch remains
`Radin/omerta-env-namespace`. Nothing was pushed, merged, installed system-wide,
rebuilt or changed in the application schema/authentication/topology.

The dedicated local OpenPGP identity has an Ed25519 signing key and cv25519
encryption subkey, one-year expiry and a randomly generated passphrase protecting
the private key. Only public identity metadata is in reports. The key directory
is mode 0700; passphrase, public export and protected private export are 0600,
outside all Git worktrees. This is an authorized local acceptance key, not an
enterprise KMS, external trust certification or proof of off-host key custody.
The passphrase remains on the same protected host; losing the host can still
lose both backup and recovery material. Separate off-host custody is outstanding.
Both dedicated GPG agent caches were explicitly cleared after validation.

| Gate | Actual result |
|---|---|
| Source safety | All eleven `omerta-m4-validation` containers stopped; foreign/active volume consumers rejected; rendered env checked against retained application containers |
| Provenance | All retained service images pinned to their actual image IDs in the encrypted configuration; canonical Compose config exit 0 |
| Protected key recovery | Exported private key imported into a separate GNUPGHOME; deliberately wrong passphrase rejected, expected exit 2 |
| Signed encrypted backup | Six consistent cold volume archives plus Compose config, original env and paired lease key: nine signed/encrypted files, AES256, signed checksum manifest; no plaintext backup file created |
| Integrity before extraction | Manifest signer fingerprint pinned; ciphertext lengths/SHA-256 checked; all nine messages had valid signature, DECRYPTION_OKAY and GOODMDC; tampered ciphertext rejected, expected exit 1 |
| Archive safety | Absolute/traversal paths, links, special files and setuid/setgid entries rejected before writing restore volumes; read-only source mounts and bounded helper resources |
| Actual cold restore | Six new `omerta-p3-restore-20261102a_*` volumes; every file-content/mode/uid/gid inventory matched the signed source inventory before any store was started |
| Logical export sidecars | PostgreSQL custom dump and MongoDB archive exported from restored stores before application startup, signed/encrypted, decryption authenticated and a separate export manifest signed; logical restore itself NOT tested |
| Live restored services | Store readiness exit 0 in 35.47s; full stack readiness exit 0 in 82.59s; one Runtime |
| Restored historical data | Existing administrator, migrations, audit task and MongoDB fixture, corresponding MinIO object and Qdrant payload read successfully without reseeding |
| Canonical path | Actual administrator login, Console -> Gateway -> Control -> Runtime echo/replay and tenant/correlation/trace audit assertions passed |
| Source preservation | All six original cold inventories rechecked after acceptance and unchanged |
| Shutdown | Normal stop exit 0 in 12.52s; eleven restore containers stopped, six new volumes retained; source and other `compose-*` worker project untouched |
| Targeted regression | Final validation image: 36 passed, 21 subtests passed, 0 failed/skipped, 7.04s; strengthened replay-path regression separately passed once; Ruff and diff check exit 0 |
| Sanitized artifacts | Two encrypted-recovery JSON reports checked against selected configured source/lease values and the new passphrase; no matches; key files not tracked |
| Resource guard | Minimum sampled available RAM 3406 MiB; no 1 GiB cutoff triggered; about 25 GiB disk available before and after; no image build or concurrent test suite |

Local evidence: `artifacts/p3/encrypted-restore.json` (131 gates) and
`artifacts/p3/encrypted-postchecks.json` (endpoint guard, bounded archive checks,
agent-cache cleanup). The first report exits **2**, `partial-blocked`: the
historical older-release upgrade is still separate. Its off-host entry means
an untested boundary, not a newly imposed P3 requirement. The current harness
classifies that boundary as a limitation. Backup/restore is no longer blocked
by a missing key. The earlier restart-only report below is historical and is
not the current global backup status.

Failures and follow-up repairs were not bypassed:

- Initial host unit run: one of 32 tests failed because its assertion matched
  the word `stderr` inside retained command metadata rather than leaked output;
  Ruff also found an unused import. The fixture now supplies a synthetic value
  through the child environment and asserts that value is absent from reports.
- First validation-image run: 33 passed, one failed because permission-denied
  path inspection raised raw PermissionError. The guard now rejects workspace
  paths up front and turns unreadable-path errors into a sanitized fail-closed
  rejection; permissions were not opened and the test was not skipped.
- Streaming archive validation initially took 154.38s for MongoDB and 160.85s
  for Qdrant. Explicit 1 MiB member reads retained all safety assertions; targeted
  checks of the same authenticated archives then passed in 9.38s and 12.13s.
- Replay review found fixed logical-export names would collide on a second
  restore. New runs place exports under `exports-<restore-project>/` without
  overwriting previous exports. The first run's sidecars remain at backup root.
- Two optional Docker observer commands raced with a normally exiting helper
  and reported 'No such container'. The authoritative pipeline completed with
  exits [0, 0]; no workload was restarted for that observer failure.

The immutable backup and key files are local, outside Git:

```text
$HOME/.local/share/omerta-recovery/keys/p3-20261102a/recovery-public.asc
$HOME/.local/share/omerta-recovery/keys/p3-20261102a/recovery-private.asc
$HOME/.local/share/omerta-recovery/keys/p3-20261102a/passphrase
$HOME/.local/share/omerta-recovery/backups/p3-20261102a/manifest.json
```

Reproduce isolated restore acceptance from that existing backup with a NEW
project suffix. It requires the retained stopped source project for the safety
and source-unchanged checks, matching ignored env, existing recovery files and
the pinned local images. It is a scoped acceptance harness, not a source-free
full-host disaster-recovery installer. Do not add `--create-key` for this mode:

```bash
python3 scripts/quickstart_encrypted_recovery.py \
  --env-file /home/omerta/projects/OMERTAOS/.env \
  --key-dir "$HOME/.local/share/omerta-recovery/keys/p3-20261102a" \
  --backup-dir "$HOME/.local/share/omerta-recovery/backups/p3-20261102a" \
  --restore-project "omerta-p3-restore-$(date -u +%Y%m%d%H%M%S)" \
  --output "artifacts/p3/restore-$(date -u +%Y%m%d%H%M%S).json" \
  --existing-backup --run
```

The original execution used the same directories, `--restore-project
omerta-p3-restore-20261102a`, `--output artifacts/p3/encrypted-restore.json`
and `--create-key --run` instead of `--existing-backup`. New backup/key paths
must not already exist. Existing backups/volumes are never deleted or replaced.
Use the validation-image command in the prior P3 section with
`tests/architecture/test_encrypted_quickstart_recovery.py` added for the tests.

This is E2 same-host, same-image cold recovery. MinIO/Qdrant are restored from
their complete cold volume data, not portable S3 exports or Qdrant API snapshots.
Redis queue/cache disaster recovery, separate logical restore, historical
upgrade compatibility, power-loss tests, native/systemd, production security,
scalability and off-host recovery remain unproven. Removing this optional
harness needs no schema/image rollback; retain all generated recovery evidence,
keys, stopped containers and volumes. P4 has not started.

## P3 partial fresh-install and restart recovery - 2026-11-02

User authorized the next phase after P2. Branch: `Radin/omerta-env-namespace`;
baseline: `849d3d0279d6b477c16da63c5cb25d5f966e8c1c`; clean-tree checkpoint:
`checkpoint/p3-start-849d3d0`; acceptance harness/tests: `9769808`.
No application source, schema, authentication rule or image was changed.
The four application images recorded in the P2 section below were reused without builds.

Host: Ubuntu 22.04.5 LTS, Linux 6.8.0-138-generic x86_64, Python 3.10.12,
Docker Compose 5.6.0, 7840 MiB total RAM. Disk went from 26 to 25 GiB available
while retaining all attempts. Test suites and stacks ran sequentially, with
one test Runtime at a time. Minimum sampled available RAM was 3669 MiB in the
final run; the 1 GiB cutoff did not trigger.

| Gate | Actual result and boundary |
|---|---|
| Targeted locked Python validation image | `21 passed, 10 subtests passed`, 0 failed/skipped, 3.66s; exit 0 |
| Targeted Ruff | Exit 0 for the two new files |
| Compose rendering | Canonical render and both isolated configurations exited 0 before startup |
| Fresh install | New `omerta-p3-fresh-retry2` project/network and six previously absent named volumes; installer/bootstrap and actual ADMIN login passed; initial readiness 111.04s |
| Existing-data reapply | Existing `omerta-m4-validation` data, same current images, initial readiness 90.40s; NOT an older-release upgrade test |
| Canonical path | Console -> Gateway -> Control -> Runtime authenticated echo, immediate replay and tenant/correlation/trace audit checks passed before and after restart in both projects |
| Runtime fencing | A genuinely signed claim executed once; duplicate metadata was rejected before and after a normal Runtime restart. The exact hashed generation/expiry record survived unchanged and the original lease was still unexpired after the final RPC. Full bounded probes took 29.73s and 31.67s, not performance benchmarks |
| PostgreSQL/bootstrap | Migration-name/checksum digest, one administrator row and all three original task audit event IDs survived normal whole-stack stop/start and installer reapply |
| MongoDB, MinIO, Qdrant | A distinct synthetic document, signed-S3 object read and vector payload read passed before/after normal whole-stack stop/start in both projects |
| Gateway replay after restart | Same task ID and successful result returned from the Redis-backed idempotency cache |
| Independent Control replay after restart | Loopback Control gRPC probe replayed the original task identity/context and returned `RUNTIME_RESULT_REPLAY_UNAVAILABLE`; historical audit remained and `runtime.dispatch.start` count stayed exactly one |
| New work after restart | New authenticated Console task executed successfully through Runtime in both projects |
| Selected credential artifact scan | Three JSON reports checked against five distinct selected configured sensitive values, including the lease-file value; no literal/JSON-escaped matches |
| Shutdown | Every attempted test project stopped normally; 44 containers retained, none running; 24 named volumes retained. Qdrant exited 143 on requested SIGTERM; all other retained test containers exited 0 |
| Other workers | Existing `compose-*` services remained running/healthy; no command changed that project. Volume-consumer guards reject active/foreign consumers before starting either selected test project |
| Encrypted backup and independent restore | BLOCKED: no operator-approved encryption recipient/public key was available; no sensitive unencrypted export or new operational secret was created |
| Older-release upgrade on restored clone | BLOCKED pending a verified backup/restore and a genuine older-release baseline; reapplying current images is not a substitute |
| Durable Control result recovery | UNAVAILABLE by current implementation; Redis cache replay is not proof of durable Control result storage |
| Redis durable queue recovery | SKIPPED: Quickstart declares no named Redis volume. Cache replay across normal container stop/start is a separate observation, not disaster recovery |
| Native/systemd, broader P4 security review, benchmarks | Not run; outside this authorized phase |

Two failed harness attempts were preserved, not counted as successful acceptance:

1. `artifacts/p3/acceptance.json`: initial internal-error-text expectation was
   incorrect. Runtime intentionally maps lease failures to the generic public
   `FAILED_PRECONDITION` diagnostic. Inspection of `server.rs::map_lease_error`
   confirmed the cause. The repaired probe retains the generic public response,
   verifies the exact persisted claim, reuses metadata that actually executed,
   and rejects expiry as fencing evidence. No Runtime diagnostic was weakened.
2. `artifacts/p3/acceptance-retry1.json`: the test incorrectly expected a
   Console-originated replay to reach restarted Control. Gateway's Redis cache
   returned the previously successful result. The repaired harness tests cache
   replay and Control's fail-closed replay separately, without clearing Redis,
   changing task identity or bypassing an application security control.

The final `artifacts/p3/acceptance-retry2.json` records 135 subprocess/HTTP gates
and both project results as passed. The overall harness deliberately exits **2**
with status `partial-blocked`, because backup/restore and historical upgrade
are NOT complete. Do not mask that exit as full P3 success. Initial unit checks
reported 19, then 20, then 21 passing tests as the regression cases were added;
the final validation-image pytest run above covers the committed code.
Raw application logs, cookies, rendered secrets and signed lease tokens were
not persisted in these reports. This is not an exhaustive log/secret audit.

Targeted test reproduction (no service startup, no network/dependency install):

```bash
validation=(docker run --rm --network none --read-only --memory 1024m --cpus 2
  --tmpfs /tmp:rw,nosuid,nodev,size=128m
  --mount "type=bind,src=$PWD,dst=/workspace,readonly"
  --env OMERTA_CONTROL_DATA_DIR=/tmp/omerta-p3 --workdir /workspace
  omertaos-python-validation:local)
"${validation[@]}" python -m pytest tests/architecture/test_quickstart_recovery.py \
  tests/architecture/test_quickstart_environment_parity.py -q -p no:cacheprovider
"${validation[@]}" ruff check scripts/validate_quickstart_recovery.py \
  tests/architecture/test_quickstart_recovery.py
```

Reproduce from the repository root with the existing source volumes, provisioned
env/lease key and recorded local image tags. A unique fresh project is mandatory
after a prior attempt; volumes are deliberately never deleted or reused as a
fresh-install substitute:

```bash
python3 scripts/validate_quickstart_recovery.py \
  --env-file /home/omerta/projects/OMERTAOS/.env \
  --console-image omertaos-console:m413-1ac6890 \
  --control-image omertaos-control:m413-9689b8a \
  --fresh-project "omerta-p3-fresh-$(date -u +%Y%m%d%H%M%S)" \
  --output "artifacts/p3/reproduction-$(date -u +%Y%m%d%H%M%S).json" --run
```

This is constrained E2 restart evidence, not backup acceptance, a completed
historical upgrade, power-loss recovery, successful Linux isolation,
multi-Control consistency, scalability, production readiness or certification.
The legacy Docker backup/restore scripts do not cover the named stores or
paired Runtime key/state and must not be used to certify P3 recovery.
No schema migration or image rollout needs rollback for this harness-only
change. Retain the synthetic fixtures, stopped containers and volumes; removing
the optional acceptance tool does not require restoring or deleting store data.

## P2 / M4.1.3 Actual process environment parity - 2026-11-02

Branch: `Radin/omerta-env-namespace`; baseline: `1ac6890`;
checkpoint: `checkpoint/m413-start-1ac6890`. User explicitly approved P2.
Repair: `9689b8a`; harness and single-worker Console build: `d02a54b`.
The image build/test worktrees contained those subsequently committed changes.

The harness renders canonical Compose in memory, decodes Compose's escaped
strings, and feeds each re-encoded variant through stdin. No rendered env,
cookie jar, password or token is written to the report. It verifies actual
container environments, not just host-variable interpolation. The higher-priority
Console `GATEWAY_URL`/`DOCKER` overrides are omitted in both test variants so the
product readers are exercised. Lease key/file and profile settings without a
supported alias remain canonical. App ports bind to loopback; the existing
isolated project, network and six volume identities are preserved.

| Gate | Actual result |
|---|---|
| Environment-file preflight | No conflicts; 34 deprecated host settings, values withheld |
| Harness unit checks | Initial 8 passed; after the escaping repair and RAM/timeout regression additions, 11 passed in 2.161s |
| Actual Compose config round-trip | Exit 0; health command and application environment values preserved |
| Affected Control suites | 40 passed, 0 failed/skipped, 5 warnings, 18.72s |
| Targeted Ruff | Exit 0 for harness, tests and modified Control files |
| Console image build | Exit 0; 1205.64s; one build worker; built once |
| Repaired Control image build | Exit 0; 14.81s; built once |
| Variant config rendering | Both exit 0 |
| Conflict preflight | 45 configured canonical/alias pairs rejected with key names only |
| Actual Runtime conflict probe | Expected exit 1; conflicting bind aliases rejected without probe values in diagnostic |
| Final canonical readiness | Exit 0; 85.65s |
| Final legacy readiness | Exit 0; 92.81s |
| Actual process environments | 52 configured service/key instances, 44 distinct canonical names; one Runtime only |
| Console, Gateway, Control HTTP health and container health | Passed for both variants |
| Console API without session | HTTP 401 in both variants |
| Actual credentials login/session | HTTP 200; ADMIN session established in both variants |
| Console -> Gateway -> Control -> Runtime echo | HTTP 200, status OK, route runtime, exit 0 and exact deterministic output in both variants |
| Same-request replay | Same task ID and outcome in both variants |
| Tenant/correlation/trace | Three schedule/start/success audit events in each variant matched all submitted context |
| Observed deprecations | Canonical: 0; legacy: 28 distinct aliases; configured does not mean every key was behaviorally consumed |
| Selected credential log scan | Passed for configured sensitive application fields and lease-file key; raw logs withheld |
| Sanitized artifact scan | Six JSON files checked against seven selected configured credential fields; no matches |
| Normal stop and volume checks | Both stops exit 0; final project running count 0; six existing volumes retained |

Failures were retained and repaired rather than bypassed:

- Attempt 1: canonical startup exited 1 after 178.34s because the new harness
  double-escaped already escaped Compose config strings. Qdrant's health command
  contained `$$status` in the container instead of `$status`. An independent
  synthetic Compose round-trip reproduced the representation behavior. The
  harness now decodes once before transforming and encodes once on stdin;
  the original readiness check remains intact.
- Attempt 2: login, task execution and replay passed, but the strict all-events
  context assertion failed. A separate read-only PostgreSQL query confirmed
  only `runtime.schedule.request_id` was missing; start/success retained it.
  The internal optional SchedulingRequest field now carries correlation into
  the existing audit column from dispatch and the administrative schedule route.
  No database/schema migration, public request payload, auth or execution
  boundary changed; historical events were not rewritten. The strict assertion
  was retained. Only Control needed an additional rebuild.
- An optional build-history log observer exited 1 without usable progress
  detail. The original live exec handle was observed until the build exited 0;
  no build was restarted because of an observation failure.

All builds and test suites ran sequentially. Minimum sampled available RAM was
2526 MiB across builds/acceptance, and 3769 MiB in the successful final acceptance.
The 1 GiB guard never triggered. Timeout and low-memory refusal are covered by
unit tests, including termination of a synthetic timed-out child. Unit warnings
were existing Starlette/httpx, anyio, FastAPI startup-event deprecations and one
expected legacy admin-token warning. The previously noted Qdrant Compose-label
warning was not repaired by deleting or replacing its volume.
Qdrant exited 143 on requested shutdown; the other final project containers
exited 0. This was not reported as a failed readiness or isolation gate.

Local sanitized artifacts, ignored by Git:
`artifacts/m413/acceptance.json` (failed attempt 1),
`acceptance-retry1.json` (failed attempt 2), `build-control.json`, and
`acceptance-retry2.json` (passed, 55 recorded subprocess/HTTP gates).

| Service | Local image tag | SHA-256 image ID |
|---|---|---|
| Console/install | `omertaos-console:m413-1ac6890` | `2462cb0a17ee2474a393afa8845d07330158a4ef151a6a497ee053ecf88e4702` |
| Control | `omertaos-control:m413-9689b8a` | `266e12e16720e074728a42d3574671dc0c510ade3714da322ef8aa03379c8418` |
| Gateway, reused | `omertaos-gateway:m412-62fdfed` | `477ba0891a67a301aa91bb03431219bdc07b0e3b9e46e247c90c888c844d8502` |
| Runtime, reused | `omertaos-runtime:m412-62fdfed` | `c83cbcd5a9b5126614bc20e446b01777c0032735941875b2afb87b70245e066c` |

Reproduction from the repository root requires the existing isolated volumes,
previous Gateway/Runtime images, provisioned ignored env file and lease secret.
It refuses to take over an already running isolated project. Rebuilds are
optional if the recorded images already exist. The guarded Control build is:

```bash
python3 - <<'PY'
from scripts.validate_quickstart_environment_parity import Runner
Runner().run("Control image build", [
    "docker", "build", "--progress=plain", "-f", "control/Dockerfile",
    "-t", "omertaos-control:m413-9689b8a", ".",
], timeout=900)
PY
python3 -m unittest discover -s tests/architecture -p test_quickstart_environment_parity.py -v
python3 scripts/validate_quickstart_environment_parity.py \
  --env-file /home/omerta/projects/OMERTAOS/.env \
  --console-image omertaos-console:m413-1ac6890 \
  --control-image omertaos-control:m413-9689b8a \
  --output artifacts/m413/reproduction.json --run
# Add --build-console to the last command only when rebuilding that image.
```

The affected Control suite ran in the existing locked validation image:

```bash
docker run --rm --network none --read-only --memory 1536m --cpus 2 \
  --tmpfs /tmp:rw,nosuid,nodev,size=256m \
  --mount type=bind,src="$PWD",dst=/workspace,readonly \
  --env OMERTA_CONTROL_DATA_DIR=/tmp/omerta-p2 --workdir /workspace \
  omertaos-python-validation:local python -m pytest \
  tests/control/test_runtime_dispatch.py tests/control/test_runtime_scheduler.py \
  tests/control/test_runtime_node_routes.py tests/control/test_runtime_audit.py \
  tests/control/test_transport_adapters.py -q -p no:cacheprovider
```

This is E2 constrained process-environment parity, not exhaustive alias
semantics or live conflict testing of every language/key. The 45-pair gate is
preflight validation; the actual binary conflict probe covers Runtime bind.
Existing Quickstart development auth/defaults were not changed, so this is not
production security acceptance. No successful Linux sandbox isolation,
scalability, or bit-identical build claim is made. Full fresh-install/upgrade
clone testing, backup/restore, independent restart fencing, native/systemd,
vulnerability scanning and benchmarks were not run in P2. Unaffected app test
suites were not repeated. Previous image tags remain available, but rollback
would restore their known defects and requires review; no volume or schema
rollback is required for this optional audit field. Nothing was pushed or merged.

## P1 Console login handoff validation - 2026-11-02

Branch: `Radin/omerta-env-namespace`; baseline: `2e8b914`;
checkpoint: `checkpoint/p1-start-2e8b914`; source commit: `dae20bf`.
P1 was authorized by the user's implementation request. Later phases remain
separately gated. See the [execution progress ledger](execution-progress-fa.md).

Transferred four remaining Console files from the other checkout without
altering that checkout. Login no longer reads the administrator password or
passes it to the client form. The identifier label agrees with existing auth
handling, and the transferred display strings use `OMERTA OS`.

| Gate | Actual result |
|---|---|
| Locked pnpm install | Exit 0; 30.0s including wrapper; Node 22.23.2, npm 10.9.8, Corepack pnpm 11.13.1 |
| Console unit suite, one worker | Exit 0; 15 files, 36 passed, 0 failed/skipped; runner 44.43s, wrapper 48.1s |
| Four new Login regression scenarios | Passed within the same suite: password absent from client props, missing email, incomplete setup redirect, authenticated-session redirect |
| Direct Prisma generation | Exit 0; 16.0s; placeholder DB URL only, no migration or checksum-ignore setting |
| Initial production build | Exit 1; 10.0s; root-owned generated `.next/trace` caused EACCES |
| Production build after generated-output ownership repair | Exit 0; 430.8s; one build worker and 1536 MiB V8 heap limit |
| Diff/dependency review | Whitespace check passed; manifests and lockfiles unchanged |

Commands, from the repository root:

```bash
corepack pnpm --dir console install --frozen-lockfile --network-concurrency=4 --child-concurrency=2 --reporter=append-only
corepack pnpm --dir console exec vitest run --config vitest.config.mts --maxWorkers=1
export DATABASE_URL='postgresql://placeholder:placeholder@127.0.0.1:1/placeholder?schema=public'
export NODE_OPTIONS='--max-old-space-size=1536'
export NEXT_TELEMETRY_DISABLED=1
corepack pnpm --dir console exec prisma generate
CIRCLE_NODE_TOTAL=2 corepack pnpm --dir console build
git diff --check
```

The commands ran sequentially under a 1 GiB available-memory stop guard with
timeouts; minimum sampled RAM was 1983 MiB during the successful build.
`CIRCLE_NODE_TOTAL=2` selects one build worker in this pinned Next version;
it does not bypass compilation, linting or type checking. Existing root-owned
`node_modules` (empty) and `.next` generated artifacts were narrowly reassigned
to the checkout user, UID/GID 1000, with no broad permission change or cleanup.
The successful unit suite was run once; only the failed build was retried.

Warnings: stale baseline-browser-mapping data in unit tests, and Next's initial
workspace-root warning about an external home-directory lockfile. The global
pnpm remains 9.15.9; all recorded commands used the pinned Corepack version.
The earlier missing-Vitest blocker is resolved. These are E1 source/build
checks, not new live Docker or authenticated-session acceptance. Existing
Console images still contain the earlier code and require a new tagged build
before P2 live acceptance. No persistent service was started; no volumes, credentials, auth
protocols or APIs changed. Nothing from P1 was pushed or merged.

## M4.1.2 Pinned images and bounded live acceptance - 2026-09-06

Branch: `Radin/omerta-env-namespace`; baseline: `62fdfed`;
checkpoint: `checkpoint/m4-1-2-start-62fdfed`.
Builds used this baseline plus the digest-pin working-tree changes recorded
with this report. No source changes were made during the builds.

Seven upstream Quickstart references and all base-image references in the four
application Dockerfiles are pinned to SHA-256 digests. Pins preserve locally
tested images; the optional Xray index digest was obtained from the registry.
Xray was not started. `.secrets-out/` is now excluded from Docker build context;
earlier context exclusion was incomplete, but this is not evidence that a key
was copied into an application image. Existing caches were not purged.

| Gate | Actual result |
|---|---|
| Focused image/toolchain and Quickstart contracts | 17 passed, exit 0, 0.54s |
| Compose rendering, including isolated image override | Exit 0; no environment values printed |
| Control build | Exit 0; BuildKit duration 15.2s |
| Runtime locked release build | Exit 0; BuildKit duration 15m 26s; one Cargo job |
| Gateway locked build | Exit 0; BuildKit duration 4m 29s |
| Console frozen-lockfile build | Exit 0; BuildKit duration 21m 41s; 21 pages and bootstrap compiler completed |
| Isolated stack readiness | Exit 0, 123.2s; Compose parallel limit 1 and one Runtime |
| Running Gateway package verification | Exit 0, 0.8s; Fastify 5.12.3, fast-uri 4.1.4 |
| Mongo ping | Exit 0, 8.6s |
| Qdrant/MinIO readiness and existing Qdrant fixture | Exit 0, 3.3s; prior fixture retained across container recreation |
| Single final native-script Quickstart smoke | Exit 0, 21.5s; 13 checks passed |
| Normal shutdown | Exit 0; all 11 containers stopped and six volumes retained |

The final smoke covers PostgreSQL, Redis, installer completion, Runtime health
and automatic registration, Control, Gateway dependencies, Console and the
Console -> Gateway -> Control health chain. It is not an authenticated task
execution test; full task/parity/restore acceptance remains in later subphases.
No repeated application test suites were run after the user's batching request.
The final acceptance ran once. No second Runtime, benchmark, live systemd test,
image vulnerability scan or optional proxy acceptance was performed.

Resource guards polled available RAM during the Console build and acceptance.
No guard triggered; minimum sampled RAM during live acceptance was 2865 MiB.
Qdrant exited 143 on requested shutdown; other project containers exited 0.

Warnings/negative evidence: Cargo index timeouts recovered without changing
the lockfile or TLS controls; npm emitted existing deprecated-tool warnings;
Console reported stale Browserslist data. The manually provisioned Qdrant volume
still lacks Compose labels. One diagnostic image-inspection command contained a
mistyped Redis digest and exited 1; the checked-in pin was correct and live
startup passed. Digest pins do not freeze apt/apk or all transitive Python
resolution, and no bit-for-bit or production-security claim is made.

Local image IDs (not published registry artifacts):

| Tag | SHA-256 image ID |
|---|---|
| `omertaos-control:m412-62fdfed` | `e40d4d92021723de368fa4544c172e3b1148ab98505c5c7b7d72b2315663c36c` |
| `omertaos-runtime:m412-62fdfed` | `c83cbcd5a9b5126614bc20e446b01777c0032735941875b2afb87b70245e066c` |
| `omertaos-gateway:m412-62fdfed` | `477ba0891a67a301aa91bb03431219bdc07b0e3b9e46e247c90c888c844d8502` |
| `omertaos-console:m412-62fdfed` | `4bb2d109a3f3da333f1dbdf1cc68f8064d18c9aa4a66d1dcab46df9a5b97eaad` |

Build commands, run sequentially from the repository root:

```bash
docker build --progress=plain -f control/Dockerfile -t omertaos-control:m412-62fdfed .
docker build --progress=plain -f runtime-daemon/Dockerfile -t omertaos-runtime:m412-62fdfed .
docker build --progress=plain -f gateway/Dockerfile -t omertaos-gateway:m412-62fdfed .
docker build --progress=plain -f console/Dockerfile -t omertaos-console:m412-62fdfed .
```

The local override `/tmp/omerta-m412-62fdfed.compose.yml` contains:

```yaml
services:
  control:
    image: omertaos-control:m412-62fdfed
  gateway:
    image: omertaos-gateway:m412-62fdfed
```

For this isolated stack, use the environment and Compose invocation below.
The existing ignored environment file and Runtime secret must be provisioned.
Start only with at least 1 GiB available RAM, monitor during execution, and
stop this project if RAM falls below that threshold.

```bash
export COMPOSE_PARALLEL_LIMIT=1
export COMPOSE_ENV_FILES=/home/omerta/projects/OMERTAOS/.env
export OMERTA_DOCKER_NETWORK=omerta-m4-validation-net
export OMERTA_CONSOLE_HOST_PORT=23000 OMERTA_GATEWAY_HOST_PORT=28080
export OMERTA_CONTROL_HOST_PORT=28000 OMERTA_RUNTIME_HOST_PORT=25051
export OMERTA_RUNTIME_IMAGE=omertaos-runtime:m412-62fdfed
export OMERTA_CONSOLE_IMAGE=omertaos-console:m412-62fdfed
export OMERTA_CORS_ORIGINS=http://localhost:23000 NEXTAUTH_URL=http://localhost:23000
export NEXT_PUBLIC_GATEWAY_URL=http://localhost:28080
compose=(docker compose --project-directory "$PWD" --project-name omerta-m4-validation
  -f deploy/docker/compose/quickstart.yml -f /tmp/omerta-m412-62fdfed.compose.yml)
"${compose[@]}" config --quiet
"${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 120
bash deploy/native/scripts/smoke-test.sh --mode quickstart --project-name omerta-m4-validation --timeout 8
"${compose[@]}" stop --timeout 30
```

Earlier images remain available for rollback. Keep the same project volumes
when selecting previous application image tags. No volume deletion, push,
merge, reset-credit redemption or production deployment occurred.

## M4.1.1 Gateway dependency remediation - 2026-09-06

Baseline/checkpoint: `1d1ed05`, `checkpoint/m4-1-1-start-1d1ed05`.
Branch: `Radin/omerta-env-namespace`.

Fastify's manifest minimum is now 5.12.1; the npm-generated lock resolves
5.12.3, with fast-uri 4.1.4 and all three nested 3.x copies at 3.1.7.
Only these dependency entries changed. Relevant upstream advisories include
[primitive coercion](https://github.com/advisories/GHSA-w2qp-rph6-63g4),
[forwarded-header spoofing](https://github.com/advisories/GHSA-3m5p-2c4r-xxw2),
[repeated hostname decoding](https://github.com/advisories/GHSA-fph4-wmhf-6fwf)
and [scheme normalization](https://github.com/advisories/GHSA-jqff-g426-hqxp).
These identify dependency defects, not proof of application exploitability.

The primitive-schema probe independently reproduced Fastify 5.11.3 handing
the string `"10"` to a handler after integer validation (exit 1). The added
regression verifies the numeric handler value and rejection of an out-of-range
input on the patched dependency.

| Command/gate | Result |
|---|---|
| `npm update fastify fast-uri --prefix gateway --package-lock-only` | Exit 0; targeted lock update, zero reported vulnerabilities |
| `npm ci --prefix gateway` | Exit 0; 408 packages installed in approximately 3 minutes |
| `node gateway/node_modules/vitest/vitest.mjs run tests/gateway/schemaValidation.spec.ts` | Exit 0; 1 passed, 4.32s |
| `npm run build --prefix gateway` | Exit 0 |
| `npm test --prefix gateway` | Exit 0; 26 passed in 9 files, 12.14s |
| `npm audit --prefix gateway --json` | Exit 0; total vulnerabilities 0, 432 dependencies reported |
| Container pytest `tests/architecture/test_javascript_toolchain.py -q -p no:cacheprovider` | Exit 0; 3 passed, 0.36s |
| `git diff --check` | Exit 0 |

Commands used Node 22.23.2 and npm 10.9.8. The host's official Linux x64 Node
archive was downloaded from nodejs.org and checked against its published
SHA-256 (`d60acfe00a2932254bb0ad20e01b0d74397a0875595de719654b214f4b03f307`).
It is installed under `~/.local/opt/node-v22.23.2-linux-x64`; new Bash login
shells report the expected Node/npm versions. Existing process environments
need a new shell or an explicit PATH prefix. The system Node was retained.
The prior Bash configuration is backed up at
`~/.cache/omerta-toolchain/bashrc.before-node-22.23.2`.

Earlier failures: Docker audit attempts were interrupted after stalled network
requests (137); host audit returned ETIMEDOUT (1) and metadata fetch timed out
(124). Retrying the official registry subsequently succeeded. The old local
Vitest installation lacked a native binding (1), resolved by locked `npm ci`.
The first host build could not write root-owned generated `gateway/dist` (2);
ownership of that generated directory alone was corrected to the workspace
user before the successful build. Deprecated ESLint/inflight/glob and related
tooling warnings remain; zero audit findings is not security certification.

No application image was rebuilt and no persistent service was started in this
subphase. The previous Gateway image still contains the previous dependencies;
image rebuild and live acceptance remain pending. Rollback is a reviewed revert
of the manifest, lock and regression change, followed by locked installation;
it would restore the known vulnerable dependencies. No push or merge occurred.

## M4 isolated Docker acceptance - 2026-09-05

Branch: `Radin/omerta-env-namespace`. Checkpoint: `6469f44`
(`checkpoint/omerta-m4-start-6469f44`). Repairs: `073e63c`, `66eb610`,
`e3a4b76`. This is local, single-worker acceptance, not a scalability,
Linux sandbox, native systemd, or production-readiness claim.

The isolated project was `omerta-m4-validation`, with network
`omerta-m4-validation-net` and Console/Gateway/Control/Runtime host ports
23000/28080/28000/25051. Other Compose projects were outside this work.

| Gate | Actual result | Limits |
|---|---|---|
| Sequential application image builds | Control, Runtime, Gateway and Console passed | Gateway install reported one moderate and one high vulnerability; unresolved |
| Console bootstrap compilation | Repaired inherited TypeScript option; rebuilt successfully | Initial build failed with TS5096 |
| Console health aggregation | Repaired internal self-probe URL and degraded aggregation; full Console suite: 32 passed | Test harness required test-mode React and dependencies under `/app` |
| Final architecture suite | 99 passed, 1 deselected; exit 0, 20.92s | Structure completion gate explicitly excluded; not passed |
| Final native contract suite | 75 passed; exit 0, 6.02s | Container-based tests, not live systemd acceptance |
| Focused Quickstart tests | 13 passed; exit 0, 0.55s | Static contract checks supplemented by live checks below |
| Compose config | Exit 0 | Rendering alone is not live acceptance |
| Qdrant readiness | Docker healthy; direct `/readyz` HTTP 200 | Official image has Bash but no curl; probe uses Bash TCP and requires HTTP 200 |
| Qdrant persistence | Fixture point retrieved after forced container recreation | Named volume preserved; fixture retained in isolated test data |
| Final Quickstart smoke | Exit 0; PostgreSQL, Redis, installer, Runtime, registration, Control, Gateway, Console and canonical health chain passed | Read-only smoke does not itself execute a task |
| Authenticated task flow, earlier in M4 | Console -> Gateway -> Control -> Runtime deterministic echo and idempotent replay passed; persisted tenant, scheduling and audit evidence inspected | One Runtime, deterministic echo only |
| Earlier restart checks | PostgreSQL records, Runtime fencing fingerprint and Control registration survived normal restarts; installer rerun retained counts | No crash or host reboot claim |
| Backup pipeline | Nonempty PostgreSQL custom dump and archive listing verified | No isolated restore performed; not full backup acceptance |

Failed attempts remain part of the evidence: the first Console build failed;
host Python lacked pytest; an early read-only container lacked Git metadata;
Console test harness attempts encountered write permissions, module resolution
and production React `act` errors before a corrected full run passed. An early
Runtime metadata assertion expected the wrong GID and was independently rerun
against actual protected metadata. The first Qdrant data copy could not access
the container writable layer via `--volumes-from`; copying the stopped
container's data with `docker cp` succeeded. Its first healthcheck failed
because curl was absent. The final smoke first exited 1 because the environment
file was omitted, then passed with `COMPOSE_ENV_FILES` explicitly supplied.
These failures were not counted as successful gates.

Open limitations: the manually provisioned Qdrant volume has no Compose labels
and causes a warning; it was preserved. Redis warned about host overcommit;
no sysctl was changed. Upstream images still use mutable tags, including
Qdrant `latest`, so exact image reproduction requires digest pinning in a
separate reviewed change. Full old-only versus new-only live-stack parity,
isolated restore, native startup/reboot acceptance and dependency vulnerability
remediation remain open. Do not remove legacy aliases on this evidence alone.

Reproduce focused checks from the repository root (the local ignored environment
file and secret must already be provisioned; never paste their values):

```bash
docker compose --project-directory "$PWD" --project-name omerta-m4-validation \
  --env-file /home/omerta/projects/OMERTAOS/.env \
  -f deploy/docker/compose/quickstart.yml config --quiet
docker run --rm --network none \
  --mount type=bind,src="$PWD",dst=/workspace,readonly --workdir /workspace \
  omertaos-python-validation:m3 python -m pytest \
  tests/architecture/test_quickstart_runtime.py -q -p no:cacheprovider
docker run --rm --network none \
  --mount type=bind,src="$PWD",dst=/workspace,readonly --workdir /workspace \
  omertaos-python-validation:m3 python -m pytest tests/native -q -p no:cacheprovider
# Requires the isolated stack to be running first:
COMPOSE_ENV_FILES=/home/omerta/projects/OMERTAOS/.env \
OMERTA_CONSOLE_HOST_PORT=23000 OMERTA_GATEWAY_HOST_PORT=28080 \
OMERTA_CONTROL_HOST_PORT=28000 bash deploy/native/scripts/smoke-test.sh \
  --mode quickstart --project-name omerta-m4-validation --timeout 8
```

Do not revert the Qdrant volume mount on an existing populated deployment:
rolling back the health probe must preserve `qdrant-data:/qdrant/storage`.
No volume deletion, push, merge, native installation or benchmark was performed.
Final `docker compose stop --timeout 30` exited 0. All eleven project containers
were retained and stopped; Qdrant reported exit 143 following the requested
stop, and the other containers exit 0. All six named project volumes remain.

## R6.15 OMERTA lease namespace and file-backed secret acceptance — 2026-09-03

Branch: `Radin/omerta-env-namespace`

Baseline: `1d9183b` (`feat(runtime): persist authenticated lease fences`)

Implementation commits: `9579bc0`, `127267a`, `d8944e9`, `cfb9c05`,
`29cda45`, and `44329cf`.

This gate moved the canonical execution-lease signing namespace from the
release/branch name to the product identity: `OMERTA_RUNTIME_LEASE_HMAC_KEY`
and `OMERTA_RUNTIME_LEASE_V1`. The preferred input is now
`OMERTA_RUNTIME_LEASE_HMAC_KEY_FILE`; the direct value remains a documented
development compatibility path. Python and Runtime reject absent, malformed,
or conflicting key sources. The local key used for acceptance remained outside
Git and no credential value was printed or committed.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Focused secret/config regression | pass | Python secret-source and lease tests reported `19 passed`; Rust reported `16 passed`; Ruff and Runtime formatting passed |
| Full Python regression | pass with exclusions | `241 passed, 2 skipped, 1 deselected`, with three existing FastAPI/Starlette deprecation warnings and the intentionally red Structure completion gate excluded |
| Architecture regression | pass | Final run reported `74 passed, 1 deselected` in 7.34 seconds |
| Compose rendering | pass | Canonical one-worker and opt-in two-worker configurations both rendered with exit 0; no second worker was started in this gate |
| Non-root secret staging | pass live | The one-shot initializer staged the key into a named volume as uid/gid 10001 and mode 0400; Runtime and Control received only the file path and no raw-key environment variable |
| Runtime and Control health | pass live | Rebuilt/recreated Runtime and Control remained healthy with one Runtime worker; PostgreSQL, Redis, Gateway, and the preserved Console also remained healthy |
| Canonical execution and persistence | pass live, constrained | Authenticated deterministic echo completed through Console -> Gateway -> Control -> Runtime. A direct Gateway probe persisted matching tenant, idempotency, correlation, and trace evidence. Runtime fence state retained the same sanitized fingerprint across a normal stop/start and remained mode 0600 as uid 10001 |
| Fresh Console image build | blocked by network | The locked BuildKit build reused 658 of 659 cached packages, but npm registry metadata/attestation requests repeatedly returned `ECONNRESET`, `UND_ERR_SOCKET`, and curl error 23. The final attempt made no CPU or output progress for more than five minutes after about 24 minutes and was interrupted with exit 130 |
| Full Console propagation on current source image | blocked | The running Console image predates the forwarding repair. Source-level forwarding is covered, but a fresh image could not be produced, so end-to-end Console-originated idempotency/correlation propagation is not claimed |
| Resource guard | pass | Available memory remained about 4.1 GiB and disk availability about 33 GiB; builds were sequential and only one Runtime worker was active |

Earlier failed attempts are retained as negative evidence: an image command
initially omitted the required Compose project directory; a direct host bind
was unreadable by the non-root Runtime and was replaced by the least-privilege
staging volume; duplicate local administrator configuration caused an initial
401; and interrupted registry-bound Console builds exited 130. No weaker
unlocked/offline installation was substituted, supply-chain verification was
not disabled, and no volume was deleted.

The named Docker volume is an access-control mechanism, not encrypted secret
storage. Production operation still requires an external secret manager or
workload identity, rotation, and audited delivery. This gate does not establish
multi-worker scalability, distributed consensus, successful Linux isolation,
production readiness, or security certification.

## R6.14 Runtime execution-lease fencing — 2026-08-31

Branch: `Radin/capo-r6-validation`

Baseline: `2e1833534e2eae4093c5acb423aeb57a0fac7b1b`

Implementation commit: `edde9b019094d5dc521ac486a8467075ce8169b3`

This gate used the preserved single-worker `compose` Quickstart and canonical
PostgreSQL database. Builds and suites ran sequentially. No volume, persisted
record, credential, or security control was removed.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Pre-fix reproduction | reproduced | Before the change, a direct Runtime command without lease metadata executed with exit code 0, and backdating an active resource lease did not cause the next lifecycle heartbeat to reclaim it |
| Additive lease model | pass | `runtime_execution_leases` stores a monotonic generation, status, expiry, timestamps, and only the SHA-256 token hash; the raw token exists only in the bounded Control dispatch object and gRPC metadata |
| Targeted Control and lint | pass | `46 passed`; Ruff passed. PostgreSQL concurrency reported `1 passed`, and the complete Control suite reported `90 passed` with three existing deprecation warnings |
| Runtime regression | pass after environment workaround | The repository target directory was root-owned and Cargo failed on `.cargo-build-lock` with permission denied. Using isolated `CARGO_TARGET_DIR=/tmp/omerta-r614-target` produced `11 passed`; formatting passed and token-debug redaction was exercised |
| Architecture and Python regression | pass with exclusions | Architecture reported `72 passed, 1 deselected`; full Python reported `235 passed, 2 skipped, 1 deselected, 3 warnings`. The intentionally red Structure completion gate remained excluded |
| Compose render and sequential images | pass | Canonical render exited 0. Control built from cache; the locked cold Runtime release image built in 22 minutes 39 seconds. The two image builds did not overlap |
| Missing-lease rejection | pass live | After recreating Runtime then Control, a direct Runtime request without lease metadata returned gRPC `FAILED_PRECONDITION` instead of executing |
| Leased dispatch and generation fence | pass live | A real Control dispatcher call completed deterministic echo execution, released both leases, and restored zero active leases. A separately scheduled generation executed once; replaying identical metadata was fenced by Runtime |
| Expiry reclamation | pass live | A test execution lease was backdated without deleting it. The lifecycle heartbeat marked the attempt, resource lease, and execution lease `expired`, restored full declared CPU/RAM, and returned the worker to zero active leases |
| Schema, persistence, and log checks | pass | Migration check reported current schema; all ten persisted execution-lease tokens were valid 64-character hashes, with zero active resource/execution leases. Runtime logs contained no lease-token field |
| Quickstart smoke | pass | PostgreSQL, Redis, one Runtime, installer, Control, Gateway, and Console passed; Runtime registration was fresh and the Console -> Gateway -> Control health chain was healthy |
| Resource guard | pass | Available RAM was about 4.0 GiB before builds and 4.2 GiB after acceptance, above the 1 GiB stop threshold |

Failed validation attempts are retained. The first targeted Python run reported
`3 failed, 25 passed` because three expected-table/finish fixtures were stale;
the fixtures were updated and the affected suites passed. A one-line live probe
used invalid Python syntax and exited 1 before execution. The first live replay
probe proved the Runtime rejection but then called a keyword-only cleanup
argument positionally and exited 1; its single test lease was subsequently
finished without deletion, and the corrected independent probe passed. No
failed command was treated as evidence of success.

R6.14 establishes bounded stale-dispatch protection for the current
single-Control, single-Runtime prototype. The metadata token is not
cryptographically verified against Control storage and does not authenticate
the caller on the current unauthenticated internal gRPC transport. Runtime's
generation fence is in memory, resets on restart, and does not cancel work that
was already admitted. This gate is not evidence of durable post-restart
fencing, multi-Control coordination, distributed consensus, successful Linux
isolation, scalability, production readiness, or security certification.

## R6.13 atomic scheduler leases — 2026-08-31

Branch: `Radin/capo-r6-validation`

Baseline: `4163f1ce4b708c237f8b03d127e8f36753dc9e94`

Implementation commit: `076db60620cf8c1b43fee921a76e47acf9a2c99a`

This gate used the preserved single-worker `compose` Quickstart and canonical
PostgreSQL database. It did not run a benchmark, add a second Runtime, delete a
record or volume, or expose a credential.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Pre-fix concurrent reproduction | failed as expected | Two concurrent 600m CPU requests were both selected on a 1000m worker, availability remained 1000m/512 MB, three persisted attempts produced an `active_leases` value of 1, and a same-identity race raised `IntegrityError` instead of replaying |
| Atomic resource model | pass | Additive `runtime_resource_leases` rows persist CPU/RAM, acquisition and release state; no existing table, column, API, or record was removed |
| Targeted scheduler/migration tests | pass | `11 passed`; accounting, aggregate capacity, heartbeat preservation, idempotent release, audit rollback, and migration idempotency were exercised |
| PostgreSQL concurrency regression | pass | `1 passed`; concurrent same-identity calls produced one lease plus one replay, and only one of two concurrent 600m requests was admitted |
| Control regression | pass | `83 passed`, with three FastAPI/Starlette deprecation warnings |
| Architecture regression | pass | `72 passed, 1 deselected`; the intentionally red Structure completion gate remained excluded |
| Full Python regression | pass with skips | `228 passed, 2 skipped, 1 deselected, 3 warnings`; the two module-level skips are the formally retired legacy Agent Catalog and stream-service namespaces |
| Compose render and Control image build | pass | Canonical render exited 0; the Control image built sequentially and the active `compose-control-1` service became healthy after a no-dependency recreate |
| Live Control scheduling | pass | An authenticated Control request selected `runtime-quickstart-1`; finish returned the worker to 1000m CPU, 512 MB and zero active leases |
| Live heartbeat reconciliation | pass | A 250m/128 MB lease remained at 750m/384 MB after a real lifecycle heartbeat, then returned to full capacity after one idempotent finish |
| Resource guard | pass | Available RAM remained about 3.8 GiB after acceptance; one Runtime worker was used and builds/tests ran sequentially |

Two environment/operator failures are retained as negative evidence. The host
has no `python` alias (exit 127), and system `python3` has no pytest module; the
repository `.venv312` interpreter was therefore used. An initial Control
recreate omitted the active project name, targeted the stopped `omertaos`
project, recreated its stopped Control container, removed its unattached
`omerta-r5-net` network, and then failed because port 8000 belonged to the
preserved `compose` stack. No volume was removed. The corrected command used
`-p compose`, rebuilt only Control, and passed. The stopped
`omertaos-control-1` container remains created and was not broadly cleaned up.

R6.13 is evidence for bounded single-Control transaction correctness on the
canonical PostgreSQL backend. It is not evidence of Runtime-side lease fencing,
automatic reclamation after a Control crash, multi-Control serialization,
distributed consensus, scalability, production readiness, or security
certification.

## R6.12.2 trusted Gateway headers — 2026-08-31

Branch: `Radin/capo-r6-validation`

Validated implementation commit: `db32030` (`fix(security): authenticate
trusted control headers`). Control now uses one constant-time Gateway service
token verifier for Configuration, Network, and Runtime administrative routes.
Gateway sends that token on Network reads before Control consumes forwarded
roles for admin versus enabled-only view filtering.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Targeted Control security tests | pass | `7 passed, 3 existing deprecation warnings`; covered forged admin/user roles, wrong and raw tokens, valid Bearer access, enabled-only user/public views, full admin view, mutations, and Runtime route regression |
| Gateway tests | pass after environment correction | The first invocation used the host Node version and Vitest stopped before collection because `node:util.styleText` was unavailable. Re-running with the bundled compatible Node reported `5 files passed, 10 tests passed` and verified that Network reads carry service authentication before role context |
| Gateway static gates | pass | Production TypeScript build and ESLint exited 0; no dependency or lockfile changed |
| Control regression | pass | `80 passed, 3 existing deprecation warnings` |
| Architecture regression | pass | `72 passed, 1 intentionally excluded Structure completion gate` |
| Full Python regression | pass | `225 passed, 2 skipped, 1 intentionally excluded Structure completion gate, 3 warnings` |
| Compose render and sequential builds | pass | Canonical `config --quiet` exited 0; Control and Gateway images built one at a time from locked cached dependencies |
| Limited recreate and smoke | pass | Only Control and Gateway were recreated with `--no-deps --wait`; PostgreSQL, Redis, Runtime, Console, and all volumes remained in place. The complete Quickstart smoke and Console -> Gateway -> Control health chain passed |
| Live negative authentication | pass | Role-only Configuration and Network requests returned HTTP 403, and a raw service token without the Bearer scheme returned HTTP 403 |
| Live positive authentication | pass | Bearer service-token Configuration access, Network enabled-only user filtering, Network admin view, and authenticated Gateway Configuration/Network paths returned HTTP 200. No token or proxy payload was printed |
| Resource guard and final state | pass | Available memory remained about 3.7 GiB, all six existing application/data containers were healthy, and no volume deletion or broad shutdown command was used |

This closes the reproduced role-header trust issue for the current
Configuration, Network, and Runtime administrative compatibility routes. It
does not establish mTLS, workload identity, network segmentation, independent
authorization review, production hardening, penetration testing, or security
certification.

## R6.12.1 Runtime boundary repairs — 2026-08-31

Branch: `Radin/capo-r6-validation`

Validated implementation commits: `78b02b1` (`fix(control): enforce runtime
tenant and admin boundaries`), `2637cb7` (`fix(control): reconcile runtime
lifecycle state`), and `b0181ee` (`fix(control): paginate runtime audit trails`).
Only the existing `compose` Control image was rebuilt, sequentially, and only
its container was normally recreated. PostgreSQL, Redis, Runtime, Gateway,
Console, containers, and persistent volumes were retained.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Independent defect reproduction | pass | In-memory Control execution reproduced role-header-only admin access, cross-tenant attempt replay, heartbeat lease reset, stale tenant/capacity configuration, and silent oldest-100 audit truncation before repair |
| Targeted repair suites | pass after one test correction | Auth/scheduler/dispatch reported `17 passed`; lifecycle/scheduler/routes reported `21 passed`; audit/routes reported `4 passed`. The first lifecycle run had `1 failed` because the new assertion assumed capability JSON order; structural set comparison replaced that stale assumption |
| Control regression | pass | `79 passed, 3 existing deprecation warnings` |
| Architecture regression | pass | `72 passed, 1 intentionally excluded Structure completion gate` |
| Full Python regression | pass | `224 passed, 2 skipped, 1 intentionally excluded Structure completion gate, 3 warnings` |
| Static and Compose validation | pass with pre-existing note | Targeted Ruff lint and format checks, `git diff --check`, and canonical Compose `config --quiet` exited 0. A broader format probe identified the untouched pre-existing `control/audit/models.py` formatting difference; no unrelated formatting was applied |
| Sequential Control build/recreate | pass | The Control image rebuilt from locked cached dependencies and only `compose-control-1` was recreated with `--no-deps --wait`; it returned healthy without restarting data or Runtime services |
| Quickstart smoke | pass | PostgreSQL, Redis, Runtime, installer, Control, Gateway, Console, automatic registration, binary healthcheck, dependencies, and Console -> Gateway -> Control health chain passed |
| Service-token boundary | pass in local prototype scope | A role-header-only Runtime admin request returned HTTP 403; the configured service token succeeded. No token value was printed or recorded |
| Tenant collision boundary | pass | A second tenant using the same task/attempt identity was rejected without a selected node or idempotent replay |
| Lifecycle reconciliation and lease preservation | pass | A fresh live heartbeat reconciled trusted tenant/capability/capacity values and preserved an active validation lease; normal attempt finish restored the baseline lease count |
| Audit pagination | pass | A live tenant-scoped trail queried with limit 1 returned explicit truncation and a cursor; the next cursor returned the remaining event |
| Resource guard and final state | pass | Available memory was about 3.7 GiB before and after validation. The six existing application/data containers remained healthy and no volume deletion command was used |

These repairs close the reproduced local prototype defects but do not establish
independent authorization review, concurrent scheduler correctness, lease
fencing, immutable audit integrity, production isolation, native systemd
acceptance, scalability, production readiness, or security certification.

## R6.12 durable Runtime audit trail — 2026-08-31

Branch: `Radin/capo-r6-validation`

Validated implementation commit: `c5a9246` (`feat(control): persist runtime
audit trails`). The run reused the preserved `omertaos-r6-two` PostgreSQL,
MongoDB, and MinIO volumes but started the base Quickstart with one project
Runtime worker. The previous secondary container remained stopped and was not
removed. The independent pre-existing Runtime remained healthy, so no more
than two Runtime processes were active on the host.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Static validation | pass | `git diff --check`, Python compile, and targeted Ruff checks exited 0 |
| Targeted audit/migration/scheduler/dispatch/routes | pass after one regression repair | First run reported `17 passed, 1 failed`: same-process cache replay bypassed the scheduler, exposing a missing durable replay event and an incorrect test expectation. Cache replay/conflict events were added; final targeted run reported `19 passed, 3 existing warnings` |
| Transaction rollback | pass | Injected audit persistence failure rolled back the attempt, lease increment, and scheduling decision together |
| Control regression | pass | `77 passed, 3 existing deprecation warnings` |
| Architecture regression | pass | `72 passed, 1 intentionally excluded Structure completion gate` |
| Full Python regression | pass | `222 passed, 2 skipped, 1 intentionally excluded Structure completion gate, 3 warnings` |
| Additive schema | pass | Control startup created `runtime_audit_events` on the preserved PostgreSQL database; migration tests apply the schema twice and no existing table or row is removed |
| Control image build | pass | Only the affected Control image built, sequentially, with locked cached dependencies. Runtime, Gateway, and Console builds were skipped because their code/images were unchanged |
| Resource guard | pass | Available memory was 3.6 GiB before startup, 3.3 GiB during live checks, and 3.6 GiB after shutdown, above the 1 GiB stop threshold |
| Initial Quickstart smoke | pass | The base project passed PostgreSQL, Redis, Runtime, installer, Control, Gateway, Console, automatic registration, dependency, and canonical health-chain checks |
| Tenant rejection evidence | pass after acceptance-input correction | The first intended success used unregistered `tenant-r612` and correctly returned application `ERROR`; durable audit recorded `runtime.schedule/rejected` with `no eligible runtime node`. The persisted node allowlist was preserved rather than overwritten |
| Authenticated canonical task | pass | A unique `tenant-primary` request traversed Console -> Gateway -> Control -> one Runtime and returned status `OK` |
| Durable reconstruction | pass | Admin-authenticated retrieval returned exactly `runtime.schedule`, `runtime.dispatch.start`, and `runtime.dispatch.success`, with matching tenant/task/attempt/node/correlation/trace and retry count 0 |
| Access and data minimization | pass in prototype scope | A different tenant returned an empty event list, no admin credential returned HTTP 403, and the schema/API contained no message, payload, stdout, stderr, idempotency-key, credential, secret, or token field |
| Restart persistence | pass | The same three events remained queryable after normal PostgreSQL and Control container restarts |
| Final Quickstart smoke | pass | The complete read-only smoke probe passed again after the restarts |
| Final shutdown | pass | `docker compose stop` left zero test-project containers running and preserved all three project volumes; no volume deletion command was used. The pre-existing Runtime remained healthy |

The persistence adapter is owned by Control and leaves the shared telemetry
primitive transport-neutral. Scheduling state, decision, and schedule audit
event commit together; dispatch-start persistence is a fail-closed barrier
before Runtime execution; terminal attempt state and outcome audit commit
together. Stored reasons are controlled strings and task/result bodies are not
accepted by the audit schema.

This is prototype-level durable reconstruction, not an immutable security log.
No retention policy, cryptographic integrity chain, external exporter,
independent authorization review, production isolation, native systemd
acceptance, benchmark, scalability result, production readiness, or security
certification is claimed. No credential, cookie, token, secret, or task payload
was printed or recorded.

## R6.11 bounded two-worker Quickstart acceptance — 2026-08-30

Branch: `Radin/capo-r6-validation`

Validated implementation commit: `cd43d8f` (`feat(deploy): add bounded
two-worker quickstart`). The opt-in Compose override used exactly two local
Runtime workers, one sequential Control lifecycle manager, host ports Console
`13100`, Gateway `18180`, loopback Control `18102`, and loopback primary Runtime
`55151` on the isolated `omerta-r6-two-net` network. The secondary Runtime had
no published host port. This run did not modify or delete existing volumes.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Targeted lifecycle/architecture tests | pass | `25 passed`; JSON list validation, duplicate rejection, sequential probing, dual registration, bounded count, image reuse, and secondary port isolation were covered |
| Control regression | pass | `74 passed, 3 existing deprecation warnings` |
| Native/Quickstart regression | pass | `70 passed` |
| Architecture regression | pass | `72 passed, 1 intentionally excluded Structure completion gate` |
| Full Python regression | pass | `219 passed, 2 skipped, 1 intentionally excluded Structure completion gate, 3 warnings` |
| Compose rendering | pass after command repair | The first render omitted `--env-file` and stopped on required bootstrap variables; the first build omitted `--project-directory .` and stopped on a nonexistent relative context. The corrected canonical render parsed two nodes, reused one Runtime image, exposed no secondary host port, and kept Control loopback-only |
| Sequential image builds | pass with one dependency repair | Control built first. Initial `up --no-build` stopped at create because the project-specific Gateway image was absent; Gateway then built separately and the unchanged stack started. Runtime and Console builds were skipped because their unchanged images were explicitly reused |
| Resource guard | pass | Available memory was 3.9 GiB before startup, 3.4 GiB during live checks, and 3.9 GiB after shutdown; exactly two Runtime workers were running during acceptance |
| Two-node lifecycle | pass | PostgreSQL recorded both trusted endpoints as `healthy` with fresh heartbeats, declared tenant/capability sets, and capacities 1000/512 and 2000/1024; lifecycle probes ran sequentially |
| Full Quickstart smoke | pass twice | Initial and final probes passed service/container health, installer exit, automatic registration, dependencies, and the Console-to-Gateway-to-Control chain; the secondary Runtime binary healthcheck also passed directly |
| Authenticated round-robin | pass | Two unique `tenant-shared` tasks traversed Console -> Gateway -> Control -> Runtime and completed on primary then secondary; audit rows recorded both eligible nodes and trace context |
| Tenant-aware eligibility | pass | `tenant-primary` completed only on primary and `tenant-secondary` only on secondary; audit rows recorded the other node rejected for `tenant` |
| Capability and capacity eligibility | pass | Admin-authenticated scheduler probes selected only secondary for `resource.allocate` and for 1500 CPU millis/800 MiB; primary rejection reasons were `capability` and `capacity` |
| Least-loaded scheduling | pass after test-fixture repair | The first probe left two acceptance leases on secondary and therefore did not create the intended load difference. Those attempts were finished without deletion; the independent rerun made both workers eligible and selected the lower-load secondary |
| Bounded failover | pass | Primary stopped immediately after a fresh heartbeat. Attempt `:0` selected primary and ended `transport_error`; retry `:1` rejected unreachable primary, selected secondary, and completed with retry count 1 of 1 |
| Automatic recovery | pass | Restarting primary restored a fresh healthy heartbeat without manual registration; two subsequent shared tasks completed primary then secondary |
| PostgreSQL restart persistence | pass | Four expected failover/recovery attempt rows remained after a normal PostgreSQL container restart |
| Final shutdown | pass with note | `docker compose stop` left no test-project service running and preserved all three project volumes. Qdrant exited 143 on SIGTERM; other running services exited 0. The pre-existing `compose-runtime-1` was restored healthy |

The node list remains trusted local Control configuration. Runtime receives no
administrator credential and cannot self-authorize tenant eligibility. The
manager enforces a configurable default limit of 2 and hard maximum of 32, and
probes configured workers sequentially on this constrained host.

This acceptance demonstrates bounded local multi-node scheduling and one
worker failover for the allowlisted deterministic echo path. It does not
measure throughput or recovery-time performance and does not establish
scalability, distributed membership, consensus, leader election, lease
fencing, federation, successful Linux isolation, native systemd operation,
production readiness, or security certification. No credential, cookie,
token, or secret value was printed or recorded.

## R6.10 automatic local Runtime lifecycle — 2026-08-30

Branch: `Radin/capo-r6-validation`

Validated implementation commit: `ac39d51` (`feat(deploy): automate
quickstart runtime lifecycle`). The run recreated the isolated Quickstart
containers while preserving the existing volumes, used one Runtime worker, and
used host ports Console `13000`, Gateway `18080`, loopback Control `18002`, and
loopback Runtime `55051` on `omerta-r6-fixed-net`. No manual node registration
or heartbeat command was used.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Lifecycle and probe tests | pass | `tests/control/test_runtime_lifecycle.py` reported `6 passed`; coverage includes bounded opt-in configuration, Runtime `QueryMetrics` readiness, invalid JSON rejection, registration, unreachable refusal, and preservation of operator draining |
| Control regression | pass | `70 passed, 3 existing deprecation warnings` |
| Native/Quickstart regression | pass | `70 passed` |
| Architecture regression | pass | `71 passed, 1 intentionally excluded completion gate` |
| Full Python regression | pass | `214 passed, 2 skipped, 1 intentionally excluded completion gate, 3 warnings` |
| Compose rendering | pass | The rendered model selected loopback-only Control publishing and enabled the bounded 10-second local lifecycle interval; no rendered secret values were recorded |
| Control image build | pass | The affected image rebuilt sequentially with locked cached dependencies and exit 0. Runtime, Gateway, and Console images were unchanged and deliberately not rebuilt |
| Resource guard | pass | Available memory was 2.9 GiB before build, 3.4 GiB during final live checks, and 3.8 GiB after shutdown; it remained above the 1 GiB stop threshold |
| Automatic registration | pass | After container recreation, PostgreSQL contained `runtime-quickstart-1` at `runtime:50051`, state `healthy`, capability `terminal.execute`, declared capacity 1000 CPU millis/512 MiB, and a heartbeat newer than 30 seconds |
| Control host-port repair | pass on this host | Publishing Control as `127.0.0.1:18002:8000` returned a valid healthy payload. This removes unnecessary non-loopback exposure and eliminated the reset reproduced with the prior all-interface mapping |
| Full Quickstart smoke | pass twice | Both the initial and post-recovery probes passed container health, installer exit, Runtime binary health, fresh automatic registration, Control/Gateway/Console payloads, dependencies, and the Console-to-Gateway-to-Control health chain |
| Canonical task without manual heartbeat | pass | An authenticated Console API request traversed Gateway, Control, and Runtime and returned HTTP 200, status `OK`, and an exact deterministic echo |
| Runtime outage detection | pass fail-closed | Runtime alone was stopped. After the 30-second freshness threshold, the next authenticated canonical task returned application status `ERROR` with `RUNTIME_NODE_UNAVAILABLE`; PostgreSQL recorded the node `unreachable` with a stale heartbeat |
| Automatic recovery | pass | Starting the same Runtime container caused the Control supervisor to restore a fresh `healthy` heartbeat without a registration call. A new authenticated canonical task returned `OK`, followed by a second complete smoke pass |
| Final shutdown | pass with note | `docker compose stop` exited 0, no project containers remained running, all three project volumes were preserved, and no volume-deletion command was used |

The supervisor is enabled by the Quickstart Compose profile and remains opt-in
for other Control deployments. It probes the configured Runtime gRPC API before
registering or heartbeating, never gives Runtime an administrator credential,
does not let Runtime choose tenant eligibility, refuses to heartbeat a persisted
node whose endpoint differs from trusted Control configuration, and preserves
operator draining. Declared capacity is static local configuration rather than
measured host utilization.

This stage does not demonstrate browser UI interaction, multiple workers,
distributed membership, consensus, leader election, lease fencing, precise
recovery-time performance, native systemd operation, successful Linux
isolation, production readiness, or security certification. Two Python tests
remain skipped by their existing contracts, and the intentional Structure
completion gate was not run. No credential, cookie, token, task payload, or
secret value was printed or recorded.

## R6.9 authenticated canonical execution — 2026-08-30

Branch: `Radin/capo-r6-validation`

Validated repair commit: `cc52204` (`fix(runtime): propagate canonical dispatch
context`). Control, Gateway, and Console images were built sequentially from
that commit. The preserved isolated project used one Runtime worker, host ports
Console `13000`, Gateway `18080`, Control `18001`, and Runtime `55051`, plus the
`omerta-r6-fixed-net` network. The Control port was changed from `18000` while
diagnosing a host publishing failure; both ports exhibited the same reset.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Context regression tests | pass | Console allowlist `2 passed`; Gateway `4 files, 9 tests passed`; targeted Control transport `7 passed`; Runtime dispatch/transport `14 passed`. Three existing Python deprecation warnings remained |
| Architecture regression | pass after stale-reference repair | The first run reported `69 passed, 1 failed, 1 deselected` because README omitted three current canonical design links. Commit `168840d` restored the references; the targeted test passed and the full rerun reported `70 passed, 1 deselected`. The intentionally red completion gate remained excluded |
| Broader Console regression | pass | `10 files, 22 tests passed` after restoring the locked pnpm `11.13.1` installation; Prisma generation and the direct Next production build exited 0 |
| Service builds | pass | Gateway and direct Console production builds passed; Control, Gateway, and Console container images then built sequentially with exit 0. The unchanged Runtime image was not rebuilt |
| Compose rendering | pass | The isolated Quickstart configuration rendered with the selected images, network, and host ports; this was treated only as static configuration evidence |
| Resource guard | pass | Available memory was 4.0 GiB before startup, 2.8 GiB during final live checks, and 3.0 GiB after shutdown, above the 1 GiB stop threshold |
| Runtime registration and heartbeat | pass, manual | `runtime-r6-1` registered inside the Control network with tenant `tenant-r6` and the single `terminal.execute` capability; a fresh heartbeat reported `healthy` |
| Authenticated canonical task | pass in constrained scope | A real NextAuth session submitted `runtime.echo.v1` through Console `/api/proxy/tasks`; Console, Gateway, Control gRPC, and one Runtime completed it with HTTP 200, application status `OK`, and an exact deterministic echo |
| Tenant and context propagation | pass | PostgreSQL recorded tenant `tenant-r6`, the submitted idempotency key, selected node `runtime-r6-1`, status `completed`, and the submitted W3C traceparent. Runtime audit recorded matching task, tenant, agent, correlation/request, trace, and `authorized`/`completed` outcomes without logging the payload |
| Same-request replay | pass in constrained scope | Repeating the authenticated request with the same idempotency key returned the same task id; PostgreSQL retained exactly one task attempt |
| Service and dependency health | pass internally | Console and Gateway host health returned valid healthy payloads; Gateway reported Redis and Control healthy; Console's system endpoint reported the Console-to-Gateway-to-Control chain healthy; Control's internal HTTP health passed |
| Quickstart smoke | partial failure | PostgreSQL, Redis, Runtime, installer, Control, Gateway, and Console container checks plus Runtime binary health passed. The next host probe failed with exit 1 because Docker's published Control port returned an empty/reset response even after isolated port change and Control recreation; internal and Gateway-to-Control probes remained HTTP 200 |
| Final shutdown | pass with note | `docker compose stop` exited 0, all services stopped, all three project volumes were preserved, and no volume-deletion command was used. Qdrant exited 143 after SIGTERM; the other running services exited 0 |

Failed toolchain attempts were not substituted silently: system Node 18 was
incompatible with the current JavaScript gates; an initial pnpm invocation
could not confirm a module purge without a TTY; the resulting partial module
state lacked Rollup's optional binary; and the pnpm build wrapper's dependency
status/network activity was interrupted with exit 130. The exact locked Console
dependencies were restored without lockfile changes, and the direct underlying
test and build commands subsequently passed. A host `python` invocation also
failed with exit 127 before acceptance orchestration began; the available
`python3` executable ran the unchanged probe successfully. Two diagnostic shell
pipelines produced misleading zero statuses after `curl` failures; neither was
accepted as evidence, and strict independent probes reproduced the failure.

This stage demonstrates one authenticated API request through the complete
canonical service path on one local worker. It does not demonstrate a browser
UI click flow, automatic Runtime registration/heartbeat, multiple workers,
scalability, successful Linux isolation, durable Control audit export,
production readiness, or security certification. The published Control host
port remains an unresolved environment/deployment gate. No credential, cookie,
token, echoed payload, or secret value was printed or recorded.

## R6.8 isolated Quickstart smoke — 2026-08-30

Branch: `Radin/capo-r6-validation`

Validated smoke repair commit:
`0c53328` (`fix(deploy): target isolated quickstart smoke`). The live run reused
the preserved single-worker `omertaos-r6-fixed` containers and images from the
R6.7 acceptance; no image build or dependency installation was performed. This
therefore validates the repaired read-only smoke probe and preserved stack, not
a fresh image build of the current branch.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Failure reproduction | pass | The previous script rejected `--project-name` with exit 1, so it could not target the isolated acceptance project explicitly |
| Smoke contract regression | pass | `6 passed`; includes mocked project selection, isolated ports, Runtime healthcheck, installer lookup, and invalid-port rejection |
| Native contract regression | pass | `70 passed` |
| Deployment architecture regression | pass | `14 passed, 57 deselected` for the focused Quickstart/deployment/CAPO selection |
| Static validation | pass | Bash syntax, Ruff, `git diff --check`, and sanitized Compose `config --quiet` exited 0 |
| Resource guard | pass | Available memory was 2.2 GiB before startup and 1.9 GiB during live smoke, above the 1 GiB stop threshold |
| Positive isolated smoke | pass | The selected project reported healthy PostgreSQL, Redis, Runtime, Control, Gateway, and Console containers; installer exit 0; Runtime binary health; service payloads; Gateway dependencies; and the Console-to-Gateway-to-Control health chain |
| Wrong-project negative probe | pass | A nonexistent project failed with exit 1 at the missing PostgreSQL container even though the independent default-port `compose-*` stack remained healthy |
| Final shutdown | pass with note | Compose stop exited 0, persistent volumes remained present, Qdrant exited 143 after SIGTERM, and the other R6 containers exited 0 |

The smoke probe remains read-only and does not start, restart, migrate,
bootstrap, or stop services. This stage does not submit a task through Console,
prove the Console-to-Runtime execution path, validate multiple workers, or
change the existing isolation and production-readiness evidence boundaries. No
credential value was printed or recorded.

## R6 Quickstart restart persistence — 2026-08-29

Branch: `codex/capo-r5-runtime-execution`

Validated commit: `5858d3696ad30a6709b60180d2690b13baf1621b`.
The run used one Runtime worker and the preserved `omertaos-r6-fixed` volumes.
It did not build images, run benchmarks, or modify the concurrently running
`compose-*` stack. The isolated acceptance ports were Console `13000`, Gateway
`18080`, Control `18000`, and Runtime `55051`; the Docker network was
`omerta-r6-fixed-net`.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Resource guard | pass | Available memory was 2.0 GiB before startup, 1.8 GiB at initial health, and 1.7 GiB after restart; it remained above the 1 GiB stop threshold |
| Quickstart startup | pass after two operator-configuration failures | An initial resumed command omitted the isolated network and encountered stale container network metadata; after recreation, the default Runtime port was occupied by the preserved `compose-*` stack. Reapplying the isolated network and port settings started the unchanged images successfully |
| Service health | pass | Console, Gateway, Control, Runtime, PostgreSQL, and Redis were healthy after startup and again after a complete normal stop/start cycle |
| Installer idempotency | pass | The one-shot install container exited 0 on both starts; the user-row count remained `1` |
| Prisma migration persistence | pass | Migration count remained `2`; the sanitized migration-name fingerprint remained `e2e79dd0d4a8b0bed0724ce827291103` before and after restart |
| Volume persistence | pass | PostgreSQL, MongoDB, and MinIO volumes remained present after the final `docker compose stop` |
| Final shutdown | pass with note | Compose stop exited 0; Qdrant exited 143 after SIGTERM and the other containers exited 0; no volume deletion command was used |

The failed startup attempts are environment/configuration evidence, not service
acceptance. This gate establishes restart persistence and idempotent bootstrap
for the constrained single-worker Quickstart only. It does not establish
multi-worker scalability, Linux isolation, native systemd acceptance,
production readiness, or security certification. No credential value was
printed or recorded.

## R5 constrained Runtime acceptance — 2026-08-28

Branch: `codex/capo-r5-runtime-execution`

Validated deployment/configuration commit:
`0deccc85d6ba5601fb181ce9968b6bdd23e40014`. The Runtime dispatch source is in
`711395a` and `681ff8f`; the build-context checkpoint is `d4ff77a`. Nothing in
this acceptance run was pushed or merged.

The run used one Runtime worker on the recorded 8 GB Linux host. Available
memory remained above 3 GB, services and image builds were executed
sequentially, and the existing `compose-*` stack was preserved. The R5 stack
used separate host ports and the `omerta-r5-net` network.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Architecture regression | pass | `68 passed, 1 deselected`; the intentionally red completion gate was excluded |
| Full Python regression | pass | `203 passed, 2 skipped, 3 warnings` before live acceptance |
| Runtime image build | pass | Locked release build completed in 17 minutes; cold-build duration is not a performance benchmark |
| Runtime image identity | pass | Image ran as `runtime`; one worker became healthy on loopback port `55051` |
| Control image build | pass after transient network failure | Initial Python base-layer request returned HTTP 403; an independent pull succeeded and the unchanged rebuild passed |
| Gateway image build | blocked | First `npm ci` attempt timed out fetching locked `yargs-parser@21.1.1`; a direct URL probe later returned HTTP 200; the second attempt made no progress for 15 minutes and was stopped with exit 130 |
| Console image/live service | skipped | Gateway image gate blocked the canonical full-stack sequence; no weaker substitute was used |
| Backend startup | partial pass | PostgreSQL, Redis, one Runtime, and Control were healthy; Qdrant and MinIO were running but have no explicit Compose readiness probe |
| Control health | pass | `/health` and `/v1/health` returned `{"status":"ok","service":"control"}` on isolated host port `18000` |
| Node registration and heartbeat | pass | `runtime-r5-1` registered with `terminal.execute`, tenant `tenant-r5`, then accepted a heartbeat |
| Worker failure detection | pass in constrained scope | A heartbeat older than the 30-second threshold changed the node to `unreachable` and dispatch failed closed with `RUNTIME_NODE_UNAVAILABLE` |
| Allowlisted execution | pass | Fresh heartbeat plus gRPC Submit selected `runtime-r5-1`; `runtime.echo.v1` returned exit code 0 and `r5-audit-ok\n` |
| Context/audit propagation | pass at Runtime log boundary | Tenant, task, attempt, request, trace, actor, and authorized/completed outcomes were logged; the echoed payload was not logged |
| In-process idempotency | pass | Identical replay returned `idempotent_replay=true`; Runtime audit-event count did not increase |
| Post-restart idempotency | pass fail-closed | After normal Control restart, replay returned `RUNTIME_RESULT_REPLAY_UNAVAILABLE`; Runtime did not execute it again |
| PostgreSQL persistence | pass | A non-sensitive probe row remained readable after normal PostgreSQL restart |
| Shutdown and volume preservation | pass with note | `docker compose stop` preserved `omertaos_postgres-data` and `omertaos_minio-data`; Qdrant reported exit 143 after SIGTERM while the other R5 services exited 0 |
| Full canonical request path | blocked | Current Gateway image was unavailable, so Console -> Gateway -> Control -> Runtime was not claimed |

Runtime audit evidence required an acceptance-only Compose override setting
`RUST_LOG=info`; the host exports `RUST_LOG=warn`. Control's `emit_audit`
primitive still returns only an in-memory entry and has no durable exporter.
Successful `lite`-profile command execution is not evidence of completed Linux
namespace/seccomp isolation, production readiness, security certification, or
multi-worker scalability.

## R3 current reconciliation — 2026-08-10

Official branch `CAPO` is synchronized at evidence commit
`91921367cdfa600abb91710f7d699a183af800fa`. The current lockfiles are tracked:

| Lockfile | SHA-256 |
|---|---|
| `runtime-daemon/Cargo.lock` | `9C7EBC387FEF54CB7C2BBC70F96EA2DDF690F7636D18175FA251B96D5D5433F6` |
| `gateway/package-lock.json` | `CECAD9E18FB37754EBDF9CAC078BDC0A10CFE939365651CEB84160746866D55F` |
| `console/pnpm-lock.yaml` | `98FCA5264683D58F5274C14A62971FE56679AC7AD0C3A61C49722CFB0D4555B1` |

CI run [`31358631289`](https://github.com/Hamedghz/OMERTAOS/actions/runs/31358631289)
passed architecture, lint, all service builds, Python and locked Cargo tests,
the locked Runtime release build, integration, security, seven image builds and
six architecture-independent checks. The remaining emulated arm64 Console image
job stayed in progress for more than three hours. R3 moves arm64 image builds to
the native `ubuntu-24.04-arm` runner and retains the locked Linux Runtime binary
plus its SHA-256 as a CI artifact.

Current Gate status:

| Gate | Status | Current evidence |
|---|---|---|
| S2 Core Migration | passed | Four service builds plus locked Runtime test/release build |
| S3 Supporting Migration | passed | 63 architecture tests and deterministic retired-root guards |
| S5 Legacy Retirement | passed (repository scope) | Explicit approval, absent retired roots, no executable dependencies |
| S6 Architecture Validation | passed | Full Python and architecture suites plus CI boundaries |
| Gate R | pending | Requires the R3 commit to be clean, pushed, fully green and architecture-complete |
| Native live acceptance | pending | No current Ubuntu/systemd reboot/smoke/update/rollback/restore evidence |
| Docker live acceptance | pending | Image build is not running-stack smoke/parity evidence |

The historical report below remains immutable evidence of its original review.

> Historical snapshot: this report records the 2026-07-12 CAPO review. The
> current Native N1-N8 contract supersedes its missing-lockfile and stop/disable
> rollback descriptions. Gateway and Runtime lockfiles now exist; N8 uses
> immutable releases, canonical backup verification, and atomic code rollback.
> Live Linux/systemd, Runtime build, smoke, update, and restore acceptance remain
> pending until rerun and recorded on the intended host.

Date: 2026-07-12 (Asia/Tehran)

Branch: `capo`

Baseline: `b4021a4327d63b8db0c0e0f87267dec28907cb36`

Phase 6 head reviewed: `d4e96723b5b6341af5c3b4c899d9fdaca2054331`

## Decision

The seven-phase CAPO implementation is **conditionally accepted for human
review and Linux-host validation**. Static contracts, configuration rendering,
application entrypoint checks, Gateway/Console builds, and the verified recovery
baseline pass. Production use, permanent legacy-path retirement, merge, and
deployment are not accepted by this report.

Native systemd acceptance remains pending on the intended Debian/Ubuntu SSD
host. Running Docker Quickstart acceptance also remains pending because the
local Docker daemon did not respond during Phases 6 and 7. These two gates are
independent and neither may be inferred from static validation.

## Delivered scope

- Verified external Git/source backup and reconstruction map.
- Non-secret CAPO environment and idempotency/security contract.
- Debian/Ubuntu, PostgreSQL, and Redis installers with dry-run behavior.
- Canonical Control, Gateway, Console, and Runtime build/install scripts.
- Four non-root systemd services, aggregate target, and lifecycle scripts.
- Read-only Native/Quickstart smoke checks, contract tests, troubleshooting,
  canonical backup verification, and immutable release rollback.

Across Phases 1–6, CAPO added 29 tracked files with 1,529 lines relative to the
baseline. No existing source, schema, table, data, legacy path, or public API was
removed or moved.

## Evidence

| Check | Result | Notes |
|---|---|---|
| Backup SHA-256 and Git bundle | pass | Three hashes match; bundle reports complete history |
| CAPO Bash syntax and `--help` | pass | All reviewed scripts via Git Bash |
| CAPO PowerShell contracts | pass | Ports, env, systemd hardening, rollback, forbidden commands |
| Quickstart/Local Compose rendering | pass | Both `config --quiet` checks |
| Architecture tests | pass | `14 passed in 0.95s` in final review |
| Control import | pass | `control.app.main:app` |
| Gateway TypeScript build | pass | `tsc -p tsconfig.json` |
| Console production build | pass with warnings | Missing local Prisma generation/DB URL; stale browser data |
| Runtime metadata | pass | Cargo manifest resolves without dependency download |
| Runtime release build | blocked | `index.crates.io:443` unavailable after retries |
| Full Python regression | blocked by legacy collection | 11 import errors for removed `os.control`, `os.kernel`, `aion`, and CLI paths |
| Native Linux smoke | pending | Requires intended Linux SSD/systemd host |
| Running Quickstart smoke | pending | Docker daemon did not respond; stack was not mutated |

No coverage report was generated because CAPO changes deployment assets and
documentation rather than application runtime code.

## Security and data review

- Services run as the dedicated non-login `omertaos` account and include
  `NoNewPrivileges` and `PrivateTmp`.
- Real secrets remain outside Git in `/etc/omertaos/omertaos.env`.
- PostgreSQL and Redis are required; optional stores default disabled.
- Static scanning found no executable destructive disk, Git move/removal,
  `DROP`, or `TRUNCATE` command in CAPO assets.
- Rollback preserves source, configuration, accounts, databases, volumes, and
  persistent state.

## Open acceptance gates

1. Run installers twice on a disposable Debian/Ubuntu SSD host and confirm the
   second execution is idempotent.
2. Run `first-boot.sh --version VERSION --backup PATH --start`, Native smoke,
   journald review, reboot recovery, stop/start, update, and rollback
   preview/execute with an operator present.
3. Start Quickstart, run its smoke test, verify Console → Gateway → Control →
   Runtime, and stop it without deleting volumes.
4. Restore the external backup in an isolated environment and reconcile the
   resulting commit and data checks.
5. Resolve or formally quarantine the legacy Python tests before treating the
   repository-wide regression suite as green.

Until all relevant gates pass, the permanent-deletion gate stays closed and
human review is required before merge or any production use.
