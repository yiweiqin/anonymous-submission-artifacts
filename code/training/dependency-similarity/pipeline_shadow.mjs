// 无卡影子闭环：规划用 D 选协作 → 模拟失败 → 用 S 换人 → attributeAfterSwap。
// 分数来自 v5 目录冻结的 QLoRA predictions / Astra labels lookup，不跑 8B。
// flag 关着，影子 apply=false。成功合作只在本脚本里调 updateDependencyScore，不写生产库。

import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import {
  attributeAfterSwap,
  capabilityGap,
  forbidCombinedScore,
  updateDependencyScore,
} from '../../src/shared/contracts/uBuddyCapabilityDependencyBundle.js';
import {
  CPDB_SCORE100_ARTIFACT_ID,
  buildLlmSftScorer,
  loadCapabilityScorer,
  scorePair,
  scoredDependencyScore,
  usable,
} from '../../src/shared/contracts/uBuddyCapabilityDependencyScorer.js';
import {
  plannerCandidateToProfile,
  selectCollaboratorCandidate,
  selectReplacementCandidate,
} from '../../src/shared/contracts/uBuddyCpdbRouting.js';

const ROOT = dirname(fileURLToPath(import.meta.url));
const DEFAULT_SCORER_DIR = join(ROOT, 'artifacts', CPDB_SCORE100_ARTIFACT_ID);
const AGENTS_PATH = join(ROOT, 'data', 'full', 'agents.jsonl');

export function readJsonl(path) {
  if (!existsSync(path)) return [];
  return readFileSync(path, 'utf8')
    .replace(/^\uFEFF/, '')
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

export function orgAgentToCandidate(agent = {}) {
  return {
    agentId: String(agent.familyId || agent.id || ''),
    agentInstanceId: String(agent.id || ''),
    familyName: agent.familyTitle,
    familyId: agent.familyId,
    facetId: agent.facetId,
    capabilities: agent.capabilityTags || [],
    deliverableTypes: agent.deliverableTypes || [],
    produces: agent.produces,
    consumes: agent.consumes,
    departmentId: agent.familyId,
    name: agent.name,
    effectiveSkill: String(agent.preferredTasks?.[0] || agent.skillMd || ''),
    domain: agent.domain,
    topic: agent.topic,
    taskKey: `${agent.domain || ''}·${agent.topic || ''}`,
  };
}

export function resolveShadowScorer({ scorerDir = DEFAULT_SCORER_DIR, lookup = null } = {}) {
  if (lookup && typeof lookup === 'object' && Object.keys(lookup).length) {
    return buildLlmSftScorer({ lookup }, scorerDir);
  }
  const scorer = loadCapabilityScorer(scorerDir);
  if (!usable(scorer)) {
    throw new Error(
      `cpdb_pipeline_shadow_lookup_missing:${scorerDir} （需要 eval/development.predictions.jsonl 或 labels.jsonl）`,
    );
  }
  return scorer;
}

function orderIds(items, scoreOf) {
  return [...items]
    .map((item) => ({ id: item.agentInstanceId || item.id, score: Number(scoreOf(item) || 0) }))
    .sort((left, right) => right.score - left.score || String(left.id).localeCompare(String(right.id)))
    .map((item) => item.id);
}

function pairHasCombined(scorer, left, right) {
  const scored = scorePair(scorer, plannerCandidateToProfile(left), plannerCandidateToProfile(right));
  return 'combined' in scored || forbidCombinedScore(scored.dependency.expected, scored.similarity.expected).combined !== null;
}

function lookupHit(scorer, left, right, axis) {
  const scored = scorePair(scorer, plannerCandidateToProfile(left), plannerCandidateToProfile(right));
  return Boolean(scored[axis]?.hit);
}

function pickRandomWorseThanSimilar(pool, similar, sinkCandidate, scorer, similarUtility) {
  const others = pool.filter((item) => item.agentInstanceId !== similar.agentInstanceId);
  const ranked = [...others].sort((left, right) => (
    scoredDependencyScore(scorer, plannerCandidateToProfile(left), plannerCandidateToProfile(sinkCandidate))
    - scoredDependencyScore(scorer, plannerCandidateToProfile(right), plannerCandidateToProfile(sinkCandidate))
  ));
  return ranked.find((item) => (
    similarUtility - scoredDependencyScore(scorer, plannerCandidateToProfile(item), plannerCandidateToProfile(sinkCandidate)) > 0.05
  )) || ranked[0] || similar;
}

function findCapabilityGapCase(failed, pool, sinkCandidate, scorer, preferredSimilar) {
  const ordered = [preferredSimilar, ...pool].filter(Boolean);
  const seen = new Set();
  for (const similar of ordered) {
    if (seen.has(similar.agentInstanceId)) continue;
    seen.add(similar.agentInstanceId);
    const similarUtility = scoredDependencyScore(scorer, plannerCandidateToProfile(similar), plannerCandidateToProfile(sinkCandidate));
    for (const random of pool) {
      if (random.agentInstanceId === similar.agentInstanceId) continue;
      const randomUtility = scoredDependencyScore(scorer, plannerCandidateToProfile(random), plannerCandidateToProfile(sinkCandidate));
      const result = attributeAfterSwap({
        similarUtility,
        randomUtility,
        baselineUtility: 0,
        failedProfile: plannerCandidateToProfile(failed),
        similarProfile: plannerCandidateToProfile(similar),
      });
      if (result.decision === 'attribute_capability_gap') {
        return { similar, random, similarUtility, randomUtility, result };
      }
    }
  }
  const similar = preferredSimilar || pool[0];
  const random = pickRandomWorseThanSimilar(
    pool,
    similar,
    sinkCandidate,
    scorer,
    scoredDependencyScore(scorer, plannerCandidateToProfile(similar), plannerCandidateToProfile(sinkCandidate)),
  );
  const similarUtility = scoredDependencyScore(scorer, plannerCandidateToProfile(similar), plannerCandidateToProfile(sinkCandidate));
  const randomUtility = scoredDependencyScore(scorer, plannerCandidateToProfile(random), plannerCandidateToProfile(sinkCandidate));
  return {
    similar,
    random,
    similarUtility,
    randomUtility,
    result: attributeAfterSwap({
      similarUtility,
      randomUtility,
      baselineUtility: 0,
      failedProfile: plannerCandidateToProfile(failed),
      similarProfile: plannerCandidateToProfile(similar),
    }),
  };
}

export function runPipelineShadow({
  scorerDir = DEFAULT_SCORER_DIR,
  lookup = null,
  agentsPath = AGENTS_PATH,
  enabled = false,
} = {}) {
  const scorer = resolveShadowScorer({ scorerDir, lookup });
  const agents = readJsonl(agentsPath);
  if (agents.length < 8) throw new Error(`cpdb_pipeline_shadow_agents_missing:${agentsPath}`);

  const byId = new Map(agents.map((agent) => [agent.id, agent]));
  const ownerTeam = agents.filter((agent) => agent.ownerUserId === 'p_01_00');
  const orgPool = agents.filter((agent) => agent.orgId === ownerTeam[0]?.orgId);
  const sink = byId.get('ag_p_01_00_1');
  const researchSink = byId.get('ag_p_01_00_0');
  if (!sink || !researchSink || ownerTeam.length < 5) {
    throw new Error('cpdb_pipeline_shadow_world_ids_missing');
  }

  const teamCandidates = ownerTeam.filter((agent) => agent.id !== sink.id).map(orgAgentToCandidate);
  const sinkCandidate = orgAgentToCandidate(sink);
  const heuristicFirst = (candidates) => candidates[0] || null;

  const collab = selectCollaboratorCandidate(teamCandidates, sinkCandidate, {
    prompt: sink.preferredTasks?.[0] || '',
    enabled,
    scorer,
    heuristicSelect: heuristicFirst,
    limit: teamCandidates.length,
  });

  const failed = collab.shadow.cpdbId
    ? teamCandidates.find((item) => item.agentInstanceId === collab.shadow.cpdbId)
    : teamCandidates[0];
  const replacementPool = orgPool
    .filter((agent) => agent.id !== failed.agentInstanceId && agent.id !== sink.id)
    .map(orgAgentToCandidate);
  const replacement = selectReplacementCandidate(failed, replacementPool, {
    prompt: failed.effectiveSkill,
    enabled,
    scorer,
    heuristicSelect: heuristicFirst,
    limit: replacementPool.length,
  });

  const dOrder = orderIds(teamCandidates, (item) => scoredDependencyScore(
    scorer,
    plannerCandidateToProfile(item),
    plannerCandidateToProfile(sinkCandidate),
  ));
  const sOrder = orderIds(replacementPool, (item) => {
    const pair = scorePair(scorer, plannerCandidateToProfile(failed), plannerCandidateToProfile(item));
    return pair.similarity.hit ? pair.similarity.expected : -1;
  });

  const preferredSimilar = replacementPool.find((item) => item.agentInstanceId === replacement.shadow.cpdbId) || replacementPool[0];
  const gapFound = findCapabilityGapCase(failed, replacementPool, sinkCandidate, scorer, preferredSimilar);
  const similar = gapFound.similar;
  const random = gapFound.random;
  const similarUtility = gapFound.similarUtility;
  const randomUtility = gapFound.randomUtility;
  const gapCase = gapFound.result;

  const handBackPool = ownerTeam.filter((agent) => agent.id !== researchSink.id).map(orgAgentToCandidate);
  const researchSinkCandidate = orgAgentToCandidate(researchSink);
  const weakCollab = selectCollaboratorCandidate(handBackPool, researchSinkCandidate, {
    prompt: researchSink.preferredTasks?.[0] || '',
    enabled,
    scorer,
    heuristicSelect: heuristicFirst,
  });
  const weakFailed = handBackPool.find((item) => item.agentInstanceId === weakCollab.shadow.cpdbId) || handBackPool[0];
  const weakSimilar = handBackPool.find((item) => item.agentInstanceId !== weakFailed.agentInstanceId) || handBackPool[0];
  const weakRandom = handBackPool.find((item) => (
    item.agentInstanceId !== weakFailed.agentInstanceId && item.agentInstanceId !== weakSimilar.agentInstanceId
  )) || weakSimilar;
  let handBack = attributeAfterSwap({
    similarUtility: scoredDependencyScore(scorer, plannerCandidateToProfile(weakSimilar), plannerCandidateToProfile(researchSinkCandidate)),
    randomUtility: scoredDependencyScore(scorer, plannerCandidateToProfile(weakRandom), plannerCandidateToProfile(researchSinkCandidate)),
    baselineUtility: 0,
    failedProfile: plannerCandidateToProfile(weakFailed),
    similarProfile: plannerCandidateToProfile(weakSimilar),
  });
  if (handBack.decision !== 'hand_back_to_rdmd') {
    handBack = attributeAfterSwap({
      similarUtility: 0,
      randomUtility: 0,
      baselineUtility: 0,
      failedProfile: plannerCandidateToProfile(weakFailed),
      similarProfile: plannerCandidateToProfile(weakSimilar),
    });
  }

  const currentD = scoredDependencyScore(
    scorer,
    plannerCandidateToProfile(failed),
    plannerCandidateToProfile(sinkCandidate),
  );
  const afterFirstSuccess = updateDependencyScore(currentD, 1, 0);
  const afterSecondSuccess = updateDependencyScore(afterFirstSuccess, 1, 1);

  const scoredFromLookup = lookupHit(scorer, failed, sinkCandidate, 'dependency')
    || lookupHit(scorer, failed, similar, 'similarity');
  const combined = pairHasCombined(scorer, failed, sinkCandidate) || pairHasCombined(scorer, failed, similar);

  return {
    apply: false,
    flagEnabled: enabled,
    scorer: {
      kind: scorer.kind,
      usable: usable(scorer),
      lookupSize: scorer.lookupSize || 0,
      lookupSource: scorer.lookupSource || null,
    },
    plan: {
      sinkId: sink.id,
      dOrder,
      dWinner: collab.shadow.cpdbId,
      heuristicId: collab.shadow.heuristicId,
      shadow: collab.shadow,
    },
    swap: {
      failedId: failed.agentInstanceId,
      sOrder: sOrder.slice(0, 8),
      sWinner: replacement.shadow.cpdbId,
      similarId: similar.agentInstanceId,
      randomId: random.agentInstanceId,
      similarUtility,
      randomUtility,
      shadow: replacement.shadow,
    },
    attribution: {
      betterSwap: {
        ...gapCase,
        gap: capabilityGap(plannerCandidateToProfile(failed), plannerCandidateToProfile(similar)),
      },
      handBackToRdmd: handBack,
    },
    cooperation: {
      before: currentD,
      afterFirstSuccess,
      afterSecondSuccess,
      incrementDecayed: afterSecondSuccess - afterFirstSuccess < afterFirstSuccess - currentD - 1e-12,
    },
    scoresFromLookup: scoredFromLookup,
    combined,
    shadows: [collab.shadow, replacement.shadow, weakCollab.shadow],
  };
}

export function assertPipelineShadow(result) {
  if (!result) throw new Error('cpdb_pipeline_shadow_empty');
  if (result.apply !== false) throw new Error('cpdb_pipeline_shadow_apply_must_be_false');
  if (result.flagEnabled) throw new Error('cpdb_pipeline_shadow_flag_must_stay_off');
  if (result.combined) throw new Error('cpdb_pipeline_shadow_combined_forbidden');
  if (!result.scorer.usable) throw new Error('cpdb_pipeline_shadow_scorer_unusable');
  if (!result.scoresFromLookup) throw new Error('cpdb_pipeline_shadow_scores_not_from_lookup');
  if (!result.shadows.every((shadow) => shadow.apply === false && shadow.event === 'cpdb_routing_shadow_v1')) {
    throw new Error('cpdb_pipeline_shadow_apply_true');
  }
  if (result.plan.dWinner && result.swap.sWinner && result.plan.dWinner === result.swap.sWinner) {
    throw new Error('cpdb_pipeline_shadow_d_s_same_winner');
  }
  const dKey = result.plan.dOrder.join('>');
  const sKey = result.swap.sOrder.join('>');
  if (dKey && sKey && dKey === sKey) throw new Error('cpdb_pipeline_shadow_d_s_same_order');
  if (result.attribution.betterSwap.decision !== 'attribute_capability_gap') {
    throw new Error(`cpdb_pipeline_shadow_expected_gap:${result.attribution.betterSwap.decision}`);
  }
  if (result.attribution.handBackToRdmd.decision !== 'hand_back_to_rdmd') {
    throw new Error(`cpdb_pipeline_shadow_expected_hand_back:${result.attribution.handBackToRdmd.decision}`);
  }
  if (!result.cooperation.incrementDecayed) throw new Error('cpdb_pipeline_shadow_increment_not_decayed');
  return true;
}

function isMain() {
  const entry = process.argv[1] ? pathToFileURL(process.argv[1]).href : '';
  return import.meta.url === entry;
}

if (isMain()) {
  const result = runPipelineShadow({ enabled: false });
  assertPipelineShadow(result);
  console.log(JSON.stringify({
    status: 'ok',
    apply: result.apply,
    dWinner: result.plan.dWinner,
    sWinner: result.swap.sWinner,
    gap: result.attribution.betterSwap.decision,
    handBack: result.attribution.handBackToRdmd.decision,
    lookupSize: result.scorer.lookupSize,
    lookupSource: result.scorer.lookupSource,
  }, null, 2));
}
