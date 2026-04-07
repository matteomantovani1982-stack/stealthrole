import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import { useQuery } from '@tanstack/react-query'
import { profileApi } from '../api/profile'
import { analyticsApi } from '../api/analytics'
import s from './Home.module.css'

export default function Home() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { data: usage } = useQuery({ queryKey: ['usage'], queryFn: profileApi.usage, staleTime: 60_000 })
  const { data: dash } = useQuery({ queryKey: ['dashboard'], queryFn: analyticsApi.dashboard, staleTime: 30_000 })

  const firstName = user?.full_name?.split(' ')[0] ?? 'there'
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  return (
    <div className={s.page}>

      {/* Hero */}
      <div className={s.hero}>
        <div className={s.heroEyebrow}>⚡ StealthRole</div>
        <h1 className={s.heroTitle}>{greeting}, {firstName}.</h1>
        <p className={s.heroSub}>
          Your next role — before the market knows you're looking.
        </p>
      </div>

      {/* What is StealthRole */}
      <div className={s.explainer}>
        <div className={s.explainerCard}>
          <div className={s.explainerIcon}>🕵️</div>
          <div className={s.explainerTitle}>Move in stealth</div>
          <div className={s.explainerText}>
            You're employed. You're good. But you're selectively exploring.
            StealthRole lets you research, prepare, and apply — without anyone knowing.
          </div>
        </div>
        <div className={s.explainerCard}>
          <div className={s.explainerIcon}>🎯</div>
          <div className={s.explainerTitle}>Beat the queue</div>
          <div className={s.explainerText}>
            Most applicants spend 20 minutes copy-pasting CVs. You arrive with a tailored CV,
            company intel, named contacts, and a salary benchmark — in 60 seconds.
          </div>
        </div>
        <div className={s.explainerCard}>
          <div className={s.explainerIcon}>📡</div>
          <div className={s.explainerTitle}>Find the hidden market</div>
          <div className={s.explainerText}>
            80% of senior roles are never posted. We monitor funding rounds, leadership changes,
            and expansion signals — and alert you before the job exists.
          </div>
        </div>
      </div>

      {/* Quick actions */}
      <div className={s.section}>
        <div className={s.sectionTitle}>What do you want to do?</div>
        <div className={s.actions}>

          <button className={s.actionCard} onClick={() => navigate('/applications/new')}>
            <div className={s.actionIcon}>🚀</div>
            <div className={s.actionContent}>
              <div className={s.actionTitle}>Generate Intelligence Pack</div>
              <div className={s.actionDesc}>
                Paste a job description → get a tailored CV, company intel, named contacts,
                salary data, and interview strategy. Takes 60 seconds.
              </div>
            </div>
            <div className={s.actionArrow}>→</div>
          </button>

          <button className={s.actionCard} onClick={() => navigate('/applications/new?mode=cv_only')}>
            <div className={s.actionIcon}>✏️</div>
            <div className={s.actionContent}>
              <div className={s.actionTitle}>Modify my CV for a role</div>
              <div className={s.actionDesc}>
                Have a JD or a few lines about a role? We'll tailor your CV to it — fast.
                No full intel pack, just the CV.
              </div>
            </div>
            <div className={s.actionArrow}>→</div>
          </button>

          <button className={s.actionCard} onClick={() => navigate('/dashboard')}>
            <div className={s.actionIcon}>🔍</div>
            <div className={s.actionContent}>
              <div className={s.actionTitle}>Scout jobs now</div>
              <div className={s.actionDesc}>
                Browse live scouted roles matched to your profile. Rate them, generate packs,
                apply directly from the card.
              </div>
            </div>
            <div className={s.actionArrow}>→</div>
          </button>

          <button className={s.actionCard} onClick={() => navigate('/applications')}>
            <div className={s.actionIcon}>📋</div>
            <div className={s.actionContent}>
              <div className={s.actionTitle}>Track my applications</div>
              <div className={s.actionDesc}>
                Kanban board across Watching → Applied → Interviewing → Offer.
                Notes, follow-ups, and status in one place.
              </div>
            </div>
            <div className={s.actionArrow}>→</div>
          </button>

          <button className={s.actionCard} onClick={() => navigate('/profile')}>
            <div className={s.actionIcon}>👤</div>
            <div className={s.actionContent}>
              <div className={s.actionTitle}>Set my job preferences</div>
              <div className={s.actionDesc}>
                Tell us your target regions, roles, seniority, sectors, and salary.
                The scout engine uses this to find your best matches automatically.
              </div>
            </div>
            <div className={s.actionArrow}>→</div>
          </button>

        </div>
      </div>

      {/* Dashboard stats */}
      {dash && (
        <div className={s.section}>
          <div className={s.sectionTitle}>Your Dashboard</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginTop: 12 }}>
            <StatCard label="Radar Opportunities" value={dash.radar_total} onClick={() => navigate('/dashboard')} />
            <StatCard label="Applications" value={dash.total_applications} onClick={() => navigate('/applications')} />
            <StatCard label="Shadow Apps" value={dash.total_shadow_applications} />
            <StatCard label="Profile Strength" value={`${Math.round(dash.profile_completeness * 100)}%`} onClick={() => navigate('/profile')} />
          </div>
          {dash.recent_shadow_applications.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-2)', marginBottom: 8 }}>Recent Shadow Applications</div>
              {dash.recent_shadow_applications.map((sa: any) => (
                <div
                  key={sa.id}
                  onClick={() => navigate(`/shadow/${sa.id}`)}
                  style={{
                    padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)',
                    borderRadius: 8, marginBottom: 6, cursor: 'pointer', fontSize: 13,
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  }}
                >
                  <span><strong>{sa.hypothesis_role || sa.company}</strong> at {sa.company}</span>
                  <span style={{
                    fontSize: 11, padding: '2px 6px', borderRadius: 4,
                    background: sa.status === 'completed' ? '#D1FAE5' : sa.status === 'failed' ? '#FEE2E2' : '#FEF3C7',
                    color: sa.status === 'completed' ? '#065F46' : sa.status === 'failed' ? '#991B1B' : '#92400E',
                  }}>
                    {sa.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Usage strip */}
      {usage && (
        <div className={s.usageStrip}>
          <span className={s.usagePlan}>{usage.plan} plan</span>
          <span className={s.usageSep}>·</span>
          <span className={s.usageCount}>
            <strong>{usage.runs_used_this_month}</strong> of {usage.monthly_run_limit ?? '∞'} packs used this month
          </span>
          {usage.plan === 'free' && (
            <>
              <span className={s.usageSep}>·</span>
              <button className={s.upgradeLink} onClick={() => navigate('/billing')}>
                Upgrade for unlimited →
              </button>
            </>
          )}
        </div>
      )}

    </div>
  )
}

function StatCard({ label, value, onClick }: { label: string; value: number | string; onClick?: () => void }) {
  return (
    <div
      onClick={onClick}
      style={{
        padding: '16px 14px', background: 'var(--bg)', border: '1px solid var(--border)',
        borderRadius: 10, cursor: onClick ? 'pointer' : 'default', textAlign: 'center',
      }}
    >
      <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--text)' }}>{value}</div>
      <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 4 }}>{label}</div>
    </div>
  )
}
