import React, { useState } from "react";
import { Wrench, ChevronDown, ChevronRight, CheckCircle2, XCircle } from "lucide-react";


interface ToolCallCardProps {
  toolName: string;
  input?: Record<string, unknown>;
  output?: unknown;
  status?: "pending" | "success" | "error";
}

export function ToolCallCard({ toolName, input, output, status = "pending" }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-white/10 bg-black/40 overflow-hidden my-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-2">
          {status === "pending" && <Wrench className="w-3.5 h-3.5 text-amber-400" />}
          {status === "success" && <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />}
          {status === "error" && <XCircle className="w-3.5 h-3.5 text-red-400" />}
          <span className="text-[11px] font-mono text-gray-300">{toolName}</span>
        </div>
        {expanded ? (
          <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-gray-500" />
        )}
      </button>
      
      {expanded && (
        <div className="p-3 border-t border-white/10 text-[10px] font-mono text-gray-400 space-y-3 bg-black/60">
          {input && (
            <div>
              <div className="text-gray-500 mb-1 font-sans font-medium text-[9px] uppercase tracking-wider">Input</div>
              <pre className="whitespace-pre-wrap overflow-x-auto text-indigo-300/80">
                {JSON.stringify(input, null, 2)}
              </pre>
            </div>
          )}
          {output !== undefined && (
            <div>
              <div className="text-gray-500 mb-1 font-sans font-medium text-[9px] uppercase tracking-wider">Result</div>
              <pre className="whitespace-pre-wrap overflow-x-auto text-green-300/80">
                {typeof output === "string" ? output : JSON.stringify(output, null, 2)}
              </pre>
            </div>
          )}
          {!input && !output && <div className="text-gray-600 italic">No parameters or output available</div>}
        </div>
      )}
    </div>
  );
}
