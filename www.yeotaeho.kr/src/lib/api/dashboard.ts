// 인사이트 대시보드(Pulse·Gap·Chance·Sync) 백엔드 서빙 API 클라이언트
import { apiClient } from './client';

export interface PulseSectorLive {
  sector_slug: string;
  sector_name: string;
  accent_color: string;
  recorded_date: string;
  score: number;
  status_badge: string;
  momentum_pct: number | null;
}

export async function fetchPulse(): Promise<PulseSectorLive[]> {
  const { data } = await apiClient.get('/api/insight/pulse');
  return data?.sectors ?? [];
}

export interface GapIssueLive {
  id: number;
  sector_slug: string;
  problem_summary: string;
  chance_summary: string;
  published_date: string | null;
}

export async function fetchGapIssues(): Promise<GapIssueLive[]> {
  const { data } = await apiClient.get('/api/insight/gap');
  return data?.issues ?? [];
}

export interface ChanceOpportunityLive {
  id: number;
  sector_slug: string | null;
  title: string;
  opportunity_type: string | null;
  host_name: string | null;
  benefit_summary: string | null;
  d_day_date: string | null;
}

export async function fetchOpportunities(): Promise<ChanceOpportunityLive[]> {
  const { data } = await apiClient.get('/api/chance/opportunities');
  return data?.opportunities ?? [];
}

export interface GapIssueDetail {
  id: number;
  sector_slug: string;
  sector_name: string;
  accent_color: string;
  problem_summary: string;
  chance_summary: string;
  detail_summary: string | null;
  stakeholders: string[];
  next_actions: string[];
  published_date: string | null;
  evidences: { type: string | null; title: string; url: string | null }[];
}

export async function fetchGapIssueDetail(id: string): Promise<GapIssueDetail> {
  const { data } = await apiClient.get(`/api/insight/gap/${id}`);
  return data.issue;
}

export interface ChanceOpportunityDetail {
  id: number;
  sector_slug: string | null;
  title: string;
  opportunity_type: string | null;
  host_name: string | null;
  benefit_summary: string | null;
  target_audience: string | null;
  d_day_date: string | null;
  brief_description: string | null;
  eligibility_checks: string[];
  actionable_preps: string[];
  reference_links: string[];
}

export async function fetchOpportunityDetail(id: string): Promise<ChanceOpportunityDetail> {
  const { data } = await apiClient.get(`/api/chance/opportunities/${id}`);
  return data.opportunity;
}

export interface SyncScoreLive {
  sector_slug: string;
  sector_name: string;
  accent_color: string;
  score: number;
  badge: string | null;
  recorded_date: string | null;
}

export async function fetchSyncScores(userId: string): Promise<SyncScoreLive[]> {
  const { data } = await apiClient.get('/api/sync/scores', { params: { user_id: userId } });
  return data?.scores ?? [];
}

export interface PulseGauge {
  weekly_index: number | null;
  speed_kmh: number | null;
  day_delta_pct: number | null;
  top_mover: { sector_slug: string; sector_name: string; momentum_pct: number } | null;
}
export interface PulseMomentumPoint {
  bucket: string;
  value: number;
}
export interface PulseHeatmapCell {
  bucket: string;
  score: number | null;
}
export interface PulseHeatmapRow {
  sector_slug: string;
  sector_name: string;
  accent_color: string;
  cells: PulseHeatmapCell[];
}
export interface PulseShareItem {
  sector_slug: string;
  sector_name: string;
  pct: number;
}
export interface PulseOverview {
  gauge: PulseGauge;
  momentum_series: PulseMomentumPoint[];
  heatmap: { buckets: string[]; rows: PulseHeatmapRow[] };
  share: PulseShareItem[];
}

export async function fetchPulseOverview(): Promise<PulseOverview> {
  const { data } = await apiClient.get('/api/insight/pulse/overview');
  return {
    gauge: data.gauge,
    momentum_series: data.momentum_series ?? [],
    heatmap: data.heatmap ?? { buckets: [], rows: [] },
    share: data.share ?? [],
  };
}

export interface PulseHistoryPoint {
  recorded_date: string;
  score: number;
  momentum_pct: number | null;
  status_badge: string;
}
export interface PulseHistory {
  sector_slug: string;
  sector_name: string;
  points: PulseHistoryPoint[];
}

export async function fetchPulseHistory(sector: string): Promise<PulseHistory> {
  const { data } = await apiClient.get(`/api/insight/pulse/${sector}/history`);
  return {
    sector_slug: data.sector_slug,
    sector_name: data.sector_name,
    points: data.points ?? [],
  };
}

/** 마감일(ISO date)을 'D-n' / 'D-DAY' / '마감' 라벨로 변환한다. */
export function ddayLabel(dDayDate: string | null): string {
  if (!dDayDate) return '상시';
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const deadline = new Date(dDayDate);
  deadline.setHours(0, 0, 0, 0);
  const diff = Math.round((deadline.getTime() - today.getTime()) / 86_400_000);
  if (diff < 0) return '마감';
  if (diff === 0) return 'D-DAY';
  return `D-${diff}`;
}
