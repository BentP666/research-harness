# CCF-A 热点 Demo 主题：LLM 软件工程智能体

## 推荐主题

**LLM 软件工程智能体：AI 程序员能不能真正修 GitHub Issue？**

更学术一点的 RH topic 名：

```text
LLM-based Software Engineering Agents
```

更适合小红书/视频的 Zotero collection 名：

```text
Research Harness / AI程序员能修Bug吗
```

## 为什么它比“AI 科学家”更适合 CCF-A 扎堆感

这个方向是真正能对齐 CCF-A 软件工程/系统/AI 交叉投稿的热点，尤其适合 ICSE/FSE/ASE/ISSTA 这一条线，也能外溢到 NeurIPS/ICLR 的 agent/evaluation/benchmark 方向。

它的热度来自一个很清楚的问题：

> 从 Copilot 到 SWE-agent，再到各种 repo-level coding agents，AI 到底只是会补代码，还是能在真实代码仓库里理解 issue、写测试、修 bug、跑 CI、避免 regression？

这比泛泛讲“AI 科学家”更像一个 CCF-A 选题池：有任务、有 benchmark、有系统、有评测、有 failure analysis，也有明显的工程落地价值。

## 适合 demo 的核心论文路线

拍视频时不用把所有论文讲完，只需要让 Zotero/RH 展示出“我在追一个正在爆的 CCF-A 方向”。建议分成 4 个 cluster：

1. **Repo-level coding agents**
   - 真实 GitHub issue 修复
   - 多步规划、工具调用、patch 生成
   - SWE-bench / repo benchmark

2. **Automated Program Repair with LLMs**
   - 从 prompt 修 bug 到 execution feedback
   - patch correctness、overfitting、regression

3. **Test generation for SWE issues**
   - 自动生成 reproduction tests
   - 用测试反向约束 agent 修复

4. **Agent behavior / trajectory analysis**
   - thought-action-result trajectory
   - agent 为什么失败、卡在哪里、怎么评价

## Demo 叙事钩子

开场不要说“我在研究软件工程智能体”。太硬。

直接说：

> “现在大家都说 AI 程序员要来了。
> 但 CCF-A 论文真正关心的不是它会不会写代码，而是：它能不能在真实仓库里修 issue，而且不把项目修炸？”

然后切 Zotero：

> “所以我建了一个 Zotero 目录：AI程序员能修Bug吗。”

## 90 秒 Demo 分镜替换版

### 0–8s：高热度问题

字幕：

```text
AI 程序员到底是噱头，还是 CCF-A 正在爆的方向？
```

画面：Zotero collection `Research Harness / AI程序员能修Bug吗`。

### 8–22s：目录模式

输入：

```text
这个目录可以怎么推进？
```

预期：RH 显示 collection mode，并给出初始化主题、推荐补库、导入缺失论文等动作。

字幕：

```text
没选论文时，它不是尬聊单篇 paper，而是把整个方向当成研究主题。
```

### 22–40s：补 CCF-A 论文池

输入：

```text
把这个主题里最关键的 3 篇论文导入当前目录
```

预期：出现导入确认卡。

字幕：

```text
写 Zotero 前必须 dry-run：来源、目标、数量都先给我看。
```

### 40–60s：切单篇论文模式

选中一篇 paper，例如：

```text
Understanding Software Engineering Agents: A Study of Thought-Action-Result Trajectories
```

输入：

```text
这篇论文为什么适合投 CCF-A 软件工程方向？
```

预期回答重点：

- 它不是单纯做 agent demo，而是分析 SE agents 的行为轨迹；
- 有任务、失败模式、可解释性、评测指标；
- 更像 ICSE/FSE/ASE 会关心的问题。

### 60–75s：PDF 附件动作

输入：

```text
下载并附加 PDF 到当前条目，先 dry-run，确认后 apply
```

预期：出现 PDF 附件确认卡。

字幕：

```text
这不是模型叫我点一个不存在的按钮。确认卡是真的，apply spec 是后端生成的。
```

### 75–90s：收束

输入：

```text
基于这些论文，帮我判断这个方向还能怎么做出 CCF-A 级别的新意？
```

字幕：

```text
这才是 Zotero + RH 的意义：不是堆 PDF，而是把一个热点方向推进成研究计划。
```

## 小红书标题备选

1. AI程序员能修Bug吗？我用Zotero追了一遍
2. CCF-A爆火方向：AI修Bug真的靠谱吗
3. 别只会用Copilot了，论文已经卷到这了
4. AI写代码过时了，现在卷的是自动修仓库
5. 研究生想发CCF-A，可以盯这个方向

## 小红书正文开头

兄弟们，这个方向是真的热。🔥

现在大家都在聊 AI 程序员，但论文里真正卷的不是“能不能写一段代码”。

而是：给它一个真实 GitHub issue，它能不能读仓库、定位 bug、写测试、改代码、跑 CI，而且别把别的地方修炸。

这就是最近 CCF-A 软件工程方向特别值得盯的：**LLM 软件工程智能体**。

我准备拿 Zotero + RH 做一个完整 demo：不是把论文丢进 PDF 仓库，而是让 Zotero 直接变成这个方向的研究驾驶舱。

## 为什么适合 RH Zotero 演示

- 目录模式：天然适合展示“一个热门方向怎么建文献池”。
- 单篇模式：天然适合问“这篇 paper 的 CCF-A 贡献在哪里”。
- 写入确认：天然适合展示“不是 AI 乱写 Zotero，而是 dry-run 后确认”。
- PDF 附件：天然适合展示“论文从 RH 回到 Zotero 条目下”。

## 建议 seed query

```text
LLM-based software engineering agents automated program repair SWE-bench test generation execution feedback ICSE FSE ASE
```

## 建议重点筛选词

```text
SWE-bench
software engineering agents
automated program repair
test generation
execution feedback
issue resolution
repository-level code agent
GUI testing agent
agent trajectory analysis
```
