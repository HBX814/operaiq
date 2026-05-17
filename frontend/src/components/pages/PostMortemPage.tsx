"use client";

import { useState, useEffect } from "react";
import { FileText, Plus, Star, Calendar, ChevronRight, Bot } from "lucide-react";
import { cn, formatRelativeTime } from "@/lib/utils";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import { CONFIG } from "@/lib/config";

interface PostMortem {
  id: string;
  incident_title: string;
  service: string;
  created_at: string;
  quality_score: number;
  status: "draft" | "review" | "published";
  content?: string;
}



function QualityBadge({ score }: { score: number | null }) {
  if (score === null || score === undefined) {
    return (
      <div className="flex items-center gap-1 px-2 py-0.5 rounded-full border border-white/10 text-gray-500 text-[10px] font-semibold">
        <Star className="w-2.5 h-2.5" />
        —/100
      </div>
    );
  }

  const color = score >= 80 ? "text-green-400 bg-green-400/10 border-green-400/20"
    : score >= 60 ? "text-amber-400 bg-amber-400/10 border-amber-400/20"
    : "text-red-400 bg-red-400/10 border-red-400/20";

  return (
    <div className={cn("flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-semibold", color)}>
      <Star className="w-2.5 h-2.5" />
      {score}/100
    </div>
  );
}

function StatusBadge({ status }: { status: PostMortem["status"] | string }) {
  const styles: Record<string, string> = {
    draft: "text-gray-400 bg-gray-400/10 border-gray-400/20",
    review: "text-amber-400 bg-amber-400/10 border-amber-400/20",
    published: "text-green-400 bg-green-400/10 border-green-400/20",
  };
  const currentStatus = status || "draft";
  return (
    <span className={cn("px-2 py-0.5 rounded-full border text-[10px] font-medium capitalize", styles[currentStatus] || styles.draft)}>
      {currentStatus}
    </span>
  );
}

export function PostMortemPage() {
  const [postmortems, setPostmortems] = useState<PostMortem[]>([]);
  const [selected, setSelected] = useState<PostMortem | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPostMortems = async () => {
    try {
      const res = await fetch("/api/postmortems");
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setPostmortems(data);
        }
      }
    } catch (error) {
      console.error("Failed to fetch postmortems:", error);
    }
  };

  useEffect(() => {
    fetchPostMortems();
  }, []);

  // Initialize Tiptap editor
  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({
        placeholder: "Start writing the post-mortem...",
      }),
    ],
    content: "",
    editorProps: {
      attributes: {
        class: "prose prose-invert prose-sm max-w-none focus:outline-none min-h-[400px]",
      },
    },
  });

  const handleSelect = (pm: PostMortem) => {
    setSelected(pm);
    if (editor) {
      editor.commands.setContent(pm.content || `
<h2>Summary</h2>
<p>The ${pm.service} service experienced an incident on ${new Date(pm.created_at).toLocaleDateString()}.</p>
<h2>Timeline</h2>
<ul>
  <li>14:17 UTC - Deployment initiated</li>
  <li>14:32 UTC - Error rate spiked</li>
  <li>14:55 UTC - Service restored</li>
</ul>
<h2>Root Cause</h2>
<p>Configuration error in deployment.</p>
<h2>Action Items</h2>
<p>1. Add validation to CI pipeline.</p>
<h2>Lessons Learned</h2>
<p>Staging environment needs better parity.</p>
      `);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      // Get the most recent open incident
      const incRes = await fetch("/api/incidents?status=open&limit=1");
      const incidents = await incRes.json();
      const incidentId = 
        incidents[0]?.id || 
        incidents[0]?.incident_id || 
        "smoke-test-001";

      const res = await fetch(`${CONFIG.AGENTS_URL}/postmortem`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ incident_id: incidentId }),
      });

      if (!res.ok) {
        throw new Error(`Post-mortem generation failed: ${res.status}`);
      }

      // Refresh the list
      await fetchPostMortems();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="flex flex-col lg:flex-row h-full">
      {/* List */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-5 border-b border-white/5">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-white">Post-Mortem Center</h1>
              <p className="text-xs text-gray-500 mt-1">{postmortems.length} documents</p>
            </div>
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-indigo-600/25 hover:bg-indigo-600/35 text-indigo-300 border border-indigo-500/30 transition-all disabled:opacity-50"
            >
              {generating ? (
                <>
                  <Bot className="w-4 h-4 animate-pulse" />
                  Generating...
                </>
              ) : (
                <>
                  <Plus className="w-4 h-4" />
                  Generate with AI
                </>
              )}
            </button>
          </div>

          {error && (
            <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-center justify-between">
              <span>{error}</span>
              <button onClick={() => setError(null)} className="hover:text-red-300">✕</button>
            </div>
          )}

          {/* Stats row */}
          <div className="mt-4 grid grid-cols-3 gap-3">
            {[
              { label: "Avg Quality Score", value: "79/100", color: "text-green-400" },
              { label: "Published", value: "3", color: "text-indigo-400" },
              { label: "Pending Review", value: "1", color: "text-amber-400" },
            ].map(({ label, value, color }) => (
              <div key={label} className="glass rounded-lg px-3 py-2.5 border">
                <p className={cn("text-lg font-bold", color)}>{value}</p>
                <p className="text-[10px] text-gray-500 mt-0.5">{label}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Document list */}
        <div className="flex-1 overflow-y-auto">
          {postmortems.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500 space-y-2">
              <FileText className="w-8 h-8 opacity-20" />
              <p className="text-sm">No post-mortems found</p>
            </div>
          ) : (
            postmortems.map((pm) => (
              <div
                key={pm.id}
                onClick={() => handleSelect(pm)}
                className={cn(
                  "px-6 py-4 border-b border-white/4 cursor-pointer transition-all flex items-start gap-4",
                  selected?.id === pm.id
                    ? "bg-indigo-600/10 border-l-2 border-l-indigo-500"
                    : "hover:bg-white/2"
                )}
              >
                <div className="w-9 h-9 rounded-lg glass border flex items-center justify-center flex-shrink-0">
                  <FileText className="w-4 h-4 text-indigo-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-200 truncate mb-1.5">{pm.incident_title || "Untitled Post-Mortem"}</p>
                  <div className="flex items-center gap-2 flex-wrap">
                    <StatusBadge status={pm.status} />
                    <QualityBadge score={pm.quality_score} />
                    <span className="text-[10px] text-gray-500 font-mono">{pm.service || "unknown"}</span>
                    <span className="text-[10px] text-gray-600 flex items-center gap-1">
                      <Calendar className="w-2.5 h-2.5" />
                      {pm.created_at ? formatRelativeTime(pm.created_at) : "Unknown date"}
                    </span>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-gray-600 flex-shrink-0 mt-1" />
              </div>
            ))
          )}
        </div>
      </div>

      {/* Detail panel */}
      {selected && (
        <div className="w-full lg:w-[420px] flex-shrink-0 lg:border-l border-t lg:border-t-0 border-white/5 overflow-y-auto">
          <div className="p-6 space-y-5">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <StatusBadge status={selected.status} />
                <QualityBadge score={selected.quality_score} />
              </div>
              <h2 className="text-base font-bold text-white">{selected.incident_title}</h2>
              <p className="text-xs text-gray-500 mt-1">
                {selected.service} · {new Date(selected.created_at).toLocaleDateString()}
              </p>
            </div>

            {/* Document editor (Tiptap) */}
            <div className="glass rounded-lg p-4 border border-white/10 mt-4">
              <EditorContent editor={editor} />
            </div>

            {/* Quality breakdown */}
            <div>
              <h3 className="text-xs font-semibold text-gray-300 mb-3">Quality Score Breakdown</h3>
              <div className="space-y-2">
                {[
                  { section: "Summary", score: 20, max: 20 },
                  { section: "Timeline completeness", score: 15, max: 20 },
                  { section: "Root cause depth", score: 20, max: 20 },
                  { section: "Action items", score: 17, max: 20 },
                  { section: "Lessons learned", score: 10, max: 20 },
                ].map(({ section, score, max }) => (
                  <div key={section} className="flex items-center gap-3">
                    <span className="text-[10px] text-gray-500 w-36 flex-shrink-0">{section}</span>
                    <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-indigo-500 rounded-full"
                        style={{ width: `${(score / max) * 100}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-gray-400 w-10 text-right">{score}/{max}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex gap-2">
              <button className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium bg-indigo-600/25 hover:bg-indigo-600/35 text-indigo-300 border border-indigo-500/30 transition-all">
                Publish
              </button>
              <button className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium glass border hover:border-white/15 text-gray-400 hover:text-gray-200 transition-all">
                Export PDF
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
