"use client";

import { ArrowLeft, Bot, CalendarRange, ChevronDown, ChevronRight, CircleUserRound, MessagesSquare, Radar, SendHorizonal, Sparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getIncidents } from "@/app/api/client";
import type { Incident } from "@/types/api";
import styles from "./mobility-agent.module.css";

type ChatMessage = {
  id: string;
  role: "assistant" | "user";
  text: string;
};

type ContextId = string;

type ChatContext = {
  id: ContextId;
  label: string;
  summary: string;
  initialPrompt: string;
  initialMessage: string;
  severity?: Incident["severity"];
  status?: Incident["status"];
};

const fallbackContexts: ChatContext[] = [
  {
    id: "vendor-alpha",
    label: "Vendor Alpha SLA breach",
    summary: "OTA 71% | 42 delayed trips | Avg delay 18 min",
    initialPrompt: "How did the OTA drop for Vendor Alpha this week?",
    initialMessage: "Vendor Alpha's OTA dropped from 84% to 71% this week. I am checking route-level impact and the likely recovery options.",
  },
  {
    id: "general",
    label: "General mobility operations",
    summary: "Network view | OTA, routes, delays, and capacity",
    initialPrompt: "Give me a general mobility operations overview.",
    initialMessage: "I am ready to help with network-wide mobility operations, including OTA, route performance, delays, capacity, and recovery actions.",
  },
];

function createIncidentContext(incident: Incident): ChatContext {
  return {
    id: `incident-${incident.id}`,
    label: incident.title,
    summary: `${incident.currentValue}% current | ${incident.affectedEmployees} employees affected`,
    initialPrompt: `What is driving the issue "${incident.title}"?`,
    initialMessage: `${incident.title} is currently ${incident.status}. ${incident.reason} I can help review the evidence and recommended recovery actions.`,
    severity: incident.severity,
    status: incident.status,
  };
}

const suggestedPrompts = [
  "How did the OTA drop for Vendor Alpha this week?",
  "What are the top routes by delayed trips?",
  "Where are the top reasons for delay?",
  "What actions can help improve OTA?",
];

export default function MobilityAgentPage() {
  const [contexts, setContexts] = useState<ChatContext[]>(fallbackContexts);
  const [contextId, setContextId] = useState<ContextId>("vendor-alpha");
  const [isContextMenuOpen, setIsContextMenuOpen] = useState(false);
  const activeContext = contexts.find((context) => context.id === contextId) ?? contexts[0];
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: "assistant-0", role: "assistant", text: activeContext.initialMessage },
  ]);
  const [draft, setDraft] = useState("");
  const [connected, setConnected] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const messageListRef = useRef<HTMLDivElement | null>(null);
  const streamRef = useRef<EventSource | null>(null);
  const focusLatestRef = useRef(false);
  const userScrolledRef = useRef(false);

  const startStream = useCallback((prompt: string, selectedContext: ContextId) => {
    if (streamRef.current) {
      streamRef.current.close();
    }

    const assistantMessageId = `assistant-${Date.now()}`;
    focusLatestRef.current = true;
    userScrolledRef.current = false;
    setIsThinking(true);
    setMessages((current) => [...current, { id: assistantMessageId, role: "assistant", text: "" }]);

    const source = new EventSource(`/api/agent/stream?message=${encodeURIComponent(prompt)}&context=${selectedContext}`);
    streamRef.current = source;

    source.addEventListener("status", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as { connected?: boolean };
      setConnected(Boolean(payload.connected));
    });

    source.addEventListener("message", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as { text?: string; role?: "assistant" | "user"; sequence?: number };
      if (!payload.text) return;

      setIsThinking(false);
      setMessages((current) => current.map((item) => item.id === assistantMessageId ? { ...item, text: payload.text ?? item.text } : item));
    });

    source.addEventListener("done", () => {
      setConnected(false);
      setIsThinking(false);
      source.close();
    });

    source.onerror = () => {
      setConnected(false);
      setIsThinking(false);
      source.close();
    };
  }, []);

  useEffect(() => {
    let active = true;

    getIncidents().then((incidents) => {
      if (!active) return;

      if (incidents.length > 0) {
        const incidentContexts = incidents.map(createIncidentContext);
        const nextContext = incidentContexts[0];

        setContexts([...incidentContexts, fallbackContexts[1]]);
        setContextId(nextContext.id);
        setMessages([{ id: "assistant-context", role: "assistant", text: nextContext.initialMessage }]);
        startStream(nextContext.initialPrompt, nextContext.id);
        return;
      }

      startStream(fallbackContexts[0].initialPrompt, fallbackContexts[0].id);
    }).catch(() => {
      if (active) startStream(fallbackContexts[0].initialPrompt, fallbackContexts[0].id);
    });

    return () => { active = false; streamRef.current?.close(); };
  }, [startStream]);

  useEffect(() => {
    const container = messageListRef.current;
    if (!container) {
      return;
    }

    if (focusLatestRef.current) {
      container.scrollTo({ top: container.scrollHeight, behavior: "auto" });
      focusLatestRef.current = false;
      return;
    }

    const isNearBottom = container.scrollHeight - (container.scrollTop + container.clientHeight) < 120;
    if (!userScrolledRef.current && isNearBottom) {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    }
  }, [messages]);

  const handleMessageScroll = () => {
    const container = messageListRef.current;
    if (!container) return;

    const isNearBottom = container.scrollHeight - (container.scrollTop + container.clientHeight) < 120;
    userScrolledRef.current = !isNearBottom;
  };

  const statusText = useMemo(() => (connected ? "Live agent stream connected" : "Agent stream ready"), [connected]);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = draft.trim();
    if (!value) return;

    setMessages((current) => [...current, { id: `user-${Date.now()}`, role: "user", text: value }]);
    setDraft("");
    startStream(value, contextId);
  };

  const handleSuggestedPrompt = (prompt: string) => {
    setDraft(prompt);
    setMessages((current) => [...current, { id: `user-${Date.now()}`, role: "user", text: prompt }]);
    startStream(prompt, contextId);
  };

  const handleContextChange = (nextContextId: ContextId) => {
    const nextContext = contexts.find((context) => context.id === nextContextId) ?? contexts[0];

    streamRef.current?.close();
    setConnected(false);
    setContextId(nextContext.id);
    setDraft("");
    setMessages([{ id: `assistant-context-${nextContext.id}`, role: "assistant", text: nextContext.initialMessage }]);
    setIsContextMenuOpen(false);
    startStream(nextContext.initialPrompt, nextContext.id);
  };

  return (
    <div className={styles.pageShell}>
      <div className={styles.canvas}>
        <header className={styles.topBar}>
          <div className={styles.rangePill}><CalendarRange size={14} /> Sep 1, 2026 - Sep 5, 2026</div>
          <div className={styles.userBadge}><span className={styles.avatar}>TM</span><span>Transport Manager</span></div>
        </header>

        <main className={styles.mainCard}>
          <div className={styles.headerRow}>
            <button className={styles.backLink} type="button"><ArrowLeft size={15} /> Back to Investigation</button>
          </div>

          <div className={styles.chatPanel}>
            <section className={styles.chatStage} aria-live="polite">
              <div className={styles.agentHeader}>
                <div className={styles.agentTitleWrap}>
                  <div className={styles.agentIcon}><Bot size={16} /></div>
                  <div>
                    <p className={styles.agentEyebrow}>Current context</p>
                    <h1>Mobility Agent</h1>
                  </div>
                </div>
                <div className={styles.contextMenu}>
                  <button
                    type="button"
                    className={styles.contextTrigger}
                    aria-expanded={isContextMenuOpen}
                    aria-haspopup="listbox"
                    onClick={() => setIsContextMenuOpen((open) => !open)}
                  >
                    <Radar size={14} />
                    <span className={styles.contextTriggerText}>{activeContext.label}</span>
                    <ChevronDown size={14} />
                  </button>
                  {isContextMenuOpen && (
                    <div className={styles.contextOptions} role="listbox" aria-label="Choose chat context">
                      <div className={styles.contextOptionsHeader}>Switch context</div>
                      {contexts.map((context) => (
                        <button
                          key={context.id}
                          type="button"
                          role="option"
                          aria-selected={context.id === contextId}
                          className={`${styles.contextOption} ${context.id === contextId ? styles.contextOptionActive : ""}`}
                          onClick={() => handleContextChange(context.id)}
                        >
                          <span className={styles.contextOptionCopy}>
                            <strong>{context.label}</strong>
                            <small>{context.summary}</small>
                          </span>
                          <span className={styles.contextOptionMeta}>
                            {context.severity && <span className={`${styles.severityDot} ${styles[`severity${context.severity}`]}`} aria-label={`${context.severity} severity`} />}
                            <small>{context.status ?? "general"}</small>
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <div className={styles.contextBadge}><Radar size={14} />{statusText}</div>
              </div>

              <div className={styles.intentCard}>
                <div className={styles.intentMeta}>
                  <Sparkles size={15} />
                  <span>{activeContext.label}</span>
                </div>
                <strong>{activeContext.summary}</strong>
              </div>

              <div ref={messageListRef} className={styles.messages} onScroll={handleMessageScroll}>
                {messages.map((message) => (
                  <div key={message.id} className={`${styles.messageRow} ${message.role === "user" ? styles.userRow : styles.assistantRow}`}>
                    <div className={styles.messageBubble}>
                      {message.role === "assistant" && <span className={styles.messageAvatar}><Bot size={12} /></span>}
                      {message.text ? <p>{message.text}</p> : isThinking && <p className={styles.thinkingText}>Thinking<span className={styles.thinkingDots}>...</span></p>}
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <aside className={styles.sideRail}>
              <div className={styles.summaryBlock}>
                <div className={styles.summaryCard}>
                  <div className={styles.summaryHeader}>Key takeaways</div>
                  <ul>
                    <li>Majority of delays are occurring on Route BLR-17 during the 9 AM window.</li>
                    <li>Vehicle allocation for morning shifts is insufficient to sustain SLA.</li>
                    <li>Overall trip volume remains stable compared to last week.</li>
                  </ul>
                </div>

                <div className={styles.summaryCard}>
                  <div className={styles.summaryHeader}>Recommended actions</div>
                  <ol>
                    <li>Review and increase vehicle allocation for BLR-17 and BLR-22 during morning shifts.</li>
                    <li>Discuss SLA breach with Vendor Alpha.</li>
                    <li>Monitor OTA closely over the next week after changes.</li>
                  </ol>
                </div>
              </div>

              <div className={styles.suggestionsPanel}>
                <div className={styles.suggestHeader}>
                  <MessagesSquare size={14} />
                  <span>Suggested questions</span>
                </div>
                <ul className={styles.suggestList}>
                  {suggestedPrompts.map((prompt) => (
                    <li key={prompt}>
                      <button type="button" onClick={() => handleSuggestedPrompt(prompt)}>
                        <span>{prompt}</span>
                        <ChevronRight size={15} />
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            </aside>
          </div>

          <form className={styles.inputRow} onSubmit={handleSubmit}>
            <div className={styles.promptBox}>
              <button type="button" className={styles.iconButton} aria-label="Attach document"><CircleUserRound size={16} /></button>
              <input
                aria-label="Ask a follow-up question"
                value={draft}
                placeholder="Ask a follow-up question..."
                onChange={(event) => setDraft(event.target.value)}
              />
            </div>
            <button type="submit" className={styles.sendButton} aria-label="Send message"><SendHorizonal size={16} /></button>
          </form>
        </main>
      </div>
    </div>
  );
}
