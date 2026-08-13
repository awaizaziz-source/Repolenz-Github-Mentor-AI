"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CheckCircle2, Copy } from "lucide-react";

function CodeBlock({ language, children }: { language?: string; children: string }) {
  const [copied, setCopied] = useState(false);
  const copy = useCallback(() => {
    navigator.clipboard.writeText(children);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [children]);
  return (
    <div className="group relative my-3 overflow-hidden rounded-xl bg-slate-950">
      {language && (
        <div className="flex items-center justify-between border-b border-slate-800/60 px-4 py-1.5">
          <span className="text-xs font-medium text-slate-500">{language}</span>
          <button
            onClick={copy}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-slate-500 opacity-0 transition hover:text-white group-hover:opacity-100"
          >
            {copied ? <CheckCircle2 className="size-3.5 text-emerald-400" /> : <Copy className="size-3.5" />}
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
      )}
      <pre className="custom-scroll overflow-x-auto p-4">
        <code className="text-sm leading-6 text-slate-300">{children}</code>
      </pre>
    </div>
  );
}

function MermaidBlock({ code }: { code: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !code.trim()) return;
    import("mermaid").then(({ default: mermaid }) => {
      mermaid.initialize({ startOnLoad: false, theme: "dark", securityLevel: "loose" });
      const id = `mermaid-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      mermaid.render(id, code).then(({ svg }) => {
        if (ref.current) ref.current.innerHTML = svg;
      });
    }).catch(() => {});
  }, [code]);

  return <div ref={ref} className="my-4 overflow-x-auto rounded-xl border border-slate-800 bg-slate-950 p-4" />;
}

export function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div className="prose-ai">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className ?? "");
            const isInline = !match && !className;
            if (isInline) {
              return (
                <code className={className} {...props}>
                  {children}
                </code>
              );
            }
            const lang = match?.[1];
            const text = String(children).replace(/\n$/, "");
            if (lang === "mermaid") {
              return <MermaidBlock code={text} />;
            }
            return <CodeBlock language={lang}>{text}</CodeBlock>;
          },
          pre({ children }) {
            return <>{children}</>;
          },
          a({ href, children }) {
            return (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
