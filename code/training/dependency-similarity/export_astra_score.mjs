/**
 * 导出给 Astra 的 0–100 盲包：`exports/cpdb-astra-score-v1/`。
 *
 * 不要复用五档 `TASK.json`。卡面只有画像，没有 teacher / hybrid / AI 五档分、没有 kind、没有 combined。
 *
 *   node experiments/cpdb_org_world/export_astra_score.mjs
 *   node experiments/cpdb_org_world/export_astra_score.mjs --limit 3 --out <tmp>
 */
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describePair, selectReviewPairs } from './lib/humanReviewSelect.mjs';
import {
  ASTRA_BUNDLE_SCHEMA,
  ASTRA_LABEL_ROW_SCHEMA,
  CPDB_SCORE100_ANNOTATOR_ID,
  CPDB_SCORE100_ARTIFACT_ID,
  assertAstraCardBlind,
  score100TaskMarkdown,
  toAstraBlindCard,
} from './lib/score100.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const DATA = join(HERE, 'data', 'full');
const DEFAULT_OUT = join(HERE, 'exports', 'cpdb-astra-score-v1');

function parseArgs(argv) {
  const out = { out: DEFAULT_OUT, dataDir: DATA, limit: 0, generatedAt: '' };
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--out') out.out = String(argv[++i]);
    else if (argv[i] === '--data') out.dataDir = String(argv[++i]);
    else if (argv[i] === '--limit') out.limit = Number(argv[++i]) || 0;
    else if (argv[i] === '--generated-at') out.generatedAt = String(argv[++i]);
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

function sha256Text(text) {
  return createHash('sha256').update(text).digest('hex');
}

function putFile(files, relPath, text) {
  const body = text.endsWith('\n') ? text : `${text}\n`;
  files.set(relPath, body);
  return body;
}

function fiveBinTimes100(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return Math.round(n * 100);
}

function importMarkdown() {
  return [
    '# 把 Astra 的 0–100 分收回来',
    '',
    '把标注文件放到任意路径，然后：',
    '',
    '```bash',
    'npm run experiment:cpdb-astra-import -- --labels <回标文件.jsonl>',
    '```',
    '',
    `默认写入 \`experiments/cpdb_org_world/artifacts/${CPDB_SCORE100_ARTIFACT_ID}/labels.jsonl\`。`,
    `annotatorId 固定为 \`${CPDB_SCORE100_ANNOTATOR_ID}\`。`,
    '',
    '**禁止**写进 `data/full/human_labels.jsonl`。非法分（非整数、越界、缺轴、带 `combined`）进 `rejects.jsonl`，不猜测。',
    '',
    '每行必须是：',
    '',
    '```json',
    '{"id":"与 cards.jsonl 相同","dependency":67,"similarity":12,"rationale":"一句话"}',
    '```',
    '',
  ].join('\n');
}

export function buildFiveBinReference({
  dataDir = DATA,
  here = HERE,
  seed = 20260920,
} = {}) {
  const pairs = readJsonl(join(dataDir, 'pairs.jsonl'));
  const ai = new Map(readJsonl(join(dataDir, 'ai_labels_qwen3_8b_v1.jsonl')).map((row) => [row.id, row]));
  const goldPath = join(here, 'exports', 'cpdb-human-review-v1', 'human_labels.policy_hybrid_v1.jsonl');
  const gold = new Map(readJsonl(goldPath).map((row) => [row.id, row]));
  const hybrid = new Map(readJsonl(join(here, 'artifacts', 'cpdb-scorer-v4-hybrid', 'labels.jsonl')).map((row) => [row.id, row]));

  const records = [];
  for (const pair of pairs) {
    const teacher = {
      dependency: pair.initDependency,
      similarity: pair.initSimilarity,
    };
    const aiRow = ai.get(pair.id);
    if (!aiRow) continue;
    records.push(describePair(pair, teacher, aiRow));
  }
  const { cards: picked } = selectReviewPairs(records, { seed });
  return picked.map((record) => {
    const source = gold.get(record.id) || hybrid.get(record.id) || {
      dependency: record.teacher.dependency,
      similarity: record.teacher.similarity,
    };
    return {
      id: record.id,
      fiveBinDependency: source.dependency,
      fiveBinSimilarity: source.similarity,
      dependencyTimes100: fiveBinTimes100(source.dependency),
      similarityTimes100: fiveBinTimes100(source.similarity),
      gold: false,
      note: '旧五档×100 粗刻度，不是 0–100 金标。回标后可报 Astra 连续分 vs 旧五档相关，不得当训练 y。',
    };
  });
}

export function exportAstraScore({
  out = DEFAULT_OUT,
  dataDir = DATA,
  limit = 0,
  generatedAt = '',
} = {}) {
  const cards = readJsonl(join(dataDir, 'annotation_cards.jsonl'));
  const selected = limit > 0 ? cards.slice(0, limit) : cards;
  const blind = selected.map((card) => assertAstraCardBlind(toAstraBlindCard(card)));
  const files = new Map();
  const at = generatedAt || new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');

  putFile(files, 'TASK.zh-CN.md', score100TaskMarkdown());
  putFile(files, 'schema/label_row.schema.json', `${JSON.stringify(ASTRA_LABEL_ROW_SCHEMA, null, 2)}\n`);
  putFile(files, 'cards.jsonl', `${blind.map((row) => JSON.stringify(row)).join('\n')}\n`);
  putFile(files, 'IMPORT.md', importMarkdown());

  const reference = buildFiveBinReference({ dataDir, here: HERE });
  putFile(files, 'reference/human_review_v1_five_bin.jsonl', `${reference.map((row) => JSON.stringify(row)).join('\n')}\n`);

  const fileMeta = {};
  for (const [rel, text] of files) {
    fileMeta[rel] = {
      bytes: Buffer.byteLength(text),
      sha256: sha256Text(text),
      lines: rel.endsWith('.jsonl') ? text.split('\n').filter(Boolean).length : undefined,
    };
  }
  const bundle = {
    schema: ASTRA_BUNDLE_SCHEMA,
    version: 1,
    generatedAt: at,
    cardCount: blind.length,
    annotatorId: CPDB_SCORE100_ANNOTATOR_ID,
    note: '盲包：无 teacher/hybrid/AI 五档分，无 kind，无 combined。reference/ 仅对照。',
    files: fileMeta,
  };
  putFile(files, 'BUNDLE.json', `${JSON.stringify(bundle, null, 2)}\n`);

  if (existsSync(out)) rmSync(out, { recursive: true, force: true });
  mkdirSync(join(out, 'schema'), { recursive: true });
  mkdirSync(join(out, 'reference'), { recursive: true });
  for (const [rel, text] of files) writeFileSync(join(out, rel), text, 'utf8');

  return { out, cardCount: blind.length, bundle, files: [...files.keys()] };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const result = exportAstraScore(args);
  process.stdout.write(`${JSON.stringify({
    status: 'ok',
    out: result.out,
    cardCount: result.cardCount,
    files: result.files,
  }, null, 2)}\n`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main();
}
