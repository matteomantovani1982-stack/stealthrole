interface StatCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  accent?: boolean;
}

export default function StatCard({ label, value, subtitle, accent }: StatCardProps) {
  return (
    <div className="bg-white rounded-xl border border-surface-200 p-5 card-hover">
      <div className="text-[12px] font-medium text-ink-400 uppercase tracking-wide mb-1.5">
        {label}
      </div>
      <div
        className={`text-2xl font-bold ${accent ? "text-brand-600" : "text-ink-900"}`}
      >
        {value}
      </div>
      {subtitle && (
        <div className="text-[12px] text-ink-400 mt-1">{subtitle}</div>
      )}
    </div>
  );
}
