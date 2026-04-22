import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Shopping Reels Generator",
  description: "Reference-driven shopping reels with Supertone TTS",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <header className="border-b border-neutral-800 px-6 py-3 flex gap-6 items-center">
          <Link href="/" className="font-semibold">🎬 SRG</Link>
          <nav className="flex gap-4 text-sm text-neutral-400">
            <Link href="/sources" className="hover:text-white">소스 영상</Link>
            <Link href="/products" className="hover:text-white">상품</Link>
            <Link href="/projects" className="hover:text-white">프로젝트</Link>
          </nav>
        </header>
        <main className="max-w-6xl mx-auto p-6">{children}</main>
      </body>
    </html>
  );
}
