# RH Discover Publishing Workflow

RH Discover is a file-backed, publishable subproduct for turning daily/weekly
research and technology signals into actionable `OpportunityBrief`s.

## Source of truth

Published issues live here:

```text
docs/discover/issues/{YYYY-MM-DD}-{daily|weekly|special}.json
```

Each issue file is curated JSON with:

- `issue_id` — stable slug, usually the file name without `.json`
- `cadence` — `daily`, `weekly`, or `special`
- `status` — `draft`, `published`, or `archived`
- report metadata — `title`, `subtitle`, `generated_at`
- `briefs[]` — validated RH Discover `OpportunityBrief`s

Only `status=published` issues are shown by default in the API and web archive.

## Daily / weekly publishing loop

1. Copy the template:

   ```bash
   cp docs/discover/templates/issue-template.json \
      docs/discover/issues/2026-05-17-weekly.json
   ```

2. Edit the issue. Every brief must answer:

   1. What happened?
   2. Why does it matter now?
   3. What research direction could it become?
   4. Who is this direction suitable for?
   5. What evidence supports it?
   6. How can it be handed off to RH?

3. Validate:

   ```bash
   rh discover validate docs/discover/issues/2026-05-17-weekly.json
   ```

4. Preview as Markdown or HTML:

   ```bash
   rh discover weekly --input docs/discover/issues/2026-05-17-weekly.json \
     --format markdown \
     --output docs/discover/published/2026-05-17-weekly.md

   rh discover weekly --input docs/discover/issues/2026-05-17-weekly.json \
     --format html \
     --output docs/discover/published/2026-05-17-weekly.html
   ```

5. Mark `status` as `published` and commit the issue file.

## Product surfaces

- CLI archive: `rh discover issues`
- Latest weekly JSON: `rh discover weekly --no-sample --format json`
- API archive: `GET /api/discover/issues?cadence=weekly`
- API latest: `GET /api/discover/issues/latest?cadence=weekly`
- Web archive: `/discover`
- Web issue detail: `/discover/issues/{issue_id}`
- RH Core handoff: click “Turn into RH topic” on any OpportunityBrief card

## Editorial rule

Do not publish generic news. If a signal cannot produce a concrete handoff query,
next action, and research-risk note, keep it as internal watchlist material.
