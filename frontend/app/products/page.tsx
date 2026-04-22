"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher, type Product } from "@/lib/api";

type Form = {
  name: string;
  brand: string;
  price: string;
  description: string;
  features: string;
  target_audience: string;
  cta_url: string;
};

const EMPTY: Form = {
  name: "",
  brand: "",
  price: "",
  description: "",
  features: "",
  target_audience: "",
  cta_url: "",
};

export default function ProductsPage() {
  const { data, mutate } = useSWR<Product[]>("/api/products", fetcher);
  const [f, setF] = useState<Form>(EMPTY);
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api("/api/products", {
        method: "POST",
        body: JSON.stringify({
          name: f.name,
          brand: f.brand || null,
          price: f.price || null,
          description: f.description || null,
          features: f.features.split(";").map((s) => s.trim()).filter(Boolean),
          target_audience: f.target_audience || null,
          cta_url: f.cta_url || null,
        }),
      });
      setF(EMPTY);
      mutate();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">상품</h1>

      <form onSubmit={submit} className="grid grid-cols-2 gap-3 rounded border border-neutral-800 p-4">
        <Input label="상품명*" value={f.name} onChange={(v) => setF({ ...f, name: v })} required />
        <Input label="브랜드" value={f.brand} onChange={(v) => setF({ ...f, brand: v })} />
        <Input label="가격" value={f.price} onChange={(v) => setF({ ...f, price: v })} />
        <Input label="타겟" value={f.target_audience} onChange={(v) => setF({ ...f, target_audience: v })} />
        <Input label="CTA URL" value={f.cta_url} onChange={(v) => setF({ ...f, cta_url: v })} full />
        <Input label="설명" value={f.description} onChange={(v) => setF({ ...f, description: v })} full />
        <Input
          label="핵심 특징 (세미콜론 구분)"
          value={f.features}
          onChange={(v) => setF({ ...f, features: v })}
          full
        />
        <div className="col-span-2 flex justify-end">
          <button disabled={submitting} className="rounded bg-blue-600 px-4 py-2 font-medium disabled:opacity-50">
            {submitting ? "…" : "추가"}
          </button>
        </div>
      </form>

      <div className="space-y-2">
        {data?.map((p) => (
          <div key={p.id} className="rounded border border-neutral-800 p-3">
            <div className="font-semibold">{p.name}</div>
            <div className="text-sm text-neutral-400">{p.brand} · {p.price}</div>
            {p.features_json.length > 0 && (
              <ul className="mt-1 list-disc pl-5 text-sm text-neutral-500">
                {p.features_json.map((x, i) => <li key={i}>{x}</li>)}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function Input({
  label, value, onChange, required, full,
}: { label: string; value: string; onChange: (v: string) => void; required?: boolean; full?: boolean }) {
  return (
    <label className={`block ${full ? "col-span-2" : ""}`}>
      <span className="block text-xs text-neutral-400 mb-1">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        className="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2"
      />
    </label>
  );
}
