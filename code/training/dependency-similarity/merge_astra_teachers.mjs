/**
 * 把多份 Astra 0–100 回标合成一份教师：每轴取中位数，rationale 取离中位最近的那份。
 * 不写 data/full/human_labels.jsonl。
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { validateAstraRow } from './lib/score100.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const CARDS = join(HERE, 'data', 'full', 'annotation_cards.jsonl');

function readJsonl(path) {
  return readFileSync(path, 'utf8')
    .replace(/^\uFEFF/, '')
    .trim()
    .split('\n')
    .filter(Boolean)
    .map((line, at) => {
      try {
        return { ok: true, row: JSON.parse(line), line: at + 1, path };
      } catch (error) {
        return { ok: false, error: String(error?.message || error), line: at + 1, path };
      }
    });
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2) return sorted[mid];
  return Math.round((sorted[mid - 1] + sorted[mid]) / 2);
}

function parseArgs(argv) {
  const inputs = [];
  let out = '';
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--out') out = String(argv[++i]);
    else if (argv[i] === '--in') inputs.push(String(argv[++i]));
    else inputs.push(argv[i]);
  }
  return { inputs, out };
}

export function mergeAstraTeachers(paths, { cardsPath = CARDS } = {}) {
  const knownIds = new Set(readJsonl(cardsPath).filter((item) => item.ok).map((item) => item.row.id));
  const byId = new Map();
  const rejects = [];
  for (const path of paths) {
    for (const item of readJsonl(path)) {
      if (!item.ok) {
        rejects.push({ path, line: item.line, code: 'json_parse' });
        continue;
      }
      const checked = validateAstraRow(item.row, { knownIds });
      if (!checked.ok) {
        rejects.push({ path, line: item.line, id: item.row?.id, code: checked.code });
        continue;
      }
      if (!byId.has(checked.row.id)) byId.set(checked.row.id, []);
      byId.get(checked.row.id).push({ ...checked.row, source: path });
    }
  }

  const rows = [];
  const stats = { ids: byId.size, with3: 0, with2: 0, with1: 0, maeD: 0, maeS: 0, nPair: 0 };
  for (const id of [...knownIds].sort()) {
    const votes = byId.get(id) || [];
    if (votes.length === 0) continue;
    if (votes.length >= 3) stats.with3 += 1;
    else if (votes.length === 2) stats.with2 += 1;
    else stats.with1 += 1;
    const dependency = median(votes.map((row) => row.dependency));
    const similarity = median(votes.map((row) => row.similarity));
    let best = votes[0];
    let bestDist = Infinity;
    for (const vote of votes) {
      const dist = Math.abs(vote.dependency - dependency) + Math.abs(vote.similarity - similarity);
      if (dist < bestDist) {
        best = vote;
        bestDist = dist;
      }
    }
    if (votes.length >= 2) {
      stats.nPair += 1;
      stats.maeD += votes.reduce((sum, row) => sum + Math.abs(row.dependency - dependency), 0) / votes.length;
      stats.maeS += votes.reduce((sum, row) => sum + Math.abs(row.similarity - similarity), 0) / votes.length;
    }
    rows.push({
      id,
      dependency,
      similarity,
      rationale: best.rationale,
      sources: votes.length,
    });
  }
  if (stats.nPair) {
    stats.maeD = Number((stats.maeD / stats.nPair).toFixed(3));
    stats.maeS = Number((stats.maeS / stats.nPair).toFixed(3));
  }
  return { rows, rejects, stats };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.inputs.length < 2 || !args.out) {
    throw new Error('usage: node merge_astra_teachers.mjs --out <file> --in a.jsonl --in b.jsonl --in c.jsonl');
  }
  const result = mergeAstraTeachers(args.inputs);
  writeFileSync(args.out, `${result.rows.map((row) => JSON.stringify({
    id: row.id,
    dependency: row.dependency,
    similarity: row.similarity,
    rationale: row.rationale,
  })).join('\n')}\n`, 'utf8');
  process.stdout.write(`${JSON.stringify({
    status: 'ok',
    out: args.out,
    rows: result.rows.length,
    rejects: result.rejects.length,
    stats: result.stats,
  }, null, 2)}\n`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main();
}
