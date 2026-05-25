# LLM-Driven Scientific Research Agents

## Long-Horizon Automation, Evidence Constraints, and Trustworthy Workflow Governance

**Version**: Demo Proposal v0.1
**Generated from**: Zotero collection `Research Harness / 科研智能体综述` + RH topic evidence pool
**Purpose**: Show how the Zotero plugin turns a paper collection into a structured, evidence-aware survey proposal.

### One-sentence Thesis

LLM-driven research agents are moving from short-form assistance toward long-horizon scientific workflow automation; the next critical question is no longer only **what they can automate**, but **how their outputs are constrained by evidence and governed by trustworthy workflows**.

### Proposed Survey Scope

This survey focuses on three coupled dimensions:

1. **Long-Horizon Automation**: how agents automate literature search, hypothesis generation, experimentation, analysis, writing, and review.
2. **Evidence Constraints**: how claims, citations, source attributions, conflicts, and limitations constrain generated conclusions.
3. **Trustworthy Workflow Governance**: how stage gates, schema-constrained tools, provenance, human approval, and recovery mechanisms make long-running research workflows auditable and reliable.

### Differentiation from Existing Surveys

Existing surveys often classify systems by task type, scientific domain, or agent architecture. This proposal reframes the field around a workflow-control question:

> When a scientific agent operates over long horizons, what mechanisms make its research process evidence-grounded, auditable, and governable?

---PAGEBREAK---

# Three-Axis Taxonomy

| Axis | Core Question | Representative Topics | Example Evidence Needed |
|---|---|---|---|
| Long-Horizon Automation | Which research stages can the agent automate? | Deep research, hypothesis generation, code/experiment execution, writing, review | End-to-end agent papers, workflow benchmarks, task decomposition traces |
| Evidence Constraints | How are generated conclusions constrained by sources? | Citation grounding, claim-evidence extraction, source attribution, conflict-aware synthesis | Citation verification papers, claim-level datasets, factuality benchmarks |
| Trustworthy Workflow Governance | How is the long-running process controlled? | Stage gates, schema-gated tool use, provenance, audit trails, human approval, rollback | Workflow systems, academic integrity benchmarks, reproducibility traces |

## Representative Paper Clusters

### Cluster A: End-to-End Scientific Agents

Papers in this cluster demonstrate increasingly autonomous scientific workflows, including ideation, experiment execution, analysis, and paper generation. They support the survey's automation axis.

### Cluster B: Deep Research and Literature Agents

This cluster covers web/literature research agents, long-form report generation, and benchmarks that test retrieval, organization, and synthesis ability.

### Cluster C: Evidence and Citation Verification

This cluster studies whether citations and sources actually support generated claims. It is essential for arguing that source presence is not equivalent to evidence faithfulness.

### Cluster D: Workflow Governance and Integrity

This cluster includes schema-gated execution, reproducible workflow systems, academic integrity evaluation, and process-level safeguards.

---PAGEBREAK---

# Readiness Gate and Next Steps

## Gate Check: Survey Proposal Readiness

**Pass**

- The scope is clear: automation, evidence, and governance.
- The seed corpus already covers scientific agents, Deep Research agents, citation verification, academic integrity, and workflow systems.
- The survey has a differentiating thesis: from capability-centric surveys to evidence-governed workflow surveys.

**Risks**

- Need stronger industry evidence from official agent/workflow documents and product reports.
- Need a comprehensive comparison table across representative systems and benchmarks.
- Need claim-level extraction for the most important papers before writing the final introduction.
- Need a careful related-survey comparison to avoid appearing as another broad AI-for-Science survey.

## Next-Step Reading Plan

1. Build an existing-survey comparison table.
2. Extract claims from 15–20 anchor papers.
3. Separate papers into the three taxonomy axes and mark cross-axis papers.
4. Add industry evidence and workflow standardization signals.
5. Draft the Introduction only after the evidence map is stable.

## Demo Takeaway

The Zotero plugin is not merely a chat interface. In this workflow, it acts as a research cockpit: it reads the current Zotero context, recommends missing papers, constrains synthesis with evidence, checks readiness gates, and exports a concrete research artifact.
