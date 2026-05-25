# 小红书 Demo 故事线：Zotero 变成会行动的科研驾驶舱

> 目标：拍出“不是又一个聊天框，而是 Zotero 里真的能规划、推荐、确认、写回”的惊艳感。视频建议 70–90 秒，节奏要像产品发布短片，不像功能说明书。

## 一句话钩子

**我把 Zotero 改成了一个会问、会推荐、会确认、会把论文放回库里的科研副驾驶。**

## 视频标题备选

1. Zotero 终于不是 PDF 仓库了！
2. 我把 Zotero 做成科研副驾驶
3. 读论文最爽的一次：Zotero 自动推进
4. Zotero + AI，论文库直接活了
5. 科研人别再手动搬 PDF 了

## 核心反差

- 以前：Zotero 是“文件柜”，论文越多越乱。
- 现在：Zotero 是“科研现场”，不同状态下自动给不同操作：
  - 选中一篇论文：解释贡献、关联 RH 主题、附加 PDF。
  - 回到目录：初始化主题、推荐缺失论文、把 RH 论文补回 Zotero。
  - 任何写入：先 dry-run 预览，再点确认，不让模型文字直接乱写库。

## Demo 数据设定

建议用一个有未来感的主题名，不要太学术：

- Zotero collection：`Research Harness / 自动科研`
- RH topic：`自动科研`
- 当前论文：`Agentic Zotero API Sync`
- arXiv：`2602.99999`（测试故事用；真实拍摄时可换成你实际要展示的论文）
- 论文状态：`已接入 RH / 已精读 / 本地 PDF 已准备`

## 70–90 秒分镜

### 0–5s：开场暴击

画面：Zotero 里一堆论文，鼠标停在 `自动科研` 目录。

旁白/字幕：

> “我不想再做一个只会聊天的 Zotero 插件了。”
>
> “我想让 Zotero 知道：我现在是在看一篇论文，还是在整理一个研究方向。”

屏幕操作：打开右侧 Research Harness 面板。

### 5–16s：目录模式，不选论文也能推进

操作：不选具体论文，只停在 `自动科研` collection。输入：

```text
这个目录可以怎么推进？
```

预期画面：面板显示 `Library chat / collection` 语义，返回可用能力：

- 从当前 Zotero 目录初始化 RH 主题
- 选择 RH 推荐/缺失论文补充到当前 Zotero 目录
- 把 RH 论文导入当前目录

字幕：

> “注意这里：没选论文时，它不是硬聊论文，而是切到目录模式。”

### 16–32s：把 RH 推荐/精读论文补回 Zotero

操作：输入：

```text
把这个主题里精读过的 1 篇论文导入当前目录
```

预期画面：出现确认卡，不是直接写库：

- 动作：导入当前目录
- 来源：RH 主题 · 自动科研
- 目标：Research Harness / 自动科研
- 计划：1 篇
- 按钮：确认导入 / 查看清单 / 取消

字幕：

> “它不会让 AI 直接写我的 Zotero。先 dry-run，给我看清楚要动什么。”

镜头节奏：先点 `查看清单`，展示论文标题；再点 `确认导入`。

### 32–48s：切到论文模式，界面自动变能力

操作：选中 `Agentic Zotero API Sync` 条目。

预期画面：面板变成 Paper chat，context card 显示：

- 当前论文标题
- RH topic
- 已精读/已接入 RH

输入：

```text
这篇论文对自动科研主题有什么启发？
```

字幕：

> “选中论文后，它就变成 paper-first 的阅读助手。”

### 48–65s：最惊艳动作：补 PDF，不再手动拖文件

操作：输入：

```text
下载并附加 PDF 到当前条目，先 dry-run，确认后 apply
```

预期画面：出现 PDF 附件确认卡：

- 动作：PDF 附件
- 来源：RH PDF · arXiv 2602.99999
- 目标：Zotero item ABCD1234 / 实际条目 key
- 计划：1 个 PDF 附件
- 按钮：确认附加 PDF / 取消

字幕：

> “这个按钮是真的。后端确认 PDF 路径安全，前端只执行后端给的 apply spec。”
>
> “不是模型说点哪里，我就点哪里。”

拍摄技巧：点击确认后，镜头切到 Zotero 条目下出现 PDF 附件。

### 65–82s：收束成“科研驾驶舱”

操作：追问：

```text
基于 RH 已有记录，下一步我应该怎么读这篇？
```

预期画面：流式回答，给出 3–5 条阅读/实验建议。

字幕：

> “它不是替我读完论文，而是把论文库、主题、PDF、下一步动作串起来。”

### 82–90s：结尾记忆点

画面：Zotero collection + RH 面板 + PDF 附件 + 确认卡闪回。

旁白/字幕：

> “这才是我想要的科研工具：能聊天，也能行动；能推荐，也会先问我确认。”

## 小红书正文草稿

兄弟们，这个我真的想拍成视频。🔥

我把 Zotero 插件改了一版，突然有点像“科研驾驶舱”了。

最爽的点不是它能聊天。

是它知道你现在在哪：

你选中一篇论文，它就围绕这篇论文解释贡献、关联 RH 主题、补 PDF。

你退回到一个目录，它就不硬聊论文了，而是问你要不要初始化主题、补哪些推荐论文、把 RH 里缺的论文同步回 Zotero。

更关键的是：写入 Zotero 前一定先给确认卡。

不是 AI 说“你点确认吧”，结果根本没按钮。

现在是真的有 dry-run、有目标、有风险提示、有 apply。

我最想拍的镜头是：

一句“下载并附加 PDF 到当前条目”，右侧弹出 PDF 附件确认卡，点一下，PDF 就出现在 Zotero 条目下面。

这感觉就不是“AI 聊天框”了。

是 Zotero 终于开始帮我推进科研流程了。

想看我把这个完整工作流拍出来吗？👀

## 标签建议

#Zotero #科研工具 #AI科研 #论文阅读 #研究生日常 #博士日常 #效率工具 #小众软件

## 拍摄前检查清单

- [ ] RH API 已启动，Zotero 插件版本是 `0.2.4` 或更高。
- [ ] 目标 Zotero collection 有清晰名称，例如 `Research Harness / 自动科研`。
- [ ] 至少一篇论文已通过 RH 匹配到 Zotero item。
- [ ] 该 RH paper 有安全可读的本地 `pdf_path`，且路径在 `PDF_ROOTS` 下。
- [ ] 先用 smoke 脚本验证 collection mode、导入 action preview、PDF attach action preview。
- [ ] 真实拍摄时，PDF attach 确认后检查 Zotero 条目下出现 PDF 附件。

## 本地 smoke 测试命令

```bash
PYTHONPATH=packages/research_harness:packages/research_harness_mcp:packages/llm_router \
.venv/bin/python scripts/zotero_demo_story_smoke.py
```

通过标准：三个关键镜头都打印 `PASS`：

1. collection mode exposes init/recommend actions
2. import request returns generic `sync_rh_papers_to_collection` preview
3. PDF request returns `zotero_attach_pdf` preview with local handler
