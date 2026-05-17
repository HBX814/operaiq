import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "OperaIQ — Production Intelligence Platform",
  description:
    "AI-powered production operations platform. Real-time incident triage, automated rollbacks, and intelligent post-mortems.",
  keywords: ["SRE", "incident management", "production operations", "AI", "post-mortem"],
  openGraph: {
    title: "OperaIQ",
    description: "Production-grade AI operations intelligence",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body suppressHydrationWarning className={`${inter.variable} font-sans antialiased bg-[#0a0a0f] text-gray-100 min-h-screen`}>
        {children}
      </body>
    </html>
  );
}
