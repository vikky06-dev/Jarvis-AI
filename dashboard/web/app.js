/* J.A.R.V.I.S dashboard frontend: clock, info bar, transcript, living orb. */

/* ── Clock ─────────────────────────────────────────────── */
function tickClock() {
  const now = new Date();
  document.getElementById("clock").textContent =
    now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  document.getElementById("date").textContent =
    now.toLocaleDateString([], { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}
setInterval(tickClock, 1000);
tickClock();

/* ── Info bar (pushed from Python via setInfo) ─────────── */
const WEATHER_ICONS = {
  clear: "☀️", mostly_clear: "🌤️", cloudy: "☁️", fog: "🌫️",
  drizzle: "🌦️", rain: "🌧️", snow: "❄️", thunder: "⛈️", unknown: "⛅",
};
function setInfo(info) {
  if (info.battery != null) {
    document.getElementById("battery-text").textContent = info.battery + "%";
    document.getElementById("battery-icon").textContent = info.charging ? "⚡" : "🔋";
    document.getElementById("battery").classList.toggle("low", info.battery <= 20 && !info.charging);
  }
  if (info.temp != null) {
    document.getElementById("weather-text").textContent = Math.round(info.temp) + "°C";
    document.getElementById("weather-icon").textContent = WEATHER_ICONS[info.condition] || WEATHER_ICONS.unknown;
  }
  if (info.location) {
    document.getElementById("location-text").textContent = info.location;
  }
}

/* ── Transcript ────────────────────────────────────────── */
function addChat(role, text) {
  const chat = document.getElementById("chat");
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.textContent = text;
  chat.appendChild(div);
  while (chat.children.length > 60) chat.removeChild(chat.firstChild);
  chat.scrollTop = chat.scrollHeight;
}

/* ── Command box ───────────────────────────────────────── */
function submit() {
  const box = document.getElementById("cmd");
  const text = box.value.trim();
  if (!text) return;
  box.value = "";
  if (window.pywebview) pywebview.api.submit_command(text);
}
document.getElementById("cmd").addEventListener("keydown", e => { if (e.key === "Enter") submit(); });
document.getElementById("send").addEventListener("click", submit);
document.getElementById("stopbtn").addEventListener("click", () => {
  if (window.pywebview) pywebview.api.submit_command("stop");
});
window.addEventListener("keydown", e => {
  if (e.key === "Escape" && window.pywebview) pywebview.api.submit_command("stop");
  if (e.target.tagName !== "INPUT" && e.key.length === 1) document.getElementById("cmd").focus();
});

/* ── Living orb ────────────────────────────────────────── */
const canvas = document.getElementById("orb");
const ctx = canvas.getContext("2d");
const CX = canvas.width / 2, CY = canvas.height / 2;
const BASE_R = canvas.width * 0.21;

let orbState = "idle";      // idle | listening | thinking | speaking
let micLevel = 0;           // latest RMS from Python (0..1)
let displayLevel = 0;       // smoothed
let t = 0;

const COLORS = {
  idle:      { core: "#0e7490", glow: "rgba(14,116,144,0.55)",  ring: "rgba(34,211,238,0.28)" },
  listening: { core: "#22d3ee", glow: "rgba(34,211,238,0.75)",  ring: "rgba(34,211,238,0.55)" },
  thinking:  { core: "#fbbf24", glow: "rgba(251,191,36,0.6)",   ring: "rgba(251,191,36,0.45)" },
  speaking:  { core: "#60a5fa", glow: "rgba(96,165,250,0.7)",   ring: "rgba(96,165,250,0.5)"  },
};

function setOrbState(s) {
  orbState = s;
  const label = document.getElementById("status-label");
  label.textContent = s.toUpperCase();
  label.className = s;
}
function setOrbLevel(v) { micLevel = Math.min(1, v); }

/* Wobbly blob path: radius modulated by layered sine noise + audio level. */
function blobPath(r, wobble, speed) {
  ctx.beginPath();
  const N = 90;
  for (let i = 0; i <= N; i++) {
    const a = (i / N) * Math.PI * 2;
    const n = Math.sin(a * 3 + t * speed) * 0.5
            + Math.sin(a * 5 - t * speed * 1.4) * 0.3
            + Math.sin(a * 8 + t * speed * 0.7) * 0.2;
    const rr = r * (1 + n * wobble);
    const x = CX + Math.cos(a) * rr;
    const y = CY + Math.sin(a) * rr;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.closePath();
}

function draw() {
  t += 0.016;
  const c = COLORS[orbState] || COLORS.idle;

  // Target energy: mic level while listening; synthetic pulse while speaking;
  // gentle breathing when idle; fast shimmer when thinking.
  let target = 0;
  if (orbState === "listening")      target = micLevel;
  else if (orbState === "speaking")  target = 0.35 + 0.3 * Math.abs(Math.sin(t * 6) * Math.sin(t * 2.3));
  else if (orbState === "thinking")  target = 0.25 + 0.1 * Math.sin(t * 9);
  else                               target = 0.08 + 0.05 * Math.sin(t * 1.5);
  displayLevel += (target - displayLevel) * 0.12;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const r = BASE_R * (1 + displayLevel * 0.45);

  // Outer glow
  const glow = ctx.createRadialGradient(CX, CY, r * 0.2, CX, CY, r * 2.4);
  glow.addColorStop(0, c.glow);
  glow.addColorStop(1, "transparent");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Rotating outer ring
  ctx.save();
  ctx.translate(CX, CY);
  ctx.rotate(t * (orbState === "thinking" ? 1.4 : 0.3));
  ctx.translate(-CX, -CY);
  ctx.strokeStyle = c.ring;
  ctx.lineWidth = 1.5;
  ctx.setLineDash([26, 14]);
  ctx.beginPath();
  ctx.arc(CX, CY, r * 1.55, 0, Math.PI * 2);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.restore();

  // Wobbly translucent halo blob
  blobPath(r * 1.18, 0.06 + displayLevel * 0.1, 1.2);
  ctx.fillStyle = c.glow.replace(/[\d.]+\)$/, "0.12)");
  ctx.fill();

  // Core blob
  blobPath(r, 0.04 + displayLevel * 0.12, 1.6);
  const core = ctx.createRadialGradient(CX - r * 0.25, CY - r * 0.3, r * 0.1, CX, CY, r * 1.15);
  core.addColorStop(0, "#eafcff");
  core.addColorStop(0.35, c.core);
  core.addColorStop(1, "rgba(3,10,20,0.85)");
  ctx.fillStyle = core;
  ctx.fill();

  // Inner highlight
  ctx.beginPath();
  ctx.arc(CX - r * 0.28, CY - r * 0.32, r * 0.32, 0, Math.PI * 2);
  const hl = ctx.createRadialGradient(CX - r * 0.28, CY - r * 0.32, 0, CX - r * 0.28, CY - r * 0.32, r * 0.32);
  hl.addColorStop(0, "rgba(255,255,255,0.35)");
  hl.addColorStop(1, "transparent");
  ctx.fillStyle = hl;
  ctx.fill();

  requestAnimationFrame(draw);
}
draw();
setOrbState("idle");
