/**
 * 把 Astra 0–100 标签做成与教师同任务的 SFT jsonl（facet 折）。
 *
 * 无 labels.jsonl 时退出 `cpdb_qlora_labels_missing`，不回落到 hybrid/v3。
 * `--smoke` 用 3 条伪造合法分做格式冒烟。
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { foldIndexSets } from './lib/splits.mjs';
import {
  ASTRA_LABELS_MISSING,
  CPDB_SCORE100_ANNOTATOR_ID,
  CPDB_SCORE100_ARTIFACT_ID,
  parseScore100,
  renderAstraCompletion,
  renderAstraPrompt,
  toAstraBlindCard,
  validateAstraRow,
} from './lib/score100.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const DATA = join(HERE, 'data', 'full');
const ARTIFACT = join(HERE, 'artifacts', CPDB_SCORE100_ARTIFACT_ID);
const DEFAULT_LABELS = join(ARTIFACT, 'labels.jsonl');

function parseArgs(argv) {
  const out = {
    labels: DEFAULT_LABELS,
    out: join(ARTIFACT, 'sft'),
    fold: 0,
    smoke: false,
  };
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--labels') out.labels = String(argv[++i]);
    else if (argv[i] === '--out') out.out = String(argv[++i]);
    else if (argv[i] === '--fold') out.fold = Number(argv[++i]) || 0;
    else if (argv[i] === '--smoke') out.smoke = true;
  }
  return out;
}

function readJsonl(path) {
  if (!existsSync(path)) return [];
  return readFileSync(path, 'utf8')
    .replace(/^\uFEFF/, '')
    .trim()
    .split('\n')
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

function smokeLabels(cards) {
  const samples = [
    { dependency: 64, similarity: 18, rationale: 'smoke: 跨职能有部分 IO 对应' },
    { dependency: 8, similarity: 81, rationale: 'smoke: 同职能更像替换' },
    { dependency: 91, similarity: 4, rationale: 'smoke: 左方产出正好是右方核心输入' },
  ];
  return cards.slice(0, 3).map((card, at) => ({
    id: card.id,
    annotatorId: CPDB_SCORE100_ANNOTATOR_ID,
    ...samples[at],
  }));
}

function toSftRow(card, label, split) {
  const checked = validateAstraRow(label, { knownIds: new Set([card.id]) });
  if (!checked.ok) throw new Error(`cpdb_sft_label_invalid:${card.id}:${checked.code}`);
  const blind = toAstraBlindCard(card);
  return {
    id: card.id,
    split,
    prompt: renderAstraPrompt(blind),
    completion: renderAstraCompletion(checked.row),
    supervised: true,
  };
}

export function buildCpdbSft({
  labelsPath = DEFAULT_LABELS,
  outDir = join(ARTIFACT, 'sft'),
  dataDir = DATA,
  fold = 0,
  smoke = false,
} = {}) {
  const cards = readJsonl(join(dataDir, 'annotation_cards.jsonl'));
  const pairs = readJsonl(join(dataDir, 'pairs.jsonl'));
  const cardById = new Map(cards.map((card) => [card.id, card]));
  const pairById = new Map(pairs.map((pair) => [pair.id, pair]));

  let labels = readJsonl(labelsPath);
  if (smoke) {
    labels = smokeLabels(cards);
    outDir = join(outDir, 'smoke');
  } else if (!existsSync(labelsPath) || !labels.length) {
    const error = new Error(ASTRA_LABELS_MISSING);
    error.code = ASTRA_LABELS_MISSING;
    throw error;
  }

  const labeledPairs = [];
  const rowsById = new Map();
  for (const label of labels) {
    const card = cardById.get(label.id);
    const pair = pairById.get(label.id);
    if (!card || !pair) continue;
    if (parseScore100(label.dependency) === null || parseScore100(label.similarity) === null) continue;
    labeledPairs.push(pair);
    rowsById.set(label.id, { card, label, pair });
  }
  if (!labeledPairs.length) {
    const error = new Error(ASTRA_LABELS_MISSING);
    error.code = ASTRA_LABELS_MISSING;
    throw error;
  }

  const folds = foldIndexSets(labeledPairs, 'facet');
  const evalFold = Math.min(Math.max(0, fold), folds.k - 1);
  const evalIds = new Set(folds.sets[evalFold].evalIndices.map((at) => labeledPairs[at].id));

  const train = [];
  const development = [];
  for (const pair of labeledPairs) {
    const item = rowsById.get(pair.id);
    const split = evalIds.has(pair.id) ? 'development' : 'train';
    const row = toSftRow(item.card, item.label, split);
    if (split === 'development') development.push(row);
    else train.push(row);
  }

  if (smoke && development.length === 0 && train.length) {
    development.push({ ...train[train.length - 1], split: 'development' });
  }
  if (smoke && train.length === 0 && development.length) {
    train.push({ ...development[0], split: 'train' });
  }

  mkdirSync(outDir, { recursive: true });
  writeFileSync(join(outDir, 'train.jsonl'), `${train.map((row) => JSON.stringify(row)).join('\n')}\n`, 'utf8');
  writeFileSync(join(outDir, 'development.jsonl'), `${development.map((row) => JSON.stringify(row)).join('\n')}\n`, 'utf8');
  const manifest = {
    schemaVersion: 'cpdb-sft-v1',
    task: 'cpdb_score100_sft',
    annotatorId: CPDB_SCORE100_ANNOTATOR_ID,
    smoke,
    scheme: 'facet',
    evalFold,
    k: folds.k,
    rows: { train: train.length, development: development.length },
    note: 'Facet fold hold-out. Not org test. Completion is generative JSON, not a 101-class head.',
  };
  writeFileSync(join(outDir, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
  return { outDir, ...manifest.rows, evalFold, k: folds.k };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  try {
    const result = buildCpdbSft(args);
    process.stdout.write(`${JSON.stringify({ status: 'ok', ...result }, null, 2)}\n`);
  } catch (error) {
    if (error.code === ASTRA_LABELS_MISSING || error.message === ASTRA_LABELS_MISSING) {
      console.error(ASTRA_LABELS_MISSING);
      process.exit(2);
    }
    throw error;
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main();
}
