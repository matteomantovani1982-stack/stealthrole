import { api as client } from './client'

export interface AnalyticsSummary {
  total_applications: number
  by_stage: Record<string, number>
  response_rate: number
  avg_keyword_score: number
}

export interface DashboardSummary {
  radar_opportunities: any[]
  radar_total: number
  recent_applications: any[]
  recent_shadow_applications: any[]
  total_applications: number
  total_shadow_applications: number
  profile_completeness: number
  sources_active: string[]
}

export const analyticsApi = {
  summary: async (): Promise<AnalyticsSummary> => {
    const res = await client.get('/api/v1/analytics/summary')
    return res.data
  },
  dashboard: async (): Promise<DashboardSummary> => {
    const res = await client.get('/api/v1/dashboard/summary')
    return res.data
  },
}
