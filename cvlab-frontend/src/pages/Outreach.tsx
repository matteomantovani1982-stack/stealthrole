import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { outreachApi, OutreachRequest, OutreachResponse } from '../api/outreach'

export default function Outreach() {
  const [company, setCompany] = useState('')
  const [role, setRole] = useState('')
  const [context, setContext] = useState('')
  const [jdUrl, setJdUrl] = useState('')
  const [jdText, setJdText] = useState('')
  const [tone, setTone] = useState<'confident' | 'formal' | 'casual'>('confident')
  const [result, setResult] = useState<OutreachResponse | null>(null)
  const [copied, setCopied] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (data: OutreachRequest) => outreachApi.generate(data),
    onSuccess: (data) => setResult(data),
  })

  const generate = () => {
    if (!company.trim() || !role.trim()) return
    mutation.mutate({
      company, role,
      signal_context: context || undefined,
      jd_url: jdUrl || undefined,
      jd_text: jdText || undefined,
      tone,
    })
  }

  const copy = (text: string, label: string) => {
    navigator.clipboard.writeText(text)
    setCopied(label)
    setTimeout(() => setCopied(null), 2000)
  }

  return (
    <div style={{ padding: '32px 24px', maxWidth: 800 }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Outreach Generator</h1>
      <p style={{ color: 'var(--text-2)', fontSize: 14, marginBottom: 24 }}>
        Generate personalised LinkedIn notes, cold emails, and follow-ups.
      </p>

      {/* Form */}
      <div style={{ display: 'grid', gap: 12, marginBottom: 20 }}>
        <input
          placeholder="Company name *"
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          style={inputStyle}
        />
        <input
          placeholder="Target role *"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          style={inputStyle}
        />
        <textarea
          placeholder="Signal context (optional) — e.g. 'Company raised $50M Series C'"
          value={context}
          onChange={(e) => setContext(e.target.value)}
          rows={2}
          style={{ ...inputStyle, resize: 'vertical' }}
        />
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-2)', marginTop: 8 }}>
          Job description (optional — makes outreach much more targeted)
        </div>
        <input
          placeholder="🔗 Paste a job listing URL — LinkedIn, careers page, job board…"
          value={jdUrl}
          onChange={(e) => setJdUrl(e.target.value)}
          style={inputStyle}
        />
        <div style={{ fontSize: 12, color: 'var(--text-3)', textAlign: 'center' }}>or paste the text</div>
        <textarea
          placeholder="Paste the full job description here…"
          value={jdText}
          onChange={(e) => setJdText(e.target.value)}
          rows={4}
          style={{ ...inputStyle, resize: 'vertical' }}
        />
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 13, color: 'var(--text-2)' }}>Tone:</span>
          {(['confident', 'formal', 'casual'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTone(t)}
              style={{
                padding: '4px 12px',
                borderRadius: 6,
                border: '1px solid var(--border)',
                background: tone === t ? 'var(--accent)' : 'transparent',
                color: tone === t ? 'white' : 'var(--text-2)',
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              {t}
            </button>
          ))}
        </div>
        <button
          onClick={generate}
          disabled={mutation.isPending || !company.trim() || !role.trim()}
          style={{
            padding: '10px 20px',
            background: 'var(--accent)',
            color: 'white',
            border: 'none',
            borderRadius: 8,
            fontWeight: 600,
            fontSize: 14,
            cursor: 'pointer',
            opacity: mutation.isPending ? 0.7 : 1,
          }}
        >
          {mutation.isPending ? 'Generating...' : 'Generate Outreach'}
        </button>
      </div>

      {mutation.isError && (
        <div style={{ color: 'var(--danger)', fontSize: 13, marginBottom: 16 }}>
          Generation failed. Please try again.
        </div>
      )}

      {/* Results */}
      {result && (
        <div style={{ display: 'grid', gap: 16 }}>
          <MessageCard
            title="LinkedIn Connection Note"
            text={result.linkedin_note}
            onCopy={() => copy(result.linkedin_note, 'linkedin')}
            copied={copied === 'linkedin'}
          />
          <MessageCard
            title="Cold Email"
            text={result.cold_email}
            onCopy={() => copy(result.cold_email, 'email')}
            copied={copied === 'email'}
          />
          <MessageCard
            title="Follow-up (1 week later)"
            text={result.follow_up}
            onCopy={() => copy(result.follow_up, 'followup')}
            copied={copied === 'followup'}
          />
          {result._disclaimer && (
            <div style={{ fontSize: 12, color: 'var(--text-3)', padding: '8px 12px', background: 'var(--bg-2)', borderRadius: 6 }}>
              {result._disclaimer}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function MessageCard({ title, text, onCopy, copied }: {
  title: string; text: string; onCopy: () => void; copied: boolean
}) {
  return (
    <div style={{
      border: '1px solid var(--border)',
      borderRadius: 10,
      padding: 16,
      background: 'var(--bg)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-2)' }}>{title}</span>
        <button
          onClick={onCopy}
          style={{
            padding: '4px 10px',
            fontSize: 12,
            border: '1px solid var(--border)',
            borderRadius: 5,
            background: copied ? 'var(--accent)' : 'transparent',
            color: copied ? 'white' : 'var(--text-2)',
            cursor: 'pointer',
          }}
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <div style={{ fontSize: 14, lineHeight: 1.6, whiteSpace: 'pre-wrap', color: 'var(--text)' }}>
        {text}
      </div>
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  padding: '10px 12px',
  border: '1px solid var(--border)',
  borderRadius: 8,
  fontSize: 14,
  background: 'var(--bg)',
  color: 'var(--text)',
  outline: 'none',
}
