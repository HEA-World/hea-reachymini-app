import test from "node:test";
import assert from "node:assert/strict";

await import("../hea_reachy_mini/static/chat_turn_state.js");
const chatTurnState = globalThis.HEAChatTurnState;

test("a pending chat turn ignores the previous completed answer", () => {
  const turn = chatTurnState.begin({}, 7);

  assert.equal(chatTurnState.ownsState(turn, {
    turn_id: 7,
    status: "complete",
    answer: "Previous answer",
  }), false);
});

test("a pending chat turn owns every snapshot from the newly queued turn", () => {
  const turn = chatTurnState.begin({}, 7);

  assert.equal(chatTurnState.ownsState(turn, { turn_id: 8, status: "queued", answer: "" }), true);
  assert.equal(chatTurnState.ownsState(turn, { turn_id: 8, status: "answering", answer: "Part" }), true);
  assert.equal(chatTurnState.ownsState(turn, { turn_id: 8, status: "complete", answer: "Part complete" }), true);
});

test("invalid or missing turn ids never claim a pending bubble", () => {
  const turn = chatTurnState.begin({}, 3);

  assert.equal(chatTurnState.ownsState(turn, {}), false);
  assert.equal(chatTurnState.ownsState(turn, { turn_id: "not-a-turn" }), false);
});
