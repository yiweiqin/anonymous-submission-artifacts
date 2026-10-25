# CPDB 训练集与交付打分器 v1

这份包回答的是"**别人拿到它，能不能重训出同一个东西、并且能直接接进系统**"。
两样东西一起给：**训练集**（可以重训、可以换标签、可以换折）和**交付打分器**（直接用）。

- 交付打分器：`artifacts/cpdb-scorer-v3-ship/`
- 训练集：`exports/cpdb-training-set-v1/`
- 绑定关系与全部哈希：`artifacts/cpdb-scorer-v3-ship/manifest.json`

## 交付打分器是什么

**默认是表，不是神经网络。** 这不是偏好，是实测结果：

| 折（留出什么） | 轴 | family 表 | MLP (92 列) | MLP (32 列，无身份列) |
| --- | --- | --- | --- | --- |
| `facet` 换一个没见过的**角色** | similarity | **0.7816** | 0.7669 | 0.7477 |
| `facet` 换一个没见过的**角色** | dependency | **0.7657** | 0.7156 | 0.7332 |
| `family` 换一个没见过的**职能** | similarity | **0.5899** | 0.5439 | 0.5544 |

最后一行的读法：换一个粗粒度职能时，MLP 的相似度**低于"永远猜众数"**（0.5899）。
这不说明"模型训练得不好"，而说明**标签本身几乎没有超出 (familyL, familyR) 的分辨率** ——
无论规则 teacher 还是 AI 判分，都在主要对两侧的粗粒度职能起反应。
标签里没有的信息，参数再多也变不出来。

所以交付物是 36 格的表：几 KB、可解释、某一格不对可以直接手改而不必重训，
而且**指标是真正的折上泛化**（表不需要训练，所以能逐折留出；全量重训的 MLP 只能报拟合值）。

表里的值仍然是**从标签学来的**，不是手写规则 —— 这正是方案二想改进的那一点：
它不会带上 teacher 那条"同族一律压到 0"的悬崖。

## 怎么接进系统

```js
import { loadCapabilityScorer, scoredDependencyScore, scoredSelectReplacement, describeScorerFallback }
  from './src/shared/contracts/uBuddyCapabilityDependencyScorer.js';

const scorer = loadCapabilityScorer('artifacts/cpdb-scorer-v3-ship');   // 表优先，其次 model/
describeScorerFallback(scorer).mode;                               // 'table' | 'model' | 'rule'

scoredDependencyScore(scorer, plannerProfile, specialistProfile);  // 规划：选互补
scoredSelectReplacement(scorer, failedProfile, candidates);        // 归因：选最像的换上去
```

三个入口与 `uBuddyCapabilityDependencyBundle.js` 的那三个**形状一致，可直接替换**。
	exttt{scorer} 为空时自动回落到手写规则，且这件事可以用 `describeScorerFallback` 读出来。

## 训练集里有什么

| 文件 | 是什么 |
| --- | --- |
| `matrix.json` | 规格：行数、维度、词表、特征名、特征变体列、四种折、标签来源、全部输入的 sha256 |
| `X.f32` | n × d 的 float32 特征矩阵（小端），行序与 `rows.jsonl` 一致 |
| `y_dependency.i8` / `y_similarity.i8` | n 个 0..4 的档位下标 |
| `rows.jsonl` | `{index,id,split,kind}`，**不含标签**（防下游误把答案拼进特征） |
| `folds.jsonl` | 四种留出方案 + 查表键 |
| `labels.jsonl` | `{id,dependency,similarity}`，便于核对标签来源 |

重训命令写在 `manifest.json` 的 `trainingSet.retrain` 里。

## 必须知道的三条限制

1. **标签是 AI 生成的，不是人工标注。** 由本机 Qwen3-8B 多数投票得到。
   `human_labels.jsonl` 里没有任何人工标注（有测试在守这条）。
2. **AI 判分对提问措辞敏感**：不同 framing 之间的 qwk 只有 0.2-0.3。所以标签本身的稳定性有上限。
3. **未知家族对会并列**：回落到 prior 后，这些 pair 的分数相同，排序退化为按 agentId。
   这是已量化的（`family` 折 = 0.5899 = 众数），不是意外。
