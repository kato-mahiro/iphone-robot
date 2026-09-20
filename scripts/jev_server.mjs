import { createServer } from "node:http";
import { readFileSync, writeFileSync } from "node:fs";
import { readFile, unlink } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { experimental_evaluate as evaluate, streamText } from "ai";
import { createOpenRouter } from "@openrouter/ai-sdk-provider";

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
    try {
      const text = JSON.parse(body).text?.trim();
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
        console.log(`応答入力: ${text}`);
        const result = streamText({
          model: openrouter("deepseek/deepseek-v4-flash", { provider: { sort: "latency" } }),
          system: "あなたは小さな展示ロボットです。日本語で親しみやすく、1〜2文、80文字以内で返答してください。絵文字やMarkdownは使いません。",
          prompt: text,
          maxOutputTokens: 120,
          providerOptions: { openrouter: { reasoning: { effort: "none" } } },
        });
        response.writeHead(200, {
          "content-type": "text/plain; charset=utf-8",
          "cache-control": "no-store",
          "x-content-type-options": "nosniff",
        });
        let answer = "";
        for await (const chunk of result.textStream) {
          answer += chunk;
          response.write(chunk);
        }
        response.end();
        console.log(`ロボット応答: ${answer}`);
        return;
      }
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
      const current = updateEmotionState(observed.valence, observed.arousal);
      console.log(`JEV出力: ${JSON.stringify(result.answers)}`);
      console.log(`感情スコア: category=${emotion} valence=${current.valence.toFixed(2)} arousal=${current.arousal.toFixed(2)}`);
      response.writeHead(200, { "content-type": "application/json; charset=utf-8" });
      response.end(JSON.stringify({ emotion, ...current }));
    } catch (error) {
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
