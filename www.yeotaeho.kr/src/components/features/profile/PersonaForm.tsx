// 역량 프로필(페르소나) 수집 폼 — 스킬·경험·학력·요약을 구조화 입력해 저장
"use client";

import { Edit2, Plus, Save, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import type {
  EducationItem,
  ExperienceItem,
  Persona,
  SkillItem,
  SkillLevel,
} from "@/lib/api/persona";
import { usePersona, useUpsertPersona } from "@/hooks/usePersona";
import { useRefreshRoadmap } from "@/hooks/useRoadmap";

const LEVELS: SkillLevel[] = ["입문", "중급", "심화"];

type Draft = {
  skills: SkillItem[];
  experiences: ExperienceItem[];
  education: EducationItem[];
  summary: string;
};

function toDraft(p?: Persona): Draft {
  return {
    skills: p?.skills ?? [],
    experiences: p?.experiences ?? [],
    education: p?.education ?? [],
    summary: p?.summary ?? "",
  };
}

const inputCls =
  "w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-sm focus:outline-none focus:ring-2 focus:ring-red-500";

export function PersonaForm() {
  const { data, isLoading } = usePersona(true);
  const upsert = useUpsertPersona();
  const refresh = useRefreshRoadmap();

  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState<Draft>(() => toDraft(data));

  // 서버 데이터 도착/갱신 시 보기모드 draft 동기화(편집 중이면 보존).
  useEffect(() => {
    if (!isEditing) setDraft(toDraft(data));
  }, [data, isEditing]);

  const startEdit = () => {
    setDraft(toDraft(data));
    setIsEditing(true);
  };
  const cancel = () => {
    setDraft(toDraft(data));
    setIsEditing(false);
  };
  const save = async () => {
    await upsert.mutateAsync({ certifications: [], languages: [], links: [], projects: [], ...draft });
    setIsEditing(false);
    // 페르소나 반영해 로드맵 자동 재생성(LLM). 실패해도 저장은 유지.
    try {
      await refresh.mutateAsync();
    } catch {
      /* 로드맵 재생성 실패는 저장 성공을 막지 않는다. */
    }
  };

  const busy = upsert.isPending || refresh.isPending;

  // ── 스킬 ──
  const addSkill = () =>
    setDraft((d) => ({ ...d, skills: [...d.skills, { name: "", level: "입문" }] }));
  const setSkill = (i: number, patch: Partial<SkillItem>) =>
    setDraft((d) => ({
      ...d,
      skills: d.skills.map((s, idx) => (idx === i ? { ...s, ...patch } : s)),
    }));
  const removeSkill = (i: number) =>
    setDraft((d) => ({ ...d, skills: d.skills.filter((_, idx) => idx !== i) }));

  // ── 경험 ──
  const addExp = () =>
    setDraft((d) => ({
      ...d,
      experiences: [...d.experiences, { title: "", description: "", period: "" }],
    }));
  const setExp = (i: number, patch: Partial<ExperienceItem>) =>
    setDraft((d) => ({
      ...d,
      experiences: d.experiences.map((e, idx) => (idx === i ? { ...e, ...patch } : e)),
    }));
  const removeExp = (i: number) =>
    setDraft((d) => ({ ...d, experiences: d.experiences.filter((_, idx) => idx !== i) }));

  // ── 학력 ──
  const addEdu = () =>
    setDraft((d) => ({
      ...d,
      education: [...d.education, { school: "", major: "", degree: "", status: "" }],
    }));
  const setEdu = (i: number, patch: Partial<EducationItem>) =>
    setDraft((d) => ({
      ...d,
      education: d.education.map((e, idx) => (idx === i ? { ...e, ...patch } : e)),
    }));
  const removeEdu = (i: number) =>
    setDraft((d) => ({ ...d, education: d.education.filter((_, idx) => idx !== i) }));

  const view = toDraft(data);
  const isEmpty =
    !view.skills.length && !view.experiences.length && !view.education.length && !view.summary;

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-lg font-bold text-gray-800">역량 프로필</h3>
        {!isEditing ? (
          <button
            type="button"
            onClick={startEdit}
            className="inline-flex items-center gap-1 text-sm text-red-600 hover:text-red-700"
          >
            <Edit2 size={16} /> 편집
          </button>
        ) : (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={save}
              disabled={busy}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-red-600 text-white text-sm hover:bg-red-700 disabled:opacity-50"
            >
              <Save size={16} />{" "}
              {refresh.isPending ? "로드맵 생성 중…" : upsert.isPending ? "저장 중…" : "저장"}
            </button>
            <button
              type="button"
              onClick={cancel}
              disabled={busy}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-gray-100 text-gray-700 text-sm hover:bg-gray-200 disabled:opacity-50"
            >
              <X size={16} /> 취소
            </button>
          </div>
        )}
      </div>
      <p className="text-sm text-gray-500 mb-4">
        스킬·경험·학력은 로드맵·싱크 분석의 기반이 됩니다. 저장하면 내 로드맵이 자동으로 다시 생성됩니다.
      </p>

      {isLoading ? (
        <p className="text-sm text-gray-400">불러오는 중…</p>
      ) : !isEditing && isEmpty ? (
        <p className="text-sm text-gray-500">
          아직 입력된 역량 정보가 없습니다. <strong>편집</strong>을 눌러 추가해 주세요.
        </p>
      ) : (
        <div className="space-y-6">
          {/* 스킬 */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-semibold text-gray-700">스킬</p>
              {isEditing && (
                <button type="button" onClick={addSkill} className="text-red-600 hover:text-red-700">
                  <Plus size={16} />
                </button>
              )}
            </div>
            {isEditing ? (
              <div className="space-y-2">
                {draft.skills.map((s, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input
                      className={inputCls}
                      value={s.name}
                      placeholder="스킬명 (예: Python)"
                      onChange={(e) => setSkill(i, { name: e.target.value })}
                    />
                    <select
                      className="px-2 py-2 border border-gray-300 rounded-md bg-white text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                      value={s.level}
                      onChange={(e) => setSkill(i, { level: e.target.value as SkillLevel })}
                    >
                      {LEVELS.map((lv) => (
                        <option key={lv} value={lv}>
                          {lv}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => removeSkill(i)}
                      className="text-gray-400 hover:text-red-600"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
                {!draft.skills.length && <p className="text-xs text-gray-400">+ 로 스킬을 추가하세요.</p>}
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {view.skills.map((s, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-gray-100 border border-gray-200 text-sm text-gray-700"
                  >
                    {s.name}
                    <span className="text-xs text-red-600">{s.level}</span>
                  </span>
                ))}
              </div>
            )}
          </section>

          {/* 경험 */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-semibold text-gray-700">경험</p>
              {isEditing && (
                <button type="button" onClick={addExp} className="text-red-600 hover:text-red-700">
                  <Plus size={16} />
                </button>
              )}
            </div>
            {isEditing ? (
              <div className="space-y-3">
                {draft.experiences.map((e, i) => (
                  <div key={i} className="rounded-md border border-gray-200 p-3 space-y-2">
                    <div className="flex gap-2">
                      <input
                        className={inputCls}
                        value={e.title}
                        placeholder="제목 (예: 데이터 분석 동아리)"
                        onChange={(ev) => setExp(i, { title: ev.target.value })}
                      />
                      <input
                        className="w-28 px-3 py-2 border border-gray-300 rounded-md bg-white text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                        value={e.period}
                        placeholder="기간"
                        onChange={(ev) => setExp(i, { period: ev.target.value })}
                      />
                      <button
                        type="button"
                        onClick={() => removeExp(i)}
                        className="text-gray-400 hover:text-red-600"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                    <input
                      className={inputCls}
                      value={e.description}
                      placeholder="설명"
                      onChange={(ev) => setExp(i, { description: ev.target.value })}
                    />
                  </div>
                ))}
                {!draft.experiences.length && (
                  <p className="text-xs text-gray-400">+ 로 경험을 추가하세요.</p>
                )}
              </div>
            ) : (
              <ul className="space-y-1">
                {view.experiences.map((e, i) => (
                  <li key={i} className="text-sm text-gray-700">
                    <span className="font-medium">{e.title}</span>
                    {e.period ? <span className="text-gray-400"> · {e.period}</span> : null}
                    {e.description ? <span className="text-gray-500"> — {e.description}</span> : null}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* 학력 */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-semibold text-gray-700">학력</p>
              {isEditing && (
                <button type="button" onClick={addEdu} className="text-red-600 hover:text-red-700">
                  <Plus size={16} />
                </button>
              )}
            </div>
            {isEditing ? (
              <div className="space-y-2">
                {draft.education.map((e, i) => (
                  <div key={i} className="flex flex-wrap gap-2">
                    <input
                      className="flex-1 min-w-[120px] px-3 py-2 border border-gray-300 rounded-md bg-white text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                      value={e.school}
                      placeholder="학교"
                      onChange={(ev) => setEdu(i, { school: ev.target.value })}
                    />
                    <input
                      className="flex-1 min-w-[120px] px-3 py-2 border border-gray-300 rounded-md bg-white text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                      value={e.major}
                      placeholder="전공"
                      onChange={(ev) => setEdu(i, { major: ev.target.value })}
                    />
                    <input
                      className="w-24 px-3 py-2 border border-gray-300 rounded-md bg-white text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                      value={e.degree}
                      placeholder="학위"
                      onChange={(ev) => setEdu(i, { degree: ev.target.value })}
                    />
                    <input
                      className="w-24 px-3 py-2 border border-gray-300 rounded-md bg-white text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                      value={e.status}
                      placeholder="상태"
                      onChange={(ev) => setEdu(i, { status: ev.target.value })}
                    />
                    <button
                      type="button"
                      onClick={() => removeEdu(i)}
                      className="text-gray-400 hover:text-red-600"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
                {!draft.education.length && (
                  <p className="text-xs text-gray-400">+ 로 학력을 추가하세요.</p>
                )}
              </div>
            ) : (
              <ul className="space-y-1">
                {view.education.map((e, i) => (
                  <li key={i} className="text-sm text-gray-700">
                    <span className="font-medium">{e.school}</span>
                    {e.major ? <span className="text-gray-500"> {e.major}</span> : null}
                    {e.degree ? <span className="text-gray-400"> · {e.degree}</span> : null}
                    {e.status ? <span className="text-gray-400"> ({e.status})</span> : null}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* 요약 */}
          <section>
            <p className="text-sm font-semibold text-gray-700 mb-2">한 줄 요약</p>
            {isEditing ? (
              <textarea
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                value={draft.summary}
                placeholder="예: 에너지·ESG 도메인 × AI 엔지니어링으로 진로를 탐색 중"
                onChange={(e) => setDraft((d) => ({ ...d, summary: e.target.value }))}
              />
            ) : (
              <p className="text-sm text-gray-700">
                {view.summary || <span className="text-gray-400">요약이 없습니다.</span>}
              </p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
