# SkillFlow 主表说明

2026-10-08。这是开跑前的冻结说明，不是结果。`paperReady=false`，`realRunAllowed=false`。

## 主表是什么

同一套 SkillFlow 任务、同一个任务基模，让七个进化方案各自进化，看谁的**进化提分**最高。

提分的定义：在同一个家族、同一题序上，

```text
提分 = 平均(进化后是否通过 − 不进化是否通过)
```

通过记 1，不通过记 0。提分可以是负数。绝对通过率只作附表，不决定排名。

不进化的对照叫 `vanilla`：同一套 Janus 执行班底，每题开始时不携带上一题的更新。

## 七个方案

| 臂 | 年份 | 出处 | 进化时写下什么 |
| --- | --- | --- | --- |
| ExpeL | 2024 | AAAI 2024 | 跨题心得，外加成功轨迹当例子 |
| Agent Workflow Memory | 2025 | ICML 2025 | 从成功轨迹归纳整段工作流 |
| ReasoningBank | 2025 | arXiv 2025-09 | 成功和失败都写成推理记忆 |
| SkillRL | 2026 | ICLR 2026 MemAgents workshop | 分层技能库，失败再加技能 |
| CoWork-X | 2026 | arXiv 2026-02 | 多 Agent，每轮把共享技能库再巩固一遍 |
| RSEA | 2026 | arXiv 2026-06 | 改写上下文，留出集没有变差才保留 |
| janus_full | — | 本系统 | 双树找出一处最小改动；D 用来组队，S 用来换人 |

先前口头列过的 ACE 是 2025 年 10 月的预印本，不占 2026 的名额，不进这张主表。

`janus_full` 跑完整系统。写进下一题的只能是侦探指出的那一处最小更新。六个 Agent 各自再写一库，不叫这个方案。

## 数据

SkillFlow：20 个工作流家族，166 题，Harbor 官方验证器。

论文 <https://arxiv.org/abs/2604.17308>
代码 <https://github.com/ZhangZi-a/SkillFlow>
数据 <https://huggingface.co/datasets/zhang-ziao/SkillFlow-Task>

家族按 id 排序后，用种子 `20261008` 打乱，切成 development 8、gate 4、locked 8。名单必须来自下载后的目录。locked 在 development 跑完并且协议不再改之前保持关闭。

任务基模当前登记为 `deepseek-v4.1-flash`，尚未锁定端点和版本。主表所有臂共用这一个基模。换基模属于后面的 backbone 实验，不混进主表。

## 这次不开的五类实验

消融、成本对照、换基模、系统流程图、鲁棒性迁移都不要在这一轮开跑。主表运行时只顺手记下每次的模型调用数、prompt tokens、completion tokens 和墙钟秒数，供以后的成本表使用，不为此多跑一遍。

## 废弃的主表

AppWorld 的 `frozen` / `planning_only` / `capability_only` / `joint` 不再作为主表。Who&When 的认人认步骤、SkillsBench 的技能消费通过率，也都不是这张表。旧的 AppWorld 全系统自进化记录另存，不删，但不与 SkillFlow 提分合并。
