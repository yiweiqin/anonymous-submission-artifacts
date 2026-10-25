# 发起人说明：这批人工标注要裁决什么

> **这一页不要给标注者看。** 他手上只应有 `README.zh-CN.md`、`cards.jsonl`、`policy.json`。

## 一句话

现有两套机器口径在**同主职能**这一格上完全对立，模型指标分不出谁对 —— 只有人能分。

## 分歧长什么样

对 8282 对做两侧分布统计，分歧不是零散的，是结构性的：

| | teacher（手写契约） | AI 判分（Qwen3-8B 多数投票） |
| --- | --- | --- |
| 同 family 的 dependency | **恒为 0**（2640/2640） | 0.5 / 0.75 / 1 |
| 同 family 的 similarity | **恒为 0.75**（2640/2640） | 0.25 / 0.5 / 0.75 / 1 |
| 跨 family 的 similarity | **恒为 0**（5614/5642） | 0 / 0.25 / 0.5 / 0.75 / 1 |

读法：teacher 把「同一个主职能」当成**充分统计量** —— 同职能即互为替代（0.75），
也即不构成上下游（dependency=0，替代关系不是串联关系）；AI 则继续看画像内容，
在同职能内部再分辨，并把大量分数压在中间档。

两者各自都自洽，所以**它们不可能都对**，而这不是靠再训一版模型能解决的：
标签停在哪一层分辨率上，模型就只能学到哪一层。

## 这批卡怎么来的

seed = `20260920`，按下列分组分层抽样，每组设上限以免某个职能淹没其他职能：

| 分组 | 候选池 | 实际取 | 这一组要问出什么 |
| --- | --- | --- | --- |
| `same_family_dependency_opposed` | 2640 | 12 | 同主职能的两个 Agent，左方产出是否可能成为右方输入？ |
| `same_family_similarity_ai_low` | 76 | 8 | 同主职能但细节能力不同时，替换代价是否真的都差不多？ |
| `same_family_agree_similarity` | 46 | 4 | 同主职能且 AI 也认为可替换时，依赖分是否仍为 0？ |
| `cross_family_dependency_opposed` | 339 | 5 | 跨主职能时，依赖分是否应按能力缺口大幅变化，而不是都落在中间？ |
| `cross_family_similarity_ai_high` | 2810 | 6 | 跨主职能的两个 Agent，是否可能互为好的替换？ |
| `agreement_control` | 431 | 6 | 两套口径一致时，人是否也给出同一个档？ |

一个 pair 同时可能满足多组条件，但它只被**一组**取走（不重复出现）：按上表从上到下取，
某组在某一层取满 quota 后，剩下的候选会让给后面的组 —— `answer_key.jsonl` 里的 `group`
记的是**真正取走它的那一组**，也是算账时它所在的分母。

卡面顺序另做了一次固定 seed 的洗牌。原因：`cards` 原本按真实 pair id 排序，而 id 前缀就是
所有者编号，同一个人手下的 pair 会连成一片；`skillDigest` 里又带着那份任务的上下文，
于是标注者容易成片给同一种答案（顺序效应），而 AI 判分器是逐卡独立推理。
洗牌把「相邻同所有者」从 29/40 降到 4/40，且不改动任何统计量（`human_review.test.mjs` 在守这条）。

## 答案回来之后怎么算账

```bash
npm run experiment:cpdb-human-review:score -- --dir exports/cpdb-human-review-v1
```

它会分别算「人 vs teacher」「人 vs AI」的同档率、±0.25 命中率、MAE 与二次加权 kappa，
**按分组分开报**。分组分开是关键：只看总分会被 `agreement_control` 那一组稀释掉 ——
那一组两套口径一致，谁都能「猜」对。

## 三种可能的结果，分别意味着什么

- **人的答案靠近 teacher** → 「主职能是充分统计量」成立。那就**不需要学习模型**，
  保留规则（或让模型去学这条规则），把指数递减那部分做掉即可。
- **人的答案靠近 AI** → 学习模型这条路成立，但也说明现在的 teacher 标签不可用，
  需要的是**同职能内部的细分标签**，而不是再训一版。
- **人对两套都不像** → 说明两轴的定义本身需要改（例如「最小能力改动」在人的理解里
  与题面锚点不是一回事）。这时候该改的是 `TASK.json` 的锚点，而不是模型。

## 输入的指纹

| 文件 | sha256（前 16 位） |
| --- | --- |
| `data/full/annotation_cards.jsonl` | `4f77f77036f73db6…` |
| `data/full/pairs.jsonl` | `639bde6abb9f6c94…` |
| `train_out/labels.jsonl` | `5792cf1e00520068…` |
| `train_out_ai/labels.jsonl` | `7eea62c3c194ccfc…` |
| `train_out_ai/folds.jsonl` | `eca4a3ddea3b7150…` |

（重跑同一条命令应得到逐字节相同的 `cards.jsonl`；`selection.json` 里记了完整指纹。）
