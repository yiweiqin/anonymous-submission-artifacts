# 怎么把判分结果交回来

## 0. 开始之前

要读的三个文件（其余都是数据，不用读）：

| 文件 | 作用 |
| --- | --- |
| `TASK.json` | 任务定义：两轴各问什么、标尺、每个 kind 该期待什么 |
| `schema/label_row.schema.json` | **输出行的权威形状** |
| `IMPORT.md` | 本文件：怎么交回来 |

要判的两个文件：

- `cards/test.blind.jsonl` —— 799 对，**必须盲判**（本包不含它们的参考分，见 §5）
- `cards/train.dev.jsonl` —— 7483 对，可对着 `reference/prelabel.jsonl` 校准

工作量与要交的行数（**每个 pair 要 2 份判分**）：

| 范围 | 对数 | 至少交多少行 |
| --- | --- | --- |
| 全部 | 8282 | 16564（分歧的还要多，见 §2） |
| 仅 test（盲判） | 799 | 1598 |
| 仅 train + development | 7483 | 14966 |

**两轴怎么读**（这是最容易错的地方）。每张卡上有 `left` / `right` 两个 agent：

- `dependency` 看**产出接不接得上输入**：`left.produces` 是不是 `right.consumes` 要的东西。
- `similarity` 看**职能像不像**：`family` / `facet` / `tags` / `skillDigest` 是否重合到
  "换上去改动最小"的程度。
- 两轴可以一高一低，且通常就是如此（职能互补的对，应当**依赖高、相似低**）。
  **不要把两个分往同一个方向拉** —— 那等于把两轴合成一轴，本任务就失去意义了。

**两份独立判分怎么做**：分两轮、两个会话（或两个不同的模型）各判一遍，署名两个不同的
`reviewerId`，**第二轮不要带第一轮的结论**。两份完全相等 → 那份就是金标（`agreed`）；
不相等 → 再补第 3 份，`role` 填 `adjudicator`。细节见 §2。

## 1. 你要产出什么

一个 JSONL 文件，每行一条判分（**不是**一个 pair 一行，是 **一份判分**一行）：

```json
{"id":"ag_p_01_00_0>ag_p_01_00_1","reviewerId":"ai_A","role":"reviewer","dependency":0.75,"similarity":0,"rationale":"..."}
```

形状的权威定义在 `schema/label_row.schema.json`。三条最容易踩的：

- `dependency` / `similarity` **必须是数字**，且严格等于 `[0, 0.25, 0.5, 0.75, 1]` 里的某一个。
  写 `"0.75"`（字符串）、`0.6`（中间值）、或漏掉一个，该行会被判无效并**整行丢弃**。
- **不要填 `combined`**（也不要以任何形式合成总分）。契约明令禁止，服务端见到非 null 的值直接抛。
- **不要填 `status`**。它不是输入，是推导量。

## 2. 要判几遍

**每个 pair 出 2 份判分，由两个不同的 `reviewerId` 产生，两次之间互不可见。**

- 两份完全相等 → 那份就是金标（记为 `agreed`）。
- 两份不相等 → 需要第 3 份 `role: "adjudicator"` 的判分来裁（记为 `adjudicated`）。
  没有第 3 份时这个 pair **不是金标**，会被我们标成 `needs_adjudication` 并搁置。

所以：**只出 1 份判分的 pair 不会变成双人金标**，只会是 `single`。

## 3. 放到哪

把结果文件放回（路径以这个为准）：

```
experiments/cpdb_org_world/import/ai-labels.jsonl
```

然后我们跑（**不给参数就走上面这个默认位置**）：

```bash
npm run experiment:cpdb-import
```

放别的路径也行，显式给 `--labels`：

```bash
npm run experiment:cpdb-import -- --labels /任意/路径/ai-labels.jsonl
```

导入侧会做这些事（都是**严格的**，宁可拒收也不要静默改分）：

1. 逐行按 §1 的判据校验；非法行拒收并逐条报告原因。
   **只要有任意一行被拒，命令就非零退出** —— 静默吞掉坏输入，会让"导入成功"这句话不可信。
2. 按 `(id, reviewerId)` **去重**（同一个 reviewerId 对同一个 pair 反复出现时只留最后一条）。
   不去重会把 rater 数算多，得到假的 `agreed`。
   同一份文件里同一个人对同一个 pair 交了两次、而**分数不一致**时，会拒收并报
   `duplicate_reviewer_conflict`（不会随机挑一条）。
3. 结果写进 `data/full/ai_labels.jsonl` —— **单独一份文件**，不混进
   `data/full/human_labels.jsonl`。那份人工判分文件只被**读来做交叉核对**
   （判断某个仲裁是否合法、这次导入是否幂等），**不会被改写**。
   每行会打上 `labelSource: "ai_reviewer"` / `"ai_adjudicator"`：
   "AI 判分"与"人工判分"必须能分开统计，否则出不了对照表。
4. 跑一遍一致性（Cohen κ），并把 `(id, reviewerId)` 与已有行冲突的情况报出来。
   对同一个 pair 重复导入同一份判分是**空操作**（幂等）；想用新分覆盖旧分要显式加 `--overwrite`。

## 4. 我们**不会**做的事

- 不会把你给的分数"四舍五入到最近档"。不在标尺上就是无效行。
- 不会把你的判分混进 `prelabel` 行。`labelSource` 会分开记。
- 不会声称你的判分等同于人工金标。报告里会按 `labelSource` 分开列。

## 5. 自检

- 你可以在 `reference/prelabel.jsonl` 上先跑一遍，对一下你与规则基线的一致程度。
  它**只覆盖 train/development**，不含 test。
- 若你在包里任何一个文件里找到了某个 **test** pair 的 `initDependency` / `initSimilarity` /
  `contractDependency` / `contractSimilarity`，请当作包损坏并回报 —— 那是我们泄题了。
  （放出本包前已自检过：799 个 test pair，0 泄漏。）
