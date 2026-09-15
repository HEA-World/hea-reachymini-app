(function exposeChatTurnState(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
    return;
  }
  root.HEAChatTurnState = api;
}(typeof window === "undefined" ? globalThis : window, function buildChatTurnState() {
  function turnId(value) {
    const parsed = Number(value);
    return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : 0;
  }

  function begin(bubble, baselineTurnId) {
    return {
      bubble,
      baselineTurnId: turnId(baselineTurnId),
      lastAnswer: "",
    };
  }

  function ownsState(turn, state) {
    return Boolean(turn) && turnId(state?.turn_id) > turn.baselineTurnId;
  }

  return Object.freeze({ begin, ownsState });
}));
