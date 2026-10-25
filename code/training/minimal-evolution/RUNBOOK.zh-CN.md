# 开训与评测操作

2026-09-24 更新：训练已完成（600 步、2 epochs），当前在克隆实例上做训练后评测。主机名 `training-host`，2 × NVIDIA A800-SXM4-80GB、32 核 CPU 配额、240 GiB 内存配额。认证使用本机环境变量，文档不记录口令。

训练 release：`/data/modelstore/rdmd-evolution/releases/3106a4d61a416c82`；训练产物：`minimal-evolution/adapter`。克隆后实测 adapter SHA-256 为 `8755e26df3f370a8396e7acdae6670f2a45c6cdcdbca4ea3d0ce911a059afebc`，与训练记录相符。

评测完成：2026-09-24 20:48（北京时间），队列退出码 0，10 组结果完整，两张 GPU 显存均归零。SFT test 最小修复 100%，holdout 76.67%；holdout 错误采用 11.67%，未通过主要验收标准。完整指标、错误分析、强通用 AI 对照缺口见 [评测报告](../../docs/rdmd-minimal-evolution-evaluation.zh-CN.md)。

旧的无卡预检记录只代表准备时状态；没有 GPU 时 preflight 输出 BLOCKED 并 exit 3，不代表已经完成的训练失败。下面开训步骤用于重现新实验，当前已训练 run 不应重启或覆盖。

## 本地重现

在 Janus 根目录：

```powershell
python -m unittest discover -s experiments/rdmd_minimal_evolution -p test_engine.py -v
# 只向不存在的新目录生成，禁止覆盖现有数据
node scripts/run_guarded.mjs -- python experiments/rdmd_minimal_evolution/prepare.py --out experiments/rdmd_minimal_evolution/data
node scripts/run_guarded.mjs -- python experiments/rdmd_minimal_evolution/audit.py --full-oracle --out experiments/rdmd_minimal_evolution/runs/local-audit.json
python experiments/rdmd_minimal_evolution/train.py --out experiments/rdmd_minimal_evolution/runs/dry-run
```

## 上传与真实 tokenizer 预检

```powershell
# Authentication comes from the environment.
node scripts/run_guarded.mjs -- python experiments/rdmd_minimal_evolution/remote_prepare.py --preflight
```

只上传本目录代码、文档和合成数据；不上传凭据、真实用户库或旧任务文本。压缩包按 SHA-256 命名，落远端独立 release 目录；逐文件核对大小和 sha256。新版本不覆盖旧权重和语料。SSH 口令只由既有环境提供。

远端预检：全部标签重算、全量真实 tokenizer 编码、JSON 不截断、监督 token 存在、split 隔离、负例反证、依赖 API、模型五个分片的完整张量索引与逐文件哈希、GPU/BF16/磁盘。不会加载模型权重到 GPU，不会运行 optimizer。

`runs/remote-deployment.json` 给出精确 release 目录；`runs/remote-preflight.json` 是取回的实测状态。代码、配置或数据变化后需要新 bundle 和新预检。

## 获得 GPU 后，由后续获授权的操作启动

```bash
cd <remote-deployment.json 中的 remoteRoot>
bash start_training.sh --execute-training minimal-evolution-sft-seed20260923
```

启动脚本首先重跑预检，任何阻塞都会停止；显式 run 名必须从未存在。不提供命令时不会启动训练。预计需要 BF16 可用、至少 22 GiB 显存的 GPU；实际显存峰值仍须训练时测量，不能用无卡预检证明不会 OOM。

## 训练后的公平评测

2026-09-24 克隆机评测使用独立代码目录 `/data/modelstore/rdmd-evolution/eval-code-20260924`，冻结训练 release 保持原样。模型臂统一 `--batch-size 8`，左侧补齐、贪心解码，最多 1536 个新 token。与冻结版相比只修正 `trained` 来源标记并增加批量生成，不改变 prompt、标签、补丁验证器或评分规则。

```bash
PY=/data/modelstore/rdmd-env/bin/python
CODE=/data/modelstore/rdmd-evolution/eval-code-20260924
DATA=/data/modelstore/rdmd-evolution/releases/3106a4d61a416c82/data
OUT=/data/modelstore/rdmd-evolution/eval
CUDA_VISIBLE_DEVICES=0 $PY $CODE/evaluate.py --data $DATA --arm H3_base --split holdout --batch-size 8 --out $OUT/h3-holdout-batch
CUDA_VISIBLE_DEVICES=1 $PY $CODE/evaluate.py --data $DATA --arm trained --adapter minimal-evolution/adapter --split holdout --batch-size 8 --out $OUT/sft-holdout-batch
$PY $CODE/evaluate.py --data $DATA --arm rule_search --split holdout --out $OUT/rule_search-holdout-batch
```

test 用相同命令改 `--split test`，并把输出目录中的 holdout 改为 test，结果单列。输出目录必须不存在；不默默复用旧预测。评测产生 predictions、provenance、summary，所有样本都进入分母。早期 `h3-holdout-new` 逐条试跑已主动停止，只有 116/960 条，不进入正式对照。批量版本在生成全部输出后才写预测文件；其 `elapsedSeconds` 与行级 `seconds` 只涵盖评分循环，推理耗时应使用进程的外部计时，不能用这两个字段声称推理加速。

## 证据同步与版本说明

本轮冻结的远端批量评测器 SHA-256 为 `62bc5ea25b826fee66376eaffb38c58858e190aa6493674a7b3df6eae00e8e2a`。本地后续版本已改为逐批落盘并计入生成耗时，额外补齐/截取测试通过；未在本轮队列中替换代码。对逐条试跑与正式批量版本前 116 条的事后检查，最小修复判定 116/116 一致，JSON 预测 107/116 相同；不将这段不完整试跑当作正式模型臂。

拉回证据和独立重算（认证来自环境变量）：

```powershell
python experiments/rdmd_minimal_evolution/collect_evaluation.py --out experiments/rdmd_minimal_evolution/runs/evaluation-20260924
python experiments/rdmd_minimal_evolution/analyze_evaluation.py --snapshot experiments/rdmd_minimal_evolution/runs/evaluation-20260924
```

未完成的模型臂会明确列为 pending，不拿部分样本计算完整成绩。下载包括本轮冻结的评测代码，逐文件 hash 核对；重算还验证 case ID 完整性、原始文本解析、逐样本分数、底座/adapter 来源和配对组区间。

## 强通用模型 H4

`evaluate.py --arm external --split holdout --export-requests --out NEW_DIRECTORY` 导出与模型臂相同的 requests.jsonl。交给所选强模型执行，结果每行必须为 `{"id":"原id","prediction":"模型原始JSON字符串"}`。

来源 JSON 必须含 `model`（具体版本）、`requestSha256`、`n:1`、`temperature:0`、`maxNewTokens:1536`。原始模型输出不要人工修订；格式错误照常算错。导入：

```bash
$PY evaluate.py --arm external --split holdout --external predictions.jsonl --external-provenance provenance.json --out NEW_EVAL_DIRECTORY
$PY compare.py --trained SFT_EVAL_DIRECTORY --baseline H3_OR_H4_EVAL_DIRECTORY --out comparison.json
```

本轮未发起收费推理。H4 的实际模型选择和结果在评测阶段登记，不能把占位或 oracle 输出当 H4。

## Janus 影子接入

见 [影子接入说明](../../docs/rdmd-minimal-evolution-shadow-integration.zh-CN.md)。源码新增本地 runner、只读 IPC 和规划建议面板，默认规则模式；本机训练模型需显式设置 `JANUS_MINIMAL_EVOLUTION_*`，不会自动通过 SSH 使用本节远端实例。真实模型冒烟在训练实例已完成，输出 `false_no_change` 被拒绝；原始结果保留于 `runs/shadow-integration-20260924/`。当前未构建安装版、未启用自动演化，也未将普通协作图冒充可执行表格图。
