import assert from 'node:assert/strict';
import childProcess from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import vm from 'node:vm';
import { reviewedArtifact, verifyArtifactIdentity } from './verify_esbuild_artifact.mjs';

const project = process.argv[2];
assert(project && path.isAbsolute(project) && fs.realpathSync(project) === project);
const require = createRequire(path.join(project, 'package.json'));
const fixture = require('./package.json');
assert.match(fixture.name, /^omerta-(npm|pnpm)-esbuild-probe$/);
const binary = '/opt/omerta-tools/esbuild';
verifyArtifactIdentity(binary);
assert.equal(process.env.ESBUILD_BINARY_PATH, binary);
const installedPackage = require('esbuild/package.json');
const publisherPackage = JSON.parse(fs.readFileSync('/inputs/esbuild-publisher-package.json'));
assert.equal(installedPackage.version, reviewedArtifact.api_version);
assert.deepEqual(installedPackage['esbuild.binaryHashes'], publisherPackage['esbuild.binaryHashes']);
const packageRoot = path.dirname(require.resolve('esbuild/package.json'));
const cli = path.join(packageRoot, 'bin/esbuild');
const cliSource = fs.readFileSync(cli, 'utf8');
assert(cliSource.startsWith('#!/usr/bin/env node\n') && cliSource.includes(JSON.stringify(binary)));
assert(fs.readFileSync(path.join(packageRoot, 'lib/main.js'), 'utf8')
  .startsWith(`var ESBUILD_BINARY_PATH = ${JSON.stringify(binary)};\n`));
assert.equal(childProcess.execFileSync(cli, ['--version'], { encoding: 'utf8', timeout: 10000 }).trim(),
  reviewedArtifact.api_version);

const spawned = [];
const spawn = childProcess.spawn;
childProcess.spawn = function (command, args, options) {
  spawned.push({ command, args });
  return spawn.call(this, command, args, options);
};
const esbuild = require('esbuild');
const source = 'const value: number = 42; export { value };';
const options = { loader: 'ts', format: 'cjs' };
function check(result) {
  const module = { exports: {} };
  vm.runInNewContext(result.code, { module, exports: module.exports }, { timeout: 1000 });
  assert.equal(module.exports.value, 42);
}
try {
  check(await esbuild.transform(source, options));
  check(esbuild.transformSync(source, options));
  assert(spawned.some(({ command, args }) => command === binary
    && args.includes(`--service=${reviewedArtifact.api_version}`)));
  for (const [extension, mode] of [['mts', 'esm'], ['cts', 'cjs']]) {
    const filename = path.join(project, `omerta-probe.${extension}`);
    const content = `const value: number = 42; console.log('omerta-${mode}-' + value);\n`;
    if (!fs.existsSync(filename)) fs.writeFileSync(filename, content, { flag: 'wx', mode: 0o600 });
    else assert.equal(fs.readFileSync(filename, 'utf8'), content);
    const result = childProcess.execFileSync(process.execPath, [require.resolve('tsx/cli'), filename],
      { encoding: 'utf8', timeout: 15000 });
    assert.equal(result.trim(), `omerta-${mode}-42`);
  }
  const vite = await import(pathToFileURL(require.resolve('vite')).href);
  check(await vite.transformWithEsbuild(source, 'omerta-probe.ts', options));
} finally {
  childProcess.spawn = spawn;
  esbuild.stop();
}

const inventory = [];
function walk(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(filename);
    else if (entry.isFile()) {
      const fd = fs.openSync(filename, 'r');
      const header = Buffer.alloc(4);
      let size;
      try { size = fs.readSync(fd, header, 0, 4, 0); } finally { fs.closeSync(fd); }
      if (size !== 4 || !header.equals(Buffer.from([0x7f, 0x45, 0x4c, 0x46]))) continue;
      const bytes = fs.readFileSync(filename);
      const looksGo = ['.go.buildinfo', '.gopclntab', 'Go build ID:', 'runtime.goexit']
        .some((marker) => bytes.includes(marker)) || entry.name === 'esbuild';
      const sha256 = crypto.createHash('sha256').update(bytes).digest('hex');
      if (looksGo) {
        assert.equal(sha256, reviewedArtifact.sha256, `Unreviewed Go ELF: ${filename}`);
        assert(bytes.includes('.go.buildinfo'));
      }
      inventory.push({ file: path.relative(project, filename), sha256, looks_go: looksGo });
    }
  }
}
walk(path.join(project, 'node_modules'));
assert(inventory.some((entry) => entry.looks_go));
verifyArtifactIdentity(binary);
console.log(JSON.stringify({ functional_probe: 'passed', project,
  cli: true, async_api_binary_observed: binary, sync_api: true, tsx_esm_cjs: true,
  vite_transform: true, inventory, security_accepted: false }));
