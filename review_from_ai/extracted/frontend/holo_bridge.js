// K1 Hologram Bridge (non-invasive)
// Loads AFTER your hologram script. Does NOT modify the 3D model or shaders.
// It only fetches backend presence state and forwards it to methods your hologram may already expose.
//
// Expected (optional) hologram API on window:
//   window.hologram.setState(state)        // "idle" | "listening" | "speaking" | "error"
//   window.hologram.setEmotion(emotion)    // "calm" | "confident" | "neutral" | ...
//   window.hologram.setFocus(focus)        // "user" | "system"

(function () {
  const POLL_MS = 250;
  const PRESENCE_URL = "/api/presence";

  async function fetchPresence() {
    const r = await fetch(PRESENCE_URL, { cache: "no-store" });
    if (!r.ok) throw new Error("presence_http_" + r.status);
    return await r.json();
  }

  function applyPresence(p) {
    const h = window.hologram;
    if (!h) return;

    if (typeof h.setState === "function" && p.state) h.setState(p.state);
    if (typeof h.setEmotion === "function" && p.emotion) h.setEmotion(p.emotion);
    if (typeof h.setFocus === "function" && p.focus) h.setFocus(p.focus);

    // Optional lipsync hint if your hologram supports it:
    if (typeof h.setSpeaking === "function") h.setSpeaking(p.state === "speaking");
  }

  async function tick() {
    try {
      const p = await fetchPresence();
      applyPresence(p);
    } catch (e) {
      // silent; do not spam console in production
    }
  }

  setInterval(tick, POLL_MS);
  tick();
})();
