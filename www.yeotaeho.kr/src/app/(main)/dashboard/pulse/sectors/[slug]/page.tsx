"use client";

// 섹터 주간 트렌드 상세 페이지 — 메인(주간 차트·인과사슬) + 우측(14일 전망·크로스오버·관련 문서) 드릴다운 뷰

import Link from "next/link";
import { useMemo, type ReactNode } from "react";
import { useParams } from "next/navigation";

import { PanelStatus } from "@/components/features/dashboard/PanelStatus";
import { toWeeklyPoints, WeeklyTrendChart } from "@/components/features/dashboard/PulseWeeklyTrend";
import { CausalFlow, CrossoverChart, Sparkline, TrendStatusBadge } from "@/components/features/dashboard/PulseViz";
import {
  useCausalChains,
  useCrossover,
  useForecast,
  usePulse,
  usePulseDocuments,
  usePulseHistory,
  usePulseInvestments,
} from "@/hooks/useDashboard";
import type { PulseDocument, PulseInvestments } from "@/lib/api/dashboard";

function StatCard({ label, value, spark }: { label: string; value: string; spark?: number[] }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
      <div>
        <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">{value}</p>
        <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{label}</p>
      </div>
      {spark && spark.length >= 2 && <Sparkline values={spark} className="w-20 h-8 shrink-0" />}
    </div>
  );
}

// 우측 컬럼 공통 카드 셸 — 제목 + 본문.
function SideCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
      <h2 className="text-sm font-bold text-slate-800 dark:text-slate-100 mb-3">{title}</h2>
      {children}
    </section>
  );
}

// 전망 방향 배지 색조 — 강세/상승 emerald · 중립 slate · 하락/약세 rose.
function badgeTone(badge: string): string {
  if (badge.includes("강세") || badge.includes("상승")) {
    return "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300";
  }
  if (badge.includes("하락") || badge.includes("약세")) {
    return "bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300";
  }
  return "bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-300";
}

function confidenceLabel(confidence: number | null): string {
  if (confidence == null) return "—";
  if (confidence >= 0.66) return "높음";
  if (confidence >= 0.33) return "보통";
  return "낮음";
}

// 원천 source_type을 사용자용 짧은 라벨로.
function docTypeLabel(sourceType: string | null): string {
  const s = (sourceType ?? "").toUpperCase();
  if (s.includes("DART")) return "공시";
  if (s.includes("PATENT") || s.includes("KIPRIS")) return "특허";
  if (s.includes("ARXIV")) return "논문";
  if (s.includes("GITHUB")) return "오픈소스";
  if (s.includes("KIAT") || s.includes("KISTEP")) return "R&D";
  if (s.includes("TECHBLOG")) return "테크블로그";
  if (s.includes("NEWS") || s.includes("RSS")) return "기사";
  return "자료";
}

function sentimentDot(sentiment: string | null): string {
  if (sentiment === "긍정") return "bg-emerald-500";
  if (sentiment === "부정") return "bg-rose-500";
  return "bg-slate-300 dark:bg-slate-600";
}

function shortDate(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return `${d.getMonth() + 1}.${d.getDate()}`;
}

// 원(KRW) 금액을 조/억/만원 단위 한국어 표기로.
function formatKrw(amount: number): string {
  if (amount >= 1_0000_0000_0000) return `${(amount / 1_0000_0000_0000).toFixed(1).replace(/\.0$/, "")}조원`;
  if (amount >= 1_0000_0000) return `${(amount / 1_0000_0000).toFixed(1).replace(/\.0$/, "")}억원`;
  if (amount >= 1_0000) return `${Math.round(amount / 1_0000).toLocaleString()}만원`;
  return `${amount.toLocaleString()}원`;
}

// 투자·자금 흐름 — 최근 윈도우 대비 요약 + 최근 자금 이벤트 목록.
function InvestmentFlowSection({ data }: { data: PulseInvestments }) {
  const s = data.summary;
  if (data.items.length === 0) {
    return (
      <p className="text-sm text-slate-400">
        이 섹터로 집계된 투자·자금 흐름 데이터가 아직 없습니다. 수집이 쌓이면 자동으로 채워집니다.
      </p>
    );
  }
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/60">
          <p className="text-lg font-bold text-slate-900 dark:text-slate-100">
            {s.recent_count > 0 ? formatKrw(s.recent_total_krw) : "—"}
          </p>
          <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
            최근 {s.window_days}일 자금 유입 ({s.recent_count}건)
          </p>
        </div>
        <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/60">
          <p className="text-lg font-bold text-slate-900 dark:text-slate-100">
            {s.prev_count > 0 ? formatKrw(s.prev_total_krw) : "—"}
          </p>
          <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
            직전 {s.window_days}일 ({s.prev_count}건)
          </p>
        </div>
        <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/60">
          {s.delta_pct != null ? (
            <p className={`text-lg font-bold ${s.delta_pct < 0 ? "text-rose-600" : "text-emerald-600"}`}>
              {s.delta_pct > 0 ? "+" : ""}
              {s.delta_pct}%
            </p>
          ) : (
            <p className="text-lg font-bold text-slate-400">—</p>
          )}
          <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
            {s.delta_pct != null ? "직전 기간 대비 증감" : "비교 기준 기간 데이터 없음"}
          </p>
        </div>
      </div>

      {s.market_total_krw != null ? (
        <p className="rounded-xl bg-indigo-50/60 px-3 py-2 text-[11px] text-slate-500 dark:bg-indigo-900/20 dark:text-slate-400">
          이 분야 <b className="text-slate-700 dark:text-slate-200">{s.market_year}년 시장 전체 신규 벤처투자 {formatKrw(s.market_total_krw)}</b>
          {" "}규모입니다(벤처투자종합포털). 아래 목록은 공시·뉴스로 <b>포착한 표본</b>이라 전체의 일부입니다.
        </p>
      ) : (
        <p className="rounded-xl bg-slate-50 px-3 py-2 text-[11px] text-slate-400 dark:bg-slate-800/40">
          이 분야는 공식 벤처투자 통계의 업종 대분류(9종)에서 별도로 집계되지 않아 시장 전체 기준선은 표시하지 않습니다. 아래 목록은 공시·뉴스로 포착한 표본입니다.
        </p>
      )}

      <ul className="flex flex-col divide-y divide-slate-100 dark:divide-slate-800">
        {data.items.map((it, i) => (
          <li key={`${it.url ?? it.title}-${i}`} className="flex items-center gap-3 py-2.5">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-slate-800 truncate dark:text-slate-100">
                {it.company ?? it.title ?? "—"}
              </p>
              <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-slate-400">
                {it.flow_label && (
                  <span className="px-1.5 py-px rounded-full bg-indigo-50 text-indigo-600 font-medium dark:bg-indigo-900/30 dark:text-indigo-300">
                    {it.flow_label}
                  </span>
                )}
                {it.investor && <span className="truncate">{it.investor}</span>}
                {shortDate(it.date) && <span>{shortDate(it.date)}</span>}
              </p>
            </div>
            <span className="shrink-0 text-sm font-bold text-slate-900 dark:text-slate-100">
              {formatKrw(it.amount_krw)}
            </span>
            {it.url && (
              <a
                href={it.url}
                target="_blank"
                rel="noreferrer"
                className="shrink-0 text-[11px] font-medium text-indigo-500 hover:underline underline-offset-2"
              >
                원문
              </a>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

// 관련 문서 리스트 — 제목(원문 링크)·출처 라벨·일자·감성 점.
function DocList({ docs, emptyText }: { docs: PulseDocument[]; emptyText: string }) {
  if (docs.length === 0) {
    return <p className="text-xs text-slate-400">{emptyText}</p>;
  }
  return (
    <ul className="flex flex-col gap-2.5">
      {docs.map((doc, i) => (
        <li key={`${doc.url ?? doc.title}-${i}`} className="flex items-start gap-2">
          <span className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${sentimentDot(doc.sentiment)}`} aria-hidden />
          <div className="min-w-0">
            {doc.url ? (
              <a
                href={doc.url}
                target="_blank"
                rel="noreferrer"
                className="block text-xs font-medium text-slate-700 leading-snug line-clamp-2 hover:text-indigo-600 hover:underline underline-offset-2 dark:text-slate-200 dark:hover:text-indigo-300"
              >
                {doc.title}
              </a>
            ) : (
              <span className="block text-xs font-medium text-slate-700 leading-snug line-clamp-2 dark:text-slate-200">
                {doc.title}
              </span>
            )}
            <span className="mt-0.5 flex items-center gap-1.5 text-[10px] text-slate-400">
              <span className="px-1.5 py-px rounded-full bg-slate-100 dark:bg-slate-800">{docTypeLabel(doc.source_type)}</span>
              {shortDate(doc.published_at) && <span>{shortDate(doc.published_at)}</span>}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function PulseSectorDetailPage() {
  const params = useParams();
  const slug = String(params?.slug ?? "");
  const { data: history, isLoading, isError } = usePulseHistory(slug || undefined);
  const { data: documents, isLoading: docLoading, isError: docError } = usePulseDocuments(slug || undefined);
  const { data: investments, isLoading: invLoading, isError: invError } = usePulseInvestments(slug || undefined);
  const { data: livePulse } = usePulse();
  const { data: forecasts, isLoading: fcLoading, isError: fcError } = useForecast();
  const { data: crossover, isLoading: coLoading, isError: coError } = useCrossover();
  const { data: causal, isLoading: ccLoading, isError: ccError } = useCausalChains();

  const live = (livePulse ?? []).find((s) => s.sector_slug === slug);
  const forecast = (forecasts ?? []).find((s) => s.sector_slug === slug);
  const chain = (causal ?? []).find((c) => c.sector_slug === slug);
  const weekly = useMemo(() => toWeeklyPoints(history?.points ?? []), [history]);
  const weeklyValues = weekly.map((p) => p.value);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold text-indigo-600">실시간 펄스 · 섹터 상세</p>
        <div className="mt-1 flex items-center gap-2.5 flex-wrap">
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100">
            {history?.sector_name ?? live?.sector_name ?? "섹터"}
          </h1>
          <TrendStatusBadge momentum={live?.momentum_pct} />
          {live?.momentum_pct != null && (
            <span
              className={`text-sm font-bold ${live.momentum_pct < 0 ? "text-rose-600" : "text-emerald-600"}`}
            >
              {live.momentum_pct > 0 ? "+" : ""}
              {live.momentum_pct}%
            </span>
          )}
        </div>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
          최근 {weekly.length}주간의 주 평균 트렌드 점수와 전망·근거 데이터입니다.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* 메인 — 주간 트렌드 차트 + 인과관계 체인 */}
        <div className="xl:col-span-2 space-y-6">
          <PanelStatus isLoading={isLoading} isError={isError} isEmpty={weekly.length === 0} label="주간 트렌드">
            <div className="space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <StatCard label="현재 점수" value={String(live?.score ?? weeklyValues[weeklyValues.length - 1] ?? "—")} spark={weeklyValues} />
                <StatCard label="주간 최고" value={String(weeklyValues.length ? Math.max(...weeklyValues) : "—")} />
                <StatCard label="주간 최저" value={String(weeklyValues.length ? Math.min(...weeklyValues) : "—")} />
              </div>

              <section className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
                <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-4">주간 트렌드</h2>
                <WeeklyTrendChart points={weekly} accent={live?.accent_color ?? null} />
              </section>
            </div>
          </PanelStatus>

          <section className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-4">인과관계 체인</h2>
            <PanelStatus isLoading={ccLoading} isError={ccError} isEmpty={!chain} label="인과사슬">
              {chain ? (
                <CausalFlow
                  sectorName={chain.sector_name}
                  accentColor={chain.accent_color}
                  macro={chain.macro_event}
                  industry={chain.industry_impact}
                  chance={chain.youth_chance}
                />
              ) : (
                <p className="text-sm text-slate-400">이 섹터의 인과사슬 분석이 아직 없습니다.</p>
              )}
            </PanelStatus>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-1">투자·자금 흐름</h2>
            <p className="mb-4 text-xs text-slate-400">
              이 분야로 흘러든 투자·조달 금액과 직전 기간 대비 패턴입니다.
            </p>
            <PanelStatus isLoading={invLoading} isError={invError} isEmpty={false} label="투자 흐름">
              {investments && <InvestmentFlowSection data={investments} />}
            </PanelStatus>
          </section>
        </div>

        {/* 우측 — 14일 전망 · 크로스오버 · 관련 문서 */}
        <div className="space-y-6">
          <SideCard title="14일 전망">
            <PanelStatus isLoading={fcLoading} isError={fcError} isEmpty={false} label="시장 전망">
              {forecast ? (
                <div>
                  <div className="flex items-end gap-2 mb-2">
                    <span className="text-3xl font-bold text-slate-900 dark:text-slate-100">{forecast.score}</span>
                    <span
                      className={`mb-1 shrink-0 text-[11px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap ${badgeTone(
                        forecast.direction_badge,
                      )}`}
                    >
                      {forecast.direction_badge}
                    </span>
                    {forecast.predicted_return_pct != null && (
                      <span
                        className={`mb-1 text-xs font-semibold ${
                          forecast.predicted_return_pct < 0 ? "text-rose-600" : "text-emerald-600"
                        }`}
                      >
                        {forecast.predicted_return_pct > 0 ? "+" : ""}
                        {forecast.predicted_return_pct.toFixed(1)}%
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 bg-slate-200 dark:bg-slate-700 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-indigo-400"
                        style={{ width: `${Math.round((forecast.confidence ?? 0) * 100)}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-slate-400 shrink-0 whitespace-nowrap">
                      신뢰도 {confidenceLabel(forecast.confidence)}
                    </span>
                  </div>
                  <p className="mt-2 text-[10px] text-slate-400">
                    AI 예측 기준일 {forecast.forecast_date} → 목표일 {forecast.target_date}
                  </p>
                </div>
              ) : (
                <p className="text-xs text-slate-400">
                  이 섹터는 시장 시계열 데이터가 없어 전망을 제공하지 않습니다.
                </p>
              )}
            </PanelStatus>
          </SideCard>

          <SideCard title="세대교체 크로스오버">
            <div className="mb-3 flex gap-3 text-xs text-slate-500 dark:text-slate-400">
              <span className="flex items-center gap-1">
                <span className="inline-block w-3 h-0.5 bg-slate-400" />
                {crossover?.legacy_label ?? "전통"}
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block w-3 h-0.5 bg-indigo-500" />
                {crossover?.emerging_label ?? "신흥"}
              </span>
            </div>
            <PanelStatus
              isLoading={coLoading}
              isError={coError}
              isEmpty={(crossover?.series.length ?? 0) === 0}
              label="크로스오버"
            >
              <CrossoverChart
                data={crossover ?? { legacy_label: "전통", emerging_label: "신흥", series: [] }}
              />
            </PanelStatus>
          </SideCard>

          <SideCard title="관련 공시·기사">
            <PanelStatus isLoading={docLoading} isError={docError} isEmpty={false} label="관련 문서">
              <DocList docs={documents?.news ?? []} emptyText="이 섹터로 분류된 공시·기사가 아직 없습니다." />
            </PanelStatus>
          </SideCard>

          <SideCard title="관련 기술·R&D 데이터">
            <PanelStatus isLoading={docLoading} isError={docError} isEmpty={false} label="기술 데이터">
              <DocList docs={documents?.tech ?? []} emptyText="이 섹터로 분류된 기술·R&D 데이터가 아직 없습니다." />
            </PanelStatus>
          </SideCard>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <Link
          href="/"
          className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white text-sm font-semibold px-4 py-2.5 text-slate-700 hover:bg-slate-50 transition dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          대시보드로
        </Link>
      </div>
    </div>
  );
}
