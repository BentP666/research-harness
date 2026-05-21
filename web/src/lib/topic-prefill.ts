import type { DiscoverOpportunityBrief } from "./api";
import type { DiscoveryTopicCandidate } from "./discovery-product";

export interface NewTopicPrefill {
  source: string | null;
  name: string;
  description: string;
  targetVenue: string;
  deadline: string;
  seedPapersRaw: string;
}

function seedPaperSource(paper: DiscoverOpportunityBrief["seed_papers"][number]): string | null {
  return paper.arxiv_id ?? paper.doi ?? paper.url ?? null;
}

export function formatDiscoverBriefDescription(
  brief: DiscoverOpportunityBrief,
): string {
  const sections = [
    brief.summary,
    `Why now:\n${brief.why_now}`,
    brief.rh_handoff.initial_queries.length > 0
      ? `Initial RH queries:\n${brief.rh_handoff.initial_queries.map((query) => `- ${query}`).join("\n")}`
      : "",
    brief.recommended_next_steps.length > 0
      ? `Recommended next steps:\n${brief.recommended_next_steps.map((step) => `- ${step}`).join("\n")}`
      : "",
    brief.risks.length > 0
      ? `Risks / watch-outs:\n${brief.risks.map((risk) => `- ${risk}`).join("\n")}`
      : "",
  ];

  return sections.filter(Boolean).join("\n\n");
}

export function buildNewTopicHrefFromDiscoverBrief(
  brief: DiscoverOpportunityBrief,
): string {
  const seedPapers = brief.seed_papers
    .map(seedPaperSource)
    .filter((source): source is string => Boolean(source));
  const params = new URLSearchParams({
    source: "discover",
    name: brief.rh_handoff.topic_name || brief.title,
    description: formatDiscoverBriefDescription(brief),
  });

  if (seedPapers.length > 0) {
    params.set("seed_papers", seedPapers.join("\n"));
  }

  return `/topics/new?${params.toString()}`;
}

export function formatTopicCandidateDescription(
  candidate: DiscoveryTopicCandidate,
  domainName?: string,
): string {
  const sections = [
    candidate.whyItFits,
    domainName ? `Domain:\n${domainName}` : "",
    `Candidate profile:\n- Novelty: ${candidate.novelty}\n- Feasibility: ${candidate.feasibility}\n- Resource need: ${candidate.resourceNeed}\n- Expected horizon: ${candidate.horizon}`,
    candidate.firstMoves.length > 0
      ? `First moves:\n${candidate.firstMoves.map((move) => `- ${move}`).join("\n")}`
      : "",
    candidate.starterPack.papers.length > 0
      ? `Starter papers:\n${candidate.starterPack.papers.map((paper) => `- ${paper}`).join("\n")}`
      : "",
    candidate.starterPack.skills.length > 0
      ? `Suggested RH skills:\n${candidate.starterPack.skills.map((skill) => `- ${skill}`).join("\n")}`
      : "",
    candidate.starterPack.outputs.length > 0
      ? `Expected first outputs:\n${candidate.starterPack.outputs.map((output) => `- ${output}`).join("\n")}`
      : "",
  ];

  return sections.filter(Boolean).join("\n\n");
}

export function buildNewTopicHrefFromTopicCandidate(
  candidate: DiscoveryTopicCandidate,
  domainName?: string,
): string {
  const params = new URLSearchParams({
    source: "discovery_explore",
    name: candidate.title,
    description: formatTopicCandidateDescription(candidate, domainName),
  });

  if (candidate.starterPack.papers.length > 0) {
    params.set("seed_papers", candidate.starterPack.papers.join("\n"));
  }

  return `/topics/new?${params.toString()}`;
}

export function parseNewTopicPrefillSearch(
  search: string | URLSearchParams,
): NewTopicPrefill {
  const params = typeof search === "string" ? new URLSearchParams(search) : search;

  return {
    source: params.get("source"),
    name: params.get("name") ?? "",
    description: params.get("description") ?? "",
    targetVenue: params.get("target_venue") ?? "",
    deadline: params.get("deadline") ?? "",
    seedPapersRaw: params.get("seed_papers") ?? "",
  };
}
