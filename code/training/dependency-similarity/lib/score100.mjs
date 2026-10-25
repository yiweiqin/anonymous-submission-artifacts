/**
 * CPDB 0–100 问法、盲卡与校验。Astra 包、回灌、SFT 共用这一份，避免 TASK 漂成另一套题。
 *
 * 五档 `CPDB_SCORE_SCALE` 不从这里出口。新标签只认整数 0–100。
 */
import {
  CPDB_SCORE100_ANCHORS,
  CPDB_SCORE100_ANNOTATOR_ID,
  CPDB_SCORE100_ARTIFACT_ID,
  CPDB_SCORE100_MAX,
  CPDB_SCORE100_MIN,
  CPDB_SCORE100_POLICY_ID,
  parseScore100,
} from '../../../src/shared/contracts/uBuddyCapabilityDependencyBundle.js';

export {
  CPDB_SCORE100_ANCHORS,
  CPDB_SCORE100_ANNOTATOR_ID,
  CPDB_SCORE100_ARTIFACT_ID,
  CPDB_SCORE100_MAX,
  CPDB_SCORE100_MIN,
  CPDB_SCORE100_POLICY_ID,
  parseScore100,
};

export const ASTRA_BUNDLE_SCHEMA = 'cpdb-astra-score-bundle/v1';
export const ASTRA_LABELS_MISSING = 'cpdb_qlora_labels_missing';

export const SCORE100_QUESTIONS = Object.freeze({
  dependency: '规划时，左方产出是否适合作为右方输入？（不要看他们像不像）',
  similarity: '若左方执行不佳，右方是否适合做最小能力改动的替换？（不要看他们是否该协作）',
});

const SIDE_KEYS = Object.freeze(['name', 'family', 'facet', 'tags', 'produces', 'consumes', 'skillDigest']);

/** 卡面禁止出现的键：泄题或把 Astra 推回五档。白名单见 `toAstraBlindSide`。 */
export const ASTRA_FORBIDDEN_CARD_KEYS = Object.freeze([
  'kind',
  'split',
  'human',
  'teacher',
  'combined',
  'combinedScore',
  'scale',
  'ownerUserId',
  'ownerName',
  'orgId',
  'group',
  'machine',
  'initDependency',
  'initSimilarity',
  'contractDependency',
  'contractSimilarity',
  'hybrid',
]);

export const ASTRA_LABEL_ROW_SCHEMA = Object.freeze({
  $schema: 'https://json-schema.org/draft/2020-12/schema',
  $id: 'cpdb-astra-score-v1/label_row',
  type: 'object',
  additionalProperties: false,
  required: ['id', 'dependency', 'similarity', 'rationale'],
  properties: {
    id: { type: 'string', minLength: 1 },
    dependency: { type: 'integer', minimum: CPDB_SCORE100_MIN, maximum: CPDB_SCORE100_MAX },
    similarity: { type: 'integer', minimum: CPDB_SCORE100_MIN, maximum: CPDB_SCORE100_MAX },
    rationale: { type: 'string' },
  },
});

export function score100TaskMarkdown() {
  return [
    '# 依赖分 / 相似度（0–100 连续分）',
    '',
    '每一对给出左、右两个 Agent 的画像：名称（含主职能与细节能力）、标签、产出、输入、技能摘要。',
    '**没有别的信息**（看不到它们属于谁、属于哪个组织、采样 kind、任何教师/混合/AI 五档分）。',
    '唯一能作为判断依据的，就是这几行画像本身。',
    '',
    '## 两个分数（每对都要给两个整数）',
    '',
    `**第一轴 dependency —— ${SCORE100_QUESTIONS.dependency}**`,
    '',
    '只看产物流向：左方的产出能不能当右方的输入。',
    '',
    '| 分 | 含义 |',
    '| --- | --- |',
    '| 0 | 产出与输入完全对不上 |',
    '| 25 | 只有边缘对应 |',
    '| 50 | 部分对应，还要补别的输入 |',
    '| 75 | 是右方主要输入之一 |',
    '| 100 | 正好是右方核心输入 |',
    '',
    `**第二轴 similarity —— ${SCORE100_QUESTIONS.similarity}**`,
    '',
    '只看换上去要改多少细节能力：右方顶左方的位置，改动越小分越高。',
    '',
    '| 分 | 含义 |',
    '| --- | --- |',
    '| 0 | 换上去等于换了件事 |',
    '| 25 | 大方向沾边，细节差得远 |',
    '| 50 | 同大职能，细节部分重合 |',
    '| 75 | 同大职能，细节大部分重合 |',
    '| 100 | 换上去改动最小 |',
    '',
    '中间分按相对这些锚点内插。**允许任何 0–100 整数**，不要再收成五档（不要只给 0 / 25 / 50 / 75 / 100）。',
    '',
    '两轴**互相独立**：不要因为「这两个不该协作」就压低 similarity，也不要因为「这两个可以互相替换」就抬高 dependency。',
    '',
    '## 软先验（不是硬截断）',
    '',
    '- 同大职能时，dependency 往往偏低（更像替换而不是上下游）。',
    '- 跨大职能时，similarity 往往偏低（换上去改动大）。',
    '',
    '你可以给出任何整数；**禁止**因为这条先验把分数夹死在 0 或某个五档上。',
    '',
    '## 怎么填',
    '',
    '对 `cards.jsonl` 每一行输出一行 JSON（不要删行、不要改 `id`）：',
    '',
    '```json',
    '{"id":"与卡面相同的 id","dependency":67,"similarity":12,"rationale":"一句话"}',
    '```',
    '',
    '- `dependency` 与 `similarity` 必须是 **0–100 的整数**。`0.75`、`67.3`、缺轴一律作废。',
    '- 不要写 `combined` / `kind` / 五档小数。',
    `- 回灌后 annotatorId 固定为 \`${CPDB_SCORE100_ANNOTATOR_ID}\`。`,
  ].join('\n');
}

export function toAstraBlindSide(side = {}) {
  return {
    name: side.name ?? '',
    family: side.family ?? '',
    facet: side.facet ?? '',
    tags: Array.isArray(side.tags) ? side.tags : [],
    produces: Array.isArray(side.produces) ? side.produces : [],
    consumes: Array.isArray(side.consumes) ? side.consumes : [],
    skillDigest: side.skillDigest ?? '',
  };
}

export function toAstraBlindCard(card) {
  return {
    id: card.id,
    left: toAstraBlindSide(card.left),
    right: toAstraBlindSide(card.right),
  };
}

export function renderSideMarkdown(side = {}) {
  const tags = Array.isArray(side.tags) ? side.tags.join(', ') : '';
  const produces = Array.isArray(side.produces) ? side.produces.join(', ') : '';
  const consumes = Array.isArray(side.consumes) ? side.consumes.join(', ') : '';
  return [
    `- 名称：${side.name || ''}`,
    `- 主职能：${side.family || ''}`,
    `- 细节能力：${side.facet || ''}`,
    `- 标签：${tags}`,
    `- 产出：${produces}`,
    `- 输入：${consumes}`,
    `- 技能摘要：${side.skillDigest || ''}`,
  ].join('\n');
}

export function renderAstraPrompt(card) {
  const blind = card.left && card.right && !card.kind ? card : toAstraBlindCard(card);
  return [
    score100TaskMarkdown(),
    '',
    '## 这一对',
    '',
    '### 左方',
    renderSideMarkdown(blind.left),
    '',
    '### 右方',
    renderSideMarkdown(blind.right),
    '',
    '只输出一行 JSON：{"dependency":整数,"similarity":整数,"rationale":"一句话"}',
  ].join('\n');
}

export function renderAstraCompletion({ dependency, similarity, rationale = '' }) {
  return JSON.stringify({
    dependency: parseScore100(dependency),
    similarity: parseScore100(similarity),
    rationale: String(rationale || ''),
  });
}

export function validateAstraRow(raw, { knownIds = null } = {}) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return fail('row_not_object');
  }
  if ('combined' in raw || 'combinedScore' in raw) {
    return fail('combined_score_forbidden', { id: raw.id, value: raw.combined ?? raw.combinedScore });
  }
  const id = String(raw.id ?? '').trim();
  if (!id) return fail('id_required');
  if (knownIds && !knownIds.has(id)) return fail('card_not_found', { id });

  const dependency = parseScore100(raw.dependency);
  const similarity = parseScore100(raw.similarity);
  if (dependency === null || similarity === null) {
    return fail('both_scores_required_integers_0_100', {
      id,
      dependency: raw.dependency ?? null,
      similarity: raw.similarity ?? null,
    });
  }
  return {
    ok: true,
    row: {
      id,
      dependency,
      similarity,
      rationale: String(raw.rationale ?? '').trim(),
      annotatorId: CPDB_SCORE100_ANNOTATOR_ID,
    },
  };
}

export function collectForbiddenKeys(value, found = new Set()) {
  if (!value || typeof value !== 'object') return found;
  if (Array.isArray(value)) {
    for (const item of value) collectForbiddenKeys(item, found);
    return found;
  }
  for (const [key, child] of Object.entries(value)) {
    if (ASTRA_FORBIDDEN_CARD_KEYS.includes(key)) found.add(key);
    collectForbiddenKeys(child, found);
  }
  return found;
}

export function assertAstraCardBlind(card) {
  const forbidden = [...collectForbiddenKeys(card)];
  if (forbidden.length) {
    throw new Error(`cpdb_astra_card_leak:${card?.id || '?'}:${forbidden.join(',')}`);
  }
  const keys = Object.keys(card || {});
  if (keys.some((key) => !['id', 'left', 'right'].includes(key))) {
    throw new Error(`cpdb_astra_card_extra_keys:${keys.join(',')}`);
  }
  for (const side of ['left', 'right']) {
    const sideKeys = Object.keys(card[side] || {});
    if (sideKeys.some((key) => !SIDE_KEYS.includes(key))) {
      throw new Error(`cpdb_astra_side_extra_keys:${side}:${sideKeys.join(',')}`);
    }
  }
  return card;
}

function fail(code, detail = {}) {
  return { ok: false, code, detail };
}
