"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher, type SourceVideo } from "@/lib/api";

export default function SourcesPage() {
  const { data, mutate, isLoading } = useSWR<SourceVideo[]>("/api/sources", fetcher, {
    refreshInterval: 3000,
  });
  const [url, setUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api("/api/sources", {
        method: "POST",
        body: JSON.stringify({ url: url.trim(), run_analysis: true }),
      });
      setUrl("");
      mutate();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">소스 영상</h1>

      <form onSubmit={submit} className="flex gap-2">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Instagram Reel / TikTok URL 붙여넣기"
          className="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-2"
          required
        />
        <button
          disabled={submitting}
          className="rounded bg-blue-600 px-4 py-2 font-medium disabled:opacity-50"
        >
          {submitting ? "…" : "추가"}
        </button>
      </form>
      {error && <p className="text-red-400 text-sm">{error}</p>}

      <div className="space-y-2">
        {isLoading && <p className="text-neutral-500">로딩…</p>}
        {data?.map((v) => (
          <div
            key={v.id}
            className="rounded border border-neutral-800 p-3 flex items-center gap-3"
          >
            <span className="rounded bg-neutral-800 px-2 py-0.5 text-xs">{v.platform}</span>
            <span className="flex-1 truncate">{v.caption || v.url}</span>
            <span className="text-xs text-neutral-500">{v.duration_sec?.toFixed(1)}s</span>
            <StatusBadge status={v.status} />
          </div>
        ))}
        {data && data.length === 0 && (
          <p className="text-neutral-500">아직 추가한 영상이 없습니다.</p>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: "bg-neutral-700",
    downloaded: "bg-blue-700",
    ingested: "bg-indigo-700",
    analyzed: "bg-green-700",
    failed: "bg-red-700",
  };
  return (
    <span className={`rounded px-2 py-0.5 text-xs ${colors[status] || "bg-neutral-700"}`}>
      {status}
    </span>
  );
}
