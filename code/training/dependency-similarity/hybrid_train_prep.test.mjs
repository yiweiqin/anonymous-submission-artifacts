// 混合口径蒸馏的开训前准备：矩阵出处、41 张政策金标、Python 表对账、MLP 门。
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const ROOT = dirname(fileURLToPath(import.meta.url));
const JANUS = join(ROOT, '..', '..');
const MATRIX_DIR = join(ROOT, 'train_out_hybrid');
const GOLD = join(ROOT, 'exports', 'cpdb-human-review-v1', 'human_labels.policy_hybrid_v1.jsonl');
const JS_TABLE = join(ROOT, 'artifacts', 'cpdb-scorer-v4-hybrid', 'table.json');
const PY_TABLE = join(ROOT, 'artifacts', '_hybrid_table_parity', 'table.json');
const TRAIN_SCRIPT = join(ROOT, 'train_scorer.py');
const SCALE = [0, 0.25, 0.5, 0.75, 1];

function readJsonl(path) {
  return readFileSync(path, 'utf8').split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
}

function argmax(dist = []) {
  let best = 0;
  for (let at = 1; at < dist.length; at += 1) {
    if (Number(dist[at]) > Number(dist[best])) best = at;
  }
  return SCALE[best];
}

function python(args) {
  try {
    return execFileSync('python', [TRAIN_SCRIPT, ...args], {
      cwd: JANUS,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  } catch (error) {
    error.combined = `${error.stdout || ''}${error.stderr || ''}${error.message || ''}`;
    throw error;
  }
}

test('train_out_hybrid 是 8282 行的 policy_hybrid_v1 快照', { skip: !existsSync(join(MATRIX_DIR, 'matrix.json')) }, () => {
  const matrix = JSON.parse(readFileSync(join(MATRIX_DIR, 'matrix.json'), 'utf8'));
  assert.equal(matrix.rows, 8282);
  assert.equal(matrix.dimension, 92);
  assert.equal(matrix.labelSource.file, 'artifacts/cpdb-scorer-v4-hybrid/labels.jsonl');
  assert.deepEqual(matrix.labelSource.annotators, ['policy_hybrid_v1/prelabel']);
  const labels = readJsonl(join(MATRIX_DIR, 'labels.jsonl'));
  assert.equal(labels.length, 8282);
  assert.equal(new Set(labels.map((row) => row.id)).size, 8282);
});

test('41 张政策金标与 hybrid 矩阵同档', {
  skip: !existsSync(join(MATRIX_DIR, 'labels.jsonl')) || !existsSync(GOLD),
}, () => {
  const gold = readJsonl(GOLD);
  assert.equal(gold.length, 41);
  const byId = new Map(readJsonl(join(MATRIX_DIR, 'labels.jsonl')).map((row) => [row.id, row]));
  for (const row of gold) {
    const matrixRow = byId.get(row.id);
    assert.ok(matrixRow, `矩阵缺金标 pair ${row.id}`);
    assert.equal(matrixRow.dependency, row.dependency, `${row.cardId} D`);
    assert.equal(matrixRow.similarity, row.similarity, `${row.cardId} S`);
  }
});

test('Python hybrid 表与 JS v4 表两轴 argmax 对齐', {
  skip: !existsSync(JS_TABLE) || !existsSync(PY_TABLE),
}, () => {
  const js = JSON.parse(readFileSync(JS_TABLE, 'utf8'));
  const py = JSON.parse(readFileSync(PY_TABLE, 'utf8'));
  assert.equal(js.keyKind, 'hybrid_family_facet');
  assert.equal(py.keyKind, 'hybrid_family_facet');
  const familyKeys = new Set([...Object.keys(js.cells || {}), ...Object.keys(py.cells || {})]);
  assert.equal(familyKeys.size, Object.keys(js.cells || {}).length);
  for (const key of familyKeys) {
    assert.equal(argmax(py.cells[key]?.dependency), argmax(js.cells[key]?.dependency), `D ${key}`);
  }
  const facetKeys = new Set([...Object.keys(js.facetCells || {}), ...Object.keys(py.facetCells || {})]);
  assert.equal(facetKeys.size, Object.keys(js.facetCells || {}).length);
  for (const key of facetKeys) {
    assert.equal(argmax(py.facetCells[key]?.similarity), argmax(js.facetCells[key]?.similarity), `S ${key}`);
  }
});

test('标签前缀门挡住 teacher/AI 矩阵', () => {
  let failed = false;
  try {
    python([
      '--fit-table',
      '--matrix-dir', join(ROOT, 'train_out'),
      '--out', join(ROOT, 'artifacts', '_hybrid_table_parity_should_not_write'),
      '--require-label-prefix', 'policy_hybrid_v1',
    ]);
  } catch (error) {
    failed = true;
    assert.match(error.combined, /cpdb_label_prefix_mismatch/);
  }
  assert.equal(failed, true);
});

test('--fit-all 没有判据 3 时被拒绝', { skip: !existsSync(join(MATRIX_DIR, 'matrix.json')) }, () => {
  let failed = false;
  try {
    python([
      '--fit-all',
      '--matrix-dir', MATRIX_DIR,
      '--out', join(ROOT, 'artifacts', '_hybrid_mlp_should_not_write'),
      '--require-label-prefix', 'policy_hybrid_v1',
      '--mlp-gate-diagnosis', join(ROOT, 'artifacts', 'missing-hybrid-diagnosis.json'),
    ]);
  } catch (error) {
    failed = true;
    assert.match(error.combined, /cpdb_fit_all_blocked:no_diagnosis/);
  }
  assert.equal(failed, true);
});
