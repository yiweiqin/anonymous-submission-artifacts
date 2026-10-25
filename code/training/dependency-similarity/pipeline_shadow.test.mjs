import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { assertPipelineShadow, runPipelineShadow } from './pipeline_shadow.mjs';

const ROOT = dirname(fileURLToPath(import.meta.url));
const V5 = join(ROOT, 'artifacts', 'cpdb-scorer-v5-100');
const AGENTS = join(ROOT, 'data', 'full', 'agents.jsonl');

const FIXTURE_LOOKUP = {
  'ag_p_01_00_0>ag_p_01_00_1': { dependency: 88, similarity: 27 },
  'ag_p_01_00_2>ag_p_01_00_1': { dependency: 15, similarity: 34 },
  'ag_p_01_00_3>ag_p_01_00_1': { dependency: 73, similarity: 30 },
  'ag_p_01_00_4>ag_p_01_00_1': { dependency: 23, similarity: 46 },
  'ag_p_01_00_0>ag_p_01_01_4': { dependency: 0, similarity: 57 },
  'ag_p_01_01_4>ag_p_01_00_1': { dependency: 90, similarity: 35 },
  'ag_p_01_00_0>ag_p_01_00_2': { dependency: 81, similarity: 22 },
  'ag_p_01_00_0>ag_p_01_00_3': { dependency: 79, similarity: 32 },
  'ag_p_01_00_0>ag_p_01_00_4': { dependency: 88, similarity: 24 },
  'ag_p_01_00_1>ag_p_01_00_0': { dependency: 0, similarity: 27 },
  'ag_p_01_00_2>ag_p_01_00_0': { dependency: 0, similarity: 22 },
  'ag_p_01_00_3>ag_p_01_00_0': { dependency: 0, similarity: 32 },
  'ag_p_01_00_4>ag_p_01_00_0': { dependency: 0, similarity: 24 },
};

test('pipeline shadow walks D then S then attribution with apply=false', () => {
  let result;
  try {
    result = runPipelineShadow({ scorerDir: V5, agentsPath: AGENTS, enabled: false });
  } catch (error) {
    if (!String(error.message || '').includes('lookup_missing')) throw error;
    result = runPipelineShadow({
      scorerDir: V5,
      lookup: FIXTURE_LOOKUP,
      agentsPath: AGENTS,
      enabled: false,
    });
  }
  assertPipelineShadow(result);
  assert.equal(result.apply, false);
  assert.equal(result.combined, false);
  assert.notEqual(result.plan.dWinner, result.swap.sWinner);
  assert.equal(result.attribution.betterSwap.decision, 'attribute_capability_gap');
  assert.equal(result.attribution.handBackToRdmd.decision, 'hand_back_to_rdmd');
  assert.ok(result.attribution.betterSwap.gap.onlyLeft.length + result.attribution.betterSwap.gap.onlyRight.length > 0);
  assert.equal(result.shadows.every((shadow) => shadow.apply === false), true);
  assert.equal(result.combined, false);
  assert.equal('combined' in (result.plan.shadow || {}), false);
});

test('pipeline shadow loads frozen predictions.jsonl as n/100 lookup', () => {
  const dir = mkdtempSync(join(tmpdir(), 'cpdb-shadow-'));
  try {
    mkdirSync(join(dir, 'eval'), { recursive: true });
    writeFileSync(join(dir, 'policy.json'), JSON.stringify({
      policyId: 'cpdb_score100_v1',
      kind: 'llm_sft',
      scale: '0-100',
    }));
    writeFileSync(
      join(dir, 'eval', 'development.predictions.jsonl'),
      Object.entries(FIXTURE_LOOKUP).map(([id, value]) => JSON.stringify({
        id,
        parsed: { ...value, parseError: false },
      })).join('\n'),
    );
    const result = runPipelineShadow({ scorerDir: dir, agentsPath: AGENTS, enabled: false });
    assertPipelineShadow(result);
    assert.match(String(result.scorer.lookupSource || '').replace(/\\/g, '/'), /development\.predictions\.jsonl$/);
    assert.equal(result.scoresFromLookup, true);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
