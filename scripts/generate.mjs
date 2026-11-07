import { spawnSync } from 'node:child_process';
import { cp, mkdir, mkdtemp, readFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createClient } from '@hey-api/openapi-ts';

const root = fileURLToPath(new URL('../', import.meta.url));
const check = process.argv.includes('--check');
const temporary = await mkdtemp(path.join(tmpdir(), 'calendar-generate-'));

function run(command, args, cwd = root) {
  const result = spawnSync(command, args, { cwd, stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} завершился с ошибкой`);
}

async function contents(directory) {
  const files = {};
  async function visit(current, relative = '') {
    const entries = await readdir(current, { withFileTypes: true });
    entries.sort((left, right) => left.name.localeCompare(right.name, 'en'));
    for (const entry of entries) {
      const name = path.join(relative, entry.name);
      if (entry.isDirectory()) await visit(path.join(current, entry.name), name);
      else files[name] = await readFile(path.join(current, entry.name), 'utf8');
    }
  }
  await visit(directory);
  return files;
}

try {
  const openapi = path.join(temporary, 'openapi');
  const models = path.join(temporary, 'models.py');
  const sdk = path.join(temporary, 'sdk');
  run(path.join(root, 'node_modules/.bin/tsp'), [
    'compile', 'specs', '--output-dir', openapi,
  ]);
  await createClient({
    input: path.join(openapi, 'openapi.json'),
    output: sdk,
    plugins: ['@hey-api/typescript', '@hey-api/sdk', '@hey-api/client-fetch'],
  });
  run('uv', [
    'run', '--locked', 'datamodel-codegen',
    '--input', path.join(openapi, 'openapi.json'),
    '--input-file-type', 'openapi',
    '--output', models,
    '--output-model-type', 'pydantic_v2.BaseModel',
    '--target-python-version', '3.13',
    '--formatters', 'builtin',
    '--disable-timestamp',
    '--custom-file-header', '# Generated from specs/main.tsp. Do not edit.',
  ], path.join(root, 'apps/backend'));
  run('uv', ['run', '--locked', 'ruff', 'check', '--select', 'I', '--fix', models], path.join(root, 'apps/backend'));
  run('uv', ['run', '--locked', 'ruff', 'format', models], path.join(root, 'apps/backend'));

  const outputs = [
    [path.join(openapi, 'openapi.json'), path.join(root, 'specs/generated/openapi.json')],
    [models, path.join(root, 'apps/backend/app/generated/models.py')],
    [sdk, path.join(root, 'apps/frontend/src/api/generated')],
  ];
  for (const [source, destination] of outputs) {
    if (check) {
      const isSdk = source === sdk;
      const expected = isSdk ? await contents(source) : await readFile(source, 'utf8');
      let actual;
      try {
        actual = isSdk ? await contents(destination) : await readFile(destination, 'utf8');
      } catch (error) {
        if (error.code !== 'ENOENT') throw error;
      }
      if (JSON.stringify(actual) !== JSON.stringify(expected)) {
        throw new Error(`Устарел ${path.relative(root, destination)}. Выполните make generate.`);
      }
    } else {
      await mkdir(path.dirname(destination), { recursive: true });
      await rm(destination, { recursive: true, force: true });
      await cp(source, destination, { recursive: true });
    }
  }
} finally {
  await rm(temporary, { recursive: true, force: true });
}
