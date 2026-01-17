// tools/force_speaking.js
// Run this in the browser DevTools console on your app page.
// It will set presence to "speaking" and request TTS from /api/voice/tts.

(async function () {
  await fetch("/api/presence", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ state: "speaking", emotion: "confident", focus: "user" })
  });

  const r = await fetch("/api/voice/tts", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ text: "Salut. Sunt K1. Vorbesc acum.", cinematic: true })
  });

  if (!r.ok) {
    console.error("TTS failed:", r.status, await r.text());
    return;
  }

  const j = await r.json();
  if (!j.ok) {
    console.error("TTS error:", j);
    return;
  }

  const audio = new Audio("data:" + (j.mime || "audio/mpeg") + ";base64," + j.audio_b64);
  await audio.play();
  console.log("OK: speaking state + audio playing");
})();
