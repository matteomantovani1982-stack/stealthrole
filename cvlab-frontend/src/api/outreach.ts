import { api as client } from './client'

export interface OutreachRequest {
  company: string
  role: string
  signal_context?: string
  jd_url?: string
  jd_text?: string
  tone?: 'confident' | 'formal' | 'casual'
}

export interface OutreachResponse {
  company: string
  role: string
  linkedin_note: string
  cold_email: string
  follow_up: string
  _disclaimer: string
  _company_verified: boolean
}

export const outreachApi = {
  generate: async (data: OutreachRequest): Promise<OutreachResponse> => {
    const res = await client.post('/api/v1/outreach/generate', data)
    return res.data
  },
}
