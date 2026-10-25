// 用冻结的混合口径重标 8282 对，写出 v4 产物（规则政策 + facet 蒸馏表）。
//
// 不跑 MLP。表的 S 按 facet 对压，D 按 family 对压；线上加载优先 `policy.json`，
// 走 hybrid_rules，表只作对照。
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  CPDB_HYBRID_POLICY_ID,
  UBUDDY_CPDB_VERSION,
  dependencyScore,
  describeHybridPolicy,
  similarityScore,
} from '../../src/shared/contracts/uBuddyCapabilityDependencyBundle.js';
import { CPDB_HYBRID_ARTIFACT_ID, CPDB_SCORER_TABLE_SCHEMA } from '../../src/shared/contracts/uBuddyCapabilityDependencyScorer.js';

const ROOT = dirname(fileURLToPath(import.meta.url));
const DATA = join(ROOT, 'data', 'full');
const OUT = join(ROOT, 'artifacts', CPDB_HYBRID_ARTIFACT_ID);
const SCALE = [0, 0.25, 0.5, 0.75, 1];

function readJsonl(path) {
  return readFileSync(path, 'utf8').replace(/^\uFEFF/, '').trim().split('\n').filter(Boolean).map((line) => JSON.parse(line));
}

function distFromCounts(counts) {
  const total = counts.reduce((sum, value) => sum + value, 0);
  if (!total) return SCALE.map(() => 1 / SCALE.length);
  return counts.map((value) => Number((value / total).toFixed(6)));
}

function bump(map, key, axis, value) {
  if (!map.has(key)) {
    map.set(key, {
      dependency: SCALE.map(() => 0),
      similarity: SCALE.map(() => 0),
    });
  }
  const index = SCALE.indexOf(value);
  if (index >= 0) map.get(key)[axis][index] += 1;
}

function cellsFrom(map) {
  return Object.fromEntries([...map.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([key, counts]) => [
    key,
    {
      dependency: distFromCounts(counts.dependency),
      similarity: distFromCounts(counts.similarity),
    },
  ]));
}

function agentToProfile(agent) {
  return {
    agentId: agent.id,
    familyId: agent.familyId,
    facetId: agent.facetId,
    name: agent.name,
    capabilityTags: agent.capabilityTags,
    supportedTaskTypes: agent.supportedTaskTypes,
    deliverableTypes: agent.deliverableTypes,
    produces: agent.produces,
    consumes: agent.consumes,
    domain: agent.domain,
    topic: agent.topic,
    preferredTasks: agent.preferredTasks,
  };
}

const agents = new Map(readJsonl(join(DATA, 'agents.jsonl')).map((agent) => [agent.id, agent]));
const pairs = readJsonl(join(DATA, 'pairs.jsonl'));
const familyCounts = new Map();
const facetCounts = new Map();
const labels = [];
const tally = { dependency: Object.fromEntries(SCALE.map((value) => [value, 0])), similarity: Object.fromEntries(SCALE.map((value) => [value, 0])) };

for (const pair of pairs) {
  const left = agents.get(pair.leftAgentId);
  const right = agents.get(pair.rightAgentId);
  if (!left || !right) throw new Error(`cpdb_hybrid_relabel_missing_agent:${pair.id}`);
  const leftProfile = agentToProfile(left);
  const rightProfile = agentToProfile(right);
  const dependency = dependencyScore(leftProfile, rightProfile);
  const similarity = similarityScore(leftProfile, rightProfile);
  labels.push({
    id: pair.id,
    annotatorId: CPDB_HYBRID_POLICY_ID,
    status: 'prelabel',
    role: 'prelabel',
    labelSource: 'policy_hybrid_v1',
    dependency,
    similarity,
    split: pair.split,
    kind: pair.kind,
    rationale: 'hybrid policy: same-family D=0, cross-family S=0, facet-near S=0.75, IO+task D',
  });
  tally.dependency[dependency] += 1;
  tally.similarity[similarity] += 1;
  bump(familyCounts, `${left.familyId}>${right.familyId}`, 'dependency', dependency);
  bump(familyCounts, `${left.familyId}>${right.familyId}`, 'similarity', similarity);
  bump(facetCounts, `${left.facetId}>${right.facetId}`, 'dependency', dependency);
  bump(facetCounts, `${left.facetId}>${right.facetId}`, 'similarity', similarity);
}

const familyCells = cellsFrom(familyCounts);
const facetCells = cellsFrom(facetCounts);
const prior = {
  dependency: distFromCounts(SCALE.map((value) => tally.dependency[value])),
  similarity: distFromCounts(SCALE.map((value) => tally.similarity[value])),
};

mkdirSync(OUT, { recursive: true });
writeFileSync(join(OUT, 'labels.jsonl'), `${labels.map((row) => JSON.stringify(row)).join('\n')}\n`);
writeFileSync(join(OUT, 'policy.json'), `${JSON.stringify({
  policyId: CPDB_HYBRID_POLICY_ID,
  version: UBUDDY_CPDB_VERSION,
  artifactId: CPDB_HYBRID_ARTIFACT_ID,
  generatedAt: new Date().toISOString(),
  ...describeHybridPolicy(),
  note: '线上加载本目录时走 hybrid_rules，不走 v3 AI 表。表只是 8282 对上的蒸馏对照。',
}, null, 2)}\n`);

const table = {
  schema: CPDB_SCORER_TABLE_SCHEMA,
  generatedAt: new Date().toISOString(),
  keyKind: 'hybrid_family_facet',
  keyFormat: 'D 用 familyL>familyR；S 用 facetL>facetR',
  featureSpec: 'cpdb_pair_features_v1',
  scale: SCALE,
  cells: familyCells,
  facetCells,
  prior,
  unseenFallback: 'prior',
  labelSource: {
    file: 'artifacts/cpdb-scorer-v4-hybrid/labels.jsonl',
    annotators: [`${CPDB_HYBRID_POLICY_ID}/prelabel`],
  },
  note: 'S 按 facet 对蒸馏（无损：混合口径的 S 只看 family+facet）。D 按 family 对蒸馏会抹掉任务门，所以加载入口优先 policy.json 走规则。',
};
writeFileSync(join(OUT, 'table.json'), `${JSON.stringify(table, null, 2)}\n`);

const manifest = {
  schema: 'cpdb_ship_manifest/v1',
  artifactId: CPDB_HYBRID_ARTIFACT_ID,
  generatedAt: new Date().toISOString(),
  defaultScorer: 'hybrid_rules',
  reason: '41 张人标冻结混合口径。MLP 不做。v3 AI 表降为对照物。',
  rows: labels.length,
  tally,
  familyCellCount: Object.keys(familyCells).length,
  facetCellCount: Object.keys(facetCells).length,
};
writeFileSync(join(OUT, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`);

console.log(JSON.stringify({
  out: OUT,
  rows: labels.length,
  tally,
  familyCellCount: manifest.familyCellCount,
  facetCellCount: manifest.facetCellCount,
}, null, 2));
