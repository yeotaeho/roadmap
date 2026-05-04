import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { QueryProvider } from "@/lib/react-query";
import { AuthInitializer } from "@/components/AuthInitializer";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "청년 인사이트 | Global Pulse",
  description: "세상의 흐름과 개인의 성장을 연결하는 인사이트 플랫폼",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var t = localStorage.getItem('yi-theme');
                  if (!t) return;
                  document.documentElement.classList.toggle('dark', t === 'dark');
                } catch (e) {}
              })();
            `,
          }}
        />
        <QueryProvider>
          <AuthInitializer />
          {children}
        </QueryProvider>
      </body>
    </html>
  );
}
