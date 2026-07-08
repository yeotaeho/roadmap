"use client";

// 여정 지도 — 퀘스트 트리를 게임 스테이지 맵으로(가지치기 배치·경로·현재 위치 아바타·이동)

import { motion } from "framer-motion";
import { Check, ChevronUp, Flag, Footprints, Lock, Star } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { QuestTreeNode, QuestTreeState } from "@/data/roadmapQuestMap";

type LaidNode = { node: QuestTreeNode; x: number; y: number; depth: number };
type Edge = { from: LaidNode; to: LaidNode };

const STATE_LABEL: Record<QuestTreeState, string> = {
  start: "시작점",
  done: "정복 완료",
  active: "진행 중",
  available: "도전 가능",
  locked: "잠김",
};

const DIFFICULTY_RING: Record<string, string> = {
  입문: "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:ring-emerald-800",
  중급: "bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:ring-amber-800",
  심화: "bg-violet-50 text-violet-800 ring-violet-200 dark:bg-violet-900/30 dark:text-violet-300 dark:ring-violet-800",
};

// 스테이지 노드 원형 뱃지 스타일(상태별)
function nodeVisual(state: QuestTreeState) {
  switch (state) {
    case "start":
      return { cls: "bg-indigo-600 text-white ring-4 ring-indigo-200 dark:ring-indigo-900/50", Icon: Flag };
    case "done":
      return { cls: "bg-emerald-500 text-white ring-2 ring-emerald-200 dark:ring-emerald-900/50", Icon: Check };
    case "active":
      return { cls: "bg-indigo-600 text-white ring-4 ring-indigo-300/70", Icon: Star };
    case "available":
      return {
        cls: "bg-white text-indigo-600 ring-2 ring-indigo-300 dark:bg-slate-800 dark:text-indigo-300 dark:ring-indigo-700",
        Icon: ChevronUp,
      };
    default:
      return {
        cls: "bg-slate-200 text-slate-400 ring-1 ring-slate-300 dark:bg-slate-700 dark:text-slate-500 dark:ring-slate-600",
        Icon: Lock,
      };
  }
}

// 트리 → 좌표(0~100 공간). 잎은 순차 컬럼, 내부 노드는 자식 평균 컬럼.
function computeLayout(root: QuestTreeNode): { nodes: LaidNode[]; edges: Edge[]; maxDepth: number } {
  let leafCol = 0;
  const colOf = new Map<string, number>();
  let maxDepth = 0;

  const assign = (n: QuestTreeNode, depth: number): number => {
    maxDepth = Math.max(maxDepth, depth);
    if (!n.children || n.children.length === 0) {
      const c = leafCol++;
      colOf.set(n.id, c);
      return c;
    }
    const cols = n.children.map((ch) => assign(ch, depth + 1));
    const c = cols.reduce((a, b) => a + b, 0) / cols.length;
    colOf.set(n.id, c);
    return c;
  };
  assign(root, 0);
  const maxCol = Math.max(0, leafCol - 1);

  const PAD_X = 13;
  const PAD_Y = 11;
  const spanX = 100 - PAD_X * 2;
  const spanY = 100 - PAD_Y * 2;

  const nodes: LaidNode[] = [];
  const edges: Edge[] = [];
  const place = (n: QuestTreeNode, depth: number, parent?: LaidNode) => {
    const col = colOf.get(n.id)!;
    const x = maxCol === 0 ? 50 : PAD_X + (col / maxCol) * spanX;
    const y = maxDepth === 0 ? 50 : PAD_Y + (depth / maxDepth) * spanY;
    const laid: LaidNode = { node: n, x, y, depth };
    nodes.push(laid);
    if (parent) edges.push({ from: parent, to: laid });
    for (const ch of n.children ?? []) place(ch, depth + 1, laid);
  };
  place(root, 0);
  return { nodes, edges, maxDepth };
}

export function JourneyQuestMap({
  tree,
  taskCounts,
}: {
  tree: QuestTreeNode;
  taskCounts?: Map<string, { done: number; total: number }>;
}) {
  const { nodes, edges, maxDepth } = useMemo(() => computeLayout(tree), [tree]);

  const currentId = useMemo(() => {
    const active = nodes.find((n) => n.node.state === "active");
    const start = nodes.find((n) => n.node.state === "start");
    return active?.node.id ?? start?.node.id ?? nodes[0]?.node.id ?? "";
  }, [nodes]);

  // avatarId: 아바타(현재 위치, 잠금 노드로는 이동 불가) / focusId: 상세 패널(잠금 포함 열람 가능)
  const [avatarId, setAvatarId] = useState(currentId);
  const [focusId, setFocusId] = useState(currentId);

  // 로드맵 갱신(트리 교체) 시 현재 위치로 리셋
  useEffect(() => {
    setAvatarId(currentId);
    setFocusId(currentId);
  }, [currentId]);

  const byId = useMemo(() => new Map(nodes.map((n) => [n.node.id, n])), [nodes]);
  const avatar = byId.get(avatarId) ?? byId.get(currentId);
  const focus = byId.get(focusId)?.node ?? byId.get(currentId)?.node ?? tree;

  const doneCount = nodes.filter((n) => n.node.state === "done").length;
  const total = nodes.length;

  const handleNodeClick = (laid: LaidNode) => {
    setFocusId(laid.node.id);
    if (laid.node.state !== "locked") setAvatarId(laid.node.id);
  };

  const focusCounts = taskCounts?.get(focus.id);
  const height = 170 + maxDepth * 104;

  return (
    <div className="space-y-4">
      {/* 진행도 + 범례 */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-600 px-3 py-1 text-xs font-bold text-white shadow-sm">
          <Flag className="h-3.5 w-3.5" />
          {doneCount}/{total} 정복
        </span>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] font-medium text-slate-500 dark:text-slate-400">
          <Legend dot="bg-emerald-500" label="완료" />
          <Legend dot="bg-indigo-600" label="진행 중" />
          <Legend dot="bg-white ring-2 ring-indigo-300" label="도전 가능" />
          <Legend dot="bg-slate-300 dark:bg-slate-600" label="잠김" />
        </div>
      </div>

      {/* 지도 캔버스 */}
      <div
        className="relative overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-b from-slate-50 to-indigo-50/50 dark:border-slate-700 dark:from-slate-900 dark:to-indigo-950/30"
        style={{ height }}
      >
        {/* 점 패턴 오버레이 */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage:
              "radial-gradient(circle, rgba(100,116,139,0.14) 1px, transparent 1px)",
            backgroundSize: "22px 22px",
          }}
        />

        {/* 경로(SVG) — 부모→자식 곡선. 잠금 자식은 점선 */}
        <svg
          className="absolute inset-0 h-full w-full"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          aria-hidden
        >
          {edges.map(({ from, to }, i) => {
            const dy = to.y - from.y;
            const d = `M ${from.x} ${from.y} C ${from.x} ${from.y + dy * 0.45} ${to.x} ${to.y - dy * 0.45} ${to.x} ${to.y}`;
            const locked = to.node.state === "locked";
            return (
              <path
                key={i}
                d={d}
                fill="none"
                stroke={locked ? "rgb(203 213 225)" : "rgb(129 140 248)"}
                strokeWidth={2.4}
                strokeLinecap="round"
                strokeDasharray={locked ? "1 3.5" : undefined}
                vectorEffect="non-scaling-stroke"
              />
            );
          })}
        </svg>

        {/* 스테이지 노드 */}
        {nodes.map((laid) => {
          const { cls, Icon } = nodeVisual(laid.node.state);
          const isFocus = laid.node.id === focus.id;
          const pulse = laid.node.state === "active";
          return (
            <button
              key={laid.node.id}
              type="button"
              onClick={() => handleNodeClick(laid)}
              className="absolute z-10 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center"
              style={{ left: `${laid.x}%`, top: `${laid.y}%` }}
            >
              <span className="relative grid place-items-center">
                {pulse ? (
                  <span className="absolute h-11 w-11 animate-ping rounded-full bg-indigo-400/40" />
                ) : null}
                <span
                  className={`relative grid h-10 w-10 place-items-center rounded-full shadow-md transition ${cls} ${
                    isFocus ? "scale-110" : "hover:scale-105"
                  } ${laid.node.state === "locked" ? "opacity-70" : ""}`}
                >
                  <Icon className="h-4 w-4" />
                </span>
              </span>
              <span
                className={`mt-1 max-w-[100px] truncate rounded-md px-1.5 py-0.5 text-[10px] font-semibold ${
                  isFocus
                    ? "bg-indigo-600 text-white"
                    : "bg-white/80 text-slate-600 dark:bg-slate-800/80 dark:text-slate-300"
                }`}
              >
                {laid.node.title}
              </span>
            </button>
          );
        })}

        {/* 현재 위치 아바타 — 이동 애니메이션 */}
        {avatar ? (
          <motion.div
            className="pointer-events-none absolute z-20"
            initial={false}
            animate={{ left: `${avatar.x}%`, top: `${avatar.y}%` }}
            transition={{ type: "spring", stiffness: 260, damping: 24 }}
            style={{ transform: "translate(-50%, -184%)" }}
          >
            <motion.div
              animate={{ y: [0, -4, 0] }}
              transition={{ repeat: Infinity, duration: 1.6, ease: "easeInOut" }}
              className="flex flex-col items-center"
            >
              <span className="grid h-8 w-8 place-items-center rounded-full bg-indigo-600 text-white shadow-lg ring-2 ring-white dark:ring-slate-900">
                <Footprints className="h-4 w-4" />
              </span>
              <span className="mt-0.5 h-0 w-0 border-x-4 border-t-[6px] border-x-transparent border-t-indigo-600" />
            </motion.div>
          </motion.div>
        ) : null}
      </div>

      {/* 상세 패널 — 선택 스테이지 (key 리마운트로 즉시 갱신·mount 애니메이션) */}
      <div>
        <motion.div
          key={focus.id}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18 }}
          className="rounded-2xl border border-slate-200 bg-[#F8FAFC] p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900"
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-1.5">
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-bold ring-1 ${DIFFICULTY_RING[focus.difficulty]}`}
                >
                  {focus.difficulty}
                </span>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  {STATE_LABEL[focus.state]}
                </span>
                {focusCounts && focusCounts.total > 0 ? (
                  <span className="rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-semibold text-sky-800 dark:bg-sky-900/35 dark:text-sky-300">
                    태스크 {focusCounts.done}/{focusCounts.total}
                  </span>
                ) : null}
              </div>
              <h3 className="mt-2 text-base font-bold text-slate-900 dark:text-slate-100">{focus.title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-slate-600 dark:text-slate-400">{focus.purpose}</p>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap gap-1.5">
            {focus.keywords.map((kw) => (
              <span
                key={kw}
                className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700 dark:bg-slate-700 dark:text-slate-300"
              >
                #{kw}
              </span>
            ))}
          </div>

          {focus.state === "locked" ? (
            <p className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-2.5 py-1.5 text-[11px] font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              <Lock className="h-3 w-3" />앞 단계를 완료하면 이 스테이지로 이동할 수 있어요.
            </p>
          ) : null}
        </motion.div>
      </div>
    </div>
  );
}

function Legend({ dot, label }: { dot: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className={`h-2.5 w-2.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
}
