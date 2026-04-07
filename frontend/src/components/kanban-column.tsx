"use client";

import type { ApplicationItem } from "@/lib/api";
import KanbanCard from "./kanban-card";

const STAGE_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  watching: { label: "Watching", color: "text-purple-700", bg: "bg-purple-50" },
  applied: { label: "Applied", color: "text-blue-700", bg: "bg-blue-50" },
  interview: { label: "Interview", color: "text-amber-700", bg: "bg-amber-50" },
  offer: { label: "Offer", color: "text-green-700", bg: "bg-green-50" },
  rejected: { label: "Rejected", color: "text-red-700", bg: "bg-red-50" },
};

interface Props {
  stage: string;
  applications: ApplicationItem[];
  onCardClick: (app: ApplicationItem) => void;
  onDrop: (appId: string, newStage: string) => void;
}

export default function KanbanColumn({ stage, applications, onCardClick, onDrop }: Props) {
  const config = STAGE_CONFIG[stage] || { label: stage, color: "text-ink-700", bg: "bg-surface-100" };

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    e.currentTarget.classList.add("ring-2", "ring-brand-500/30");
  }

  function handleDragLeave(e: React.DragEvent) {
    e.currentTarget.classList.remove("ring-2", "ring-brand-500/30");
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    e.currentTarget.classList.remove("ring-2", "ring-brand-500/30");
    const appId = e.dataTransfer.getData("application/id");
    if (appId) {
      onDrop(appId, stage);
    }
  }

  return (
    <div
      className="flex flex-col min-w-[200px] flex-1 rounded-xl bg-surface-50 border border-surface-200 transition-all"
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-surface-200">
        <div className="flex items-center gap-2">
          <span className={`text-[13px] font-semibold ${config.color}`}>
            {config.label}
          </span>
          <span className={`text-[11px] px-1.5 py-0.5 rounded-full font-medium ${config.bg} ${config.color}`}>
            {applications.length}
          </span>
        </div>
      </div>

      {/* Cards */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2 min-h-[200px]">
        {applications.map((app) => (
          <KanbanCard
            key={app.id}
            app={app}
            onClick={() => onCardClick(app)}
            onDragStart={(e) => {
              e.dataTransfer.setData("application/id", app.id);
              e.dataTransfer.effectAllowed = "move";
            }}
          />
        ))}
        {applications.length === 0 && (
          <div className="text-[12px] text-ink-300 text-center py-8">
            Drop here
          </div>
        )}
      </div>
    </div>
  );
}
