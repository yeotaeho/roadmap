"use client";

/**
 * 실시간 펄스(Pulse) L2 탭
 * @see www.yeotaeho.kr/docs/gemini-code-1777040200243.md — 4단 Bento, Youth & Tech 컬러, 차트 영역
 * 백엔드 연동 시 이 파일의 mock 상수를 API 응답으로 치환하면 됩니다.
 */

import React from "react";
import Link from "next/link";
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  CircleAlert,
  CircleCheck,
  TrendingUp,
} from "lucide-react";
import { PULSE_SECTORS } from "@/data/pulseSectors";

const MONTHLY_MOMENTUM = [58, 62, 66, 71, 74, 79, 76, 83, 87, 85, 90, 92];
const MONTH_LABELS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];

const SECTOR_SHARE = [
  { label: "지능형 기술 (AI & Data)", pct: 30 },
  { label: "지속 가능성 (Sustainability & ESG)", pct: 22 },
  { label: "바이오·헬스테크 (Bio & Health-Tech)", pct: 18 },
  { label: "미래 금융 (Future Finance)", pct: 15 },
  { label: "콘텐츠/IP (Next-Gen Media)", pct: 8 },
  { label: "지능형 제조 (Smart Manufacturing)", pct: 7 },
] as const;

const KEYWORDS = ["LLM", "배터리", "ESG", "FastAPI", "콘텐츠기획", "LangGraph"] as const;
const LIVE_TICKER = [
  "AI Agent 공고 +27%",
  "KOSPI 변동성 확대",
  "달러/원 1,412원",
  "클라우드 보안 투자 증가",
  "반도체 장비 수요 반등",
  "기후테크 정책 지원 확대",
] as const;

const SUMMARY = {
  speedKmh: 180,
  dayDeltaPct: 14.8,
  weeklyIndex: 86,
  insight: "AI·보안·클라우드 급상승",
} as const;

const MATRIX_COLS = ["태풍급", "급상승", "상승", "관찰"] as const;
const MATRIX_ROWS = [
  { sector: "지능형 기술", scores: [92, 80, 67, 40] },
  { sector: "지속 가능성", scores: [71, 84, 63, 45] },
  { sector: "바이오·헬스테크", scores: [55, 70, 73, 52] },
  { sector: "미래 금융", scores: [49, 66, 69, 57] },
  { sector: "콘텐츠/IP", scores: [43, 58, 64, 61] },
  { sector: "지능형 제조", scores: [62, 76, 70, 48] },
] as const;

const CAUSAL_CHAIN = {
  macro: "미국 금리 인하 시그널 강화",
  impact: "빅테크의 AI·클라우드 투자 재가속",
  opportunity: "AI 백엔드/보안 엔지니어 채용 수요 확대",
} as const;

const LEGACY_SERIES = [81, 79, 75, 72, 68, 65, 61, 59, 55, 53, 50, 47];
const EMERGING_SERIES = [34, 38, 43, 47, 52, 56, 60, 65, 70, 74, 79, 84];

function getHeatTone(score: number) {
  if (score >= 85) return "bg-indigo-600 text-white";
  if (score >= 70) return "bg-indigo-400 text-white";
  if (score >= 55) return "bg-indigo-200 text-indigo-900";
  return "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-200";
}

function MomentumAreaChart() {
  const values = MONTHLY_MOMENTUM;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const pad = 36;
  const w = 520;
  const h = 180;
  const innerW = w - pad * 2;
  const innerH = h - 28;
  const n = values.length - 1;

  const xAt = (i: number) => pad + (innerW * i) / n;
  const yAt = (v: number) => {
    const t = (v - min) / (max - min || 1);
    return pad + innerH * (1 - t);
  };

  const linePoints = values.map((v, i) => `${xAt(i)},${yAt(v)}`).join(" ");
  const areaPath = `M ${xAt(0)},${pad + innerH} L ${values
    .map((v, i) => `${xAt(i)},${yAt(v)}`)
    .join(" L ")} L ${xAt(n)},${pad + innerH} Z`;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-48" role="img" aria-label="연간 글로벌 모멘텀 트렌드 차트">
      <defs>
        <linearGradient id="pulseAreaFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#6366f1" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#6366f1" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {[0, 1, 2, 3].map((i) => (
        <line
          key={i}
          x1={pad}
          y1={pad + (innerH / 3) * i}
          x2={w - pad}
          y2={pad + (innerH / 3) * i}
          stroke="#e2e8f0"
          strokeWidth="1"
        />
      ))}
      <path d={areaPath} fill="url(#pulseAreaFill)" />
      <polyline fill="none" stroke="#4f46e5" strokeWidth="2.5" points={linePoints} />
      {values.map((v, i) => (
        <circle key={i} cx={xAt(i)} cy={yAt(v)} r="4" fill="#fff" stroke="#4f46e5" strokeWidth="2" />
      ))}
      {MONTH_LABELS.map((lbl, i) => (
        <text
          key={lbl + i}
          x={xAt(i)}
          y={h - 6}
          textAnchor="middle"
          className="fill-slate-400"
          style={{ fontSize: 10 }}
        >
          {lbl}
        </text>
      ))}
    </svg>
  );
}

function CrossoverLineChart() {
  const w = 520;
  const h = 180;
  const pad = 28;
  const innerW = w - pad * 2;
  const innerH = h - pad * 2;
  const n = LEGACY_SERIES.length - 1;

  const all = [...LEGACY_SERIES, ...EMERGING_SERIES];
  const min = Math.min(...all);
  const max = Math.max(...all);

  const xAt = (i: number) => pad + (innerW * i) / n;
  const yAt = (v: number) => pad + innerH * (1 - (v - min) / (max - min || 1));

  const toPoints = (arr: readonly number[]) => arr.map((v, i) => `${xAt(i)},${yAt(v)}`).join(" ");

  let crossoverIdx = -1;
  for (let i = 1; i < LEGACY_SERIES.length; i += 1) {
    if (LEGACY_SERIES[i] <= EMERGING_SERIES[i]) {
      crossoverIdx = i;
      break;
    }
  }

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-48" role="img" aria-label="세대교체 크로스오버 차트">
      {[0, 1, 2, 3].map((line) => (
        <line
          key={line}
          x1={pad}
          y1={pad + (innerH / 3) * line}
          x2={w - pad}
          y2={pad + (innerH / 3) * line}
          stroke="#e2e8f0"
          strokeWidth="1"
        />
      ))}
      <polyline fill="none" stroke="#64748b" strokeWidth="2.5" points={toPoints(LEGACY_SERIES)} />
      <polyline fill="none" stroke="#4f46e5" strokeWidth="3" points={toPoints(EMERGING_SERIES)} />

      {crossoverIdx >= 0 && (
        <>
          <line
            x1={xAt(crossoverIdx)}
            y1={pad}
            x2={xAt(crossoverIdx)}
            y2={h - pad}
            stroke="#8b5cf6"
            strokeWidth="1.5"
            strokeDasharray="5 4"
          />
          <circle cx={xAt(crossoverIdx)} cy={yAt(EMERGING_SERIES[crossoverIdx])} r="5" fill="#8b5cf6" />
          <text x={xAt(crossoverIdx) + 8} y={yAt(EMERGING_SERIES[crossoverIdx]) - 10} fill="#7c3aed" style={{ fontSize: 11 }}>
            전환 시점
          </text>
        </>
      )}
    </svg>
  );
}

export function PulseTab() {
  return (
    <div className="w-full flex flex-col gap-6 font-sans">
      {/* 1. 글로벌 펄스 헤더 */}
      <section className="bg-gradient-to-br from-indigo-600 to-blue-600 p-6 rounded-2xl text-white shadow-md relative overflow-hidden">
        <div className="absolute top-4 right-4 opacity-20 pointer-events-none">
          <Activity size={64} />
        </div>
        <div className="relative">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-indigo-100">글로벌 펄스 헤더</h2>
            <span className="text-xs px-2.5 py-1 rounded-full bg-white/20">
              전일 대비 +{SUMMARY.dayDeltaPct}%
            </span>
          </div>
          <div className="mt-4 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
            <div>
              <div className="flex items-end gap-2">
                <span className="text-5xl font-extrabold tracking-tight">{SUMMARY.speedKmh}</span>
                <span className="text-xl font-medium mb-1">km/h</span>
              </div>
              <p className="text-indigo-100 flex items-center gap-2 mt-2">
                <TrendingUp size={16} aria-hidden />
                {SUMMARY.insight}
              </p>
            </div>
            <div className="w-full sm:w-64">
              <div className="flex items-center justify-between text-xs text-indigo-100 mb-1">
                <span>주간 지수</span>
                <span>{SUMMARY.weeklyIndex} / 100</span>
              </div>
              <div className="w-full bg-white/20 h-3 rounded-full overflow-hidden">
                <div className="bg-emerald-400 h-full" style={{ width: `${SUMMARY.weeklyIndex}%` }} />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Top 섹터 히트맵/매트릭스 + 인과관계 체인 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="lg:col-span-2 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm dark:bg-slate-800 dark:border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-md font-bold text-slate-800 dark:text-slate-100">Top 섹터 히트맵 / 매트릭스</h2>
            <span className="text-xs text-slate-400 dark:text-slate-500">분야 x 상태</span>
          </div>
          <div className="overflow-x-auto">
            <div className="min-w-[560px]">
              <div className="grid grid-cols-5 gap-2 mb-2">
                <div />
                {MATRIX_COLS.map((col) => (
                  <div key={col} className="text-xs font-semibold text-slate-500 text-center dark:text-slate-400">
                    {col}
                  </div>
                ))}
              </div>
              {MATRIX_ROWS.map((row) => (
                <div key={row.sector} className="grid grid-cols-5 gap-2 mb-2">
                  <div className="text-sm font-medium text-slate-700 flex items-center dark:text-slate-300">
                    {row.sector}
                  </div>
                  {row.scores.map((score, idx) => {
                    const goodSignal = score >= 70;
                    return (
                      <div
                        key={`${row.sector}-${MATRIX_COLS[idx]}`}
                        className={`h-12 rounded-lg flex items-center justify-between px-2 text-xs font-semibold ${getHeatTone(score)}`}
                        title={`${row.sector} / ${MATRIX_COLS[idx]} / ${score}`}
                      >
                        <span>{score}</span>
                        {goodSignal ? <CircleCheck size={14} /> : <CircleAlert size={14} />}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm dark:bg-slate-800 dark:border-slate-700">
          <h2 className="text-md font-bold text-slate-800 mb-4 dark:text-slate-100">인과관계 체인</h2>
          <div className="space-y-3">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-900">
              <p className="text-[11px] text-slate-500 dark:text-slate-400">거시 이벤트</p>
              <p className="text-sm text-slate-800 font-medium dark:text-slate-100">{CAUSAL_CHAIN.macro}</p>
            </div>
            <div className="flex justify-center text-slate-400 dark:text-slate-500">
              <ArrowRight size={18} />
            </div>
            <div className="rounded-xl border border-indigo-100 bg-indigo-50 p-3 dark:border-indigo-900/40 dark:bg-indigo-900/20">
              <p className="text-[11px] text-indigo-500 dark:text-indigo-300">산업 영향</p>
              <p className="text-sm text-indigo-900 font-medium dark:text-indigo-200">{CAUSAL_CHAIN.impact}</p>
            </div>
            <div className="flex justify-center text-slate-400 dark:text-slate-500">
              <ArrowRight size={18} />
            </div>
            <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-3 dark:border-emerald-900/40 dark:bg-emerald-900/20">
              <p className="text-[11px] text-emerald-600 dark:text-emerald-300">청년 기회</p>
              <p className="text-sm text-emerald-900 font-medium dark:text-emerald-200">{CAUSAL_CHAIN.opportunity}</p>
            </div>
          </div>
        </section>
      </div>

      {/* 3. 분야별 트렌드 속도 현황 (Top 6 섹터) */}
      <section className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm dark:bg-slate-800 dark:border-slate-700">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">분야별 트렌드 속도 현황</h2>
          <span className="text-sm text-slate-400 dark:text-slate-500">Top 6 섹터</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {PULSE_SECTORS.map((sector) => (
            <Link
              key={sector.slug}
              href={`/dashboard/pulse/sectors/${sector.slug}`}
              className="block p-4 border border-slate-100 rounded-xl bg-slate-50/50 hover:bg-white hover:border-indigo-100 hover:shadow-sm transition dark:border-slate-700 dark:bg-slate-900/50 dark:hover:bg-slate-900 dark:hover:border-indigo-700"
            >
              <div className="flex justify-between items-center mb-2">
                <span className="font-semibold text-slate-700 dark:text-slate-200">{sector.title}</span>
                <span className={`text-xs px-2 py-1 rounded-full ${sector.badgeInfo}`}>
                  {sector.status}
                </span>
              </div>
              <div className="text-2xl font-bold text-slate-900 mb-2 dark:text-slate-100">{sector.score}</div>
              <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden dark:bg-slate-700">
                <div className={`${sector.color} h-full`} style={{ width: `${sector.score}%` }} />
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* 4. 메인 지표 영역 (속도계 & 브리핑) — 2:1 벤토 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="lg:col-span-2 bg-gradient-to-br from-indigo-500 to-blue-600 p-6 rounded-2xl text-white shadow-md relative overflow-hidden">
          <div className="absolute top-4 right-4 opacity-20 pointer-events-none">
            <Activity size={64} />
          </div>
          <h2 className="text-sm font-medium text-indigo-100 mb-4">트렌드 속도계</h2>
          <div className="flex items-end gap-2 mb-2">
            <span className="text-5xl font-extrabold tracking-tight">180</span>
            <span className="text-xl font-medium mb-1">km/h</span>
          </div>
          <p className="text-indigo-100 flex items-center gap-2 mb-6">
            <TrendingUp size={16} aria-hidden />
            AI · 보안 · 클라우드 태풍급 상승
          </p>
          <div className="flex items-center gap-4 mt-auto">
            <div className="flex-1 bg-white/20 h-3 rounded-full overflow-hidden">
              <div className="bg-emerald-400 h-full w-[86%]" />
            </div>
            <span className="text-sm shrink-0">주간 속도 지수 86 / 100</span>
          </div>
        </section>

        <section className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-center dark:bg-slate-800 dark:border-slate-700">
          <h2 className="text-md font-bold text-slate-800 mb-4 dark:text-slate-100">3줄 경제 브리핑</h2>
          <ul className="space-y-4">
            <li className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
              <ArrowUpRight className="text-emerald-500 shrink-0" size={18} aria-hidden />
              <span>환율 상승: 해외 취업 준비 비용과 IT 수입 단가에 영향</span>
            </li>
            <li className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
              <ArrowDownRight className="text-blue-500 shrink-0" size={18} aria-hidden />
              <span>금리 동결: 청년 대출·전세 자금 부담 완화 기대</span>
            </li>
            <li className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
              <TrendingUp className="text-purple-500 shrink-0" size={18} aria-hidden />
              <span>이번 주 키워드: AI 규제, 에너지 전환</span>
            </li>
          </ul>
        </section>
      </div>

      {/* 5. 차트 영역 (연간 모멘텀 & 관심 점유율) — 2:1 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="lg:col-span-2 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col dark:bg-slate-800 dark:border-slate-700">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-md font-bold text-slate-800 dark:text-slate-100">연간 글로벌 모멘텀 트렌드</h2>
            <span className="text-xs text-slate-400 dark:text-slate-500">월별 지수 (Mock)</span>
          </div>
          <div className="flex-1 w-full min-h-[12rem] rounded-lg border border-slate-100 bg-slate-50/80 flex items-center justify-center p-2 dark:border-slate-700 dark:bg-slate-900/60">
            <MomentumAreaChart />
          </div>
        </section>

        <section className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col dark:bg-slate-800 dark:border-slate-700">
          <h2 className="text-md font-bold text-slate-800 mb-4 dark:text-slate-100">분야별 관심 점유율</h2>
          <div className="flex-1 w-full flex flex-col items-center justify-center">
            <div
              className="w-32 h-32 rounded-full border-8 border-indigo-500 border-t-emerald-400 border-l-purple-400 flex items-center justify-center mb-4"
              aria-hidden
            >
              <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">Top Sectors</span>
            </div>
            <div className="w-full text-xs text-slate-500 space-y-1 dark:text-slate-400">
              {SECTOR_SHARE.map((row) => (
                <div key={row.label} className="flex justify-between">
                  <span>{row.label}</span>
                  <span>{row.pct}%</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>

      {/* 6. 세대교체/크로스오버 라인 차트 */}
      <section className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm dark:bg-slate-800 dark:border-slate-700">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
          <h2 className="text-md font-bold text-slate-800 dark:text-slate-100">세대교체 / 크로스오버</h2>
          <span className="text-xs text-slate-400 dark:text-slate-500">기존 수요 vs 신흥 수요</span>
        </div>
        <div className="w-full min-h-[12rem] rounded-lg border border-slate-100 bg-slate-50/80 p-2 dark:border-slate-700 dark:bg-slate-900/60">
          <CrossoverLineChart />
        </div>
        <div className="mt-3 flex flex-wrap gap-3 text-xs">
          <span className="inline-flex items-center gap-1 text-slate-600 dark:text-slate-300">
            <span className="w-2.5 h-2.5 rounded-full bg-slate-500" />
            기존 수요(하락)
          </span>
          <span className="inline-flex items-center gap-1 text-indigo-700">
            <span className="w-2.5 h-2.5 rounded-full bg-indigo-600" />
            신흥 수요(상승)
          </span>
        </div>
      </section>

      {/* 7. 3줄 경제 브리핑 + 티커 */}
      <section className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm dark:bg-slate-800 dark:border-slate-700">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-md font-bold text-slate-800 mb-1 dark:text-slate-100">실시간 키워드 티커</h2>
            <span className="text-xs text-slate-400 dark:text-slate-500">지금 세상이 움직이는 신호</span>
          </div>
          <div className="w-full md:w-[70%] overflow-hidden rounded-full border border-indigo-100 bg-indigo-50 dark:border-indigo-900/40 dark:bg-indigo-900/20">
            <div className="ticker-track whitespace-nowrap py-2">
              {[...LIVE_TICKER, ...LIVE_TICKER].map((item, idx) => (
                <span
                  key={`${item}-${idx}`}
                  className="inline-flex items-center text-sm text-indigo-700 font-medium mr-6 dark:text-indigo-300"
                >
                  <span className="mr-2 text-indigo-400 dark:text-indigo-500">•</span>
                  {item}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* 8. 급상승 키워드 클라우드 */}
      <section className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4 dark:bg-slate-800 dark:border-slate-700">
        <div>
          <h2 className="text-md font-bold text-slate-800 mb-1 dark:text-slate-100">급상승 키워드 클라우드</h2>
          <span className="text-xs text-slate-400 dark:text-slate-500">지난 24시간 기준</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {KEYWORDS.map((keyword) => (
            <span
              key={keyword}
              className="px-4 py-2 bg-indigo-50 text-indigo-700 rounded-full text-sm font-medium border border-indigo-100 hover:bg-indigo-100 cursor-pointer transition-colors dark:bg-indigo-900/20 dark:text-indigo-300 dark:border-indigo-900/40 dark:hover:bg-indigo-900/35"
            >
              {keyword}
            </span>
          ))}
        </div>
      </section>
      <style jsx>{`
        .ticker-track {
          animation: pulseTicker 24s linear infinite;
        }
        @keyframes pulseTicker {
          0% {
            transform: translateX(0);
          }
          100% {
            transform: translateX(-50%);
          }
        }
      `}</style>
    </div>
  );
}
