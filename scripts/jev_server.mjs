import { createServer } from "node:http";
import { readFileSync, writeFileSync } from "node:fs";
import { readFile, unlink } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { experimental_evaluate as evaluate, generateText, streamText } from "ai";
import { createOpenRouter } from "@openrouter/ai-sdk-provider";
import { Conversation } from "./conversation.mjs";

for (const line of readFileSync(new URL("../.env", import.meta.url), "utf8").split(/\r?\n/)) {
  const match = line.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
  if (match && !process.env[match[1]]) process.env[match[1]] = match[2].replace(/^(['"])(.*)\1$/, "$2");
}

if (!process.env.AI_GATEWAY_API_KEY) throw new Error("AI_GATEWAY_API_KEY が設定されていません");
if (!process.env.OPENROUTER_API_KEY) throw new Error("OPENROUTER_API_KEY が設定されていません");

const port = Number(process.env.JEV_PORT || 8844);
const restartFile = new URL("../logs/restart.request", import.meta.url);
const decayMs = 15_000;
const openrouter = createOpenRouter({ apiKey: process.env.OPENROUTER_API_KEY });
const run = promisify(execFile);
let emotionState = { valence: 0, arousal: 0 };
let stateUpdatedAt = Date.now();

const conversation = new Conversation({
  logDir: new URL("../logs/", import.meta.url),
  summarize: async (previousSummary, messages) => {
    const transcript = messages.map(({ role, content }) => `${role === "user" ? "ユーザー" : "ロボット"}: ${content}`).join("\n");
    const result = await generateText({
      model: openrouter("deepseek/deepseek-v4-flash", { provider: { sort: "latency" } }),
      system: `展示ロボットの会話履歴を、次回以降の応答に必要な情報だけ残して更新してください。
次の固定形式を使い、全体を600文字以内にしてください。
【会話の概要】
- 現在の話題:
- ユーザーが明示した事実・好み:
- ロボットが伝えた重要事項:
- 未解決の質問・約束:
- 直前までの流れ:
既存の要約は累積記憶です。名前、固有名詞、好み、関係、数値、約束など、ユーザーが明示した事実は、ユーザー自身が訂正または撤回しない限り必ずそのまま残してください。
ロボットの発言や誤回答でユーザーの事実を上書きしてはいけません。矛盾する場合はユーザーの最新の明示的な発言を優先してください。
更新してよいのは現在の話題、解決済みの質問、直前までの流れです。推測や感情の断定を追加せず、挨拶、相づち、重複は省略してください。`,
      prompt: `既存の要約:\n${previousSummary || "（なし）"}\n\n新たに要約へ統合する会話:\n${transcript}`,
      maxOutputTokens: 600,
      abortSignal: AbortSignal.timeout(30_000),
      providerOptions: { openrouter: { reasoning: { effort: "none" } } },
    });
    return result.text;
  },
});

function updateEmotionState(valence, arousal, now = Date.now()) {
  const decay = Math.max(0, 1 - (now - stateUpdatedAt) / decayMs);
  emotionState.valence = emotionState.valence * decay * 0.7 + valence * 0.3;
  emotionState.arousal = emotionState.arousal * decay * 0.7 + arousal * 0.3;
  stateUpdatedAt = now;
  return emotionState;
}

async function synthesizeSpeech(text) {
  const path = `${tmpdir()}/iphone-robot-${randomUUID()}.aiff`;
  const startedAt = Date.now();
  try {
    await run("/usr/bin/say", ["-v", "Eddy (日本語（日本）)", "-r", "300", "-o", path, text]);
    const audio = await readFile(path);
    console.log(`音声合成: Eddy ${(Date.now() - startedAt) / 1000}s ${audio.length}bytes`);
    return audio;
  } finally {
    await unlink(path).catch(() => {});
  }
}

if (process.argv.includes("--self-test")) {
  const state = updateEmotionState(1, 1, stateUpdatedAt);
  if (state.valence !== 0.3 || state.arousal !== 0.3) throw new Error("感情スコア更新テスト失敗");
  console.log("感情スコア更新テスト成功");
  process.exit(0);
}

const server = createServer((request, response) => {
  if (request.method === "GET" && (request.url === "/health" || request.url.startsWith("/health?"))) {
    response.writeHead(200, { "content-type": "application/json", "cache-control": "no-store" });
    response.end(JSON.stringify({ ok: true }));
    return;
  }
  if (request.method === "POST" && request.url === "/restart" && request.headers["x-robot-restart"] === "hold-3s") {
    response.writeHead(202, { "content-type": "application/json; charset=utf-8" });
    response.end(JSON.stringify({ restarting: true }));
    setTimeout(() => {
      server.close(() => writeFileSync(restartFile, new Date().toISOString()));
      server.closeAllConnections();
    }, 250);
    return;
  }
  if (request.method === "POST" && request.url === "/conversation/reset") {
    const session = conversation.reset("manual");
    emotionState = { valence: 0, arousal: 0 };
    stateUpdatedAt = Date.now();
    response.writeHead(200, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" });
    response.end(JSON.stringify({ reset: true, ...session }));
    return;
  }
  if (request.method !== "POST" || !["/emotion", "/response", "/speech"].includes(request.url)) {
    response.writeHead(404).end();
    return;
  }

  let body = "";
  request.setEncoding("utf8");
  request.on("data", (chunk) => {
    body += chunk;
    if (body.length > 16_000) request.destroy();
  });
  request.on("end", async () => {
    let responseContext;
    let turnId;
    const requestStartedAt = Date.now();
    try {
      const payload = JSON.parse(body);
      const text = payload.text?.trim();
      turnId = payload.turnId || randomUUID();
      if (!text || text.length > 4_000) throw new Error("発話内容が空か、長すぎます");
      if (request.url === "/speech") {
        console.log(`音声合成入力: ${text}`);
        const audio = await synthesizeSpeech(text);
        response.writeHead(200, {
          "content-type": "audio/aiff",
          "content-length": audio.length,
          "cache-control": "no-store",
        });
        response.end(audio);
        return;
      }
      if (request.url === "/response") {
        const context = conversation.startResponse(text, turnId);
        responseContext = context.request;
        const controller = new AbortController();
        let clientClosed = false;
        response.on("close", () => {
          if (!response.writableFinished) {
            clientClosed = true;
            controller.abort();
          }
        });
        console.log(`応答入力: ${text}`);
        const result = streamText({
          model: openrouter("deepseek/deepseek-v4-flash", { provider: { sort: "latency" } }),
          system: `あなたは小さな展示ロボットです。日本語で親しみやすく、1〜2文、80文字以内で返答してください。絵文字やMarkdownは使いません。${context.summary ? `\n\n以下はこのセッションの信頼できる会話記憶です。過去の会話、名前、好み、約束について聞かれた場合は必ずこの記憶から答えてください。記憶に書かれている事実を「聞いていない」「覚えていない」と否定してはいけません。\n【会話記憶】\n${context.summary}` : ""}`,
          messages: context.messages,
          maxOutputTokens: 120,
          abortSignal: controller.signal,
          providerOptions: { openrouter: { reasoning: { effort: "none" } } },
        });
        response.writeHead(200, {
          "content-type": "text/plain; charset=utf-8",
          "cache-control": "no-store",
          "x-content-type-options": "nosniff",
        });
        let answer = "";
        for await (const chunk of result.textStream) {
          if (!conversation.isCurrent(context.request)) break;
          if (clientClosed) {
            conversation.cancelResponse(context.request, "client_disconnected");
            return;
          }
          answer += chunk;
          response.write(chunk);
        }
        response.end();
        conversation.finishResponse(context.request, answer);
        console.log(`ロボット応答: ${answer}`);
        return;
      }
      const emotionMarker = conversation.marker();
      const emotionStartedAt = Date.now();
      console.log(`判定入力: ${text}`);
      const result = await evaluate({
        model: "typesafe-ai/jev",
        state: text,
        questions: {
          emotion: {
            type: "choice",
            instructions: "メッセージに対する反応として生起する感情として最も強いものを一つ選んでください。",
            criteria: {
              joy: "嬉しい、満足、感謝、安心などの喜び",
              anger: "怒り、不満、苛立ち、非難",
              sadness: "悲しい、寂しい、不安、落胆",
              fun: "楽しい、愉快、わくわく、興奮",
            },
          },
          valence: {
            type: "score",
            instructions: "この反応の快・不快の度合いを評価してください。",
            criteria: ["非常に不快", "やや不快", "中立", "やや快", "非常に快"],
          },
          arousal: {
            type: "score",
            instructions: "この反応の情動的な活性度を評価してください。",
            criteria: ["非常に静か", "静か", "中程度", "活発", "非常に興奮"],
          },
        },
      });
      const emotion = result.answers.emotion.choice;
      const observed = {
        valence: (result.answers.valence.score - 2) / 2,
        arousal: result.answers.arousal.score / 4,
      };
      if (!conversation.isCurrent(emotionMarker)) {
        response.writeHead(409, { "content-type": "application/json; charset=utf-8" });
        response.end(JSON.stringify({ error: "会話がリセットされました" }));
        return;
      }
      const current = updateEmotionState(observed.valence, observed.arousal);
      conversation.recordEmotion({
        marker: emotionMarker,
        turnId,
        text,
        emotion,
        valence: current.valence,
        arousal: current.arousal,
        durationMs: Date.now() - emotionStartedAt,
      });
      console.log(`JEV出力: ${JSON.stringify(result.answers)}`);
      console.log(`感情スコア: category=${emotion} valence=${current.valence.toFixed(2)} arousal=${current.arousal.toFixed(2)}`);
      response.writeHead(200, { "content-type": "application/json; charset=utf-8" });
      response.end(JSON.stringify({ emotion, ...current }));
    } catch (error) {
      if (request.url === "/response" && responseContext) {
        if (error?.name === "AbortError") conversation.cancelResponse(responseContext, "client_disconnected");
        else conversation.recordFailure(responseContext, error, error?.name === "TimeoutError");
      }
      if (request.url === "/emotion") conversation.audit("emotion_failed", {
        turn_id: turnId,
        duration_ms: Date.now() - requestStartedAt,
        error: error?.message || String(error),
        timeout: error?.name === "TimeoutError" || error?.name === "AbortError",
      });
      if (request.url === "/speech") conversation.audit("speech_failed", {
        duration_ms: Date.now() - requestStartedAt,
        error: error?.message || String(error),
        timeout: error?.name === "TimeoutError" || error?.name === "AbortError",
      });
      console.error(request.url === "/response" ? "応答失敗:" : request.url === "/speech" ? "音声合成失敗:" : "判定失敗:", error);
      if (response.headersSent) response.end();
      else {
        response.writeHead(400, { "content-type": "application/json; charset=utf-8" });
        response.end(JSON.stringify({ error: error.message || "処理できませんでした" }));
      }
    }
  });
});

server.listen(port, "127.0.0.1", () => console.log(`jev server: http://127.0.0.1:${port}`));
