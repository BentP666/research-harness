import { describe, expect, it } from "vitest";
import {
  DISCOVERY_CHANNEL_PROFILES,
  DISCOVERY_FINDINGS,
  DISCOVERY_HOT_TOPICS,
  DISCOVERY_INSPIRATIONS,
  DISCOVERY_INTELLIGENCE_RUN,
  DISCOVERY_OPPORTUNITIES,
  DISCOVERY_EVIDENCE_COVERAGE,
  DISCOVERY_PROBLEM_CATEGORIES,
  DISCOVERY_PROBLEM_MAP_RUN,
  DISCOVERY_PROBLEM_THEMES,
  DISCOVERY_SOURCE_STATUS,
  DISCOVERY_WATCHLISTS,
  getDiscoveryFindingsByChannel,
  getDiscoverySnapshot,
  getFindingCompositeScore,
  getDiscoveryProblemClusters,
  getProblemCategoryEvidenceCount,
  getHotTopics,
  getOpportunity,
  getProblemClusterScore,
  getTopProblemCategories,
  getTotalSignalCount,
  getRecommendedOpportunities,
} from "@/lib/discovery-product";

describe("Discovery standalone product data", () => {

  it("organizes Discovery into hierarchical problem-solution clusters", () => {
    expect(DISCOVERY_PROBLEM_MAP_RUN.model).toContain("category");
    expect(DISCOVERY_PROBLEM_CATEGORIES).toHaveLength(10);
    expect(getTopProblemCategories(10)).toHaveLength(10);
    expect(DISCOVERY_EVIDENCE_COVERAGE.routeErrorCount).toBe(0);
    expect(DISCOVERY_EVIDENCE_COVERAGE.records).toBeGreaterThanOrEqual(1000);
    expect(DISCOVERY_PROBLEM_THEMES.length).toBeGreaterThanOrEqual(3);

    const clusters = getDiscoveryProblemClusters();
    expect(clusters.length).toBeGreaterThanOrEqual(8);

    for (const category of DISCOVERY_PROBLEM_CATEGORIES) {
      expect(category.trend12m).toHaveLength(12);
      expect(category.primaryClusterIds.length).toBeGreaterThan(0);
      expect(getProblemCategoryEvidenceCount(category)).toBeGreaterThanOrEqual(100);
    }

    for (const theme of DISCOVERY_PROBLEM_THEMES) {
      expect(theme.clusters.length).toBeGreaterThanOrEqual(2);
    }

    for (const cluster of clusters) {
      expect(cluster.solutionTracks.length).toBeGreaterThanOrEqual(2);
      expect(cluster.unresolvedGaps.length).toBeGreaterThanOrEqual(3);
      expect(cluster.storyAngles.length).toBeGreaterThanOrEqual(1);
      expect(cluster.evidence.some((item) => item.side === "industry")).toBe(true);
      expect(cluster.evidence.some((item) => item.side === "academia" || item.side === "bridge")).toBe(true);
      expect(getProblemClusterScore(cluster)).toBeGreaterThanOrEqual(80);
    }
  });

  it("ships focused recent-month intelligence findings for two Discovery channels", () => {
    expect(DISCOVERY_INTELLIGENCE_RUN.channels).toEqual(["ai_frontier", "ai_for_research"]);
    expect(DISCOVERY_CHANNEL_PROFILES).toHaveLength(2);
    expect(DISCOVERY_FINDINGS.length).toBeGreaterThanOrEqual(10);

    const frontier = getDiscoveryFindingsByChannel("ai_frontier");
    const research = getDiscoveryFindingsByChannel("ai_for_research");

    expect(frontier.length).toBeGreaterThanOrEqual(5);
    expect(research.length).toBeGreaterThanOrEqual(5);
    for (const finding of DISCOVERY_FINDINGS) {
      expect(finding.evidence.length).toBeGreaterThanOrEqual(2);
      expect(getFindingCompositeScore(finding)).toBeGreaterThanOrEqual(70);
      expect(finding.implications.length).toBeGreaterThan(0);
      expect(finding.openQuestions.length).toBeGreaterThan(0);
    }
  });
  it("ships a CS radar with RH handoff-ready opportunities", () => {
    expect(DISCOVERY_OPPORTUNITIES).toHaveLength(5);
    for (const opportunity of DISCOVERY_OPPORTUNITIES) {
      expect(opportunity.slug).toBeTruthy();
      expect(opportunity.signals.length).toBeGreaterThanOrEqual(3);
      expect(opportunity.thirtyDayPlan).toHaveLength(4);
      expect(opportunity.brief.rh_handoff.initial_queries.length).toBeGreaterThan(0);
    }
  });

  it("includes watchlists and open-source inspirations for product design", () => {
    expect(DISCOVERY_WATCHLISTS.length).toBeGreaterThanOrEqual(3);
    expect(DISCOVERY_INSPIRATIONS.map((item) => item.name)).toEqual(
      expect.arrayContaining(["STORM", "PaperQA2", "ASTA Paper Finder", "Argo Scholar"]),
    );
  });


  it("ships multi-source hot topics with ocean judgment", () => {
    expect(DISCOVERY_HOT_TOPICS.length).toBeGreaterThanOrEqual(5);
    const todayTopics = getHotTopics("today");
    expect(todayTopics.length).toBeGreaterThan(0);
    expect(todayTopics[0].heatScore).toBeGreaterThanOrEqual(todayTopics.at(-1)?.heatScore ?? 0);

    for (const topic of DISCOVERY_HOT_TOPICS) {
      expect(topic.oceanLabel).toBeTruthy();
      expect(topic.evidence.length).toBeGreaterThanOrEqual(2);
      expect(getTotalSignalCount(topic)).toBeGreaterThanOrEqual(topic.evidence.length);
      expect(topic.contrarianSignals.length).toBeGreaterThan(0);
    }
  });

  it("computes workbench snapshots and source health for product KPIs", () => {
    const todaySnapshot = getDiscoverySnapshot("today");

    expect(todaySnapshot.topicCount).toBe(getHotTopics("today").length);
    expect(todaySnapshot.signalCount).toBeGreaterThan(0);
    expect(todaySnapshot.opportunityCandidateCount).toBeGreaterThan(0);
    expect(DISCOVERY_SOURCE_STATUS.length).toBeGreaterThanOrEqual(4);
    expect(DISCOVERY_SOURCE_STATUS.map((source) => source.name)).toContain("论文流");
  });

  it("finds opportunities by slug", () => {
    expect(
      getOpportunity("security-policy-and-auditing-for-tool-using-ai-agents")
        ?.category,
    ).toBe("Agent Security");
  });

  it("personalizes recommendations from a free-form profile", () => {
    const recommendations = getRecommendedOpportunities(
      "我想做 agent security 和 systems 方向的硕士论文",
    );

    expect(recommendations.map((item) => item.category)).toContain(
      "Agent Security",
    );
    expect(recommendations).toHaveLength(3);
  });
});
