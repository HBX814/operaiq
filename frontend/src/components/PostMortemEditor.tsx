"use client";

import React, { useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import { Save, CheckCircle2, Clock } from "lucide-react";

interface PostMortemSectionProps {
  title: string;
  initialContent: string;
  onSave: (content: string) => Promise<void>;
}

function PostMortemSection({ title, initialContent, onSave }: PostMortemSectionProps) {
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(true);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({
        placeholder: `Write ${title.toLowerCase()} here...`,
      }),
    ],
    content: initialContent,
    editorProps: {
      attributes: {
        class: "prose prose-invert prose-sm max-w-none focus:outline-none min-h-[100px]",
      },
    },
    onUpdate: () => {
      setSaved(false);
    },
  });

  const handleSave = async () => {
    if (!editor) return;
    setSaving(true);
    await onSave(editor.getHTML());
    setSaving(false);
    setSaved(true);
  };

  return (
    <div className="glass rounded-xl border mb-6 overflow-hidden">
      <div className="px-5 py-3 border-b border-white/5 flex items-center justify-between bg-white/2">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-gray-500 flex items-center gap-1">
            {saving ? (
              <>
                <Clock className="w-3 h-3 animate-pulse" /> Saving...
              </>
            ) : saved ? (
              <>
                <CheckCircle2 className="w-3 h-3 text-green-400" /> Saved
              </>
            ) : (
              "Unsaved changes"
            )}
          </span>
          <button
            onClick={handleSave}
            disabled={saved || saving}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-medium bg-indigo-600/20 text-indigo-300 border border-indigo-500/25 hover:bg-indigo-600/40 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Save className="w-3 h-3" />
            Save Section
          </button>
        </div>
      </div>
      <div className="p-5">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}

interface PostMortemEditorProps {
  postmortemId: string;
  document: {
    summary: string;
    timeline: string;
    root_cause: string;
    action_items: string;
    lessons_learned: string;
  };
}

export function PostMortemEditor({ postmortemId, document }: PostMortemEditorProps) {
  const handleSaveSection = async (section: string, content: string) => {
    try {
      const res = await fetch("/api/postmortems", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          postmortem_id: postmortemId,
          [section]: content
        })
      });
      if (!res.ok) throw new Error("Failed to save");
    } catch (error) {
      console.error(`Error saving ${section}:`, error);
      alert(`Failed to save ${section}`);
    }
  };

  return (
    <div className="space-y-2">
      <PostMortemSection
        title="Summary"
        initialContent={document.summary}
        onSave={(c) => handleSaveSection("summary", c)}
      />
      <PostMortemSection
        title="Timeline"
        initialContent={document.timeline}
        onSave={(c) => handleSaveSection("timeline", c)}
      />
      <PostMortemSection
        title="Root Cause"
        initialContent={document.root_cause}
        onSave={(c) => handleSaveSection("root_cause", c)}
      />
      <PostMortemSection
        title="Action Items"
        initialContent={document.action_items}
        onSave={(c) => handleSaveSection("action_items", c)}
      />
      <PostMortemSection
        title="Lessons Learned"
        initialContent={document.lessons_learned}
        onSave={(c) => handleSaveSection("lessons_learned", c)}
      />
    </div>
  );
}
