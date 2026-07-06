"use client";

// 노트 에디터 — 편집(textarea)/미리보기(react-markdown) 토글, [[자동완성]], 백링크

import { Eye, Link2, PencilLine, Save } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import type { NoteDetail } from "@/lib/api/notes";

/** [[제목]] → 마크다운 링크(#note=제목)로 전처리 — 미리보기 클릭 이동용 */
function preprocessWikiLinks(content: string): string {
  return content.replace(/\[\[([^\[\]]+?)\]\]/g, (_, t: string) => {
    const title = t.trim();
    return `[${title}](#note=${encodeURIComponent(title)})`;
  });
}

export function NoteEditor({
  detail,
  allTitles,
  readOnly,
  saving,
  onSave,
  onOpenByTitle,
}: {
  detail: NoteDetail;
  allTitles: string[];
  readOnly: boolean;
  saving: boolean;
  onSave: (v: { title: string; content: string }) => void;
  onOpenByTitle: (title: string) => void;
}) {
  const [mode, setMode] = useState<"edit" | "preview">("preview");
  const [title, setTitle] = useState(detail.title);
  const [content, setContent] = useState(detail.content);
  const [autocomplete, setAutocomplete] = useState<{ query: string; at: number } | null>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  // 다른 노트 선택 시 로컬 상태 리셋 — key 리마운트와 이중 안전망. 저장 성공(detail.content 갱신)에는 반응하지 않아 편집 중 입력·모드를 보존한다.
  useEffect(() => {
    setTitle(detail.title);
    setContent(detail.content);
    setAutocomplete(null);
    setMode("preview");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail.id]);

  const dirty = title !== detail.title || content !== detail.content;
  const existingTitles = useMemo(() => new Set(allTitles), [allTitles]);

  const suggestions = useMemo(() => {
    if (!autocomplete) return [];
    const q = autocomplete.query.toLowerCase();
    return allTitles
      .filter((t) => t !== detail.title && t.toLowerCase().includes(q))
      .slice(0, 6);
  }, [autocomplete, allTitles, detail.title]);

  const handleContentChange = (value: string, cursor: number) => {
    setContent(value);
    // 커서 앞에서 가장 가까운 "[[" 이후, "]]" 가 아직 닫히지 않았으면 자동완성
    const before = value.slice(0, cursor);
    const open = before.lastIndexOf("[[");
    if (open >= 0 && before.indexOf("]]", open) === -1) {
      setAutocomplete({ query: before.slice(open + 2), at: open });
    } else {
      setAutocomplete(null);
    }
  };

  const acceptSuggestion = (t: string) => {
    if (!autocomplete) return;
    const cursor = taRef.current?.selectionStart ?? content.length;
    const next = `${content.slice(0, autocomplete.at)}[[${t}]]${content.slice(cursor)}`;
    setContent(next);
    setAutocomplete(null);
    taRef.current?.focus();
  };

  const save = () => {
    if (!readOnly && dirty && title.trim()) onSave({ title: title.trim(), content });
  };

  return (
    <div
      className="flex h-full flex-col"
      onKeyDown={(e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === "s") {
          e.preventDefault();
          save();
        }
      }}
    >
      <div className="flex items-center gap-2">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          disabled={readOnly}
          className="w-full rounded-xl border border-transparent bg-transparent px-2 py-1.5 text-lg font-bold text-slate-900 focus:border-indigo-300 focus:outline-none dark:text-slate-100"
          placeholder="노트 제목"
        />
        <div className="flex shrink-0 rounded-xl border border-slate-200 p-0.5 dark:border-slate-700">
          <button
            type="button"
            onClick={() => setMode("edit")}
            disabled={readOnly}
            className={`rounded-lg p-1.5 ${mode === "edit" ? "bg-indigo-600 text-white" : "text-slate-500"}`}
            aria-label="편집"
          >
            <PencilLine className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setMode("preview")}
            className={`rounded-lg p-1.5 ${mode === "preview" ? "bg-indigo-600 text-white" : "text-slate-500"}`}
            aria-label="미리보기"
          >
            <Eye className="h-3.5 w-3.5" />
          </button>
        </div>
        {!readOnly ? (
          <button
            type="button"
            onClick={save}
            disabled={!dirty || saving}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-indigo-600 px-3 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
          >
            <Save className="h-3.5 w-3.5" />
            {saving ? "저장 중…" : "저장"}
          </button>
        ) : null}
      </div>

      <div className="relative mt-3 flex-1">
        {mode === "edit" && !readOnly ? (
          <>
            <textarea
              ref={taRef}
              value={content}
              onChange={(e) => handleContentChange(e.target.value, e.target.selectionStart)}
              rows={18}
              className="h-full min-h-[360px] w-full resize-y rounded-2xl border border-slate-200 bg-white p-4 font-mono text-sm leading-relaxed text-slate-900 focus:border-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              placeholder={"마크다운으로 기록하세요. [[다른 노트]] 로 연결할 수 있습니다."}
            />
            {suggestions.length > 0 ? (
              <div className="absolute left-4 top-16 z-10 w-64 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-800">
                {suggestions.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => acceptSuggestion(t)}
                    className="block w-full px-3 py-2 text-left text-xs text-slate-800 hover:bg-indigo-50 dark:text-slate-200 dark:hover:bg-slate-700"
                  >
                    [[{t}]]
                  </button>
                ))}
              </div>
            ) : null}
          </>
        ) : (
          <div className="prose prose-sm prose-slate min-h-[360px] max-w-none rounded-2xl border border-slate-200 bg-white p-5 dark:prose-invert dark:border-slate-700 dark:bg-slate-800">
            <ReactMarkdown
              components={{
                a: ({ href, children }) => {
                  if (href?.startsWith("#note=")) {
                    const t = decodeURIComponent(href.slice(6));
                    const exists = existingTitles.has(t);
                    return (
                      <a
                        href={href}
                        onClick={(e) => {
                          e.preventDefault();
                          onOpenByTitle(t);
                        }}
                        className={
                          exists
                            ? "font-semibold text-indigo-600 no-underline hover:underline dark:text-indigo-400"
                            : "border-b border-dashed border-slate-400 font-semibold text-slate-500 no-underline"
                        }
                        title={exists ? t : `"${t}" — 아직 없는 노트`}
                      >
                        {children}
                      </a>
                    );
                  }
                  return (
                    <a href={href} target="_blank" rel="noreferrer">
                      {children}
                    </a>
                  );
                },
              }}
            >
              {preprocessWikiLinks(content) || "*빈 노트입니다.*"}
            </ReactMarkdown>
          </div>
        )}
      </div>

      {detail.questKey || detail.taskId != null ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {detail.questKey ? (
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600 dark:bg-slate-700 dark:text-slate-300">
              🗺 퀘스트 연결 — {detail.questKey}
            </span>
          ) : null}
          {detail.taskId != null ? (
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600 dark:bg-slate-700 dark:text-slate-300">
              📋 태스크 #{detail.taskId} 연결
            </span>
          ) : null}
        </div>
      ) : null}

      {detail.backlinks.length > 0 ? (
        <div className="mt-4 rounded-2xl border border-slate-200 bg-[#F8FAFC] p-4 dark:border-slate-700 dark:bg-slate-900">
          <p className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-700 dark:text-slate-300">
            <Link2 className="h-3.5 w-3.5 text-indigo-500" />
            이 노트를 언급한 노트 {detail.backlinks.length}개
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {detail.backlinks.map((b) => (
              <button
                key={b.id}
                type="button"
                onClick={() => onOpenByTitle(b.title)}
                className="rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-800 hover:bg-indigo-100 dark:border-indigo-900/40 dark:bg-indigo-900/20 dark:text-indigo-300"
              >
                {b.title}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
