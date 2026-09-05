"use client";

import { ArrowUp, Bot, ChevronsUpDown, Database, Gauge, ShieldAlert, Sparkles, Square, UserRound } from "lucide-react";
import Link from "next/link";
import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AgentContext, AgentMessage, getAgentStatus, getIncidents, Incident, streamAgent } from "../api/client";
import { BrandLockup } from "../components/brand-lockup";
import { MobileNav } from "../components/mobile-nav";
import styles from "./agent.module.css";

const SUGGESTIONS = [
  "Summarize current operational health",
  "What should the transport manager prioritize?",
  "Which vendor incidents need attention?",
  "Explain the OTA breach using current facts",
];

const WELCOME: AgentMessage = {
  role: "assistant",
  content: "I can analyze the current mobility snapshot, explain active SLA incidents, and recommend operational next steps. My answers are read-only and grounded in the data currently loaded in SHLOK.",
};

const INCIDENT_WELCOME: AgentMessage = {
  role: "assistant",
  content: "I’m focused on this incident. Ask me to explain the breach, summarize its evidence, or recommend the next operational response.",
};

type AgentScope = "general" | "incident";

export default function AgentPage() {
  const [messages, setMessages] = useState<AgentMessage[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [context, setContext] = useState<AgentContext | null>(null);
  const [provider, setProvider] = useState<Pick<AgentContext, "mode" | "model"> | null>(null);
  const [scope, setScope] = useState<AgentScope>("general");
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<number | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const selectedIncident = incidents.find((incident) => incident.id === selectedIncidentId) ?? null;
  const activeProvider = context ?? provider;

  useEffect(() => {
    void getAgentStatus().then(setProvider).catch(() => setProvider(null));
    void getIncidents().then((next) => {
      setIncidents(next);
      const queryId = Number(new URLSearchParams(window.location.search).get("incidentId"));
      const linkedIncident = next.find((incident) => incident.id === queryId);
      setSelectedIncidentId(linkedIncident?.id ?? next[0]?.id ?? null);
      if (linkedIncident) {
        setScope("incident");
        setMessages([INCIDENT_WELCOME]);
      }
    }).catch((requestError) => setError(requestError instanceof Error ? requestError.message : "Unable to load incidents"));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: streaming ? "auto" : "smooth" });
  }, [messages, streaming]);

  async function sendMessage(prompt = input) {
    const message = prompt.trim();
    if (!message || streaming) return;
    const history = messages.slice(1).slice(-10);
    setInput("");
    setError(null);
    setStreaming(true);
    setMessages((current) => [...current, { role: "user", content: message }, { role: "assistant", content: "" }]);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await streamAgent(
        message,
        history,
        scope === "incident" ? selectedIncidentId : null,
        {
          onContext: setContext,
          onToken: (token) => setMessages((current) => {
            const next = [...current];
            const last = next[next.length - 1];
            next[next.length - 1] = { ...last, content: last.content + token };
            return next;
          }),
        },
        controller.signal,
      );
    } catch (requestError) {
      if (!controller.signal.aborted) {
        setError(requestError instanceof Error ? requestError.message : "The agent could not complete this response");
        setMessages((current) => current.at(-1)?.content ? current : current.slice(0, -1));
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  function changeScope(nextScope: AgentScope, incidentId = selectedIncidentId) {
    if (streaming || (nextScope === "incident" && incidentId === null)) return;
    setScope(nextScope);
    setSelectedIncidentId(incidentId);
    setMessages([nextScope === "incident" ? INCIDENT_WELCOME : WELCOME]);
    setContext(null);
    setError(null);
    const url = nextScope === "incident" && incidentId ? `/agent?incidentId=${incidentId}` : "/agent";
    window.history.replaceState(null, "", url);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void sendMessage();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  }

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <BrandLockup />
        <nav aria-label="Primary navigation">
          <Link href="/"><Gauge size={18} /> Operations</Link>
          <Link href="/incidents"><ShieldAlert size={18} /> Incidents</Link>
          <Link className={styles.navActive} href="/agent" aria-current="page"><Bot size={18} /> Mobility Agent</Link>
          <Link href="/trips"><Database size={18} /> Data dashboards</Link>
        </nav>
        <div className={styles.persona}><span>Viewing as</span><strong>Transport Manager</strong></div>
      </aside>

      <main className={styles.page}>
        <header className={styles.header}>
          <div><p>AI OPERATIONS COPILOT</p><h1>Mobility Agent</h1><span>{scope === "incident" ? "Analyze one incident with its exact operational evidence." : "Ask questions grounded in the overall mobility snapshot."}</span></div>
          <div className={styles.mode}><span className={activeProvider?.mode === "model" ? styles.live : styles.local} />{activeProvider?.mode === "model" ? activeProvider.model : activeProvider ? "Grounded local mode" : "Checking provider"}</div>
        </header>

        <section className={styles.scopeBar} aria-label="Agent scope">
          <div className={styles.scopeToggle}>
            <button className={scope === "general" ? styles.scopeActive : ""} onClick={() => changeScope("general")} disabled={streaming}>General</button>
            <button className={scope === "incident" ? styles.scopeActive : ""} onClick={() => changeScope("incident")} disabled={streaming || incidents.length === 0}>Incident</button>
          </div>
          {scope === "incident" && <label className={styles.incidentSelector}><ShieldAlert size={17} /><span><small>Selected incident</small><select value={selectedIncidentId ?? ""} onChange={(event) => changeScope("incident", Number(event.target.value))} disabled={streaming}>{incidents.map((incident) => <option value={incident.id} key={incident.id}>{incident.severity.toUpperCase()} · {incident.title}</option>)}</select></span><ChevronsUpDown size={16} /></label>}
        </section>

        <section className={styles.workspace}>
          <div className={styles.conversation} aria-live="polite">
            {messages.map((message, index) => (
              <article className={message.role === "user" ? styles.userMessage : styles.agentMessage} key={`${message.role}-${index}`}>
                <div className={styles.avatar}>{message.role === "user" ? <UserRound size={17} /> : <Bot size={17} />}</div>
                <div><span>{message.role === "user" ? "You" : "Mobility Agent"}</span>{message.role === "user" ? <p className={styles.userBubble}>{message.content}</p> : <div className={styles.markdown}><ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content || "Analyzing the current operation..."}</ReactMarkdown></div>}{message.role === "assistant" && index > 0 && <small>Advisory response · No operational records changed</small>}</div>
              </article>
            ))}
            {error && <div className={styles.error} role="alert">{error}</div>}
            <div ref={endRef} />
          </div>

          <aside className={styles.contextPanel}>
            <div className={styles.contextHeading}><Sparkles size={17} /><div><strong>Grounding context</strong><span>Refreshed for every question</span></div></div>
            <dl>
              <div><dt>Dataset</dt><dd>{context?.sourceFile ?? "Loaded on first question"}</dd></div>
              <div><dt>Completed trips</dt><dd>{context ? context.completedTrips.toLocaleString() : "-"}</dd></div>
              <div><dt>Attention incidents</dt><dd>{context?.attentionIncidents ?? "-"}</dd></div>
              <div><dt>Scope</dt><dd>{context?.scope === "incident" ? context.incidentTitle : context ? "Overall operation" : scope === "incident" ? selectedIncident?.title : "Overall operation"}</dd></div>
              <div><dt>Response mode</dt><dd>{activeProvider?.mode === "model" ? `AI model · ${activeProvider.model}` : activeProvider ? "Local grounded" : "Checking"}</dd></div>
            </dl>
            <p>The agent can explain and recommend. A manager must still acknowledge incidents or take operational action.</p>
          </aside>
        </section>

        <section className={styles.composerArea}>
          {messages.length === 1 && <div className={styles.suggestions}>{(scope === "incident" ? ["Explain this incident", "What evidence supports this alert?", "What should the manager do next?"] : SUGGESTIONS).map((suggestion) => <button key={suggestion} onClick={() => void sendMessage(suggestion)}>{suggestion}</button>)}</div>}
          <form className={styles.composer} onSubmit={submit}>
            <textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={handleKeyDown} placeholder={scope === "incident" ? "Ask about this incident’s evidence or next action..." : "Ask about SLA risk, incidents, vendors, or next actions..."} rows={2} disabled={streaming} aria-label="Message Mobility Agent" />
            {streaming ? <button type="button" onClick={() => abortRef.current?.abort()} aria-label="Stop response" title="Stop response"><Square size={17} /></button> : <button type="submit" disabled={!input.trim()} aria-label="Send message" title="Send message"><ArrowUp size={19} /></button>}
          </form>
          <p className={styles.disclaimer}>Answers use the current SHLOK operational snapshot and may require manager verification.</p>
        </section>
      </main>
      <MobileNav active="agent" />
    </div>
  );
}
