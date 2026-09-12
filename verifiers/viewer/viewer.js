"use strict";
const $ = id => document.getElementById(id);
let token = new URLSearchParams(location.hash.slice(1)).get("token") || "";
history.replaceState(null, "", location.pathname);
let frame = null, interactive = false, busy = false, polling = false, blobUrl = null, pointer = null;
let modeKnown = false, publicReadonly = false;
const api = async (path, options = {}) => {
  const response = await fetch(path, {cache:"no-store", ...options,
    headers:{...(token ? {Authorization:"Bearer " + token} : {}), ...(options.headers || {})}});
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.error || `Request failed (${response.status})`);
  }
  return response;
};
async function refresh() {
  if (polling) return;
  polling = true;
  try {
    if (!modeKnown) {
      const mode = await (await api("/api/viewer-mode")).json();
      publicReadonly = mode.public_readonly === true;
      modeKnown = true;
      $("access-note").textContent = publicReadonly ? "Public read-only viewing: share this link with anyone. No token is needed. The link closes with its session." : "Private viewing: do not share the token. The link closes with its session.";
    }
    if (!publicReadonly && !token) {
      $("login").hidden = false;
      $("connection").textContent = "Access token required";
      return;
    }
    const state = await (await api("/api/status")).json();
    $("login").hidden = true;
    $("connection").textContent = state.test_fixture ? "OFFLINE TEST · not live" : state.connected ? "LIVE · connected" : "STALE / reconnecting";
    $("connection").className = "pill " + (state.connected ? "good" : "bad");
    $("source").textContent = state.label + " · real Android captures · session-scoped connection";
    $("age").textContent = state.frame_age_seconds === null ? "No frame received" : `Frame age: ${state.frame_age_seconds}s`;
    $("runtime-location").textContent = state.local_readiness ? "LOCAL KVM RUNTIME" : "PRIME RUNTIME";
    $("mode").textContent = state.local_readiness ? "Read-only readiness check — NOT AN EVALUATION. No model is running." :
      state.interactive ? "Manual inspection session — not an evaluation." : "Read-only Prime session — human input is locked. Check the session label for evaluation status.";
    if (state.local_readiness) {
      $("access-note").textContent = "Local read-only viewing: use an SSH tunnel to this server. This is not a public Prime endpoint. The link closes with the readiness session.";
    }
    interactive = !publicReadonly && state.interactive && state.connected;
    $("controls").hidden = publicReadonly || !state.interactive;
    $("screen").setAttribute("aria-disabled", String(!interactive));
    $("screen").classList.toggle("stale", !state.connected);
    if (state.frame_id && (!frame || state.frame_id !== frame.frame_id)) {
      const image = await (await api("/api/frame?frame_id=" + encodeURIComponent(state.frame_id))).blob();
      const nextUrl = URL.createObjectURL(image);
      $("screen").src = nextUrl;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
      blobUrl = nextUrl;
      frame = state;
      $("empty").hidden = true;
      $("dimensions").textContent = `${state.width} × ${state.height}`;
    }
    $("error").textContent = state.error || "";
  } catch (error) {
    interactive = false;
    $("connection").textContent = "Disconnected";
    $("connection").className = "pill bad";
    $("screen").classList.add("stale");
    $("error").textContent = error.message;
    $("login").hidden = publicReadonly;
  } finally { polling = false; }
}
async function control(action, capturedFrame = frame) {
  if (!interactive || !capturedFrame || busy) return;
  busy = true;
  try {
    await api("/api/control", {method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({...action, frame_id:capturedFrame.frame_id})});
    $("error").textContent = "Input sent. Waiting for the next Android frame…";
  } catch (error) { $("error").textContent = error.message; }
  finally { busy = false; }
}
function point(event, current = frame) {
  const box = $("screen").getBoundingClientRect();
  return {x:Math.max(0, Math.min(current.width-1, Math.floor((event.clientX-box.left)*current.width/box.width))),
          y:Math.max(0, Math.min(current.height-1, Math.floor((event.clientY-box.top)*current.height/box.height)))};
}
$("screen").addEventListener("pointerdown", event => {
  if (!interactive || !frame || busy) return;
  pointer = {...point(event), frame};
  $("screen").setPointerCapture(event.pointerId);
});
$("screen").addEventListener("pointerup", event => {
  if (!pointer) return;
  const start = pointer, end = point(event, start.frame); pointer = null;
  control(Math.hypot(end.x-start.x,end.y-start.y) < 18 ? {type:"tap",x:end.x,y:end.y} :
    {type:"swipe",x1:start.x,y1:start.y,x2:end.x,y2:end.y}, start.frame);
});
$("screen").addEventListener("pointercancel", () => { pointer = null; });
$("login").addEventListener("submit", event => { event.preventDefault(); token = $("token").value.trim(); $("token").value=""; refresh(); });
$("back").addEventListener("click", () => control({type:"back"}));
$("refresh").addEventListener("click", refresh);
$("send").addEventListener("click", () => control({type:"text",text:$("text").value}));
setInterval(refresh, 1500);
refresh();


