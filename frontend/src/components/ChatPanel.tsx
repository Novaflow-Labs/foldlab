// Chat-first assistant: streams text into bubbles, applies viewer directives,
// resumes job polling on onJob, surfaces errors inline, and exposes a few
// explicit quick-action buttons as robust fallbacks.
import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { streamChat } from "../api/chat";
import { useChatStore } from "../state/useChatStore";
import { useJobsStore } from "../state/useJobsStore";
import type { Directive } from "../types";
import { SendIcon } from "../ui/icons";

/** Short human-readable label for a directive, for the inline activity chips. */
function directiveLabel(d: Directive): string {
  const t = d.target ?? {};
  const where =
    t.chain != null
      ? `chain ${t.chain}${t.residue != null ? `·${t.residue}` : ""}`
      : t.residue != null
        ? `res ${t.residue}`
        : t.residue_range
          ? `${t.residue_range[0]}–${t.residue_range[1]}`
          : "structure";
  switch (d.kind) {
    case "color":
      return `colored ${where}`;
    case "label":
      return `labeled ${where}`;
    case "representation":
      return `${d.repr ?? "repr"} · ${where}`;
    case "focus":
      return `focused ${where}`;
    case "select":
      return `selected ${where}`;
    default:
      return where;
  }
}

export function ChatPanel() {
  const projectId = useJobsStore((s) => s.projectId);
  const pickContext = useJobsStore((s) => s.pickContext);
  const directives = useJobsStore((s) => s.directives);
  const pushDirective = useJobsStore((s) => s.pushDirective);
  const clearDirectives = useJobsStore((s) => s.clearDirectives);
  const qc = useQueryClient();

  const messages = useChatStore((s) => s.messages);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const appendUserMessage = useChatStore((s) => s.appendUserMessage);
  const startAssistantMessage = useChatStore((s) => s.startAssistantMessage);
  const appendAssistantDelta = useChatStore((s) => s.appendAssistantDelta);
  const finishAssistantMessage = useChatStore((s) => s.finishAssistantMessage);
  const setMessageError = useChatStore((s) => s.setMessageError);
  const setStreaming = useChatStore((s) => s.setStreaming);

  const [input, setInput] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to the newest message.
  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages]);

  // Abort any in-flight stream on unmount.
  useEffect(() => () => abortRef.current?.abort(), []);

  function send(text: string) {
    const message = text.trim();
    if (!message || isStreaming) return;

    appendUserMessage(message);
    setInput("");
    const assistantId = startAssistantMessage();
    setStreaming(true);

    abortRef.current = streamChat(
      {
        project_id: projectId,
        message,
        context: pickContext ? { selection: pickContext } : undefined,
      },
      {
        onText: (delta) => appendAssistantDelta(assistantId, delta),
        onDirective: (d) => pushDirective(d),
        onJob: () => qc.invalidateQueries({ queryKey: ["jobs", projectId] }),
        onDone: () => {
          finishAssistantMessage(assistantId);
          setStreaming(false);
        },
        onError: (msg) => {
          setMessageError(assistantId, `⚠ ${msg}`);
          setStreaming(false);
        },
      },
    );
  }

  const pickLabel = pickContext
    ? `${pickContext.chain ?? "?"}${
        pickContext.residue != null ? `·${pickContext.residue}` : ""
      }${pickContext.resName ? ` ${pickContext.resName}` : ""}`
    : null;

  // Curated "smart suggestions" — each shows off a real capability of the
  // workspace (optimize/batch, homo-oligomer assembly, viewer analysis, design).
  const quickActions: { label: string; prompt: string }[] = [
    {
      label: "Optimize binding",
      prompt:
        "Act as a protein engineer optimizing this protein for tighter, more stable binding. " +
        "Propose a focused panel of point mutations at the most promising positions, then " +
        "batch-fold them so I can rank the candidates by predicted affinity and confidence.",
    },
    {
      label: "Assemble oligomer",
      prompt:
        "Predict how this protein self-assembles: fold it as a homotrimer and as a homohexamer, " +
        "then tell me which oligomeric state folds with higher confidence.",
    },
    {
      label: "Map active site",
      prompt:
        "Identify the most likely active site or functional pocket from the structure, then " +
        "color it and label the key residues in the viewer.",
    },
    {
      label: "Color by confidence",
      prompt:
        "Color the structure to reflect predicted confidence — highlight the least-confident " +
        "loops in red — and tell me which regions are reliable and which to treat with caution.",
    },
    {
      label: "Engineer stability",
      prompt:
        "Recommend the top stabilizing mutations (new disulfides, salt bridges, core repacking), " +
        "explain the rationale for each, then batch-fold the panel to test them.",
    },
    {
      label: pickLabel ? `Explain ${pickLabel}` : "Summarize & rank",
      prompt: pickLabel
        ? "Explain the residue I've selected — its structural role and local environment — and " +
          "whether it's a promising site to mutate; then zoom in and label it."
        : "Summarize the current folding results (pTM, ipTM, pLDDT, and binding affinity where " +
          "available), rank them, and tell me what stands out and what to try next.",
    },
  ];

  // Most recent directives surfaced as subtle inline activity chips.
  const recentDirectives = directives.slice(-4);

  return (
    <div className="chat">
      <div className="chat__head">
        <div className="chat__titlewrap">
          <span className="chat__title">Assistant</span>
          <span className="chat__powered">
            powered by <b>Claude</b>
          </span>
        </div>
        {pickLabel && (
          <span className="chip chip--pick chat__pick" title="Selected residue (sent as context)">
            Selected: {pickLabel}
          </span>
        )}
      </div>

      <div className="chat__list" ref={listRef}>
        {messages.length === 0 && (
          <div className="chat__empty small">
            Ask about structures, request a fold, or recolor the viewer. Try a quick action below.
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`bubble bubble--${m.role} ${m.error ? "bubble--error" : ""}`}>
            {m.text}
            {m.streaming && <span className="bubble__caret" aria-hidden />}
          </div>
        ))}

        {recentDirectives.length > 0 && (
          <>
            {recentDirectives.map((d, i) => (
              <span className="tool-trace" key={`${i}-${d.kind}`}>
                <span className="tool-trace__dot" aria-hidden />
                {directiveLabel(d)}
              </span>
            ))}
          </>
        )}
      </div>

      <div className="chat__quick">
        {quickActions.map((a) => (
          <button
            key={a.label}
            className="chip chip--action"
            disabled={isStreaming}
            onClick={() => send(a.prompt)}
          >
            {a.label}
          </button>
        ))}
      </div>

      <form
        className="chat__input"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <div className="chat__field">
          <textarea
            className="input chat__textarea"
            value={input}
            rows={2}
            placeholder="Message the assistant…"
            disabled={isStreaming}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(input);
              }
            }}
          />
          {!isStreaming && (
            <button
              type="submit"
              className="chat__send"
              disabled={!input.trim()}
              title="Send message"
              aria-label="Send message"
            >
              <SendIcon size={16} />
            </button>
          )}
        </div>
        <div className="chat__actions">
          <button
            type="button"
            className="btn btn--link"
            onClick={clearDirectives}
            title="Reset viewer overlays"
          >
            Reset view
          </button>
          {isStreaming && (
            <button
              type="button"
              className="btn btn--danger-ghost"
              onClick={() => {
                abortRef.current?.abort();
                setStreaming(false);
              }}
            >
              Stop
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
