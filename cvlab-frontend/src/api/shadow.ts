import { api as client } from './client'

export interface ShadowGenerateRequest {
  company: string
  signal_type: string
  likely_roles?: string[]
  signal_context?: string
  tone?: 'confident' | 'formal' | 'casual'
  radar_score?: number
}

export interface ShadowSummary {
  id: string
  company: string
  signal_type: string
  hypothesis_role: string | null
  radar_score: number | null
  confidence: number | null
  status: string
  pipeline_stage: string | null
  created_at: string
}

export interface ShadowDetail {
  id: string
  company: string
  signal_type: string
  signal_context: string | null
  radar_score: number | null
  status: string
  hypothesis_role: string | null
  hiring_hypothesis: string | null
  strategy_memo: string | null
  outreach_linkedin: string | null
  outreach_email: string | null
  outreach_followup: string | null
  tailored_cv_download_url: string | null
  confidence: number | null
  reasoning: string | null
  pipeline_stage: string | null
  created_at: string
}

export const shadowApi = {
  generate: async (data: ShadowGenerateRequest) => {
    const res = await client.post('/api/v1/shadow/generate', data)
    return res.data
  },
  list: async (): Promise<{ shadow_applications: ShadowSummary[]; total: number }> => {
    const res = await client.get('/api/v1/shadow')
    return res.data
  },
  get: async (id: string): Promise<ShadowDetail> => {
    const res = await client.get(`/api/v1/shadow/${id}`)
    return res.data
  },
}
