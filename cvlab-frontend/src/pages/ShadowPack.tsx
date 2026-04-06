import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { shadowApi, ShadowDetail } from '../api/shadow'

export default function ShadowPack() {
  const { shadowId } = useParams<{ shadowId: string }>()

  const { data, isLoading, error } = useQuery({
    queryKey: ['shadow', shadowId],
    queryFn: () => shadowApi.get(shadowId!),
    enabled: !!shadowId,
    refetchInterval: (query) => {
      const d = query.state.data as ShadowDetail | undefined
      return d?.status === 'generating' ? 3000 : false
    },
  })

  if (isLoading) return <Loading />
  if (error || !data) return <Error />

  const isGenerating = data.status === 'generating'
  const isFailed = data.status === 'failed'

  return (
    <div style={{ padding: '32px 24px', maxWidth: 800 }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <StatusBadge status={data.status} />
          {data.confidence != null && (
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>
              Confidence: {Math.round(data.confidence * 100)}%
            </span>
          )}
        </div>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>
          {data.hypothesis_role || 'Shadow Application'}
        </h1>
        <p style={{ fontSize: 15, color: 'var(--text-2)', margin: '4px 0 0' }}>
          {data.company} — {data.signal_type}
        </p>
      </div>

      {isGenerating && (
        <div style={{ padding: 20, background: 'var(--bg-2)', borderRadius: 10, textAlign: 'center', color: 'var(--text-2)' }}>
          Generating shadow application... This takes 15-30 seconds.
        </div>
      )}

      {isFailed && (
        <div style={{ padding: 16, background: '#FEF2F2', borderRadius: 10, color: '#B91C1C', fontSize: 14 }}>
          Generation failed. Please try again with more profile detail.
        </div>
      )}

      {data.status === 'completed' && (
        <div style={{ display: 'grid', gap: 20 }}>
          {/* Hiring Hypothesis */}
          {data.hiring_hypothesis && (
            <Section title="Hiring Hypothesis">
              <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>{data.hiring_hypothesis}</p>
            </Section>
          )}

          {/* Strategy Memo */}
          {data.strategy_memo && (
            <Section title="Strategy Memo">
              <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>{data.strategy_memo}</p>
            </Section>
          )}

          {/* Outreach Messages */}
          {data.outreach_linkedin && (
            <Section title="LinkedIn Note">
              <CopyBlock text={data.outreach_linkedin} />
            </Section>
          )}
          {data.outreach_email && (
            <Section title="Cold Email">
              <CopyBlock text={data.outreach_email} />
            </Section>
          )}
          {data.outreach_followup && (
            <Section title="Follow-up">
              <CopyBlock text={data.outreach_followup} />
            </Section>
          )}

          {/* CV Download */}
          {data.tailored_cv_download_url && (
            <Section title="Tailored CV">
              <a
                href={data.tailored_cv_download_url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'inline-block',
                  padding: '10px 20px',
                  background: 'var(--accent)',
                  color: 'white',
                  borderRadius: 8,
                  textDecoration: 'none',
                  fontWeight: 600,
                  fontSize: 14,
                }}
              >
                Download CV
              </a>
            </Section>
          )}

          {data.reasoning && (
            <div style={{ fontSize: 12, color: 'var(--text-3)', padding: '8px 12px', background: 'var(--bg-2)', borderRadius: 6 }}>
              {data.reasoning}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 16 }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-2)', margin: '0 0 10px', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
        {title}
      </h3>
      {children}
    </div>
  )
}

function CopyBlock({ text }: { text: string }) {
  const copy = () => navigator.clipboard.writeText(text)
  return (
    <div style={{ position: 'relative' }}>
      <div style={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.6 }}>{text}</div>
      <button
        onClick={copy}
        style={{
          position: 'absolute', top: 0, right: 0,
          padding: '3px 8px', fontSize: 11, border: '1px solid var(--border)',
          borderRadius: 4, background: 'var(--bg)', cursor: 'pointer', color: 'var(--text-2)',
        }}
      >
        Copy
      </button>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, { bg: string; text: string }> = {
    generating: { bg: '#FEF3C7', text: '#92400E' },
    completed: { bg: '#D1FAE5', text: '#065F46' },
    failed: { bg: '#FEE2E2', text: '#991B1B' },
  }
  const c = colors[status] || colors.generating
  return (
    <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4, background: c.bg, color: c.text }}>
      {status}
    </span>
  )
}

function Loading() {
  return <div style={{ padding: 40, color: 'var(--text-2)' }}>Loading...</div>
}
function Error() {
  return <div style={{ padding: 40, color: 'var(--danger)' }}>Shadow application not found.</div>
}
