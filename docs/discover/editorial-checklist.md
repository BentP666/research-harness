# RH Discovery Editorial Checklist

Discovery issues are publishable only when every opportunity is more than a news item.
The validator enforces the parts that can be checked mechanically; editors still own source judgment and scientific taste.

## Published issue gates

Each published issue must have:

1. `issue_id`, `cadence`, `status=published`, `generated_at`, title, and subtitle.
2. At least one `OpportunityBrief`.
3. Every opportunity must include:
   - a concrete `summary` answering what happened;
   - `why_now` explaining the timing;
   - at least **2 evidence signals**;
   - at least one non-news signal such as paper, product, model, benchmark, repo, or blog;
   - explicit `risks`;
   - at least one `goal_preview` with dataset, baseline, metric, compute need, and first steps;
   - RH handoff queries and suggested primitives.

## Source usage labels

The source registry must classify sources by operational mode:

- `connector`: first-class source expected to become a direct integration.
- `sidecar`: external index or crawler-style source used to enrich signals.
- `manual`: editorial watchlist or source that needs human verification before publication.

## Human editorial checks

Before marking an issue published, an editor should verify:

1. Links resolve to primary sources where possible.
2. Claims are phrased as research opportunities, not product hype.
3. Safety/privacy-sensitive opportunities avoid actionable misuse details.
4. The first goal can be started in roughly 30 days with low or explicitly stated compute.
5. RH handoff queries are specific enough to seed `paper_search` and `gap_detect`.
