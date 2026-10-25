# 把 Astra 的 0–100 分收回来

把标注文件放到任意路径，然后：

```bash
npm run experiment:cpdb-astra-import -- --labels <回标文件.jsonl>
```

默认写入 `experiments/cpdb_org_world/artifacts/cpdb-scorer-v5-100/labels.jsonl`。
annotatorId 固定为 `astra_score_v1`。

**禁止**写进 `data/full/human_labels.jsonl`。非法分（非整数、越界、缺轴、带 `combined`）进 `rejects.jsonl`，不猜测。

每行必须是：

```json
{"id":"与 cards.jsonl 相同","dependency":67,"similarity":12,"rationale":"一句话"}
```
