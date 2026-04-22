"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export default function RenderPage({ params }: { params: { id: string } }) {
  const projectId = Number(params.id);
  const [scriptId, setScriptId] = useState("");
  const [voiceId, setVoiceId] = useState("");
  const [bgm, setBgm] = useState("");
  const [result, setResult] = useState<{ id: number; output_path: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const r = await api<{ id: number; output_path: string }>(
        `/api/projects/${projectId}/render`,
        {
          method: "POST",
          body: JSON.stringify({
            script_id: Number(scriptId),
            voice_id: voiceId,
            bgm_path: bgm || null,
          }),
        }
      );
      setResult(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">프로젝트 #{projectId} · 렌더</h1>
      <form onSubmit={submit} className="space-y-3 rounded border border-neutral-800 p-4">
        <label className="block">
          <span className="text-xs text-neutral-400">Script ID*</span>
          <input
            type="number"
            value={scriptId}
            onChange={(e) => setScriptId(e.target.value)}
            required
            className="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2"
          />
        </label>
        <label className="block">
          <span className="text-xs text-neutral-400">Supertone voice_id*</span>
          <input
            value={voiceId}
            onChange={(e) => setVoiceId(e.target.value)}
            required
            className="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2"
          />
        </label>
        <label className="block">
          <span className="text-xs text-neutral-400">BGM 파일 경로 (선택)</span>
          <input
            value={bgm}
            onChange={(e) => setBgm(e.target.value)}
            placeholder="/path/to/bgm.mp3"
            className="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2"
          />
        </label>
        <button disabled={submitting} className="rounded bg-blue-600 px-4 py-2 disabled:opacity-50">
          {submitting ? "제출 중…" : "렌더 시작"}
        </button>
      </form>
      {error && <p className="text-red-400 text-sm">{error}</p>}
      {result && (
        <div className="rounded border border-neutral-800 p-3">
          <p>렌더 작업 #{result.id} 시작됨 — 완료 시 {result.output_path} 에 저장됩니다.</p>
        </div>
      )}
    </div>
  );
}
