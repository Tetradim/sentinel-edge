import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const testDir = path.dirname(fileURLToPath(import.meta.url));
const assetsDir = path.resolve(testDir, '../dist/assets');

function listJsAssets() {
  return readdirSync(assetsDir).filter((name) => name.endsWith('.js'));
}

function findBuiltAsset(prefix) {
  return listJsAssets().find((name) => name.startsWith(prefix));
}

function readBuiltAsset(assetName) {
  return readFileSync(path.join(assetsDir, assetName), 'utf8');
}

function extractStaticJsImports(assetName) {
  const source = readBuiltAsset(assetName);
  const imports = new Set();
  const sideEffectImportPattern = /(?:^|;)\s*import\s*["']([^"']+\.js)["']/g;
  const fromImportPattern = /(?:^|;)\s*import(?!\s*\()[^;]*?from\s*["']([^"']+\.js)["']/g;

  for (const pattern of [sideEffectImportPattern, fromImportPattern]) {
    let match = pattern.exec(source);
    while (match) {
      imports.add(path.basename(match[1]));
      match = pattern.exec(source);
    }
  }

  return [...imports];
}

function findStaticImportPath(startAsset, targetPredicate) {
  const queue = [[startAsset]];
  const visited = new Set();

  while (queue.length > 0) {
    const pathToAsset = queue.shift();
    const currentAsset = pathToAsset.at(-1);
    if (!currentAsset || visited.has(currentAsset)) continue;
    visited.add(currentAsset);

    if (targetPredicate(currentAsset)) return pathToAsset;

    extractStaticJsImports(currentAsset).forEach((importedAsset) => {
      if (!visited.has(importedAsset) && existsSync(path.join(assetsDir, importedAsset))) {
        queue.push([...pathToAsset, importedAsset]);
      }
    });
  }

  return null;
}

test('built app entry chunk stays below the Sentinel Edge budget', { skip: !existsSync(assetsDir) }, () => {
  const entry = listJsAssets()
    .filter((name) => name.startsWith('index-'))
    .map((name) => ({ name, size: statSync(path.join(assetsDir, name)).size }))
    .sort((a, b) => b.size - a.size)[0];

  assert.ok(entry, 'expected an index JS asset after npm run build');
  assert.ok(
    entry.size < 900 * 1024,
    `expected app entry below 900 KB, received ${Math.round(entry.size / 1024)} KB in ${entry.name}`,
  );
});

test('chart vendor code stays outside the startup graph when emitted', { skip: !existsSync(assetsDir) }, () => {
  const jsAssets = listJsAssets();
  const entryAsset = findBuiltAsset('index-');
  const chartVendorAsset = findBuiltAsset('vendor-charts-');

  assert.ok(findBuiltAsset('vendor-icons-'), `expected vendor-icons chunk, received ${jsAssets.join(', ')}`);
  assert.ok(entryAsset, `expected index chunk, received ${jsAssets.join(', ')}`);

  if (!chartVendorAsset) return;

  const startupChartPath = findStaticImportPath(entryAsset, (assetName) => assetName === chartVendorAsset);
  assert.equal(
    startupChartPath,
    null,
    `expected chart vendor code outside startup graph, found ${startupChartPath?.join(' -> ')}`,
  );
});

test('heavy workspace panels are emitted outside the app entry chunk', { skip: !existsSync(assetsDir) }, () => {
  const jsAssets = listJsAssets();
  const expectedChunks = [
    'UnifiedChartingPanel-',
    'GreeksPanel-',
    'DirectivesPanel-',
    'OperationsPanel-',
    'SettingsPanel-',
    'ProtectionPanel-',
    'SettingsDashboard-',
    'tutorials-',
  ];

  expectedChunks.forEach((prefix) => {
    assert.ok(
      jsAssets.some((name) => name.startsWith(prefix)),
      `expected ${prefix} chunk, received ${jsAssets.join(', ')}`,
    );
  });
});
