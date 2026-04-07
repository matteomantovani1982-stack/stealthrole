"use client";

import { useEffect, useRef, useState } from "react";
import type { Opportunity } from "@/lib/api";

const CYCLE_MS = 20_000; // 20 seconds per card

function initialsFrom(name: string): string {
  return name
    .split(/[\s&]+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() || "")
    .join("");
}

function freshnessTag(firstSeen: string | null): string {
  if (!firstSeen) return "New";
  const days = Math.floor(
    (Date.now() - new Date(firstSeen).getTime()) / 86_400_000
  );
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days <= 7) return `${days}d ago`;
  return `${Math.floor(days / 7)}w ago`;
}

function matchColor(score: number): string {
  if (score >= 75) return "text-green-600 bg-green-50";
  if (score >= 50) return "text-amber-600 bg-amber-50";
  return "text-ink-500 bg-surface-100";
}

interface Props {
  opportunities: Opportunity[];
}

export default function OpportunityCarousel({ opportunities }: Props) {
  const [index, setIndex] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval>>();

  const items = opportunities.slice(0, 10);

  useEffect(() => {
    if (items.length <= 1) return;
    timerRef.current = setInterval(() => {
      setIndex((prev) => (prev + 1) % items.length);
    }, CYCLE_MS);
    return () => clearInterval(timerRef.current);
  }, [items.length]);

  if (!items.length) {
    return (
      <div className="bg-white rounded-xl border border-surface-200 p-8 text-center text-ink-400 text-sm">
        No opportunities yet. Set up your profile and preferences to start scanning.
      </div>
    );
  }

  // Show 3 cards at a time (or fewer on small lists)
  const visible = [];
  for (let i = 0; i < Math.min(3, items.length); i++) {
    visible.push(items[(index + i) % items.length]);
  }

  return (
    <div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {visible.map((opp) => (
          <div
            key={opp.id}
            className="bg-white rounded-xl border border-surface-200 p-5 card-hover cursor-pointer"
          >
            {/* Header: initials + title */}
            <div className="flex items-start gap-3 mb-3">
              <div className="w-10 h-10 rounded-lg bg-brand-50 text-brand-700 flex items-center justify-center text-sm font-bold shrink-0">
                {initialsFrom(opp.company)}
              </div>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-ink-900 truncate">
                  {opp.role || "Potential Role"}
                </div>
                <div className="text-[12px] text-ink-400 truncate">
                  {opp.company}
                  {opp.location ? ` \u00B7 ${opp.location}` : ""}
                </div>
              </div>
            </div>

            {/* Tags row */}
            <div className="flex flex-wrap gap-1.5 mb-3">
              {/* Match % */}
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium ${matchColor(opp.radar_score)}`}
              >
                {opp.radar_score}% match
              </span>

              {/* Freshness */}
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-surface-100 text-ink-500">
                {freshnessTag(opp.first_seen_at)}
              </span>

              {/* Hidden market badge */}
              {opp.evidence_tier !== "strong" && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-purple-50 text-purple-700">
                  Hidden market
                </span>
              )}
            </div>

            {/* Signal tags */}
            {opp.source_tags?.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {opp.source_tags.slice(0, 3).map((tag) => (
                  <span
                    key={tag}
                    className="text-[10px] px-1.5 py-0.5 rounded bg-surface-50 text-ink-500 border border-surface-200"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Dots */}
      {items.length > 3 && (
        <div className="flex justify-center gap-1.5 mt-4">
          {items.map((_, i) => (
            <button
              key={i}
              onClick={() => setIndex(i)}
              className={`w-1.5 h-1.5 rounded-full transition-colors ${
                i === index ? "bg-brand-600" : "bg-surface-300"
              }`}
            />
          ))}
        </div>
      )}
    </div>
  );
}
