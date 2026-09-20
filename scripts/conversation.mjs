import { appendFile, mkdir } from "node:fs/promises";
import { randomUUID } from "node:crypto";

const IDLE_MS = 60_000;
const KEEP_MESSAGES = 12;
const COMPACT_AFTER_TURNS = 10;
const COMPACT_AFTER_CHARS = 8_000;

export class Conversation {
  constructor({ summarize, logDir, now = () => Date.now() }) {
    this.summarize = summarize;
    this.logDir = logDir;
    this.now = now;
    this.logQueue = Promise.resolve();
    this.compaction = null;
    this.session = this.newSession();
    this.audit("session_started", { reason: "startup" });
  }

  newSession() {
    return {
      id: randomUUID(),
      revision: (this.session?.revision || 0) + 1,
      summary: "",
      messages: [],
      lastActivityAt: this.now(),
    };
  }

  ensureActive() {
    if (this.now() - this.session.lastActivityAt >= IDLE_MS) this.reset("idle_timeout");
    this.session.lastActivityAt = this.now();
    return this.session;
  }

  reset(reason = "manual") {
    const previousSessionId = this.session.id;
    this.session = this.newSession();
    this.audit("session_reset", { reason, previous_session_id: previousSessionId });
    this.audit("session_started", { reason });
    return { sessionId: this.session.id, revision: this.session.revision };
  }

  startResponse(text, turnId) {
    const session = this.ensureActive();
    const message = { id: randomUUID(), role: "user", content: text };
    session.messages.push(message);
    const request = {
      sessionId: session.id,
      revision: session.revision,
      turnId,
      userMessageId: message.id,
      startedAt: this.now(),
    };
    this.audit("user_message", { turn_id: turnId, user_text: text });
    this.audit("response_started", {
      turn_id: turnId,
      response_mode: null,
      model: "deepseek/deepseek-v4-flash",
      reasoning_effort: "none",
    });
    return {
      request,
      summary: session.summary,
      messages: session.messages.map(({ role, content }) => ({ role, content })),
    };
  }

  isCurrent(request) {
    return request.sessionId === this.session.id && request.revision === this.session.revision;
  }

  marker() {
    const session = this.ensureActive();
    return { sessionId: session.id, revision: session.revision };
  }

  finishResponse(request, answer) {
    if (!this.isCurrent(request)) {
      this.audit("response_cancelled", { turn_id: request.turnId, reason: "stale_session" }, request.sessionId);
      return false;
    }
    this.session.messages.push({ id: randomUUID(), role: "assistant", content: answer });
    this.session.lastActivityAt = this.now();
    this.audit("assistant_message", {
      turn_id: request.turnId,
      assistant_text: answer,
      model: "deepseek/deepseek-v4-flash",
      reasoning_effort: "none",
      duration_ms: this.now() - request.startedAt,
    });
    this.compactInBackground();
    return true;
  }

  cancelResponse(request, reason) {
    if (this.isCurrent(request)) {
      this.session.messages = this.session.messages.filter(({ id }) => id !== request.userMessageId);
    }
    this.audit("response_cancelled", { turn_id: request.turnId, reason }, request.sessionId);
  }

  recordEmotion({ marker, turnId, text, emotion, valence, arousal, durationMs }) {
    if (!this.isCurrent(marker)) return false;
    this.audit("emotion_evaluated", {
      turn_id: turnId,
      user_text: text,
      emotion: { category: emotion, valence, arousal },
      model: "typesafe-ai/jev",
      duration_ms: durationMs,
    });
    return true;
  }

  recordFailure(request, error, timeout = false) {
    if (request && this.isCurrent(request)) {
      this.session.messages = this.session.messages.filter(({ id }) => id !== request.userMessageId);
    }
    this.audit("response_failed", {
      turn_id: request?.turnId,
      duration_ms: request ? this.now() - request.startedAt : undefined,
      error: error?.message || String(error),
      timeout,
    }, request?.sessionId);
  }

  compactInBackground() {
    if (this.compaction) return;
    const session = this.session;
    const turns = session.messages.filter(({ role }) => role === "assistant").length;
    const characters = session.messages.reduce((sum, message) => sum + message.content.length, 0);
    if ((turns <= COMPACT_AFTER_TURNS && characters <= COMPACT_AFTER_CHARS) || session.messages.length <= KEEP_MESSAGES) return;

    const oldMessages = KEEP_MESSAGES ? session.messages.slice(0, -KEEP_MESSAGES) : [...session.messages];
    const prefixIds = oldMessages.map(({ id }) => id);
    const startedAt = this.now();
    let completed = false;
    console.log(`会話要約開始: ${oldMessages.length}メッセージ`);
    this.audit("history_compaction_started", { message_count: oldMessages.length, character_count: characters });
    this.compaction = this.summarize(session.summary, oldMessages)
      .then((summary) => {
        const prefixStillMatches = prefixIds.every((id, index) => this.session.messages[index]?.id === id);
        if (this.session.id !== session.id || this.session.revision !== session.revision || !prefixStillMatches) return;
        this.session.summary = summary.trim();
        this.session.messages.splice(0, oldMessages.length);
        completed = true;
        console.log(`会話要約: ${JSON.stringify(this.session.summary)}`);
        this.audit("history_compacted", {
          message_count: oldMessages.length,
          summary_characters: this.session.summary.length,
          duration_ms: this.now() - startedAt,
        });
      })
      .catch((error) => {
        console.error(`会話要約失敗: ${error?.message || error}`);
        this.audit("history_compaction_failed", {
          duration_ms: this.now() - startedAt,
          error: error?.message || String(error),
          timeout: error?.name === "TimeoutError" || error?.name === "AbortError",
        });
      })
      .finally(() => {
        this.compaction = null;
        if (completed) this.compactInBackground();
      });
  }

  audit(event, details = {}, sessionId = this.session.id) {
    const entry = {
      timestamp: new Date(this.now()).toISOString(),
      session_id: sessionId,
      event,
      ...details,
    };
    this.logQueue = this.logQueue
      .then(async () => {
        await mkdir(this.logDir, { recursive: true });
        const date = entry.timestamp.slice(0, 10);
        await appendFile(new URL(`conversation-${date}.jsonl`, this.logDir), `${JSON.stringify(entry)}\n`);
      })
      .catch((error) => console.error("監査ログ書き込み失敗:", error));
  }
}

export const conversationSettings = {
  idleMs: IDLE_MS,
  keepMessages: KEEP_MESSAGES,
  compactAfterTurns: COMPACT_AFTER_TURNS,
  compactAfterChars: COMPACT_AFTER_CHARS,
};
