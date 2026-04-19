import test from "node:test";
import assert from "node:assert/strict";

import {
  createRuntimeState,
  findConflictingRuns,
  findRunForCancel,
  registerRun,
  unregisterRun,
} from "./runtime-state.mjs";

test("finds a running request by conversationId when requestId is not available yet", () => {
  const state = createRuntimeState();
  const run = { requestId: "req-1", conversationId: "conv-1", sessionId: "sess-1" };
  registerRun(state, run);

  assert.equal(findRunForCancel(state, { conversationId: "conv-1" }), run);
});

test("deduplicates conflicts when conversationId and sessionId point to the same run", () => {
  const state = createRuntimeState();
  const run = { requestId: "req-1", conversationId: "conv-1", sessionId: "sess-1" };
  registerRun(state, run);

  assert.deepEqual(
    findConflictingRuns(state, { conversationId: "conv-1", sessionId: "sess-1" }).map(
      (entry) => entry.requestId
    ),
    ["req-1"]
  );
});

test("unregister keeps newer conversation mapping intact", () => {
  const state = createRuntimeState();
  const olderRun = { requestId: "req-1", conversationId: "conv-1", sessionId: "sess-1" };
  const newerRun = { requestId: "req-2", conversationId: "conv-1", sessionId: "sess-2" };
  registerRun(state, olderRun);
  registerRun(state, newerRun);

  unregisterRun(state, "req-1");

  assert.equal(findRunForCancel(state, { conversationId: "conv-1" }), newerRun);
  assert.equal(findRunForCancel(state, { requestId: "req-1" }), null);
});
