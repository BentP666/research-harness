---
name: paper-reading-annotation
description: Create PhD-level PDF highlights/comments for newly added Zotero papers or RH PDFs. Trigger when importing/syncing a paper into Zotero, adding a PDF attachment, 精读标注, 论文批注, 博士生读论文, or equivalent requests to make a paper quickly graspable through PDF annotations.
category: research
version: 0.1.0
---

# Paper Reading Annotation

Use this skill whenever a paper PDF is added to Zotero/RH and should receive actionable reading highlights, not just section navigation.

## Objective

Produce PDF annotations that help a PhD student quickly grasp:

- the paper's core problem, motivation, and claims;
- theoretical innovation and application innovation;
- taxonomy/method structure and hidden assumptions;
- evidence strength, benchmark/baseline choices, limitations, and risks;
- writing moves, framing strategies, and surprising presentation choices;
- direct reuse value for the current RH topic or the user's own research.

## Workflow

1. **Resolve context**
   - Identify `paper_id`, topic, title, local `pdf_path`, and Zotero item/attachment keys when available.
   - If this is part of Zotero import/sync, run this before or immediately after attaching the PDF so the Zotero copy contains the annotations.

2. **Read before annotating**
   - Use existing RH `paper_annotations`, deep-read notes, and/or extracted PDF text.
   - For normal research papers, inspect abstract, introduction, method, experiments, limitations, and conclusion.
   - For surveys, inspect scope, taxonomy, paper-selection evidence, benchmark/resource tables, challenges, and limitations.

3. **Create an annotation plan**
   - Use `references/phd-annotation-schema.md` for categories and minimum coverage.
   - Write a JSON plan with anchor text and comments. Prefer 25–40 annotations for a full paper; 15–25 for short papers.
   - Each comment must be actionable: explain why the highlighted text matters and how to use/critique it.

4. **Apply annotations**
   - Run the bundled tool:
     ```bash
     python skills/paper-reading-annotation/scripts/phd_pdf_annotator.py \
       --pdf /absolute/path/to/paper.pdf \
       --spec /absolute/path/to/annotation_plan.json \
       --in-place \
       --json
     ```
   - For Zotero, apply to the actual Zotero storage PDF if known; otherwise apply before attachment so Zotero imports the annotated copy.
   - Keep backups unless the user explicitly asks not to.

5. **Verify and record**
   - Confirm applied/missing counts from the tool output.
   - If used inside RH, record a `zotero_pdf_annotation_receipt` or `paper_pdf_annotation_receipt` artifact with paper ids, paths, annotation count, and missing anchors.
   - If the PDF is already open in Zotero Reader, tell the user to close/reopen the PDF or restart Zotero to refresh embedded annotations.

## Trigger contract for Zotero import

When a future agent imports or syncs papers into Zotero, treat this as the default post-processing step unless the user opts out:

1. RH paper has a local PDF.
2. Generate the PhD annotation plan.
3. Apply annotations to the PDF that will be attached or to the attached Zotero storage PDF.
4. Attach/sync the annotated PDF and deep-read note.
5. Record the receipt.

Do not silently claim annotations were added: always verify PDF annotation counts.
