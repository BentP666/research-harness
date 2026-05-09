"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Play, StopCircle, Zap, Target, Microscope } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  fetchTopicExpansion,
  startTopicExpansion,
  cancelTopicExpansion,
  type ExpansionJob,
  type ExpansionJobStatus as JobStatus,
} from "@/lib/api";

interface Preset {
  key: "quick" | "standard" | "deep" | "custom";
  label: string;
  sublabel: string;
  retrieval: number;
  deepRead: number;
  rounds: number;
  icon: typeof Zap;
}

const PRESETS: Preset[] = [
  { key: "quick",    label: "快速",  sublabel: "20 / 5 / 1",   retrieval: 20,  deepRead: 5,  rounds: 1, icon: Zap },
  { key: "standard", label: "标准",  sublabel: "100 / 20 / 3", retrieval: 100, deepRead: 20, rounds: 3, icon: Target },
  { key: "deep",     label: "深度",  sublabel: "300 / 50 / 5", retrieval: 300, deepRead: 50, rounds: 5, icon: Microscope },
];

const STATUS_BADGE: Record<JobStatus, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  pending:   { label: "排队中", variant: "secondary" },
  running:   { label: "运行中", variant: "default" },
  completed: { label: "已完成", variant: "outline" },
  failed:    { label: "失败",   variant: "destructive" },
  cancelled: { label: "已取消", variant: "secondary" },
};

interface Props {
  topicId: number;
}

export function ExpansionPanel({ topicId }: Props) {
  const qc = useQueryClient();
  const [selectedPreset, setSelectedPreset] = useState<Preset["key"]>("standard");
  const [customRetrieval, setCustomRetrieval] = useState(100);
  const [customDeepRead, setCustomDeepRead] = useState(20);
  const [customRounds, setCustomRounds] = useState(3);

  const jobQuery = useQuery<ExpansionJob | null>({
    queryKey: ["topic-expansion", topicId],
    queryFn: async () => {
      try {
        return await fetchTopicExpansion(topicId);
      } catch {
        return null;
      }
    },
    refetchInterval: (query) => {
      const job = query.state.data;
      return job && (job.status === "running" || job.status === "pending") ? 2000 : false;
    },
  });

  const startMut = useMutation({
    mutationFn: (params: { retrieval_target: number; deep_read_target: number; rounds: number }) =>
      startTopicExpansion(topicId, params),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["topic-expansion", topicId] }),
  });

  const cancelMut = useMutation({
    mutationFn: () => cancelTopicExpansion(topicId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["topic-expansion", topicId] }),
  });

  const job = jobQuery.data;
  const isActive = job && (job.status === "running" || job.status === "pending");

  const currentPreset = PRESETS.find((p) => p.key === selectedPreset);
  const targets =
    selectedPreset === "custom"
      ? { retrieval: customRetrieval, deepRead: customDeepRead, rounds: customRounds }
      : { retrieval: currentPreset!.retrieval, deepRead: currentPreset!.deepRead, rounds: currentPreset!.rounds };

  const handleStart = () => {
    startMut.mutate({
      retrieval_target: targets.retrieval,
      deep_read_target: targets.deepRead,
      rounds: targets.rounds,
    });
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Target className="size-4" />
            检索与精读批次
          </CardTitle>
          {job && (
            <Badge variant={STATUS_BADGE[job.status].variant}>
              {STATUS_BADGE[job.status].label}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {isActive ? (
          <ActiveJobView job={job} onCancel={() => cancelMut.mutate()} cancelling={cancelMut.isPending} />
        ) : (
          <PresetPicker
            selected={selectedPreset}
            onSelect={setSelectedPreset}
            customRetrieval={customRetrieval}
            customDeepRead={customDeepRead}
            customRounds={customRounds}
            onCustomChange={(r, d, n) => {
              setCustomRetrieval(r);
              setCustomDeepRead(d);
              setCustomRounds(n);
            }}
            lastJob={job}
          />
        )}

        {!isActive && (
          <div className="flex items-center justify-between gap-3 pt-2 border-t">
            <div className="text-xs text-muted-foreground">
              目标：检索 <span className="font-semibold text-foreground">{targets.retrieval}</span>，
              精读 <span className="font-semibold text-foreground">{targets.deepRead}</span>，
              共 <span className="font-semibold text-foreground">{targets.rounds}</span> 轮
            </div>
            <Button onClick={handleStart} disabled={startMut.isPending} size="sm">
              {startMut.isPending ? (
                <><Loader2 className="size-4 animate-spin mr-1" /> 启动中</>
              ) : (
                <><Play className="size-4 mr-1" /> 启动扩展</>
              )}
            </Button>
          </div>
        )}

        {startMut.isError && (
          <p className="text-xs text-destructive">
            启动失败：{(startMut.error as Error).message}
          </p>
        )}
        {job?.status === "failed" && job.last_error && (
          <p className="text-xs text-destructive">上次失败：{job.last_error}</p>
        )}
      </CardContent>
    </Card>
  );
}

function PresetPicker({
  selected,
  onSelect,
  customRetrieval,
  customDeepRead,
  customRounds,
  onCustomChange,
  lastJob,
}: {
  selected: Preset["key"];
  onSelect: (k: Preset["key"]) => void;
  customRetrieval: number;
  customDeepRead: number;
  customRounds: number;
  onCustomChange: (r: number, d: number, n: number) => void;
  lastJob: ExpansionJob | null | undefined;
}) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {PRESETS.map((p) => {
          const Icon = p.icon;
          return (
            <button
              key={p.key}
              onClick={() => onSelect(p.key)}
              className={cn(
                "flex flex-col items-start gap-1 p-3 rounded-md border text-left transition",
                selected === p.key
                  ? "border-primary bg-primary/5 ring-1 ring-primary"
                  : "border-border hover:bg-muted/50"
              )}
            >
              <Icon className="size-4" />
              <div className="text-sm font-medium">{p.label}</div>
              <div className="text-xs text-muted-foreground tabular-nums">{p.sublabel}</div>
            </button>
          );
        })}
        <button
          onClick={() => onSelect("custom")}
          className={cn(
            "flex flex-col items-start gap-1 p-3 rounded-md border text-left transition",
            selected === "custom"
              ? "border-primary bg-primary/5 ring-1 ring-primary"
              : "border-border hover:bg-muted/50"
          )}
        >
          <div className="text-sm font-medium">自定义</div>
          <div className="text-xs text-muted-foreground">手动设定</div>
        </button>
      </div>

      {selected === "custom" && (
        <div className="grid grid-cols-3 gap-2">
          <label className="space-y-1">
            <span className="text-xs text-muted-foreground">检索目标</span>
            <Input
              type="number"
              min={1}
              max={500}
              value={customRetrieval}
              onChange={(e) => onCustomChange(Number(e.target.value || 0), customDeepRead, customRounds)}
            />
          </label>
          <label className="space-y-1">
            <span className="text-xs text-muted-foreground">精读目标</span>
            <Input
              type="number"
              min={0}
              max={100}
              value={customDeepRead}
              onChange={(e) => onCustomChange(customRetrieval, Number(e.target.value || 0), customRounds)}
            />
          </label>
          <label className="space-y-1">
            <span className="text-xs text-muted-foreground">扩展轮次</span>
            <Input
              type="number"
              min={1}
              max={10}
              value={customRounds}
              onChange={(e) => onCustomChange(customRetrieval, customDeepRead, Number(e.target.value || 0))}
            />
          </label>
        </div>
      )}

      {lastJob && lastJob.status === "completed" && (
        <div className="text-xs text-muted-foreground">
          上次任务：入库 {lastJob.papers_fetched} 篇，精读 {lastJob.papers_deep_read} 篇（{lastJob.rounds_target} 轮）
        </div>
      )}
    </div>
  );
}

function ActiveJobView({
  job,
  onCancel,
  cancelling,
}: {
  job: ExpansionJob;
  onCancel: () => void;
  cancelling: boolean;
}) {
  const retrievalPct = Math.min(100, Math.round((job.papers_fetched / Math.max(1, job.retrieval_target)) * 100));
  const deepReadPct = Math.min(100, Math.round((job.papers_deep_read / Math.max(1, job.deep_read_target)) * 100));

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium">
          Round {job.current_round} / {job.rounds_target}
        </span>
        <Button
          size="sm"
          variant="outline"
          onClick={onCancel}
          disabled={cancelling}
        >
          {cancelling ? (
            <><Loader2 className="size-3 animate-spin mr-1" /> 取消中</>
          ) : (
            <><StopCircle className="size-3 mr-1" /> 取消</>
          )}
        </Button>
      </div>

      <ProgressBar
        label="本轮新增"
        done={job.papers_fetched}
        target={job.retrieval_target}
        pct={retrievalPct}
        footnote={
          typeof job.topic_paper_count === "number"
            ? `主题已有 ${job.topic_paper_count} 篇（含往期）`
            : undefined
        }
      />
      <ProgressBar
        label="精读"
        done={job.papers_deep_read}
        target={job.deep_read_target}
        pct={deepReadPct}
        footnote={
          typeof job.topic_deep_read_count === "number"
            ? `主题已精读 ${job.topic_deep_read_count} 篇`
            : undefined
        }
      />
    </div>
  );
}

function ProgressBar({
  label,
  done,
  target,
  pct,
  footnote,
}: {
  label: string;
  done: number;
  target: number;
  pct: number;
  footnote?: string;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="tabular-nums font-medium">
          {done} / {target} <span className="text-muted-foreground ml-1">({pct}%)</span>
        </span>
      </div>
      <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-primary transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      {footnote && (
        <div className="text-[10px] text-muted-foreground/70 tabular-nums">
          {footnote}
        </div>
      )}
    </div>
  );
}
