"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  ArrowRight, CheckCircle2, ChevronRight, Code2, ExternalLink, FileCode2, FileText, Folder, GitBranch,
  GitCommit, GitFork, GitPullRequest, Github, Globe, Layers, LoaderCircle, MessageSquare, Package, RefreshCw, Search, Sparkles, Star, X, Zap,
} from "lucide-react";
import { MarkdownRenderer } from "@/components/markdown-renderer";
import { showToast, ToastContainer } from "@/components/toast";

type Repository = {
  id: string; owner: string; name: string; full_name: string; html_url: string; description: string | null;
  owner_avatar_url: string | null; stars_count: number; forks_count: number; primary_language: string | null;
  languages: Record<string, number>; default_branch: string; size_kb: number; import_status: string; imported_at: string;
};

type Architecture = {
  framework: string[]; languages: Record<string, number>; dependencies: Record<string, string[]>;
  structure: string[]; important_files: string[]; summary: string;
};

type FileContent = { repository_id: string; path: string; content: string; language: string | null };

type Activity = {
  commits: { sha: string; message: string; author: string; date: string; url: string }[];
  issues: { number: number; title: string; state: string; author: string; comments: number; url: string; created_at: string }[];
  pull_requests: { number: number; title: string; state: string; author: string; url: string; created_at: string }[];
};

type Tab = "overview" | "architecture" | "readme" | "activity";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

const LANGUAGE_COLORS: Record<string, string> = {
  TypeScript: "#3178c6", JavaScript: "#f7df1e", Python: "#3572A5", Go: "#00ADD8", Rust: "#dea584",
  Java: "#b07219", "C#": "#178600", Ruby: "#701516", PHP: "#4F5D95", Swift: "#F05138", Kotlin: "#A97BFF",
  Vue: "#41b883", HTML: "#e34c26", CSS: "#563d7c", SCSS: "#c6538c", Svelte: "#ff3e00",
};

const FILE_ICONS: Record<string, string> = {
  ts: "🟦", tsx: "⚛️", js: "🟨", jsx: "⚛️", py: "🐍", go: "🔷", rs: "🦀", java: "☕", md: "📝",
  json: "📋", yml: "⚙️", yaml: "⚙️", html: "🌐", css: "🎨", sql: "🗄️", sh: "💻",
};

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "overview", label: "Overview", icon: FileText },
  { id: "architecture", label: "Architecture", icon: Layers },
  { id: "readme", label: "README", icon: Globe },
  { id: "activity", label: "Activity", icon: GitCommit },
];

const DEMO_REPOS = [
  { url: "https://github.com/tiangolo/fastapi", label: "FastAPI", desc: "Python API framework" },
  { url: "https://github.com/vercel/next.js", label: "Next.js", desc: "React framework" },
  { url: "https://github.com/pallets/flask", label: "Flask", desc: "Lightweight Python web" },
];

const fmt = (n: number) => new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(n);

function parseApiError(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object") return fallback;
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((i) => (typeof i === "object" && i && "msg" in i ? String(i.msg) : String(i))).join(". ");
  return fallback;
}

function LanguageBar({ languages }: { languages: Record<string, number> }) {
  const total = Object.values(languages).reduce((a, b) => a + b, 0);
  const sorted = Object.entries(languages).sort(([, a], [, b]) => b - a).slice(0, 6);
  if (!total) return null;
  return (
    <div className="space-y-2">
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-slate-800">
        {sorted.map(([lang, bytes]) => (
          <div key={lang} className="h-full transition-all" style={{ width: `${((bytes / total) * 100).toFixed(1)}%`, backgroundColor: LANGUAGE_COLORS[lang] ?? "#6366f1" }} />
        ))}
      </div>
      <div className="flex flex-wrap gap-3">
        {sorted.map(([lang, bytes]) => (
          <div key={lang} className="flex items-center gap-1.5 text-xs text-slate-400">
            <span className="size-2.5 rounded-full" style={{ backgroundColor: LANGUAGE_COLORS[lang] ?? "#6366f1" }} />
            {lang} <span className="text-slate-500">{((bytes / total) * 100).toFixed(0)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function CodeFileIcon({ filename }: { filename: string }) {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  return <span className="mr-1.5">{FILE_ICONS[ext] ?? "📄"}</span>;
}

function timeAgo(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

export default function Home() {
  const [url, setUrl] = useState("");
  const [repo, setRepo] = useState<Repository | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  const [architecture, setArchitecture] = useState<Architecture | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const [repoFiles, setRepoFiles] = useState<string[]>([]);
  const [fileSearch, setFileSearch] = useState("");

  const [fileContent, setFileContent] = useState<FileContent | null>(null);
  const [isLoadingFile, setIsLoadingFile] = useState(false);

  const [readmeContent, setReadmeContent] = useState<string | null>(null);
  const [isLoadingReadme, setIsLoadingReadme] = useState(false);

  const [activity, setActivity] = useState<Activity | null>(null);
  const [isLoadingActivity, setIsLoadingActivity] = useState(false);

  const loadRepoFiles = useCallback(async (repoId: string) => {
    try {
      const res = await fetch(`${API}/repositories/${repoId}/files`);
      const data = await res.json();
      if (res.ok) setRepoFiles(data.files ?? []);
    } catch { /* silent */ }
  }, []);

  useEffect(() => { if (repo?.id) loadRepoFiles(repo.id); }, [repo?.id, loadRepoFiles]);

  async function importRepository(e: FormEvent<HTMLFormElement>, overrideUrl?: string) {
    e.preventDefault();
    const targetUrl = overrideUrl ?? url;
    if (!targetUrl.trim()) return;
    setError(null);
    setIsImporting(true);
    try {
      const res = await fetch(`${API}/repositories/import`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repository_url: targetUrl }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(parseApiError(data, "Could not import this repository."));
      setUrl(targetUrl); setRepo(data); setActiveTab("overview");
      setArchitecture(null); setRepoFiles([]); setReadmeContent(null); setActivity(null);
      showToast(`Imported ${data.full_name}`, "success");
      loadRepoFiles(data.id);
      setTimeout(() => document.getElementById("workspace")?.scrollIntoView({ behavior: "smooth" }), 100);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not import this repository.";
      setError(msg); showToast(msg, "error");
    } finally { setIsImporting(false); }
  }

  function importDemoRepo(demoUrl: string) {
    setUrl(demoUrl);
    void importRepository({ preventDefault: () => {} } as FormEvent<HTMLFormElement>, demoUrl);
  }

  async function analyzeArchitecture() {
    if (!repo) return;
    setError(null); setIsAnalyzing(true);
    try {
      const res = await fetch(`${API}/repositories/${repo.id}/architecture`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(parseApiError(data, "Architecture analysis failed."));
      setArchitecture(data); showToast("Architecture analysis complete", "success");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Architecture analysis failed.";
      setError(msg); showToast(msg, "error");
    } finally { setIsAnalyzing(false); }
  }

  async function loadFileContent(path: string) {
    if (!repo) return;
    setError(null); setIsLoadingFile(true); setFileContent(null);
    try {
      const res = await fetch(`${API}/repositories/${repo.id}/content?path=${encodeURIComponent(path)}`);
      const data = await res.json();
      if (!res.ok) throw new Error(parseApiError(data, "Could not read file."));
      setFileContent(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not read file.";
      setError(msg); showToast(msg, "error");
    } finally { setIsLoadingFile(false); }
  }

  async function loadReadme() {
    if (!repo) return;
    setError(null); setIsLoadingReadme(true);
    try {
      const res = await fetch(`${API}/repositories/${repo.id}/readme`);
      const data = await res.json();
      if (!res.ok) throw new Error(parseApiError(data, "Could not load README."));
      setReadmeContent(data.content);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not load README.";
      setError(msg); showToast(msg, "error");
    } finally { setIsLoadingReadme(false); }
  }

  async function loadActivity() {
    if (!repo) return;
    setError(null); setIsLoadingActivity(true);
    try {
      const res = await fetch(`${API}/repositories/${repo.id}/activity`);
      const data = await res.json();
      if (!res.ok) throw new Error(parseApiError(data, "Could not load activity."));
      setActivity(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not load activity.";
      setError(msg); showToast(msg, "error");
    } finally { setIsLoadingActivity(false); }
  }

  useEffect(() => {
    if (activeTab === "readme" && repo && readmeContent === null && !isLoadingReadme) loadReadme();
  }, [activeTab, repo?.id]);

  useEffect(() => {
    if (activeTab === "activity" && repo && activity === null && !isLoadingActivity) loadActivity();
  }, [activeTab, repo?.id]);

  return (
    <main className="min-h-screen">
      <ToastContainer />
      <nav className="sticky top-0 z-50 border-b border-slate-800/50 bg-[#080b14]/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg shadow-indigo-500/30">
                <Sparkles className="size-4.5 text-white" />
              </div>
              <div className="absolute -inset-0.5 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 opacity-20 blur" />
            </div>
            <span className="text-base font-semibold tracking-tight text-white">RepoLens</span>
          </div>
          <div className="flex items-center gap-3">
            <a href="https://github.com" target="_blank" rel="noreferrer"
              className="flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:border-slate-700 hover:text-white">
              <Github className="size-3.5" /><span>GitHub</span>
            </a>
          </div>
        </div>
      </nav>

      {!repo && (
        <section className="relative overflow-hidden px-6 pb-20 pt-24 text-center lg:px-8">
          <div className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="absolute -top-40 left-1/2 size-[600px] -translate-x-1/2 rounded-full bg-indigo-600/10 blur-3xl" />
            <div className="absolute top-20 right-1/4 size-[300px] rounded-full bg-purple-600/8 blur-3xl" />
          </div>
          <div className="relative">
            <h1 className="mx-auto max-w-4xl text-5xl font-bold tracking-tight text-white sm:text-6xl lg:text-7xl">
              Understand any GitHub repo in <span className="gradient-text">seconds</span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-slate-400">
              Paste a public repository URL to instantly see metadata, language breakdown, architecture map, source files, README, and recent activity — no configuration needed.
            </p>
            <form onSubmit={importRepository} className="mx-auto mt-10 flex max-w-3xl flex-col gap-3 sm:flex-row">
              <div className="relative flex-1">
                <Github className="absolute left-4 top-1/2 size-4 -translate-y-1/2 text-slate-500" />
                <input required value={url} onChange={(e) => setUrl(e.target.value)} type="url" placeholder="https://github.com/owner/repository"
                  className="h-12 w-full rounded-xl bg-slate-900/80 pl-11 pr-4 text-sm text-white outline-none ring-1 ring-slate-700 placeholder:text-slate-500 focus:ring-indigo-500 transition backdrop-blur" />
              </div>
              <button type="submit" disabled={isImporting}
                className="flex h-12 shrink-0 items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-6 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition hover:from-indigo-500 hover:to-purple-500 disabled:opacity-60">
                {isImporting ? <><LoaderCircle className="size-4 animate-spin" /> Importing…</> : <>Analyze Repository <ArrowRight className="size-4" /></>}
              </button>
            </form>
            {error && <div className="mx-auto mt-4 max-w-3xl rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}
            <div className="mx-auto mt-8 max-w-3xl">
              <p className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-500">Try a demo repository</p>
              <div className="flex flex-wrap justify-center gap-2">
                {DEMO_REPOS.map((demo) => (
                  <button key={demo.url} type="button" disabled={isImporting} onClick={() => importDemoRepo(demo.url)}
                    className="flex items-center gap-2 rounded-xl border border-slate-700/80 bg-slate-900/60 px-4 py-2.5 text-left transition hover:border-indigo-500/50 hover:bg-indigo-500/10 disabled:opacity-50">
                    <Github className="size-4 shrink-0 text-indigo-400" />
                    <span><span className="block text-sm font-medium text-white">{demo.label}</span><span className="block text-xs text-slate-500">{demo.desc}</span></span>
                  </button>
                ))}
              </div>
            </div>
            <div className="mt-16 grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-left">
              {[
                { icon: Layers, title: "Architecture Map", desc: "Framework detection, dependency graph, folder hierarchy, key files.", gradient: "from-purple-500 to-pink-500" },
                { icon: Code2, title: "Source File Viewer", desc: "Click any file to view its contents with syntax-aware display.", gradient: "from-blue-500 to-cyan-500" },
                { icon: Globe, title: "README Viewer", desc: "Rendered documentation for every repository.", gradient: "from-emerald-500 to-teal-500" },
                { icon: GitCommit, title: "Live Activity Feed", desc: "Recent commits, open issues, and pull requests from GitHub.", gradient: "from-amber-500 to-orange-500" },
              ].map(({ icon: Icon, title, desc, gradient }) => (
                <article key={title} className="surface group p-6 transition-all duration-300 hover:border-slate-700">
                  <div className={`inline-flex size-10 items-center justify-center rounded-xl bg-gradient-to-br ${gradient} shadow-lg`}><Icon className="size-5 text-white" /></div>
                  <h2 className="mt-4 font-semibold text-white">{title}</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-400">{desc}</p>
                </article>
              ))}
            </div>
          </div>
        </section>
      )}

      {repo && (
        <div id="workspace" className="mx-auto max-w-7xl px-6 pb-20 pt-8 lg:px-8">
          <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center">
            <form onSubmit={importRepository} className="flex flex-1 gap-2">
              <div className="relative flex-1">
                <Github className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" />
                <input value={url} onChange={(e) => setUrl(e.target.value)} type="url" placeholder="Analyze a different repository…"
                  className="h-10 w-full rounded-xl bg-slate-900/60 pl-10 pr-3 text-sm text-white outline-none ring-1 ring-slate-700 placeholder:text-slate-500 focus:ring-indigo-500" />
              </div>
              <button type="submit" disabled={isImporting}
                className="flex h-10 items-center gap-2 rounded-xl bg-indigo-600 px-4 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-60 transition">
                {isImporting ? <LoaderCircle className="size-4 animate-spin" /> : <RefreshCw className="size-4" />} {isImporting ? "…" : "Analyze"}
              </button>
            </form>
          </div>
          {error && <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

          <div className="surface mb-6 overflow-hidden">
            <div className="flex flex-col gap-5 border-b border-slate-800/60 p-6 sm:flex-row sm:items-start">
              <div className="flex items-start gap-4 flex-1">
                {repo.owner_avatar_url
                  ? <img src={repo.owner_avatar_url} alt="" className="size-14 rounded-2xl ring-2 ring-slate-700" />
                  : <div className="size-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600" />}
                <div className="flex-1 min-w-0">
                  <a href={repo.html_url} target="_blank" rel="noreferrer"
                    className="flex items-center gap-2 text-xl font-bold text-white hover:text-indigo-300 transition">
                    <Github className="size-5 shrink-0" /><span className="truncate">{repo.full_name}</span><ExternalLink className="size-4 shrink-0 opacity-50" />
                  </a>
                  <p className="mt-1.5 text-sm leading-6 text-slate-400 line-clamp-2">{repo.description || "No description provided."}</p>
                  <div className="mt-3 flex flex-wrap gap-4 text-sm">
                    <span className="flex items-center gap-1.5 text-amber-300"><Star className="size-4" />{fmt(repo.stars_count)} stars</span>
                    <span className="flex items-center gap-1.5 text-slate-400"><GitFork className="size-4" />{fmt(repo.forks_count)} forks</span>
                    <span className="flex items-center gap-1.5 text-slate-400"><GitBranch className="size-4" />{repo.default_branch}</span>
                    {repo.primary_language && <span className="flex items-center gap-1.5 text-slate-400"><div className="size-2.5 rounded-full" style={{ backgroundColor: LANGUAGE_COLORS[repo.primary_language] ?? "#6366f1" }} />{repo.primary_language}</span>}
                    <span className="flex items-center gap-1.5 text-slate-400"><Package className="size-4" />{repo.size_kb.toLocaleString()} KB</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 self-start">
                <CheckCircle2 className="size-4 text-emerald-400" /><span className="text-sm font-medium text-emerald-300">Ready</span>
              </div>
            </div>
            {Object.keys(repo.languages).length > 0 && <div className="px-6 py-4"><LanguageBar languages={repo.languages} /></div>}
          </div>

          <div className="mb-6 flex overflow-x-auto">
            <div className="flex gap-1 rounded-2xl border border-slate-800/50 bg-slate-900/50 p-1 backdrop-blur">
              {TABS.map(({ id, label, icon: Icon }) => (
                <button key={id} onClick={() => setActiveTab(id)}
                  className={`flex shrink-0 items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition-all ${activeTab === id ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-500/20" : "text-slate-400 hover:bg-slate-800 hover:text-white"}`}>
                  <Icon className="size-4" />{label}
                </button>
              ))}
            </div>
          </div>

          <div className="tab-content">
            {activeTab === "overview" && (
              <div className="grid gap-5 lg:grid-cols-2">
                <div className="card p-5">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Repository Profile</p>
                  <dl className="mt-4 space-y-3">
                    {[
                      { label: "Owner", value: repo.owner }, { label: "Default branch", value: repo.default_branch },
                      { label: "Primary language", value: repo.primary_language ?? "Not detected" },
                      { label: "Repository size", value: `${repo.size_kb.toLocaleString()} KB` },
                      { label: "Import status", value: repo.import_status },
                    ].map(({ label, value }) => (
                      <div key={label} className="flex items-center justify-between gap-3 text-sm">
                        <dt className="text-slate-500">{label}</dt>
                        <dd className="text-right text-slate-200 font-medium">{value}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
                <div className="card p-5">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Quick Actions</p>
                  <div className="mt-4 space-y-2.5">
                    {[
                      { tab: "architecture" as Tab, icon: Layers, label: "View Architecture", desc: "Frameworks, deps & structure" },
                      { tab: "readme" as Tab, icon: Globe, label: "View README", desc: "Repository documentation" },
                      { tab: "activity" as Tab, icon: GitCommit, label: "View Activity", desc: "Commits, issues & PRs" },
                    ].map(({ tab, icon: Icon, label, desc }) => (
                      <button key={tab} onClick={() => setActiveTab(tab)}
                        className="flex w-full items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/50 px-4 py-3 text-left transition hover:border-indigo-500/40 hover:bg-indigo-500/5">
                        <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-indigo-500/20"><Icon className="size-4 text-indigo-400" /></div>
                        <div className="min-w-0"><p className="text-sm font-medium text-white">{label}</p><p className="text-xs text-slate-500">{desc}</p></div>
                        <ChevronRight className="ml-auto size-4 shrink-0 text-slate-600" />
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {activeTab === "architecture" && (
              <div className="space-y-5">
                {!architecture && !isAnalyzing && (
                  <div className="surface flex flex-col items-center gap-5 p-12 text-center">
                    <div className="grid size-16 place-items-center rounded-2xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 ring-1 ring-inset ring-indigo-500/20"><Layers className="size-8 text-indigo-400" /></div>
                    <div><h3 className="text-lg font-semibold text-white">Architecture Intelligence</h3><p className="mt-2 max-w-md text-sm text-slate-400">Generate a source-grounded map of framework detection, dependency graph, critical files, and folder hierarchy.</p></div>
                    <button onClick={analyzeArchitecture}
                      className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 hover:from-indigo-500 hover:to-purple-500 transition">
                      <Sparkles className="size-4" /> Generate Architecture Map</button>
                  </div>
                )}
                {isAnalyzing && (
                  <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
                    <div className="relative"><div className="size-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 p-3 shadow-lg shadow-indigo-500/30"><Sparkles className="size-8 text-white" /></div><div className="absolute -inset-1 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 opacity-20 blur-lg animate-pulse" /></div>
                    <p className="font-semibold text-white">Mapping repository architecture…</p>
                  </div>
                )}
                {architecture && (
                  <>
                    <div className="surface p-6">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2"><Sparkles className="size-4 text-indigo-400" /><h3 className="font-semibold text-white">Architecture Summary</h3></div>
                        <button onClick={analyzeArchitecture} disabled={isAnalyzing}
                          className="flex items-center gap-1.5 rounded-lg border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-400 hover:border-slate-600 hover:text-white transition disabled:opacity-50">
                          <RefreshCw className="size-3.5" /> Refresh</button>
                      </div>
                      <p className="mt-3 leading-7 text-slate-300">{architecture.summary}</p>
                    </div>
                    <div className="grid gap-5 lg:grid-cols-3">
                      <div className="card p-5">
                        <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500"><Zap className="size-3.5" /> Frameworks</p>
                        <div className="mt-4 flex flex-wrap gap-2">
                          {architecture.framework.length > 0 ? architecture.framework.map((fw) => (
                            <span key={fw} className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-sm font-medium text-indigo-300">{fw}</span>
                          )) : <p className="text-sm text-slate-500">None detected</p>}
                        </div>
                        {Object.entries(architecture.dependencies).map(([group, deps]) => (
                          <div key={group} className="mt-5">
                            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">{group} ({deps.length})</p>
                            <div className="flex max-h-32 flex-wrap gap-1 overflow-y-auto custom-scroll">
                              {deps.slice(0, 30).map((dep) => <span key={dep} className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">{dep}</span>)}
                            </div>
                          </div>
                        ))}
                      </div>
                      <div className="card p-5">
                        <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500"><FileCode2 className="size-3.5" /> Key Files</p>
                        <div className="mt-4 max-h-80 space-y-1 overflow-y-auto custom-scroll">
                          {architecture.important_files.length > 0 ? architecture.important_files.map((file) => (
                            <button key={file} onClick={() => { loadFileContent(file); }}
                              className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm transition hover:bg-slate-800">
                              <FileCode2 className="size-3.5 shrink-0 text-indigo-400" /><span className="truncate font-mono text-xs text-indigo-300 hover:text-white">{file}</span>
                              <Code2 className="ml-auto size-3.5 shrink-0 text-slate-600" />
                            </button>
                          )) : <p className="text-sm text-slate-500">No key files detected.</p>}
                        </div>
                      </div>
                      <div className="card p-5">
                        <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500"><Folder className="size-3.5" /> Structure</p>
                        <pre className="mt-4 max-h-72 overflow-auto custom-scroll whitespace-pre font-mono text-xs leading-5 text-slate-400">{architecture.structure.join("\n")}</pre>
                      </div>
                    </div>
                    {repoFiles.length > 0 && (
                      <div className="card p-5">
                        <div className="flex items-center justify-between">
                          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500"><Code2 className="size-3.5" /> Source Files ({repoFiles.length})</p>
                          <div className="relative w-60">
                            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" />
                            <input value={fileSearch} onChange={(e) => setFileSearch(e.target.value)} placeholder="Search files…"
                              className="h-9 w-full rounded-lg bg-slate-950 pl-9 pr-3 text-xs text-white outline-none ring-1 ring-slate-700 placeholder:text-slate-500 focus:ring-indigo-500" />
                          </div>
                        </div>
                        <div className="mt-4 max-h-80 space-y-0.5 overflow-y-auto custom-scroll">
                          {repoFiles.filter((f) => !fileSearch || f.toLowerCase().includes(fileSearch.toLowerCase())).slice(0, 100).map((file) => (
                            <button key={file} onClick={() => loadFileContent(file)}
                              className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs transition hover:bg-slate-800">
                              <CodeFileIcon filename={file} />
                              <span className="truncate font-mono text-slate-400 hover:text-indigo-300">{file}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {activeTab === "readme" && (
              <div className="surface overflow-hidden">
                <div className="flex items-center gap-3 border-b border-slate-800/60 px-6 py-4">
                  <div className="grid size-8 place-items-center rounded-xl bg-emerald-500/20"><Globe className="size-4 text-emerald-400" /></div>
                  <div><h3 className="font-semibold text-white">README</h3><p className="text-xs text-slate-500">{repo.full_name}</p></div>
                  {readmeContent && <button onClick={loadReadme} disabled={isLoadingReadme}
                    className="ml-auto flex items-center gap-1.5 rounded-lg border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white transition disabled:opacity-50">
                    <RefreshCw className="size-3.5" /> Refresh</button>}
                </div>
                <div className="p-6">
                  {isLoadingReadme ? (
                    <div className="flex items-center justify-center py-16"><LoaderCircle className="size-8 animate-spin text-slate-500" /></div>
                  ) : readmeContent ? (
                    <MarkdownRenderer content={readmeContent} />
                  ) : (
                    <div className="flex flex-col items-center py-16 text-center">
                      <Globe className="size-12 text-slate-700" />
                      <p className="mt-4 text-slate-500">README not available. It may not exist or the import may need to be refreshed.</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === "activity" && (
              <div className="space-y-5">
                {isLoadingActivity ? (
                  <div className="flex items-center justify-center py-16"><LoaderCircle className="size-8 animate-spin text-slate-500" /></div>
                ) : activity ? (
                  <>
                    <div className="surface p-6">
                      <div className="flex items-center justify-between mb-5">
                        <div className="flex items-center gap-2"><GitCommit className="size-4 text-indigo-400" /><h3 className="font-semibold text-white">Recent Commits</h3></div>
                        <button onClick={loadActivity} disabled={isLoadingActivity}
                          className="flex items-center gap-1.5 rounded-lg border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white transition disabled:opacity-50">
                          <RefreshCw className="size-3.5" /> Refresh</button>
                      </div>
                      <div className="space-y-2">
                        {activity.commits.length === 0 && <p className="text-sm text-slate-500">No commits found.</p>}
                        {activity.commits.map((c, i) => (
                          <a key={i} href={c.url} target="_blank" rel="noreferrer"
                            className="flex items-start gap-3 rounded-xl border border-slate-800 bg-slate-950/50 px-4 py-3 transition hover:border-slate-700">
                            <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-indigo-500/20 mt-0.5"><GitCommit className="size-4 text-indigo-400" /></div>
                            <div className="min-w-0 flex-1"><p className="text-sm font-medium text-white truncate">{c.message}</p><p className="text-xs text-slate-500 mt-0.5"><span className="text-indigo-400">{c.sha}</span> · {c.author} · {timeAgo(c.date)}</p></div>
                            <ExternalLink className="size-3.5 shrink-0 text-slate-600 mt-1" />
                          </a>
                        ))}
                      </div>
                    </div>
                    <div className="grid gap-5 lg:grid-cols-2">
                      <div className="card p-5">
                        <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500 mb-4"><MessageSquare className="size-3.5" /> Open Issues ({activity.issues.length})</p>
                        <div className="space-y-2 max-h-80 overflow-y-auto custom-scroll">
                          {activity.issues.length === 0 && <p className="text-sm text-slate-500">No open issues.</p>}
                          {activity.issues.map((issue) => (
                            <a key={issue.number} href={issue.url} target="_blank" rel="noreferrer"
                              className="flex items-start gap-3 rounded-xl border border-slate-800 bg-slate-950/50 px-4 py-3 transition hover:border-slate-700">
                              <div className="grid size-7 shrink-0 place-items-center rounded-lg bg-green-500/20 mt-0.5"><MessageSquare className="size-3.5 text-green-400" /></div>
                              <div className="min-w-0 flex-1"><p className="text-sm text-white truncate">#{issue.number} {issue.title}</p><p className="text-xs text-slate-500 mt-0.5">{issue.author} · {issue.comments} comments · {timeAgo(issue.created_at)}</p></div>
                            </a>
                          ))}
                        </div>
                      </div>
                      <div className="card p-5">
                        <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500 mb-4"><GitPullRequest className="size-3.5" /> Open Pull Requests ({activity.pull_requests.length})</p>
                        <div className="space-y-2 max-h-80 overflow-y-auto custom-scroll">
                          {activity.pull_requests.length === 0 && <p className="text-sm text-slate-500">No open pull requests.</p>}
                          {activity.pull_requests.map((pr) => (
                            <a key={pr.number} href={pr.url} target="_blank" rel="noreferrer"
                              className="flex items-start gap-3 rounded-xl border border-slate-800 bg-slate-950/50 px-4 py-3 transition hover:border-slate-700">
                              <div className="grid size-7 shrink-0 place-items-center rounded-lg bg-purple-500/20 mt-0.5"><GitPullRequest className="size-3.5 text-purple-400" /></div>
                              <div className="min-w-0 flex-1"><p className="text-sm text-white truncate">#{pr.number} {pr.title}</p><p className="text-xs text-slate-500 mt-0.5">{pr.author} · {timeAgo(pr.created_at)}</p></div>
                            </a>
                          ))}
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="surface flex flex-col items-center gap-5 p-12 text-center">
                    <div className="grid size-16 place-items-center rounded-2xl bg-gradient-to-br from-amber-500/20 to-orange-500/20 ring-1 ring-inset ring-amber-500/20"><GitCommit className="size-8 text-amber-400" /></div>
                    <div><h3 className="text-lg font-semibold text-white">Repository Activity</h3><p className="mt-2 max-w-md text-sm text-slate-400">View recent commits, open issues, and pull requests fetched live from the GitHub API.</p></div>
                    <button onClick={loadActivity}
                      className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-600 to-orange-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-amber-500/20 hover:from-amber-500 hover:to-orange-500 transition">
                      <RefreshCw className="size-4" /> Load Activity</button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {fileContent && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-12 pb-8 px-4 bg-black/60 backdrop-blur-sm" onClick={() => setFileContent(null)}>
          <div className="w-full max-w-5xl max-h-[85vh] rounded-2xl border border-slate-700/50 bg-slate-950 shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-slate-800/60 px-5 py-3 bg-slate-900/50">
              <div className="flex items-center gap-2 min-w-0">
                <CodeFileIcon filename={fileContent.path} />
                <span className="truncate font-mono text-sm text-white">{fileContent.path}</span>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => { navigator.clipboard.writeText(fileContent.content); showToast("Copied to clipboard", "success"); }}
                  className="rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white transition">Copy</button>
                <button onClick={() => setFileContent(null)}
                  className="rounded-lg bg-slate-800 p-1.5 text-slate-400 hover:text-white transition"><X className="size-4" /></button>
              </div>
            </div>
            <div className="overflow-auto max-h-[calc(85vh-56px)] custom-scroll">
              <pre className="p-5 text-sm leading-6 font-mono text-slate-200 whitespace-pre">
                <code>{fileContent.content}</code>
              </pre>
            </div>
          </div>
        </div>
      )}

      <footer className="border-t border-slate-800/50 py-8">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <div className="flex items-center gap-2">
              <div className="grid size-7 place-items-center rounded-lg bg-indigo-600"><Layers className="size-3.5 text-white" /></div>
              <span className="text-sm font-semibold text-white">RepoLens</span>
              <span className="text-slate-600">·</span>
              <span className="text-xs text-slate-400">GitHub Repository Analyzer</span>
            </div>
            <p className="text-xs text-slate-500">Next.js 15 · FastAPI · SQLite · GitHub API</p>
          </div>
        </div>
      </footer>
    </main>
  );
}
