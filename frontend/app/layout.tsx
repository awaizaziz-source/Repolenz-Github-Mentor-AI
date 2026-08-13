import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RepoLens — GitHub Repository Analyzer",
  description: "Explore and analyze any public GitHub repository with architecture mapping, dependency visualization, file tree inspection, and live activity feeds.",
  keywords: "GitHub, repository analyzer, codebase analysis, architecture map, developer tools",
  openGraph: {
    title: "RepoLens — GitHub Repository Analyzer",
    description: "Instant repository analysis and codebase exploration.",
    type: "website",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className="grid-pattern">{children}</body>
    </html>
  );
}
