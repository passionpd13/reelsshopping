import Link from "next/link";

export default function Home() {
  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <h1 className="text-2xl font-bold">Shopping Reels Generator</h1>
        <p className="text-neutral-400">
          참고 릴스를 분석해서, Supertone TTS와 자막이 들어간 새 쇼핑 릴스를 반자동으로 만듭니다.
        </p>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card href="/sources" title="① 소스 영상" desc="URL을 붙여넣어 다운로드·분석" />
        <Card href="/products" title="② 상품 등록" desc="팔 상품 정보 입력" />
        <Card href="/projects" title="③ 릴스 프로젝트" desc="대본 생성 → 편집 → 렌더" />
      </section>

      <section className="text-sm text-neutral-500">
        빠른 E2E 검증이 필요하면 CLI 스파이크:
        <pre className="mt-2 rounded bg-neutral-900 p-3 overflow-x-auto">
{`cd backend && python -m app.cli.main spike \\
  --url "https://www.tiktok.com/@xxx/video/123" \\
  --product-name "상품명" --duration 30`}
        </pre>
      </section>
    </div>
  );
}

function Card({ href, title, desc }: { href: string; title: string; desc: string }) {
  return (
    <Link
      href={href}
      className="block rounded-lg border border-neutral-800 p-4 hover:border-neutral-600 transition"
    >
      <div className="font-semibold">{title}</div>
      <div className="text-sm text-neutral-400 mt-1">{desc}</div>
    </Link>
  );
}
