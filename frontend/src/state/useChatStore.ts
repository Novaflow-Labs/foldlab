// Chat transcript state plus streaming-assistant buffer helpers.
import { create } from "zustand";

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  text: string;
  /** True while the assistant bubble is still being streamed into. */
  streaming?: boolean;
  /** Non-null when this message represents an inline error. */
  error?: boolean;
}

let counter = 0;
function nextId(): string {
  counter += 1;
  return `m${counter}_${Date.now()}`;
}

interface ChatState {
  messages: ChatMessage[];
  /** True while a streamChat request is in flight. */
  isStreaming: boolean;

  appendUserMessage: (text: string) => void;
  /** Open a fresh assistant bubble and return its id for subsequent appends. */
  startAssistantMessage: () => string;
  /** Append a streamed delta to a specific assistant bubble. */
  appendAssistantDelta: (id: string, delta: string) => void;
  /** Mark an assistant bubble as finished streaming. */
  finishAssistantMessage: (id: string) => void;
  /** Replace a bubble's contents with an error string. */
  setMessageError: (id: string, text: string) => void;
  setStreaming: (v: boolean) => void;
  clear: () => void;
}

export const useChatStore = create<ChatState>()((set) => ({
  messages: [],
  isStreaming: false,

  appendUserMessage: (text) =>
    set((s) => ({
      messages: [...s.messages, { id: nextId(), role: "user", text }],
    })),

  startAssistantMessage: () => {
    const id = nextId();
    set((s) => ({
      messages: [...s.messages, { id, role: "assistant", text: "", streaming: true }],
    }));
    return id;
  },

  appendAssistantDelta: (id, delta) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, text: m.text + delta } : m,
      ),
    })),

  finishAssistantMessage: (id) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, streaming: false } : m,
      ),
    })),

  setMessageError: (id, text) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, text, streaming: false, error: true } : m,
      ),
    })),

  setStreaming: (v) => set({ isStreaming: v }),
  clear: () => set({ messages: [] }),
}));
