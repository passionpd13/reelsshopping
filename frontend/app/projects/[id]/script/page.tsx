"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher, type Script, type ScriptSegment } from "@/lib/api";

export default function ScriptEditorPage({ params }: { params: { id: string } }) {
  const projectId = Number(params.id);
  const [script, setScript] = useState<Script | null>(null);
  const [generating, setGenerating] = useState(false);
  const [revising, setRevising] = useState(false);
  const [instruction, setInstruction] = useState("");

  async function generate() {
    setGenerating(true);
    try {
      const s = await api<Script>(`/api/projects/${projectId}/generate-script`, { method: "POST" });
      setScript(s);
    } finally {
      setGenerating(false);
    }
  }

  async function applyEdit() {
    if (!script) return;
    const updated = await api<Script>(`/api/scripts/${script.id}`, {
      method: "PATCH",
      body: JSON.stringify(script.segments_json),
    });
    setScript(updated);
  }

  async function aiRevise() {
    if (!script || !instruction.trim()) return;
    setRevising(true);
    try {
      const updated = await api<Script>(`/api/scripts/${script.id}/revise`, {
        method: "POST",
        body: JSON.stringify({ instruction }),
      });
      setScript(updated);
      setInstruction("");
    } finally {
      setRevising(false);
    }
  }

  function updateSegment(i: number, patch: Partial<ScriptSegment>) {
    if (!script) return;
    setScript({
      ...script,
      segments_json: script.segments_json.map((seg, idx) => (idx === i ? { ...seg, ...patch } : seg)),
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">프로젝트 #{projectId} · 대본 편집</h1>
        <button
          onClick={generate}
          disabled={generating}
          className="rounded bg-blue-600 px-4 py-2 font-medium disabled:opacity-50"
        >
          {generating ? "생성 중…" : script ? "재생성" : "대본 생성"}
        </button>
      </div>

      {script && (
        <>
          <div className="text-sm text-neutral-400">
            v{script.version} · {script.total_chars}자 · {script.created_by}
          </div>
          <div className="space-y-3">
            {script.segments_json.map((seg, i) => (
              <div key={i} className="rounded border border-neutral-800 p-3">
                <div className="flex items-center gap-2 mb-2 text-xs text-neutral-400">
                  <span className="rounded bg-neutral-800 px-2 py-0.5">{seg.role}</span>
                  <span>{seg.duration_hint_ms} ms</span>
                  <span>{seg.text.length}자</span>
                </div>
                <textarea
                  value={seg.text}
                  onChange={(e) => updateSegment(i, { text: e.target.value })}
                  className="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-base"
                  rows={2}
                />
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <button onClick={applyEdit} className="rounded bg-green-700 px-4 py-2">수동 수정 저장</button>
          </div>

          <div className="rounded border border-neutral-800 p-3 space-y-2">
            <div className="text-sm text-neutral-400">Claude에게 수정 지시</div>
            <div className="flex gap-2">
              <input
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder="예: 후킹을 더 강하게, 가격 언급 제거"
                className="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-2"
              />
              <button
                onClick={aiRevise}
                disabled={revising || !instruction}
                className="rounded bg-purple-700 px-4 py-2 disabled:opacity-50"
              >
                {revising ? "…" : "AI 수정"}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
