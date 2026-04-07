import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { scoutApi } from '../api/scout'
import { profileApi } from '../api/profile'
import s from './Dashboard.module.css'

// ─── Types ────────────────────────────────────────────────────────────────────
interface Signal { signal_type: string; headline: string; detail: string; source_url: string; source_name: string; published_date: string }
interface OpportunityCard {
  id: string; company: string; company_type?: string; sector: string; location: string
  signals?: Signal[]; signal_sources?: any[]
  signal_summary: string; fit_score: number; fit_reasons: string[]; red_flags: string[]
  suggested_role: string; suggested_action: string; contact_name: string; contact_title: string
  salary_estimate: string; urgency: string; apply_url: string; is_posted: boolean; posted_title: string
  timeline?: string; competition_level?: string; outreach_hook?: string
  signal_types?: string[]; signal_badges?: any[]
}
interface LiveOpening {
  title: string; company: string; snippet: string; url: string; source: string
  date: string; status: 'current' | 'imminent' | 'strategic'; is_posted: boolean
}
interface ScoutData {
  opportunities: OpportunityCard[]; live_openings: LiveOpening[]
  signals_detected: number; is_demo: boolean; scored_by: string; engine_version?: string
}

// ─── Config ──────────────────────────────────────────────────────────────────
const SIG_META: Record<string, { icon: string; label: string; color: string }> = {
  funding:    { icon: '💰', label: 'Funding',          color: '#059669' },
  leadership: { icon: '👤', label: 'Leadership change', color: '#7c3aed' },
  expansion:  { icon: '🌍', label: 'Expansion',         color: '#2563eb' },
  velocity:   { icon: '📈', label: 'Hiring spike',      color: '#0891b2' },
  distress:   { icon: '⚠️', label: 'Restructure',      color: '#dc2626' },
}
const URGENCY: Record<string, { color: string; bg: string; label: string }> = {
  high:   { color: '#dc2626', bg: '#fef2f2', label: 'Act now' },
  medium: { color: '#d97706', bg: '#fffbeb', label: 'This week' },
  low:    { color: '#6b7280', bg: '#f9fafb', label: 'Monitor' },
}
const TIMELINE_META: Record<string, { icon: string; label: string }> = {
  immediate:    { icon: '🔴', label: 'Immediate — role likely open now' },
  '1-3 months': { icon: '🟡', label: '1-3 months — hiring process forming' },
  '3-6 months': { icon: '🟢', label: '3-6 months — strategic positioning window' },
}
const STATUS_META: Record<string, { bg: string; border: string; badge: string; label: string; sub: string }> = {
  current:   { bg: '#dcfce7', border: '#86efac', badge: '#16a34a', label: 'Current vacancy',    sub: 'Posted now — apply directly' },
  imminent:  { bg: '#fefce8', border: '#fde047', badge: '#ca8a04', label: 'Imminent opening',   sub: 'Signal detected — role forming' },
  strategic: { bg: '#fef2f2', border: '#fca5a5', badge: '#dc2626', label: 'Strategic horizon',  sub: 'Early signal — position yourself' },
}

// ─── Opportunity Card ────────────────────────────────────────────────────────
function OppCard({ card, onGenerate }: { card: OpportunityCard; onGenerate: (c: OpportunityCard) => void }) {
  const [open, setOpen] = useState(false)
  const urg = URGENCY[card.urgency] || URGENCY.low
  const signals = card.signals || []
  const sigTypes = card.signal_types || [...new Set(signals.map(s => s.signal_type))]
  const timeline = TIMELINE_META[card.timeline || ''] || null

  return (
    <div className={s.oppCard}>
      {/* Header bar */}
      <div className={s.oppHeader} style={{ borderLeft: `4px solid ${urg.color}` }} onClick={() => setOpen(o => !o)}>
        <div className={s.oppHeaderLeft}>
          <div className={s.oppCompany}>
            {card.company}
            {card.company_type && <span className={s.oppType}>{card.company_type}</span>}
          </div>
          <div className={s.oppMeta}>
            {card.suggested_role && <strong>{card.suggested_role}</strong>}
            {card.sector && <span> · {card.sector}</span>}
            {card.location && <span> · {card.location}</span>}
          </div>
          <div className={s.oppBadges}>
            {sigTypes.map(t => {
              const m = SIG_META[t]
              return m ? <span key={t} className={s.sigBadge} style={{background: m.color + '15', color: m.color}}>{m.icon} {m.label}</span> : null
            })}
            <span className={s.urgBadge} style={{background: urg.bg, color: urg.color, border: `1px solid ${urg.color}30`}}>{urg.label}</span>
          </div>
        </div>
        <div className={s.oppHeaderRight}>
          <div className={s.fitRing} style={{ borderColor: card.fit_score >= 70 ? '#059669' : card.fit_score >= 50 ? '#d97706' : '#94a3b8' }}>
            <span className={s.fitNum}>{card.fit_score}</span>
          </div>
          <span className={s.chevron}>{open ? '▲' : '▼'}</span>
        </div>
      </div>

      {/* Summary line — always visible */}
      <div className={s.oppSummary} onClick={() => setOpen(o => !o)}>
        {card.signal_summary}
      </div>

      {/* Quick info row */}
      <div className={s.oppQuickRow}>
        {card.salary_estimate && <span className={s.quickChip}>💰 {card.salary_estimate}</span>}
        {card.contact_name && <span className={s.quickChip}>👤 {card.contact_name}{card.contact_title ? `, ${card.contact_title}` : ''}</span>}
        {timeline && <span className={s.quickChip}>{timeline.icon} {card.timeline}</span>}
        {card.competition_level && <span className={s.quickChip}>🏁 Competition: {card.competition_level}</span>}
      </div>

      {/* ── Expanded detail panel ── */}
      {open && (
        <div className={s.oppDetail}>
          {/* Intelligence Analysis */}
          <div className={s.detailSection}>
            <div className={s.detailTitle}>🔍 Intelligence Analysis</div>
            <div className={s.detailBody}>{card.signal_summary}</div>
            {card.suggested_action && (
              <div className={s.detailAction}>
                <strong>Recommended action:</strong> {card.suggested_action}
              </div>
            )}
          </div>

          {/* Timeline */}
          {timeline && (
            <div className={s.detailSection}>
              <div className={s.detailTitle}>📅 Expected Timeline</div>
              <div className={s.detailBody}>{timeline.label}</div>
            </div>
          )}

          {/* Why you fit */}
          {card.fit_reasons && card.fit_reasons.length > 0 && (
            <div className={s.detailSection}>
              <div className={s.detailTitle}>✅ Why you're a fit</div>
              <ul className={s.detailList}>
                {card.fit_reasons.map((r,i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          )}

          {/* Red flags */}
          {card.red_flags && card.red_flags.length > 0 && (
            <div className={s.detailSection}>
              <div className={s.detailTitle}>⚠️ Watch out</div>
              <ul className={s.detailList} style={{color:'#b91c1c'}}>
                {card.red_flags.map((r,i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          )}

          {/* Outreach hook */}
          {card.outreach_hook && (
            <div className={s.detailSection}>
              <div className={s.detailTitle}>💬 Ready-to-use outreach</div>
              <div className={s.outreachBox}>{card.outreach_hook}</div>
            </div>
          )}

          {/* Sources — where the intelligence came from */}
          {signals.length > 0 && (
            <div className={s.detailSection}>
              <div className={s.detailTitle}>📰 Sources</div>
              <div className={s.sourceList}>
                {signals.map((sig, i) => (
                  <a key={i} href={sig.source_url} target="_blank" rel="noreferrer" className={s.sourceLink}>
                    <span className={s.sourceIcon}>{SIG_META[sig.signal_type]?.icon || '📄'}</span>
                    <div className={s.sourceInfo}>
                      <div className={s.sourceHeadline}>{sig.headline}</div>
                      <div className={s.sourceMeta}>{sig.source_name}{sig.published_date ? ` · ${sig.published_date}` : ''}</div>
                    </div>
                    <span className={s.sourceArrow}>↗</span>
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Also show signal_sources if no signals array */}
          {signals.length === 0 && card.signal_sources && (card.signal_sources as any[]).length > 0 && (
            <div className={s.detailSection}>
              <div className={s.detailTitle}>📰 Sources</div>
              <div className={s.sourceList}>
                {(card.signal_sources as any[]).map((src: any, i: number) => (
                  <a key={i} href={src.url} target="_blank" rel="noreferrer" className={s.sourceLink}>
                    <div className={s.sourceInfo}>
                      <div className={s.sourceHeadline}>{src.headline || src.name}</div>
                      <div className={s.sourceMeta}>{src.name}{src.date ? ` · ${src.date}` : ''}</div>
                    </div>
                    <span className={s.sourceArrow}>↗</span>
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div className={s.detailActions}>
            {card.apply_url && (
              <a href={card.apply_url} target="_blank" rel="noreferrer" className={s.actionBtnOutline}>View company ↗</a>
            )}
            <button className={s.actionBtnPrimary} onClick={() => onGenerate(card)}>Generate full pack →</button>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Live Opening Card ───────────────────────────────────────────────────────
function OpeningCard({ job, onGenerate }: { job: LiveOpening; onGenerate: (url: string, title: string) => void }) {
  const meta = STATUS_META[job.status] || STATUS_META.strategic
  return (
    <div className={s.openingCard} style={{ background: meta.bg, borderColor: meta.border }}>
      <div className={s.openingTop}>
        <div className={s.openingBadge} style={{ background: meta.badge }}>{meta.label}</div>
        <div className={s.openingSource}>{job.source}</div>
      </div>
      <div className={s.openingTitle}>{job.title}</div>
      {job.company && <div className={s.openingCompany}>{job.company}</div>}
      {job.snippet && <div className={s.openingSnippet}>{job.snippet}</div>}
      <div className={s.openingFooter}>
        <div className={s.openingSub}>{meta.sub}</div>
        <div className={s.openingBtns}>
          {job.url && <a href={job.url} target="_blank" rel="noreferrer" className={s.viewBtn}>View →</a>}
          <button className={s.genBtnSm} onClick={() => onGenerate(job.url, job.title)}>Generate pack →</button>
        </div>
      </div>
    </div>
  )
}

// ─── Main Dashboard ──────────────────────────────────────────────────────────
export default function Dashboard() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<'signals' | 'openings'>('signals')

  const { data: profile } = useQuery({ queryKey: ['profile'], queryFn: profileApi.get })

  const { data, isLoading, error, refetch } = useQuery<ScoutData>({
    queryKey: ['scout-signals'],
    queryFn: scoutApi.getSignals,
    staleTime: 10 * 60 * 1000,
  })

  const handleGenerate = (card: OpportunityCard) => {
    sessionStorage.setItem('scout_job_url', card.apply_url || '')
    sessionStorage.setItem('scout_job_title', card.suggested_role || card.company)
    sessionStorage.setItem('scout_company', card.company)
    navigate(`/applications/new`)
  }

  const handleOpeningGenerate = (url: string, title: string) => {
    sessionStorage.setItem('scout_job_url', url || '')
    sessionStorage.setItem('scout_job_title', title || '')
    navigate('/applications/new')
  }

  const opportunities = data?.opportunities || []
  const liveOpenings  = data?.live_openings  || []
  const current   = liveOpenings.filter(j => j.status === 'current')
  const imminent  = liveOpenings.filter(j => j.status === 'imminent')
  const strategic = liveOpenings.filter(j => j.status === 'strategic')

  const prefComplete = (() => {
    try {
      const ctx = JSON.parse(profile?.global_context || '{}')
      const p = ctx.__preferences || {}
      return (p.regions?.length > 0) && (p.roles?.length > 0 || p.level?.length > 0)
    } catch { return false }
  })()

  return (
    <div className={s.page}>
      <header className={s.topbar}>
        <div className={s.topbarLeft}>
          <h1 className={s.pageTitle}>Job Scout</h1>
          {data && !data.is_demo && (
            <div className={s.engineBadge}>
              {data.signals_detected} signals detected · scored by {data.scored_by}
            </div>
          )}
        </div>
        <div className={s.tabBar}>
          <button className={[s.tab, tab==='signals'?s.tabActive:''].join(' ')} onClick={() => setTab('signals')}>
            Predicted Opportunities
            {opportunities.length > 0 && <span className={s.tabBadge}>{opportunities.length}</span>}
          </button>
          <button className={[s.tab, tab==='openings'?s.tabActive:''].join(' ')} onClick={() => setTab('openings')}>
            Live Vacancies
            {liveOpenings.length > 0 && <span className={s.tabBadge}>{liveOpenings.length}</span>}
          </button>
        </div>
        <button className={s.refreshBtn} onClick={() => refetch()} disabled={isLoading}>
          {isLoading ? 'Scanning...' : 'Refresh'}
        </button>
      </header>

      {!prefComplete && (
        <div className={s.noPrefs}>
          Set your target roles and regions in{' '}
          <button className={s.noPrefsLink} onClick={() => navigate('/profile')}>Job Preferences</button>
          {' '}to get personalised results
        </div>
      )}

      {isLoading && (
        <div className={s.loading}>
          <div className={s.radar}><div className={s.radarRing}/><div className={s.radarRing}/><div className={s.radarRing}/><div className={s.radarDot}/></div>
          <div className={s.loadingText}>Scanning market signals across news, job boards & company announcements...</div>
          <div className={s.loadingSub}>Analysing funding rounds, leadership changes, expansions & hiring spikes</div>
        </div>
      )}

      {error && !isLoading && (
        <div className={s.errorBox}>
          <div className={s.errorTitle}>Something went wrong</div>
          <div className={s.errorSub}>{(error as any)?.message || 'Could not reach signal engine'}</div>
          <button className={s.retryBtn} onClick={() => refetch()}>Try again</button>
        </div>
      )}

      {/* ── PREDICTED OPPORTUNITIES TAB ── */}
      {!isLoading && !error && tab === 'signals' && (
        <div className={s.content}>
          {data?.is_demo && (
            <div className={s.demoBanner}>Demo mode — set your preferences in Profile to see live signals</div>
          )}
          {opportunities.length === 0 ? (
            <div className={s.empty}>
              <div className={s.emptyIcon}>🔮</div>
              <div className={s.emptyTitle}>No opportunities detected yet</div>
              <div className={s.emptySub}>Set your target roles, regions and sectors in <button className={s.emptyLink} onClick={() => navigate('/profile')}>Job Preferences</button> and refresh.</div>
            </div>
          ) : (
            <div className={s.cards}>
              {opportunities.map(c => <OppCard key={c.id} card={c} onGenerate={handleGenerate} />)}
            </div>
          )}
        </div>
      )}

      {/* ── LIVE VACANCIES TAB ── */}
      {!isLoading && !error && tab === 'openings' && (
        <div className={s.content}>
          {liveOpenings.length === 0 ? (
            <div className={s.empty}>
              <div className={s.emptyIcon}>📋</div>
              <div className={s.emptyTitle}>No openings found</div>
              <div className={s.emptySub}>Set your target roles and regions in <button className={s.emptyLink} onClick={() => navigate('/profile')}>Job Preferences</button> and refresh.</div>
            </div>
          ) : (
            <>
              {current.length > 0 && (
                <div className={s.openingSection}>
                  <div className={s.openingSectionHeader}>
                    <div className={s.openingSectionDot} style={{background:'#16a34a'}}/>
                    <div>
                      <div className={s.openingSectionTitle}>Current Vacancies ({current.length})</div>
                      <div className={s.openingSectionSub}>Live posted roles — apply now</div>
                    </div>
                  </div>
                  <div className={s.openingGrid}>{current.map((j,i) => <OpeningCard key={i} job={j} onGenerate={handleOpeningGenerate}/>)}</div>
                </div>
              )}

              {imminent.length > 0 && (
                <div className={s.openingSection}>
                  <div className={s.openingSectionHeader}>
                    <div className={s.openingSectionDot} style={{background:'#ca8a04'}}/>
                    <div>
                      <div className={s.openingSectionTitle}>Imminent Openings ({imminent.length})</div>
                      <div className={s.openingSectionSub}>Strong signals — roles forming, position yourself now</div>
                    </div>
                  </div>
                  <div className={s.openingGrid}>{imminent.map((j,i) => <OpeningCard key={i} job={j} onGenerate={handleOpeningGenerate}/>)}</div>
                </div>
              )}

              {strategic.length > 0 && (
                <div className={s.openingSection}>
                  <div className={s.openingSectionHeader}>
                    <div className={s.openingSectionDot} style={{background:'#dc2626'}}/>
                    <div>
                      <div className={s.openingSectionTitle}>Strategic Horizon ({strategic.length})</div>
                      <div className={s.openingSectionSub}>Early signals — build relationships before the role exists</div>
                    </div>
                  </div>
                  <div className={s.openingGrid}>{strategic.map((j,i) => <OpeningCard key={i} job={j} onGenerate={handleOpeningGenerate}/>)}</div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
