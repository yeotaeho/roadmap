"use client";

// 노트 탭 — 좌측 목록(검색·생성) + 우측 마크다운 에디터, 비로그인 목업 폴백

import { NotebookPen, Plus, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { NOTES_MOCK_DETAIL, NOTES_MOCK_LIST } from "@/data/plannerMock";
import {
  useCreateNote,
  useDeleteNote,
  useNote,
  useNotesList,
  useUpdateNote,
} from "@/hooks/useNotes";
import type { NoteDetail } from "@/lib/api/notes";
import { useStore } from "@/store";
import { NoteEditor } from "./NoteEditor";

export function NotesTab() {
  const profile = useStore((s) => s.profile);
  const enabled = !!profile?.id;

  const { data: liveList } = useNotesList(enabled);
  const list = enabled && liveList ? liveList : NOTES_MOCK_LIST;

  const [selectedId, setSelectedId] = useState<number | null>(list[0]?.id ?? null);
  const [query, setQuery] = useState("");

  const { data: liveDetail } = useNote(selectedId, enabled);
  const detail: NoteDetail | null = enabled
    ? liveDetail ?? null
    : selectedId != null
      ? NOTES_MOCK_DETAIL[selectedId] ?? null
      : null;

  const createNote = useCreateNote();
  const updateNote = useUpdateNote();
  const deleteNote = useDeleteNote();

  const filtered = useMemo(
    () =>
      query.trim()
        ? list.filter(
            (n) =>
              n.title.toLowerCase().includes(query.toLowerCase()) ||
              n.preview.toLowerCase().includes(query.toLowerCase()),
          )
        : list,
    [list, query],
  );

  const allTitles = useMemo(() => list.map((n) => n.title), [list]);

  const handleCreate = (title?: string) => {
    if (!enabled) {
      window.alert("로그인하면 노트를 만들 수 있습니다.");
      return;
    }
    const name = (title ?? window.prompt("새 노트 제목"))?.trim();
    if (!name) return;
    createNote.mutate(
      { title: name },
      {
        onSuccess: (n) => setSelectedId(n.id),
        onError: () => window.alert("같은 제목의 노트가 이미 있습니다."),
      },
    );
  };

  const openByTitle = (title: string) => {
    const found = list.find((n) => n.title === title);
    if (found) setSelectedId(found.id);
    else if (enabled && window.confirm(`"${title}" 노트가 없습니다. 새로 만들까요?`)) {
      handleCreate(title);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
      {/* 좌측 — 목록 */}
      <section className="flex flex-col rounded-2xl border border-slate-200 bg-[#F8FAFC] p-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <div className="flex items-center justify-between gap-2 px-1">
          <h2 className="inline-flex items-center gap-1.5 text-sm font-bold text-slate-900 dark:text-slate-100">
            <NotebookPen className="h-4 w-4 text-indigo-600" />
            노트
          </h2>
          <button
            type="button"
            onClick={() => handleCreate()}
            className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-2 py-1.5 text-[11px] font-semibold text-white hover:bg-indigo-700"
          >
            <Plus className="h-3 w-3" />
            새 노트
          </button>
        </div>
        <div className="relative mt-2">
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="검색"
            className="w-full rounded-xl border border-slate-200 bg-white py-1.5 pl-8 pr-3 text-xs text-slate-900 focus:border-indigo-300 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
          />
        </div>
        {!enabled ? (
          <span className="mt-2 self-start rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
            예시 데이터
          </span>
        ) : null}
        <div className="mt-2 flex-1 space-y-1 overflow-y-auto">
          {filtered.map((n) => (
            <div key={n.id} className="group relative">
              <button
                type="button"
                onClick={() => setSelectedId(n.id)}
                className={`w-full rounded-xl border px-3 py-2 text-left transition ${
                  selectedId === n.id
                    ? "border-indigo-200 bg-white shadow-sm dark:border-indigo-800 dark:bg-slate-800"
                    : "border-transparent hover:bg-white/70 dark:hover:bg-slate-800/60"
                }`}
              >
                <p className="text-xs font-semibold text-slate-900 dark:text-slate-100">{n.title}</p>
                <p className="mt-0.5 line-clamp-1 text-[11px] text-slate-500 dark:text-slate-500">
                  {n.preview || "빈 노트"}
                </p>
              </button>
              {enabled ? (
                <button
                  type="button"
                  onClick={() => {
                    if (window.confirm(`"${n.title}" 노트를 삭제할까요?`)) {
                      deleteNote.mutate(n.id, {
                        onSuccess: () => {
                          if (selectedId === n.id) setSelectedId(null);
                        },
                      });
                    }
                  }}
                  className="absolute right-2 top-2 hidden rounded-md p-1 text-slate-300 hover:text-rose-500 group-hover:block"
                  aria-label="노트 삭제"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              ) : null}
            </div>
          ))}
          {filtered.length === 0 ? (
            <p className="p-4 text-center text-[11px] text-slate-400">노트가 없습니다.</p>
          ) : null}
        </div>
      </section>

      {/* 우측 — 에디터 */}
      <section className="min-h-[480px] rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        {detail ? (
          <NoteEditor
            key={detail.id}
            detail={detail}
            allTitles={allTitles}
            readOnly={!enabled}
            saving={updateNote.isPending}
            onSave={({ title, content }) =>
              updateNote.mutate(
                { id: detail.id, payload: { title, content } },
                { onError: () => window.alert("저장 실패 — 같은 제목의 노트가 있는지 확인하세요.") },
              )
            }
            onOpenByTitle={openByTitle}
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-slate-400">좌측에서 노트를 선택하거나 새로 만드세요.</p>
          </div>
        )}
      </section>
    </div>
  );
}
