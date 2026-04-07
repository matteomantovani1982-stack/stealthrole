"use client";

import type { HiddenSignal } from "@/lib/api";

const SIGNAL_COLORS: Record<string, string> = {
  funding: "bg-green-50 text-green-700 border-green-200",
  leadership: "bg-blue-50 text-blue-700 border-blue-200",
  expansion: "bg-amber-50 text-amber-700 border-amber-200",
  hiring_surge: "bg-purple-50 text-purple-700 border-purple-200",
  product_launch: "bg-pink-50 text-pink-700 border-pink-200",
  velocity: "bg-orange-50 text-orange-700 border-orange-200",
  distress: "bg-red-50 text-red-700 border-red-200",
};

const SIGNAL_LABELS: Record<string, string> = {
  funding: "Funding",
  leadership: "Leadership Change",
  expansion: "Expansion",
  hiring_surge: "Hiring",
  product_launch: "Product Launch",
  velocity: "Market Trend",
  distress: "Restructuring",
};

interface Props {
  signals: HiddenSignal[];
}

export default function MarketSignals({ signals }: Props) {
  const items = signals;

  if (!items.length) {
    return (
      <div className="bg-white rounded-xl border border-surface-200 p-8 text-center text-ink-400 text-sm">
        No market signals detected yet. Signals refresh every 30 minutes.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {items.map((signal) => {
        const tagStyle =
          SIGNAL_COLORS[signal.signal_type] ||
          "bg-surface-100 text-ink-500 border-surface-200";
        const tagLabel =
          SIGNAL_LABELS[signal.signal_type] || signal.signal_type;

        return (
          <div
            key={signal.id}
            className="bg-white rounded-xl border border-surface-200 px-5 py-4 card-hover cursor-pointer flex items-start gap-4"
          >
            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-ink-900 mb-1 leading-snug">
                {signal.company_name}
                {signal.likely_roles?.[0]
                  ? ` \u2014 likely hiring ${signal.likely_roles[0]}`
                  : ""}
              </div>
              <div className="text-[12px] text-ink-400 line-clamp-2">
                {signal.reasoning || "Signal detected from market activity."}
              </div>
            </div>

            {/* Tags */}
            <div className="flex flex-col gap-1 shrink-0 items-end">
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium border ${tagStyle}`}
              >
                {tagLabel}
              </span>
              {signal.confidence >= 0.7 && (
                <span className="text-[10px] text-ink-400">
                  {Math.round(signal.confidence * 100)}% confidence
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
