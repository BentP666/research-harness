# 论文管理规范

Research Harness 的论文管理目标是：**所有论文、PDF、topic 关系和精读产出都能跨 session 稳定复用，并且可以被审计。**

!!! warning "硬性规则"
    任何 session、任何工具、任何 Agent 都必须遵守：论文必须入库，PDF 必须进入统一目录，论文必须绑定 topic。

## 三个不变量

| 不变量 | 说明 |
| --- | --- |
| 唯一数据库 | `~/.research-harness/pool.db` 指向项目数据库 |
| 唯一 PDF 目录 | `.research-harness/downloads/` |
| 必须指定 topic | 新论文入库必须带 `topic_id` 或 topic 名称 |

## 正确入库方式

优先通过 MCP 工具：

```python
paper_ingest(source="arxiv:2401.12345", topic_id=<N>)
paper_ingest(source="doi:10.1145/XXXXXXX", topic_id=<N>)
paper_ingest(source="file:///absolute/path/to/paper.pdf", topic_id=<N>, title="...")
```

也可以通过 CLI：

```bash
rh paper ingest --arxiv-id 2401.12345 --topic my-topic
rh paper ingest --doi 10.1145/XXXXXXX --topic my-topic
rh paper ingest --file /absolute/path/to/paper.pdf --topic my-topic
```

## 禁止事项

| 禁止 | 原因 |
| --- | --- |
| 直接 SQL 更新 `pdf_path` | 绕过路径校验和 provenance |
| 把 PDF 散放在项目目录 | 后续 session 和 Agent 难以恢复 |
| 使用相对路径 | 换机器或换 cwd 后会失效 |
| 不带 topic 入库 | 论文会变成孤儿状态 |

## 每次 session 开始建议检查

```bash
rh topic list
rh topic overview <topic-name>
rh paper queue --topic <topic-name> --only-actionable
rh paper resolve-pdfs --topic <topic-name> --dry-run
```

## PDF 健康检查

```bash
python3 -c "
import sqlite3, os

db = os.path.expanduser('~/.research-harness/pool.db')
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute('SELECT pdf_path FROM papers WHERE pdf_path IS NOT NULL AND pdf_path != ""')
paths = [row[0] for row in cur.fetchall()]
broken = [path for path in paths if not os.path.exists(path)]
print(f'Records with pdf_path: {len(paths)}')
print(f'Broken links: {len(broken)}')
for path in broken[:10]:
    print(path)
conn.close()
"
```

## 详细参考

原始规范见 [`docs/PAPER_MANAGEMENT.md`](PAPER_MANAGEMENT.md)。
