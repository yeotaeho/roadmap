// 역량 프로필(페르소나) 수집 폼 — 스킬·경험·학력·요약·자격증·언어·링크·프로젝트 구조화 입력
"use client";

import { Edit2, Plus, Save, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import type {
  CertificationItem,
  EducationItem,
  ExperienceItem,
  LanguageItem,
  LinkItem,
  Persona,
  ProjectItem,
  SkillItem,
  SkillLevel,
} from "@/lib/api/persona";
import { usePersona, useUpsertPersona } from "@/hooks/usePersona";
import { useRefreshRoadmap } from "@/hooks/useRoadmap";

const LEVELS: SkillLevel[] = ["입문", "중급", "심화"];
const LINK_TYPES = ["github", "portfolio", "blog"];

type Draft = {
  skills: SkillItem[];
  experiences: ExperienceItem[];
  education: EducationItem[];
  summary: string;
  certifications: CertificationItem[];
  languages: LanguageItem[];
  links: LinkItem[];
  projects: ProjectItem[];
};

function toDraft(p?: Persona): Draft {
  return {
    skills: p?.skills ?? [],
    experiences: p?.experiences ?? [],
    education: p?.education ?? [],
    summary: p?.summary ?? "",
    certifications: p?.certifications ?? [],
    languages: p?.languages ?? [],
    links: p?.links ?? [],
    projects: p?.projects ?? [],
  };
}

const inputCls =
  "w-full px-3 py-2 border border-border rounded-md bg-card text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500";

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
    await upsert.mutateAsync(draft);
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

  // ── 자격증 ──
  const addCert = () =>
    setDraft((d) => ({
      ...d,
      certifications: [...d.certifications, { name: "", issuer: "", year: "" }],
    }));
  const setCert = (i: number, patch: Partial<CertificationItem>) =>
    setDraft((d) => ({
      ...d,
      certifications: d.certifications.map((c, idx) => (idx === i ? { ...c, ...patch } : c)),
    }));
  const removeCert = (i: number) =>
    setDraft((d) => ({ ...d, certifications: d.certifications.filter((_, idx) => idx !== i) }));

  // ── 어학 ──
  const addLang = () =>
    setDraft((d) => ({
      ...d,
      languages: [...d.languages, { language: "", test: "", score: "" }],
    }));
  const setLang = (i: number, patch: Partial<LanguageItem>) =>
    setDraft((d) => ({
      ...d,
      languages: d.languages.map((l, idx) => (idx === i ? { ...l, ...patch } : l)),
    }));
  const removeLang = (i: number) =>
    setDraft((d) => ({ ...d, languages: d.languages.filter((_, idx) => idx !== i) }));

  // ── 링크 ──
  const addLink = () =>
    setDraft((d) => ({
      ...d,
      links: [...d.links, { type: "github", url: "" }],
    }));
  const setLink = (i: number, patch: Partial<LinkItem>) =>
    setDraft((d) => ({
      ...d,
      links: d.links.map((l, idx) => (idx === i ? { ...l, ...patch } : l)),
    }));
  const removeLink = (i: number) =>
    setDraft((d) => ({ ...d, links: d.links.filter((_, idx) => idx !== i) }));

  // ── 프로젝트 ──
  const addProject = () =>
    setDraft((d) => ({
      ...d,
      projects: [
        ...d.projects,
        { title: "", description: "", role: "", period: "", tech_stack: [] },
      ],
    }));
  const setProject = (i: number, patch: Partial<Omit<ProjectItem, "tech_stack">> & { tech_stack?: string[] }) =>
    setDraft((d) => ({
      ...d,
      projects: d.projects.map((p, idx) => (idx === i ? { ...p, ...patch } : p)),
    }));
  const removeProject = (i: number) =>
    setDraft((d) => ({ ...d, projects: d.projects.filter((_, idx) => idx !== i) }));

  const view = toDraft(data);
  const isEmpty =
    !view.skills.length &&
    !view.experiences.length &&
    !view.education.length &&
    !view.summary &&
    !view.certifications.length &&
    !view.languages.length &&
    !view.links.length &&
    !view.projects.length;

  return (
    <div className="bg-card rounded-lg shadow-sm border border-border p-6 mb-6">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-lg font-bold text-foreground">역량 프로필</h3>
        {!isEditing ? (
          <button
            type="button"
            onClick={startEdit}
            className="inline-flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-700"
          >
            <Edit2 size={16} /> 편집
          </button>
        ) : (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={save}
              disabled={busy}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-indigo-600 text-white text-sm hover:bg-indigo-700 disabled:opacity-50"
            >
              <Save size={16} />{" "}
              {refresh.isPending ? "로드맵 생성 중…" : upsert.isPending ? "저장 중…" : "저장"}
            </button>
            <button
              type="button"
              onClick={cancel}
              disabled={busy}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-muted text-foreground text-sm hover:bg-accent disabled:opacity-50"
            >
              <X size={16} /> 취소
            </button>
          </div>
        )}
      </div>
      <p className="text-sm text-muted-foreground mb-4">
        스킬·경험·학력은 로드맵·싱크 분석의 기반이 됩니다. 저장하면 내 로드맵이 자동으로 다시 생성됩니다.
      </p>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">불러오는 중…</p>
      ) : !isEditing && isEmpty ? (
        <p className="text-sm text-muted-foreground">
          아직 입력된 역량 정보가 없습니다. <strong>편집</strong>을 눌러 추가해 주세요.
        </p>
      ) : (
        <div className="space-y-6">
          {/* 스킬 */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-semibold text-foreground">스킬</p>
              {isEditing && (
                <button type="button" onClick={addSkill} className="text-indigo-600 hover:text-indigo-700">
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
                      className="px-2 py-2 border border-border rounded-md bg-card text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
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
                      className="text-muted-foreground hover:text-red-600"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
                {!draft.skills.length && <p className="text-xs text-muted-foreground">+ 로 스킬을 추가하세요.</p>}
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {view.skills.map((s, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-muted border border-border text-sm text-foreground"
                  >
                    {s.name}
                    <span className="text-xs text-indigo-600">{s.level}</span>
                  </span>
                ))}
              </div>
            )}
          </section>

          {/* 경험 */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-semibold text-foreground">경험</p>
              {isEditing && (
                <button type="button" onClick={addExp} className="text-indigo-600 hover:text-indigo-700">
                  <Plus size={16} />
                </button>
              )}
            </div>
            {isEditing ? (
              <div className="space-y-3">
                {draft.experiences.map((e, i) => (
                  <div key={i} className="rounded-md border border-border p-3 space-y-2">
                    <div className="flex gap-2">
                      <input
                        className={inputCls}
                        value={e.title}
                        placeholder="제목 (예: 데이터 분석 동아리)"
                        onChange={(ev) => setExp(i, { title: ev.target.value })}
                      />
                      <input
                        className="w-28 px-3 py-2 border border-border rounded-md bg-card text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        value={e.period}
                        placeholder="기간"
                        onChange={(ev) => setExp(i, { period: ev.target.value })}
                      />
                      <button
                        type="button"
                        onClick={() => removeExp(i)}
                        className="text-muted-foreground hover:text-red-600"
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
                  <p className="text-xs text-muted-foreground">+ 로 경험을 추가하세요.</p>
                )}
              </div>
            ) : (
              <ul className="space-y-1">
                {view.experiences.map((e, i) => (
                  <li key={i} className="text-sm text-foreground">
                    <span className="font-medium">{e.title}</span>
                    {e.period ? <span className="text-muted-foreground"> · {e.period}</span> : null}
                    {e.description ? <span className="text-muted-foreground"> — {e.description}</span> : null}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* 학력 */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-semibold text-foreground">학력</p>
              {isEditing && (
                <button type="button" onClick={addEdu} className="text-indigo-600 hover:text-indigo-700">
                  <Plus size={16} />
                </button>
              )}
            </div>
            {isEditing ? (
              <div className="space-y-2">
                {draft.education.map((e, i) => (
                  <div key={i} className="flex flex-wrap gap-2">
                    <input
                      className="flex-1 min-w-[120px] px-3 py-2 border border-border rounded-md bg-card text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      value={e.school}
                      placeholder="학교"
                      onChange={(ev) => setEdu(i, { school: ev.target.value })}
                    />
                    <input
                      className="flex-1 min-w-[120px] px-3 py-2 border border-border rounded-md bg-card text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      value={e.major}
                      placeholder="전공"
                      onChange={(ev) => setEdu(i, { major: ev.target.value })}
                    />
                    <input
                      className="w-24 px-3 py-2 border border-border rounded-md bg-card text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      value={e.degree}
                      placeholder="학위"
                      onChange={(ev) => setEdu(i, { degree: ev.target.value })}
                    />
                    <input
                      className="w-24 px-3 py-2 border border-border rounded-md bg-card text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      value={e.status}
                      placeholder="상태"
                      onChange={(ev) => setEdu(i, { status: ev.target.value })}
                    />
                    <button
                      type="button"
                      onClick={() => removeEdu(i)}
                      className="text-muted-foreground hover:text-red-600"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
                {!draft.education.length && (
                  <p className="text-xs text-muted-foreground">+ 로 학력을 추가하세요.</p>
                )}
              </div>
            ) : (
              <ul className="space-y-1">
                {view.education.map((e, i) => (
                  <li key={i} className="text-sm text-foreground">
                    <span className="font-medium">{e.school}</span>
                    {e.major ? <span className="text-muted-foreground"> {e.major}</span> : null}
                    {e.degree ? <span className="text-muted-foreground"> · {e.degree}</span> : null}
                    {e.status ? <span className="text-muted-foreground"> ({e.status})</span> : null}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* 자격증 */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-semibold text-foreground">자격증</p>
              {isEditing && (
                <button type="button" onClick={addCert} className="text-indigo-600 hover:text-indigo-700">
                  <Plus size={16} />
                </button>
              )}
            </div>
            {isEditing ? (
              <div className="space-y-2">
                {draft.certifications.map((c, i) => (
                  <div key={i} className="flex flex-wrap gap-2 items-center">
                    <input
                      className="flex-1 min-w-[120px] px-3 py-2 border border-border rounded-md bg-card text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      value={c.name}
                      placeholder="자격증명"
                      onChange={(e) => setCert(i, { name: e.target.value })}
                    />
                    <input
                      className="flex-1 min-w-[100px] px-3 py-2 border border-border rounded-md bg-card text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      value={c.issuer}
                      placeholder="발급기관"
                      onChange={(e) => setCert(i, { issuer: e.target.value })}
                    />
                    <input
                      className="w-20 px-3 py-2 border border-border rounded-md bg-card text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      value={c.year}
                      placeholder="취득연도"
                      onChange={(e) => setCert(i, { year: e.target.value })}
                    />
                    <button
                      type="button"
                      onClick={() => removeCert(i)}
                      className="text-muted-foreground hover:text-red-600"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
                {!draft.certifications.length && (
                  <p className="text-xs text-muted-foreground">+ 로 자격증을 추가하세요.</p>
                )}
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {view.certifications.map((c, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-muted border border-border text-sm text-foreground"
                  >
                    {c.name}
                    {c.issuer ? <span className="text-xs text-muted-foreground">({c.issuer})</span> : null}
                    {c.year ? <span className="text-xs text-indigo-600">{c.year}</span> : null}
                  </span>
                ))}
              </div>
            )}
          </section>

          {/* 어학 */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-semibold text-foreground">어학</p>
              {isEditing && (
                <button type="button" onClick={addLang} className="text-indigo-600 hover:text-indigo-700">
                  <Plus size={16} />
                </button>
              )}
            </div>
            {isEditing ? (
              <div className="space-y-2">
                {draft.languages.map((l, i) => (
                  <div key={i} className="flex flex-wrap gap-2 items-center">
                    <input
                      className="flex-1 min-w-[80px] px-3 py-2 border border-border rounded-md bg-card text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      value={l.language}
                      placeholder="언어 (예: 영어)"
                      onChange={(e) => setLang(i, { language: e.target.value })}
                    />
                    <input
                      className="flex-1 min-w-[80px] px-3 py-2 border border-border rounded-md bg-card text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      value={l.test}
                      placeholder="시험 (예: TOEIC)"
                      onChange={(e) => setLang(i, { test: e.target.value })}
                    />
                    <input
                      className="w-24 px-3 py-2 border border-border rounded-md bg-card text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      value={l.score}
                      placeholder="점수"
                      onChange={(e) => setLang(i, { score: e.target.value })}
                    />
                    <button
                      type="button"
                      onClick={() => removeLang(i)}
                      className="text-muted-foreground hover:text-red-600"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
                {!draft.languages.length && (
                  <p className="text-xs text-muted-foreground">+ 로 어학 성적을 추가하세요.</p>
                )}
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {view.languages.map((l, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-muted border border-border text-sm text-foreground"
                  >
                    {l.language}
                    {l.test ? <span className="text-xs text-muted-foreground">{l.test}</span> : null}
                    {l.score ? <span className="text-xs text-indigo-600">{l.score}</span> : null}
                  </span>
                ))}
              </div>
            )}
          </section>

          {/* 링크 */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-semibold text-foreground">링크</p>
              {isEditing && (
                <button type="button" onClick={addLink} className="text-indigo-600 hover:text-indigo-700">
                  <Plus size={16} />
                </button>
              )}
            </div>
            {isEditing ? (
              <div className="space-y-2">
                {draft.links.map((l, i) => (
                  <div key={i} className="flex gap-2 items-center">
                    <select
                      className="px-2 py-2 border border-border rounded-md bg-card text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      value={l.type}
                      onChange={(e) => setLink(i, { type: e.target.value })}
                    >
                      {LINK_TYPES.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                    <input
                      className={inputCls}
                      value={l.url}
                      placeholder="URL"
                      onChange={(e) => setLink(i, { url: e.target.value })}
                    />
                    <button
                      type="button"
                      onClick={() => removeLink(i)}
                      className="text-muted-foreground hover:text-red-600"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
                {!draft.links.length && (
                  <p className="text-xs text-muted-foreground">+ 로 링크를 추가하세요.</p>
                )}
              </div>
            ) : (
              <ul className="space-y-1">
                {view.links.map((l, i) => (
                  <li key={i} className="text-sm text-foreground">
                    <span className="text-xs text-muted-foreground mr-1">[{l.type}]</span>
                    <a
                      href={l.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-indigo-600 hover:underline break-all"
                    >
                      {l.url}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* 프로젝트 */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-semibold text-foreground">프로젝트</p>
              {isEditing && (
                <button type="button" onClick={addProject} className="text-indigo-600 hover:text-indigo-700">
                  <Plus size={16} />
                </button>
              )}
            </div>
            {isEditing ? (
              <div className="space-y-3">
                {draft.projects.map((p, i) => (
                  <div key={i} className="rounded-md border border-border p-3 space-y-2">
                    <div className="flex gap-2">
                      <input
                        className={inputCls}
                        value={p.title}
                        placeholder="프로젝트명"
                        onChange={(e) => setProject(i, { title: e.target.value })}
                      />
                      <input
                        className="w-28 px-3 py-2 border border-border rounded-md bg-card text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        value={p.period}
                        placeholder="기간"
                        onChange={(e) => setProject(i, { period: e.target.value })}
                      />
                      <button
                        type="button"
                        onClick={() => removeProject(i)}
                        className="text-muted-foreground hover:text-red-600"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                    <input
                      className={inputCls}
                      value={p.role}
                      placeholder="역할 (예: 백엔드 개발)"
                      onChange={(e) => setProject(i, { role: e.target.value })}
                    />
                    <input
                      className={inputCls}
                      value={p.description}
                      placeholder="설명"
                      onChange={(e) => setProject(i, { description: e.target.value })}
                    />
                    <input
                      className={inputCls}
                      value={p.tech_stack.join(", ")}
                      placeholder="기술 스택 (콤마로 구분: React, Python)"
                      onChange={(e) =>
                        setProject(i, {
                          tech_stack: e.target.value
                            .split(",")
                            .map((s) => s.trim())
                            .filter(Boolean),
                        })
                      }
                    />
                  </div>
                ))}
                {!draft.projects.length && (
                  <p className="text-xs text-muted-foreground">+ 로 프로젝트를 추가하세요.</p>
                )}
              </div>
            ) : (
              <ul className="space-y-2">
                {view.projects.map((p, i) => (
                  <li key={i} className="text-sm text-foreground">
                    <span className="font-medium">{p.title}</span>
                    {p.role ? <span className="text-muted-foreground"> · {p.role}</span> : null}
                    {p.period ? <span className="text-muted-foreground"> ({p.period})</span> : null}
                    {p.tech_stack.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {p.tech_stack.map((t, ti) => (
                          <span
                            key={ti}
                            className="px-1.5 py-0.5 rounded bg-muted text-xs text-muted-foreground"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* 요약 */}
          <section>
            <p className="text-sm font-semibold text-foreground mb-2">한 줄 요약</p>
            {isEditing ? (
              <textarea
                rows={3}
                className="w-full px-3 py-2 border border-border rounded-md bg-card text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                value={draft.summary}
                placeholder="예: 에너지·ESG 도메인 × AI 엔지니어링으로 진로를 탐색 중"
                onChange={(e) => setDraft((d) => ({ ...d, summary: e.target.value }))}
              />
            ) : (
              <p className="text-sm text-foreground">
                {view.summary || <span className="text-muted-foreground">요약이 없습니다.</span>}
              </p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
