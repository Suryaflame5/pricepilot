"use client";

import type { ReactNode } from "react";
import type { ChatStep } from "@/lib/types";
import ToolActivity from "./ToolActivity";

export function renderReply(reply: string): ReactNode[] {
  const blocks = reply.split(/\n{2,}/);
  return blocks.map((block, i) => {
    const trimmed = block.trim();
    if (!trimmed) return null;
    if (trimmed.startsWith("- ")) {
      return (
        <ul key={i} className="my-1 list-disc pl-5">
          {trimmed.split("\n").map((line, j) => (
            <li key={j}>{renderInline(line.replace(/^- /, ""))}</li>
          ))}
        </ul>
      );
    }
    return (
      <p key={i} className="my-1">
        {renderInline(trimmed)}
      </p>
    );
  });
}

export function renderInline(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? (
      <strong key={i}>{part.slice(2, -2)}</strong>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

interface Props {
  content: string;
  steps?: ChatStep[];
  busy?: boolean;
  busyLabel?: string | null;
}

/** One assistant message: narrated answer + the tool trail that produced it. */
export default function AIMessage({ content, steps, busy, busyLabel }: Props) {
  return (
    <div className="max-w-[92%] rounded-lg rounded-tl-none bg-slate-100 px-3 py-2 text-sm text-slate-800">
      {renderReply(content)}
      {(steps && steps.length > 0) || busy ? (
        <div className="mt-2 border-t border-slate-200/70 pt-2">
          <ToolActivity steps={steps ?? []} busy={busy} busyLabel={busyLabel} />
        </div>
      ) : null}
    </div>
  );
}