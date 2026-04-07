"use client";

import type { ApplicationItem } from "@/lib/api";

const SOURCE_LABELS: Record<string, string> = {
  linkedin: "LinkedIn",
  indeed: "Indeed",
  glassdoor: "Glassdoor",
  referral: "Referral",
  company_site: "Company Site",
  recruiter: "Recruiter",
  job_board: "Job Board",
  auto_apply: "Auto-Apply",
  email: "Email",
  other: "Other",
};

interface Props {
  app: ApplicationItem;
  onClick: () => void;
  onDragStart: (e: React.DragEvent) => void;
}

export default function KanbanCard({ app, onClick, onDragStart }: Props) {
  const daysAgo = Math.floor(
    (Date.now() - new Date(app.date_applied).getTime()) / 86_400_000
  );

  return (
    <div
      draggable
      onDragStart={onDragStart}
      onClick={onClick}
      className="bg-white rounded-lg border border-surface-200 p-3.5 cursor-pointer card-hover select-none"
    >
      <div className="text-sm font-medium text-ink-900 truncate">
        {app.company}
      </div>
      <div className="text-[12px] text-ink-500 truncate mt-0.5">
        {app.role}
      </div>
      <div className="flex items-center gap-2 mt-2.5">
        <span className="text-[11px] px-1.5 py-0.5 rounded bg-surface-100 text-ink-500">
          {SOURCE_LABELS[app.source_channel] || app.source_channel}
        </span>
        <span className="text-[11px] text-ink-400">
          {daysAgo === 0 ? "Today" : `${daysAgo}d ago`}
        </span>
      </div>
      {app.notes && (
        <div className="text-[11px] text-ink-400 mt-2 line-clamp-1">
          {app.notes}
        </div>
      )}
    </div>
  );
}
