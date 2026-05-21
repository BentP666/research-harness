"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, WandSparkles } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { getRecommendedOpportunities } from "@/lib/discovery-product";

const defaultProfile = "我想做 agent / systems / security 相关的硕士论文，希望 30 天内能做出实验雏形。";

export function ScoutPanel() {
  const [profile, setProfile] = useState(defaultProfile);
  const recommendations = useMemo(() => getRecommendedOpportunities(profile), [profile]);

  return (
    <section className="rounded-[2rem] border border-slate-200 bg-slate-950 p-6 text-white shadow-2xl shadow-slate-950/20 dark:border-white/10">
      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-cyan-100">
            <WandSparkles className="size-3.5" />
            Discovery Scout
          </div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight">输入你的背景，立刻给出方向排序</h2>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            这一版先在前端做轻量匹配；产品化后这里会接入用户约束、历史阅读、可用数据、目标会议和风险偏好。
          </p>
          <Textarea
            value={profile}
            onChange={(event) => setProfile(event.target.value)}
            className="mt-5 min-h-36 border-white/10 bg-white/5 text-white placeholder:text-slate-500 focus-visible:ring-cyan-300/30"
            placeholder="例如：我在广告系统组，有日志数据，想做 agent evaluation 或 causal inference..."
          />
        </div>
        <div className="space-y-3">
          {recommendations.map((item, index) => (
            <Link
              key={item.slug}
              href={`/discovery/opportunities/${item.slug}`}
              className="group block rounded-2xl border border-white/10 bg-white/[0.04] p-4 transition hover:border-cyan-200/50 hover:bg-white/[0.08]"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-500">推荐 {index + 1}</div>
                  <h3 className="mt-1 font-semibold text-white">{item.title}</h3>
                </div>
                <ArrowRight className="size-4 text-slate-500 transition group-hover:translate-x-1 group-hover:text-cyan-200" />
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-300">{item.oneLiner}</p>
              <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-400">
                <span>动量 {item.radar.momentum}</span>
                <span>·</span>
                <span>可行 {item.radar.feasibility}</span>
                <span>·</span>
                <span>{item.category}</span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
