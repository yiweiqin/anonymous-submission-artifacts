/**
 * 把 Astra 的 0–100 分收回 `artifacts/cpdb-scorer-v5-100/labels.jsonl`。
 *
 * 禁止写 `data/full/human_labels.jsonl`。非法分行进 `rejects.jsonl`，不猜测。
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  ASTRA_LABELS_MISSING,
  CPDB_SCORE100_ANNOTATOR_ID,
  CPDB_SCORE100_ARTIFACT_ID,
  CPDB_SCORE100_POLICY_ID,
  validateAstraRow,
} from './lib/score100.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const DATA = join(HERE, 'data', 'full');
const ARTIFACT = join(HERE, 'artifacts', CPDB_SCORE100_ARTIFACT_ID);
export const DEFAULT_OUT = join(ARTIFACT, 'labels.jsonl');
export const HUMAN_LABELS_PATH = join(DATA, 'human_labels.jsonl');

function parseArgs(argv) {
  const out = { labels: '', out: DEFAULT_OUT, rejects: '', cards: join(DATA, 'annotation_cards.jsonl') };
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--labels') out.labels = String(argv[++i]);
    else if (argv[i] === '--out') out.out = String(argv[++i]);
    else if (argv[i] === '--rejects') out.rejects = String(argv[++i]);
    else if (argv[i] === '--cards') out.cards = String(argv[++i]);
  }
  return out;
}

function readJsonl(path) {
  return readFileSync(path, 'utf8')
    .replace(/^\uFEFF/, '')
    .trim()
    .split('\n')
    .filter(Boolean)
    .map((line, at) => {
      try {
        return { ok: true, row: JSON.parse(line), line: at + 1 };
      } catch (error) {
        return { ok: false, error: String(error?.message || error), line: at + 1, raw: line };
      }
    });
}

function assertNotHumanLabels(outPath) {
  const normalized = resolve(outPath).replace(/\\/g, '/').toLowerCase();
  const forbidden = resolve(HUMAN_LABELS_PATH).replace(/\\/g, '/').toLowerCase();
  if (normalized === forbidden || normalized.endsWith('/data/full/human_labels.jsonl')) {
    throw new Error('cpdb_astra_refuses_human_labels_jsonl');
  }
}

export function importAstraScores({
  labelsPath,
  outPath = DEFAULT_OUT,
  rejectsPath = '',
  cardsPath = join(DATA, 'annotation_cards.jsonl'),
} = {}) {
  if (!labelsPath) throw new Error('cpdb_astra_labels_path_required');
  assertNotHumanLabels(outPath);

  const knownIds = new Set(readJsonl(cardsPath).filter((item) => item.ok).map((item) => item.row.id));
  const accepted = [];
  const rejects = [];
  const seen = new Set();

  for (const item of readJsonl(labelsPath)) {
    if (!item.ok) {
      rejects.push({ line: item.line, code: 'json_parse', detail: { error: item.error } });
      continue;
    }
    const checked = validateAstraRow(item.row, { knownIds });
    if (!checked.ok) {
      rejects.push({ line: item.line, id: item.row?.id, code: checked.code, detail: checked.detail });
      continue;
    }
    if (seen.has(checked.row.id)) {
      rejects.push({ line: item.line, id: checked.row.id, code: 'duplicate_id' });
      continue;
    }
    seen.add(checked.row.id);
    accepted.push({
      ...checked.row,
      annotatorId: CPDB_SCORE100_ANNOTATOR_ID,
      status: 'astra_score',
      labelSource: CPDB_SCORE100_ANNOTATOR_ID,
    });
  }

  mkdirSync(dirname(outPath), { recursive: true });
  writeFileSync(outPath, `${accepted.map((row) => JSON.stringify(row)).join('\n')}${accepted.length ? '\n' : ''}`, 'utf8');

  const rejectFile = rejectsPath || join(dirname(outPath), 'rejects.jsonl');
  writeFileSync(rejectFile, `${rejects.map((row) => JSON.stringify(row)).join('\n')}${rejects.length ? '\n' : ''}`, 'utf8');

  const policyPath = join(dirname(outPath), 'policy.json');
  writeFileSync(policyPath, `${JSON.stringify({
    policyId: CPDB_SCORE100_POLICY_ID,
    kind: 'llm_sft',
    scale: '0-100',
    adapterReady: false,
    annotatorId: CPDB_SCORE100_ANNOTATOR_ID,
    imported: accepted.length,
    rejected: rejects.length,
    note: 'Astra 0–100 教师。adapter 未就绪时 usable=false，规划路径回落规则。tokenizer 不进 Electron。',
  }, null, 2)}\n`, 'utf8');

  return {
    accepted: accepted.length,
    rejected: rejects.length,
    outPath,
    rejectFile,
    missing: accepted.length === 0 ? ASTRA_LABELS_MISSING : null,
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const result = importAstraScores({
    labelsPath: args.labels,
    outPath: args.out,
    rejectsPath: args.rejects,
    cardsPath: args.cards,
  });
  process.stdout.write(`${JSON.stringify({ status: 'ok', ...result }, null, 2)}\n`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main();
}
