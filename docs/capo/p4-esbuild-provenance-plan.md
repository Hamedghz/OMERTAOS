# P4 auditable esbuild rebuild proposal

Date: 2026-11-11. Status: **Stage A implementation authorized and in validation;
Console integration and final image acceptance remain open**.
Baseline: `63f6f6e99ce220de3a02f3f1a2c0300f71b0401b`, branch
`Radin/omerta-env-namespace`; pre-edit checkpoint
`checkpoint/p4-esbuild-plan-start-63f6f6e`.

The user subsequently authorized the outstanding implementation permissions.
Implementation `fd95ecc` adds the Stage A builder, pinned inputs and regression
tests. This approval does not waive resource guards or authorize deleting
persistent volumes/shared caches, publishing, P5, host-wide installation or
Docker daemon changes. Current executable results belong in the acceptance
report; the original proposal below is not itself acceptance evidence.

### Reviewed transport adjustment

The direct compiler archive returned HTTP 404 through both `go.dev` and
`dl.google.com`; independent HEAD and bounded GET requests reproduced it even
though official metadata still lists its version and hash. No compiler downgrade
or checksum bypass was accepted. The explicit `--compiler-image` option instead
uses the official Linux amd64 Go 1.27.4 image pinned to
`docker.io/library/golang@sha256:ea30e25680a5470bac02b08bb0e0a735fb75bd0ab7d431b9b95ee0abef362586`.
The [pinned publisher Dockerfile](https://raw.githubusercontent.com/docker-library/golang/6aa5c5f09346fb65fdefa941a23eb3cb25ba7b1a/1.27/alpine3.24/Dockerfile)
declares the same compiler archive/hash. OCI digest verification is not a claim
that this host downloaded or verified the original tarball or its GPG signature.

Compiler invocations use separate ephemeral containers: caller UID/GID, readonly
root, no capabilities, no-new-privileges, 1 GiB memory, two CPUs and 256 PIDs.
Only module download has bridge networking; other Go commands use no network.
Only the private work directory is writable. The image must declare no implicit
volumes; timeout cleanup may force-remove only the privately recorded container
ID from that invocation, never a stack or volume. This is build containment, not
evidence of successful OMERTA Runtime Linux isolation.

Verified local archives may alternatively be supplied with `--compiler-archive`
and `--source-archive`; the original SHA256 remains mandatory before copying
and extraction. There is no automatic fallback to a different compiler/image.
The source contains one relative internal browser-fixture symlink. Extraction
defers links until regular files are complete, permits only targets inside the
archive root, and rejects escaping links, hardlinks and writes through links.

The first upstream Go test attempt stopped at the unchanged 3 GiB primary-disk
guard. The optional `--scratch-dir` now separates Go caches/temporary executables
onto an existing private, executable filesystem; no mount flags are modified.
It requires 512 MiB initially free and stops below 64 MiB scratch headroom.
The existing 3 GiB primary-output-disk and 1 GiB host-RAM guards remain intact.
Only this task's stopped test temporary files were relocated with a verified
copy retained; existing user files, shared caches and persistent volumes were
not pruned. RAM-backed caches/data are volatile, not persistence evidence.

## Problem and decision

The installed Console dependency graph uses tsx 4.23.15 and esbuild 0.28.1;
the secondary npm lock resolves esbuild 0.28.2. Both supported owners accept
0.28.2: tsx declares `~0.28.0`, Vite 7.3.7 declares `^0.27.0 || ^0.28.0`.
The proposed target is one exact esbuild 0.28.2, not a cross-major override.
Node 22.23.2, npm 10.9.10 and pnpm 11.13.1 remain unchanged.

The installed publisher ELF lacks `.go.buildinfo`. The previous direct rootfs
scan exited zero without Go analysis; the wrapper correctly rejected it.
Upstream's [Makefile](https://raw.githubusercontent.com/evanw/esbuild/v0.28.2/Makefile)
patches the Go linker in its release compiler target. Do not invoke
`make go-compiler`, platform/release targets that depend on it, or rebuild that
patched compiler. Use the unmodified official compiler instead. Preserve build
information; do not patch scanner rules, strip metadata or suppress CVEs.

This is a supply-chain/provenance repair proposal, not proof that every reported
Go CVE is reachable, or that a new compiler makes the application secure. Earlier
functional tests and the failed coverage gate remain as recorded in the
[acceptance report](acceptance-report.md).

## Verified inputs

Read-only checks on 2026-11-11 established these proposed immutable inputs:

| Input | Pin / provenance |
|---|---|
| esbuild source | `609683d892977362a0f99026cb74b96263d728a9` |
| Upstream tag and source version | `v0.28.2`; `version.txt` says `0.28.2` |
| Source archive | `https://codeload.github.com/evanw/esbuild/tar.gz/609683d892977362a0f99026cb74b96263d728a9` |
| Observed source SHA256 | `04cb2d38fb6af093577aa8bf174add7286099b65ef7854480cbbb8ff061cef1f` |
| Observed archive size | 2,011,018 bytes; streamed to a hash, not stored/extracted |
| Official compiler | `go1.27.4.linux-amd64.tar.gz`, 70,680,823 bytes |
| Compiler URL | `https://go.dev/dl/go1.27.4.linux-amd64.tar.gz` |
| Published compiler SHA256 | `7226736c2339719cda28fbf3a54d71aa63bcefe376e98cef00034268dab24840` |
| npm source correspondence | Registry `esbuild@0.28.2` gitHead equals the source commit; publication `2026-08-08T20:00:55.454Z` |

Sources: [Go download metadata](https://go.dev/dl/?mode=json),
[immutable source version](https://raw.githubusercontent.com/evanw/esbuild/609683d892977362a0f99026cb74b96263d728a9/version.txt),
[npm package metadata](https://registry.npmjs.org/esbuild/0.28.2).
The Git ref was independently read with `git ls-remote` (exit 0, 1.38s);
the bounded source hash request exited 0 in 2.22s. The GitHub API URL was
unavailable through the web reader; the Git transport succeeded, not an API pass.
The source digest is an observed HTTPS download pin, not a publisher signature
or signed build attestation. The compiler archive has not been downloaded or
verified locally. Recheck advisories and pins at execution time; a changed input
requires review, not silent substitution. The source's `go 1.13` directive is a
compatibility floor, not evidence of its publisher's compiler version.

## Stage A: provenance proof before installation changes

1. Confirm the current branch/diff and tag a clean checkpoint. Check free RAM
   and bytes on every actual output filesystem, not just the current directory.
2. Use a new, task-owned directory outside the repository; never reuse or modify
   another worker's Go cache. Download both pinned archives over verified HTTPS
   with bounded retries/timeouts and verify digests **before extraction or
   execution**. Reject traversal/symlink escapes when extracting. Do not install
   into `/usr`, edit shell profiles or copy the Go toolchain into the final image.
3. Set private `GOROOT`, `GOCACHE`, `GOMODCACHE`, `GOTMPDIR` and `GOPATH` there.
   Set `GOTOOLCHAIN=local`, `GOMAXPROCS=2`, `GOMEMLIMIT=768MiB`, `CGO_ENABLED=0`,
   `GOOS=linux`, `GOARCH=amd64`, `GOAMD64=v1`. Start from a sanitized allowlisted
   environment; reject inherited `GOFLAGS`, alternate `GOROOT`, `GOWORK`,
   `GOPRIVATE`, checksum exclusions or altered proxy/sumdb settings. No secrets
   are needed. Keep `GOSUMDB=sum.golang.org` and normal TLS verification enabled.
4. In the verified source tree, generate the version using
   `node scripts/esbuild.js --update-version-go`. Record the generated diff;
   require exactly version `0.28.2` and no compiler/source security patches.
   Resolve the original `go.mod`/`go.sum` dependencies with checksum verification;
   network failures remain blocked. Do not upgrade `x/sys` implicitly.
5. Build directly, avoiding release targets. The following is the build recipe
   for that already isolated, verified source/toolchain environment:

   ```sh
   go build -p=1 -mod=readonly -trimpath -buildvcs=false \
     -o "$OUTPUT/esbuild" ./cmd/esbuild
   go test -p=1 -parallel=1 -mod=readonly ./cmd/... ./internal/... ./pkg/...
   go version -m "$OUTPUT/esbuild"
   "$OUTPUT/esbuild" --version
   readelf -SW "$OUTPUT/esbuild"
   sha256sum "$OUTPUT/esbuild"
   ```

   No metadata-stripping postprocessing. Require the compiler, target, module
   dependencies and `.go.buildinfo` to be readable. Record the main module's
   `(devel)` version, if emitted, honestly alongside the verified source SHA and
   application version; never relabel it as a detected module release.
6. Build again into a separate new output with identical inputs, sequentially,
   and compare SHA256. A mismatch blocks reproducibility pending diagnosis.
   Compiler compatibility with this source and Alpine execution are tests to
   perform, not results already obtained.
7. Produce a binary-rootfs Trivy JSON and CycloneDX SBOM using the existing
   reviewed scanner/version and database. Require positive `gobinary` analysis,
   `stdlib` with the exact compiler version, and dependency inventory. Preserve
   all severities, scan exit codes, DB timestamps/digest and any stale-DB warning.
   A detected vulnerability is a failed security gate; no detected packages is
   failed coverage, even with scanner exit zero. Follow the
   [Trivy Go contract](https://trivy.dev/docs/latest/coverage/language/golang/).

Receipt contract: argv, source/OMERTA commit SHAs, compiler/archive/binary hashes,
generated-source diff, Go module JSON, target, sanitized build environment,
start/end/duration/exit for each command, tests passed/failed/skipped, resource
minimums, SBOM and scanner metadata. The implementation stores private receipts
beside the new external work directory's logs; ignored `artifacts/p4/` may hold
aggregate validation summaries. Commit only a sanitized summary after review.
Unsigned local provenance must not be described as signed enterprise attestation.

## Stage B: controlled integration, not a silent binary substitution

The upstream [runtime path resolver](https://raw.githubusercontent.com/evanw/esbuild/v0.28.2/lib/npm/node-platform.ts)
supports `ESBUILD_BINARY_PATH`, but a missing file warns and falls back. Its
[installer](https://raw.githubusercontent.com/evanw/esbuild/v0.28.2/lib/npm/node-install.ts)
returns through the manual override path before publisher binary-hash checking;
the normal CLI can also have been hard-linked to a publisher ELF at install.
An environment variable alone does not prove that every CLI/API invocation uses
our artifact. Its own SHA is not expected to match the publisher's binary hash.

Proposed integration must therefore:

- Verify the custom artifact against an independent, reviewed local provenance
  manifest before any installer or application executes it. Enforce exact API/
  executable version agreement and a private/non-writable tool location. Missing,
  modified, wrong-platform, wrong-version or metadata-free artifacts must fail
  before upstream's warning/fallback can execute a different binary.
- Try the installation contract in a new isolated fixture first, not existing
  `node_modules` or the shared pnpm store. Test a scoped, locally packaged
  platform dependency supplied from Stage A plus the documented binary override.
  Keep the publisher's JS package SRI and `esbuild.binaryHashes` unchanged;
  give the locally built platform artifact its own recorded identity/integrity.
  The exact pnpm/npm local-artifact override representation remains a feasibility
  gate: generate each lock with its native tool, verify clean reinstall and CLI/
  API behavior, and stop if either tool cannot represent it reproducibly. Do not
  hand-edit lockfiles, disable all optional packages or create a fake publisher
  hash. Scope this to Console's Linux x64 esbuild, not Desktop/BridgeUI.
- Align both Console locks to 0.28.2 within the owners' supported ranges. Keep
  release-age controls, script allowlists, TLS and package integrity enabled.
  Installation with a configured override may generate absolute-path shims;
  test path relocation explicitly instead of copying a host path into Docker.
- Put the validated static binary at the same absolute `/opt/omerta-tools/`
  path in Docker deps, builder and runner stages. Verify its digest before
  scripts, Prisma/bootstrap compilation and the final non-root execution check.
  Use an explicit narrow build-context input, never expose the surrounding
  toolchain directory or secrets. `.dockerignore` and COPY need review.
- Inventory **every** Go ELF in each fresh install/image, including optional
  packages, CLI hardlinks and cached copies. An unused metadata-free publisher
  ELF still present in the distributable is not fixed by an override; do not
  skip it in scanning. If packaging leaves such copies, Stage B fails until a
  reviewed clean assembly excludes them from the new artifact. Existing user
  files, old images, dependency stores and volumes must not be deleted. Any
  required change to this packaging proposal needs a reviewed patch/decision.

Expected affected modules after approval: a focused builder/verifier and pinned
input manifest under `scripts/` (exact names chosen with implementation),
`console/package.json`, both Console locks, `console/pnpm-workspace.yaml`,
`console/Dockerfile`, relevant CI Console job, regression tests and reproducibility
instructions. Reuse current resource guards and child-exit-race handling; do not
blindly promote ignored experimental runners to supported scripts. No Control,
Gateway or Runtime protocol, tenant/auth boundary, secret contract, public API,
database/schema/migration, persistent volume name or topology change is needed.
The new supply-chain manifest is tooling metadata, not an application schema.

## Consolidated validation order after approval

1. Unit-test verifier failures: bad archive/binary digest, missing metadata,
   missing/relative/fallback path, wrong version/target and writable binary.
   Reuse the preserved publisher binary as the negative coverage fixture without
   modifying it. Assert wrapper failure even when a mocked scanner exits zero.
2. Run Stage A build/tests, repeat-build comparison, scan and SBOM sequentially.
3. Validate Stage B clean frozen pnpm install and secondary npm `ci` in separate
   fixtures; real esbuild CLI plus sync/async JS API, tsx typed ESM/CJS and Vite.
   Confirm the invoked executable by path/hash, not just its version string.
4. Run `tests/architecture/test_javascript_toolchain.py`, Console's complete
   collected Vitest suite (including Prisma wrapper tests), Prisma generation
   without checksum-ignore, bootstrap TypeScript compilation, both explicit
   dependency audits, one production build and Next trace-reference checks.
   Use repository commands in the reproducibility guide; do not change collection
   filters, timeout policy or assertions to make the result pass.
5. Render canonical Compose quietly; build only the affected Console image,
   with a unique source-SHA tag, no simultaneous image builds and a successful
   export exit required. Verify payload, UID, every Go ELF, SBOM and full image
   scan. Host-only tests do not imply Docker acceptance.
6. Resume the separate outstanding P4 image/Python gates and then approved
   one-worker live request/restart/persistence acceptance. Rebuild the affected
   services sequentially; do not assume old successful images prove the new tree.
   Keep failed, blocked and skipped gates in the aggregate report.

## Capacity gate and reversible operator choices

Fresh `df -h .`: root `/dev/sda2` is 234G total, 218G used, 3.8G available,
99% full. Existing inspection found no separate attached data disk. `/tmp`,
the worktree and validation root share this filesystem. Docker image/cache
logical sizes overlap; they are not an additive physical-free-space forecast.
No cache entry has been proven exclusively owned by this task. A reclaimable
or unshared BuildKit record is not proof of ownership; no deletion list is
approved or proposed as safe based only on those flags.

Plan for at least **15 GiB free** on Docker's actual storage filesystem before
Console image export. This is a conservative planning budget, not measured
peak use or a guarantee. Estimate 1-3 GiB incremental task storage for the Go
toolchain, source, two outputs, module/build cache and reports; measure before
committing to the image build. Start one subprocess/scenario at a time, `-p=1`,
at most two concurrent Go execution processors (not a hard OS-thread limit);
estimated compiler working budget 0.75-1.5 GiB, not a measured bound.
`GOMEMLIMIT` is a soft limit, not a hard RSS cap.

Use the existing monitor with a bounded timeout for every heavy operation.
Stop and reap owned processes when MemAvailable falls below 1 GiB or free disk
falls below 3 GiB; never lower guards to pass. Retain partial logs/artifacts and
report cancellation as failure, including an interrupted export with a surviving
image tag. Do not touch another worker's process groups or services.

Capacity paths to choose **before heavy Console image export** (bounded Stage A
attempts still enforce the existing 3 GiB free-disk guard):

1. Operator supplies an adequately sized mounted destination. Read-only check
   `findmnt -T PATH` and `df -B1 PATH`; the task may use a new owned directory
   there after path confirmation. This helps only tool/cache outputs; an external
   directory alone does not give the existing Docker daemon more export space.
2. Operator explicitly approves an exact, independently reviewed item list for
   reclamation, coordinated with other workers and with verified expected
   physical headroom. No wildcard/prune, no volumes and no inferred ownership.
3. Operator provides a separate suitable build host/daemon under separate
   authority. Moving this host's Docker root/storage driver or editing daemon
   configuration is not included in this proposal.

At current capacity, retain the build block; do not try another heavy export.
The Python wheel DNS/production closure/pip-audit block and five existing low
Bandit findings are independent open gates, not fixed by this proposal.

## Rollback and completion

Keep old artifacts/checkpoints untouched and use new run/image names. A reviewed
revert of future tooling/lock/Docker patches restores the prior installation
contract without schema/data restore; never reset history or prune volumes.
Reverting to an opaque/vulnerable binary restores a known limitation and cannot
be called successful security remediation. Human review remains required before
merge or production use; no push, merge or publication is part of this work.

The proposal alone has no runtime or evidence-level upgrade. Completion of the
future esbuild repair requires successful coverage and vulnerability gates for
the actual distributed binary/image, not just a clean source audit, SBOM creation
or successful version command. Full P4 and later phases remain separately gated.

Validation of this document: `git diff --check` exited 0; a read-only Node check
of both changed Markdown documents exited 0 with nine existing local link
targets and balanced code fences. No application suites, compiler build, image
export, vulnerability scan or live acceptance were rerun for this docs-only
change. The checks validate document structure, not the proposed implementation.
