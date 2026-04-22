export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${text}`);
  }
  return res.json();
}

export const fetcher = <T,>(path: string) => api<T>(path);

export type SourceVideo = {
  id: number;
  platform: string;
  url: string;
  caption: string | null;
  local_path: string | null;
  duration_sec: number | null;
  width: number | null;
  height: number | null;
  view_count: number | null;
  like_count: number | null;
  posted_at: string | null;
  status: string;
  error: string | null;
};

export type Product = {
  id: number;
  name: string;
  brand: string | null;
  price: string | null;
  description: string | null;
  features_json: string[];
  images_json: string[];
  cta_url: string | null;
  target_audience: string | null;
};

export type ScriptSegment = {
  index: number;
  role: string;
  text: string;
  duration_hint_ms: number;
  broll_query: string[];
  overlay: Record<string, unknown> | null;
  emphasis_words: string[];
};

export type Script = {
  id: number;
  project_id: number;
  version: number;
  segments_json: ScriptSegment[];
  voice_id: string | null;
  total_chars: number;
  estimated_cost: number;
  created_by: string;
};

export type Project = {
  id: number;
  name: string;
  product_id: number | null;
  target_duration_sec: number;
  reference_video_ids_json: number[];
  tone: string;
  must_include_json: string[];
  avoid_json: string[];
  status: string;
};
