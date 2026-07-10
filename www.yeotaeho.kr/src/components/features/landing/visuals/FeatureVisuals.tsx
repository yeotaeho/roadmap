// 랜딩 기능 카드용 인라인 SVG 모션 그래픽 6종 — 실제 스크린샷 에셋 도착 시 next/image로 교체 가능한 슬롯
import type { LandingFeatureId } from "../landing.copy";

const VIEWBOX = "0 0 240 150";
const FRAME_CLASS =
  "h-full w-full rounded-xl border border-slate-200 bg-white/70 dark:border-slate-700 dark:bg-slate-900/60";

/** Pulse — 스파크라인 + 섹터 점수 바 */
function PulseVisual() {
  const bars = [58, 72, 45, 84, 66];
  return (
    <svg viewBox={VIEWBOX} className={FRAME_CLASS} role="img" aria-label="섹터 트렌드 점수 차트">
      <path
        d="M16 96 L48 78 L80 88 L112 56 L144 66 L176 38 L224 46"
        fill="none"
        pathLength={1}
        className="landing-viz-draw stroke-indigo-500"
        strokeWidth={3}
        strokeLinecap="round"
      />
      <circle cx="176" cy="38" r="5" className="landing-viz-blink fill-indigo-500" />
      {bars.map((h, i) => (
        <rect
          key={i}
          x={24 + i * 42}
          y={138 - h * 0.28}
          width={22}
          height={h * 0.28}
          rx={3}
          className={i === 3 ? "fill-indigo-500" : "fill-slate-300 dark:fill-slate-600"}
        />
      ))}
    </svg>
  );
}

/** Gap — 버블 스캐터, 미해결 기회 버블 하이라이트 */
function GapVisual() {
  const bubbles = [
    { cx: 52, cy: 98, r: 14 },
    { cx: 96, cy: 62, r: 10 },
    { cx: 138, cy: 104, r: 18 },
    { cx: 202, cy: 92, r: 12 },
  ];
  return (
    <svg viewBox={VIEWBOX} className={FRAME_CLASS} role="img" aria-label="시장 기회 버블 차트">
      <line x1="20" y1="130" x2="224" y2="130" className="stroke-slate-300 dark:stroke-slate-600" strokeWidth={1.5} />
      <line x1="20" y1="130" x2="20" y2="18" className="stroke-slate-300 dark:stroke-slate-600" strokeWidth={1.5} />
      {bubbles.map((b, i) => (
        <circle
          key={i}
          {...b}
          className="landing-viz-pop fill-slate-300/60 dark:fill-slate-600/60"
          style={{ animationDelay: `${0.15 * i}s` }}
        />
      ))}
      <circle cx="168" cy="44" r="20" className="landing-viz-pop fill-indigo-500/25" style={{ animationDelay: "0.7s" }} />
      <circle cx="168" cy="44" r="11" className="landing-viz-blink fill-indigo-500" />
    </svg>
  );
}

/** Sync — 원형 게이지 아크 + 일별 점 시계열 */
function SyncVisual() {
  return (
    <svg viewBox={VIEWBOX} className={FRAME_CLASS} role="img" aria-label="싱크로율 게이지">
      <circle cx="86" cy="72" r="38" fill="none" className="stroke-slate-200 dark:stroke-slate-700" strokeWidth={10} />
      <circle
        cx="86"
        cy="72"
        r="38"
        fill="none"
        pathLength={1}
        strokeDasharray="0.78 1"
        className="landing-viz-draw stroke-indigo-500"
        strokeWidth={10}
        strokeLinecap="round"
        transform="rotate(-90 86 72)"
      />
      <text x="86" y="80" textAnchor="middle" className="fill-slate-900 text-2xl font-bold dark:fill-white">
        78
      </text>
      {[0, 1, 2, 3, 4].map((i) => (
        <circle
          key={i}
          cx={156 + i * 18}
          cy={104 - [8, 18, 12, 26, 34][i]}
          r={4}
          className={`landing-viz-pop ${i === 4 ? "fill-indigo-500" : "fill-slate-400 dark:fill-slate-500"}`}
          style={{ animationDelay: `${0.2 * i}s` }}
        />
      ))}
    </svg>
  );
}

/** Chance — 기회 카드 스택 + 채널 태그 칩 */
function ChanceVisual() {
  const cards = [
    { y: 62, label: "채용 공고", cls: "" },
    { y: 42, label: "부트캠프", cls: "" },
    { y: 22, label: "공모전 · 지원사업", cls: "landing-viz-float" },
  ];
  return (
    <svg viewBox={VIEWBOX} className={FRAME_CLASS} role="img" aria-label="기회 매칭 카드">
      {cards.map((c, i) => (
        <g key={i} className={c.cls}>
          <rect
            x={40 + i * 10}
            y={c.y}
            width={160}
            height={52}
            rx={10}
            className={
              i === 2
                ? "fill-white stroke-indigo-400 dark:fill-slate-800"
                : "fill-slate-100 stroke-slate-300 dark:fill-slate-800/60 dark:stroke-slate-600"
            }
            strokeWidth={1.5}
          />
          <text
            x={54 + i * 10}
            y={c.y + 22}
            className="fill-slate-600 text-[11px] font-semibold dark:fill-slate-300"
          >
            {c.label}
          </text>
          <rect
            x={54 + i * 10}
            y={c.y + 32}
            width={i === 2 ? 46 : 70}
            height={8}
            rx={4}
            className={i === 2 ? "fill-indigo-500" : "fill-slate-300 dark:fill-slate-600"}
          />
        </g>
      ))}
    </svg>
  );
}

/** Roadmap — 퀘스트 트리 노드-엣지, 순차 점등 */
function RoadmapVisual() {
  const nodes = [
    { cx: 40, cy: 110 },
    { cx: 96, cy: 76 },
    { cx: 96, cy: 124 },
    { cx: 156, cy: 52 },
    { cx: 156, cy: 96 },
    { cx: 210, cy: 72 },
  ];
  const edges = [
    "M40 110 L96 76",
    "M40 110 L96 124",
    "M96 76 L156 52",
    "M96 76 L156 96",
    "M156 52 L210 72",
  ];
  return (
    <svg viewBox={VIEWBOX} className={FRAME_CLASS} role="img" aria-label="퀘스트 트리">
      {edges.map((d, i) => (
        <path
          key={i}
          d={d}
          fill="none"
          pathLength={1}
          className="landing-viz-draw stroke-slate-300 dark:stroke-slate-600"
          strokeWidth={2}
          style={{ animationDelay: `${0.25 * i}s` }}
        />
      ))}
      {nodes.map((n, i) => (
        <circle
          key={i}
          {...n}
          r={i === 5 ? 10 : 7}
          className={`landing-viz-pop ${
            i === 5 ? "landing-viz-blink fill-indigo-500" : i < 3 ? "fill-indigo-400" : "fill-slate-400 dark:fill-slate-500"
          }`}
          style={{ animationDelay: `${0.2 * i}s` }}
        />
      ))}
    </svg>
  );
}

/** Coach — 챗 버블 + 타이핑 도트 (SSE 스트리밍 은유) */
function CoachVisual() {
  return (
    <svg viewBox={VIEWBOX} className={FRAME_CLASS} role="img" aria-label="AI 코치 대화">
      <g className="landing-viz-pop" style={{ animationDelay: "0.1s" }}>
        <rect x="24" y="24" width={132} height={34} rx={12} className="fill-slate-200 dark:fill-slate-700" />
        <rect x="38" y="38" width={96} height={7} rx={3.5} className="fill-slate-400 dark:fill-slate-500" />
      </g>
      <g className="landing-viz-pop" style={{ animationDelay: "0.5s" }}>
        <rect x="84" y="68" width={132} height={34} rx={12} className="fill-indigo-500/90" />
        <rect x="98" y="82" width={100} height={7} rx={3.5} className="fill-indigo-200" />
      </g>
      <g className="landing-viz-pop" style={{ animationDelay: "0.9s" }}>
        <rect x="24" y="112" width={72} height={26} rx={12} className="fill-slate-200 dark:fill-slate-700" />
        {[0, 1, 2].map((i) => (
          <circle
            key={i}
            cx={48 + i * 12}
            cy={125}
            r={3.5}
            className="landing-viz-blink fill-slate-500 dark:fill-slate-400"
            style={{ animationDelay: `${0.2 * i}s` }}
          />
        ))}
      </g>
    </svg>
  );
}

const VISUALS: Record<LandingFeatureId, () => React.ReactElement> = {
  pulse: PulseVisual,
  gap: GapVisual,
  sync: SyncVisual,
  chance: ChanceVisual,
  roadmap: RoadmapVisual,
  coach: CoachVisual,
};

export function FeatureVisual({ id }: { id: LandingFeatureId }) {
  const Visual = VISUALS[id];
  return <Visual />;
}
