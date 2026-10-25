/**
 * 0–100 Astra 盲包 / 回灌 / SFT 入口。泄题没有症状，所以必须有专门测试盯着。
 */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import { buildCpdbSft } from './build_cpdb_sft.mjs';
import { exportAstraScore } from './export_astra_score.mjs';
import { HUMAN_LABELS_PATH, importAstraScores } from './import_astra_scores.mjs';
import {
  ASTRA_LABEL_ROW_SCHEMA,
  ASTRA_LABELS_MISSING,
  parseScore100,
  validateAstraRow,
} from './lib/score100.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DATA = path.join(HERE, 'data', 'full');
const REPO = path.join(HERE, '..', '..');

function readJsonl(file) {
  return readFileSync(file, 'utf8').replace(/^\uFEFF/, '').trim().split('\n').filter(Boolean).map((line) => JSON.parse(line));
}

function tmpDir(t) {
  const dir = mkdtempSync(path.join(os.tmpdir(), 'cpdb-astra-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return dir;
}

test('parseScore100 只收 0–100 整数，拒绝 0.75', () => {
  assert.equal(parseScore100(0), 0);
  assert.equal(parseScore100(100), 100);
  assert.equal(parseScore100(67), 67);
  assert.equal(parseScore100('25'), 25);
  assert.equal(parseScore100(0.75), null);
  assert.equal(parseScore100(67.3), null);
  assert.equal(parseScore100(-1), null);
  assert.equal(parseScore100(101), null);
  assert.equal(parseScore100(null), null);
});

test('schema 拒绝 0.75 与 combined', () => {
  assert.equal(ASTRA_LABEL_ROW_SCHEMA.properties.dependency.type, 'integer');
  assert.equal(ASTRA_LABEL_ROW_SCHEMA.additionalProperties, false);
  const cardId = 'ag_p_01_00_0>ag_p_01_00_1';
  const knownIds = new Set([cardId]);
  assert.equal(validateAstraRow({
    id: cardId, dependency: 0.75, similarity: 10, rationale: 'no',
  }, { knownIds }).ok, false);
  assert.equal(validateAstraRow({
    id: cardId, dependency: 67, similarity: 12, rationale: 'ok', combined: null,
  }, { knownIds }).code, 'combined_score_forbidden');
  assert.equal(validateAstraRow({
    id: cardId, dependency: 67, similarity: 12, rationale: 'ok',
  }, { knownIds }).ok, true);
});

test('smoke 盲包无 kind / combined / 五档 scale / teacher 分', (t) => {
  const out = tmpDir(t);
  const result = exportAstraScore({
    out,
    dataDir: DATA,
    limit: 3,
    generatedAt: '2026-09-20T12:00:00Z',
  });
  assert.equal(result.cardCount, 3);
  const cards = readJsonl(path.join(out, 'cards.jsonl'));
  assert.equal(cards.length, 3);
  const blob = readFileSync(path.join(out, 'cards.jsonl'), 'utf8');
  for (const leak of ['"kind"', '"combined"', '"scale"', '"teacher"', '"human"', 'hard_negative', 'initDependency']) {
    assert.equal(blob.includes(leak), false, `cards.jsonl leaked ${leak}`);
  }
  for (const card of cards) {
    assert.deepEqual(Object.keys(card).sort(), ['id', 'left', 'right'].sort());
    assert.ok(card.left.skillDigest);
    assert.ok(card.right.family);
  }
  const task = readFileSync(path.join(out, 'TASK.zh-CN.md'), 'utf8');
  assert.match(task, /允许任何 0–100 整数/);
  assert.match(task, /软先验/);
  assert.doesNotMatch(task, /不许给别的值/);
  const reference = readJsonl(path.join(out, 'reference', 'human_review_v1_five_bin.jsonl'));
  assert.equal(reference.length, 41);
  assert.ok(reference.every((row) => row.gold === false));
  assert.ok(reference.every((row) => Number.isInteger(row.dependencyTimes100)));
  const schema = JSON.parse(readFileSync(path.join(out, 'schema', 'label_row.schema.json'), 'utf8'));
  assert.equal(schema.properties.dependency.type, 'integer');
});

test('回灌拒绝写 human_labels.jsonl，非法分行进 rejects', (t) => {
  const dir = tmpDir(t);
  const cards = readJsonl(path.join(DATA, 'annotation_cards.jsonl')).slice(0, 3);
  const labelsPath = path.join(dir, 'astra.jsonl');
  writeFileSync(labelsPath, [
    JSON.stringify({ id: cards[0].id, dependency: 64, similarity: 18, rationale: 'ok' }),
    JSON.stringify({ id: cards[1].id, dependency: 0.75, similarity: 10, rationale: 'five-bin' }),
    JSON.stringify({ id: cards[2].id, dependency: 40, similarity: 8, rationale: 'nope', combined: 0.5 }),
  ].join('\n') + '\n', 'utf8');

  assert.throws(
    () => importAstraScores({ labelsPath, outPath: HUMAN_LABELS_PATH, cardsPath: path.join(DATA, 'annotation_cards.jsonl') }),
    /cpdb_astra_refuses_human_labels_jsonl/,
  );

  const outPath = path.join(dir, 'labels.jsonl');
  const result = importAstraScores({
    labelsPath,
    outPath,
    cardsPath: path.join(DATA, 'annotation_cards.jsonl'),
  });
  assert.equal(result.accepted, 1);
  assert.equal(result.rejected, 2);
  const accepted = readJsonl(outPath);
  assert.equal(accepted[0].annotatorId, 'astra_score_v1');
  assert.equal(accepted[0].dependency, 64);
  const rejects = readJsonl(result.rejectFile);
  assert.equal(rejects.length, 2);
  assert.ok(!outPath.replace(/\\/g, '/').endsWith('data/full/human_labels.jsonl'));
});

test('无 Astra 标签时 SFT 退出 cpdb_qlora_labels_missing；smoke 写出合法 JSON', (t) => {
  const dir = tmpDir(t);
  assert.throws(
    () => buildCpdbSft({ labelsPath: path.join(dir, 'missing.jsonl'), outDir: path.join(dir, 'sft') }),
    (error) => error.code === ASTRA_LABELS_MISSING || error.message === ASTRA_LABELS_MISSING,
  );
  const built = buildCpdbSft({ smoke: true, outDir: path.join(dir, 'sft'), dataDir: DATA });
  assert.ok(built.train >= 1);
  assert.ok(built.development >= 1);
  const train = readJsonl(path.join(built.outDir, 'train.jsonl'));
  const development = readJsonl(path.join(built.outDir, 'development.jsonl'));
  for (const row of [...train, ...development]) {
    const gold = JSON.parse(row.completion);
    assert.equal(parseScore100(gold.dependency) === null, false);
    assert.equal('combined' in gold, false);
    assert.match(row.prompt, /软先验/);
    assert.equal(row.completion.includes('0.75'), false);
  }
});

test('QLoRA 入口无 labels.jsonl 时退出 cpdb_qlora_labels_missing', (t) => {
  const dir = tmpDir(t);
  const result = spawnSync('python', [
    path.join(REPO, 'scripts', 'train_qlora_cpdb.py'),
    '--labels', path.join(dir, 'nope.jsonl'),
    '--output', path.join(dir, 'run'),
  ], { encoding: 'utf8' });
  assert.ok(result.status !== 0);
  assert.match(`${result.stderr || ''}${result.stdout || ''}`, /cpdb_qlora_labels_missing/);
});

test('QLoRA --smoke --prepare-only --skip-tokenize 吃 SFT smoke', (t) => {
  const dir = tmpDir(t);
  const built = buildCpdbSft({ smoke: true, outDir: path.join(dir, 'sft'), dataDir: DATA });
  const result = spawnSync('python', [
    path.join(REPO, 'scripts', 'train_qlora_cpdb.py'),
    '--smoke',
    '--prepare-only',
    '--skip-tokenize',
    '--force',
    '--data', path.join(dir, 'sft'),
    '--output', path.join(dir, 'run'),
  ], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  const manifest = JSON.parse(readFileSync(path.join(dir, 'run', 'run_manifest.json'), 'utf8'));
  assert.equal(manifest.kind, 'llm_sft');
  assert.equal(manifest.head, 'generative_json');
  assert.ok(manifest.rows.train >= 1);
  assert.equal(built.outDir.endsWith('smoke'), true);
});
