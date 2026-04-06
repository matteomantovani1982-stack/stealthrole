import { api as client } from './client'

export interface RadarOpportunity {
  id: string
  rank: number
  company: string
  role: string | null
  location: string | null
  sector: string | null
  radar_score: number
  evidence_tier: string
  urgency: string
  reasoning: string
  suggested_action: string
  source_tags: string[]
  fit_reasons: string[]
  red_flags: string[]
  actions: {
    can_generate_pack: boolean
    can_generate_shadow: boolean
    can_generate_outreach: boolean
  }
}

export interface RadarResponse {
  opportunities: RadarOpportunity[]
  total: number
  returned: number
  scoring: {
    method: string
    profile_completeness: number
    sources_active: string[]
  }
  meta: { scored_in_ms: number }
  onboarding_hint?: string
}

export const radarApi = {
  get: async (params?: {
    limit?: number
    min_score?: number
    source?: string
    urgency?: string
    include_speculative?: boolean
  }): Promise<RadarResponse> => {
    const res = await client.get('/api/v1/opportunities/radar', { params })
    return res.data
  },
}
