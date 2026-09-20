import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { Conversation } from "./conversation.mjs";

async function fixture(options = {}) {
  const directory = await mkdtemp(join(tmpdir(), "iphone-robot-conversation-"));
  let now = 1_800_000_000_000;
  const conversation = new Conversation({
    logDir: pathToFileURL(`${directory}/`),
    now: () => now,
    summarize: options.summarize || (async () => "要約済み"),
  });
  return { conversation, directory, advance: (milliseconds) => { now += milliseconds; } };
}

test("1分の無操作後は新しいセッションになる", async () => {
  const context = await fixture();
  const first = context.conversation.session.id;
  context.advance(60_000);
  context.conversation.startResponse("こんにちは", "turn-1");
  assert.notEqual(context.conversation.session.id, first);
  await context.conversation.logQueue;
  await rm(context.directory, { recursive: true });
});

test("要約後も直近6ターンを原文で残す", async () => {
  const originalLog = console.log;
  console.log = () => {};
  const context = await fixture({
    summarize: async (previous, messages) => `${previous}${messages.length}件を要約`,
  });
  try {
    for (let turn = 1; turn <= 11; turn += 1) {
      const { request } = context.conversation.startResponse(`質問${turn}`, `turn-${turn}`);
      context.conversation.finishResponse(request, `回答${turn}`);
    }
    await context.conversation.compaction;
    assert.equal(context.conversation.session.messages.length, 12);
    assert.equal(context.conversation.session.messages[0].content, "質問6");
    assert.equal(context.conversation.session.summary, "10件を要約");
    await context.conversation.logQueue;
    await rm(context.directory, { recursive: true });
  } finally {
    console.log = originalLog;
  }
});

test("リセット前の応答は履歴へ追加しない", async () => {
  const context = await fixture();
  const { request } = context.conversation.startResponse("古い質問", "turn-old");
  context.conversation.reset();
  assert.equal(context.conversation.finishResponse(request, "古い回答"), false);
  assert.deepEqual(context.conversation.session.messages, []);
  await context.conversation.logQueue;
  const log = await readFile(join(context.directory, "conversation-2027-01-15.jsonl"), "utf8");
  assert.match(log, /"event":"response_cancelled"/);
  await rm(context.directory, { recursive: true });
});
