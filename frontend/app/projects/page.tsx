"use client";

import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { api, fetcher, type Product, type Project, type SourceVideo } from "@/lib/api";

export default function ProjectsPage() {
  const { data: projects, mutate } = useSWR<Project[]>("/api/projects", fetcher);
  const { data: products } = useSWR<Product[]>("/api/products", fetcher);
  const { data: sources } = useSWR<SourceVideo[]>("/api/sources", fetcher);

  const [name, setName] = useState("");
  const [productId, setProductId] = useState<number | "">("");
  const [duration, setDuration] = useState(30);
  const [refs, setRefs] = useState<number[]>([]);
  const [tone, setTone] = useState("energetic");
  const [submitting, setSubmitting] = useState(false);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api("/api/projects", {
        method: "POST",
        body: JSON.stringify({
          name,
          product_id: productId || null,
          target_duration_sec: duration,
          reference_video_ids: refs,
          tone,
          must_include: [],
          avoid: [],
        }),
      });
      setName("");
      setRefs([]);
      mutate();
    } finally {
      setSubmitting(false);
    }
  }

  const analyzed = (sources || []).filter((s) => s.status === "analyzed");

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">프로젝트</h1>

      <form onSubmit={create} className="space-y-3 rounded border border-neutral-800 p-4">
        <div className="grid grid-cols-3 gap-3">
          <input
            placeholder="프로젝트 이름*"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="rounded border border-neutral-700 bg-neutral-900 px-3 py-2"
          />
          <select
            value={productId}
            onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : "")}
            className="rounded border border-neutral-700 bg-neutral-900 px-3 py-2"
          >
            <option value="">상품 선택…</option>
            {products?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <div className="flex gap-2">
            <input
              type="number"
              min={10}
              max={120}
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="w-24 rounded border border-neutral-700 bg-neutral-900 px-3 py-2"
            />
            <select
              value={tone}
              onChange={(e) => setTone(e.target.value)}
              className="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-2"
            >
              <option value="energetic">energetic</option>
              <option value="calm">calm</option>
              <option value="informative">informative</option>
              <option value="humorous">humorous</option>
              <option value="aspirational">aspirational</option>
            </select>
          </div>
        </div>

        <div>
          <div className="text-xs text-neutral-400 mb-1">참고 릴스 (분석 완료된 것만)</div>
          <div className="grid grid-cols-2 gap-1 max-h-48 overflow-auto">
            {analyzed.map((s) => (
              <label key={s.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={refs.includes(s.id)}
                  onChange={(e) =>
                    setRefs((prev) =>
                      e.target.checked ? [...prev, s.id] : prev.filter((id) => id !== s.id)
                    )
                  }
                />
                <span className="truncate">{s.caption || s.url}</span>
              </label>
            ))}
            {analyzed.length === 0 && <p className="text-neutral-500 text-sm">분석 완료된 소스가 없습니다.</p>}
          </div>
        </div>

        <div className="flex justify-end">
          <button disabled={submitting || !name} className="rounded bg-blue-600 px-4 py-2 font-medium disabled:opacity-50">
            {submitting ? "…" : "프로젝트 생성"}
          </button>
        </div>
      </form>

      <div className="space-y-2">
        {projects?.map((p) => (
          <Link
            key={p.id}
            href={`/projects/${p.id}/script`}
            className="block rounded border border-neutral-800 p-3 hover:border-neutral-600"
          >
            <div className="flex items-center gap-2">
              <span className="font-semibold">{p.name}</span>
              <span className="rounded bg-neutral-800 px-2 py-0.5 text-xs">{p.status}</span>
              <span className="text-xs text-neutral-500">{p.target_duration_sec}s · {p.tone}</span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
