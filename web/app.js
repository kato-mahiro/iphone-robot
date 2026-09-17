(() => {
  "use strict";

  const SAMPLE_RATE = 16000;
  const SILENCE_MS = 900;
  const FINAL_WAIT_MS = 1800;
  const $ = (id) => document.getElementById(id);
  const button = $("talk-button");
  const panel = document.querySelector(".face-panel");
  const stateLabel = $("state-label");
  const transcript = $("transcript");
  const hint = $("hint");
  const connectionDot = $("connection-dot");
  const connectionLabel = $("connection-label");
  const wsInput = $("ws-url");

  let audioContext;
  let mediaStream;
  let source;
  let processor;
  let socket;
  let isTalking = false;
  let stopping = false;
  let silenceTimer;
  let closeTimer;

  const defaultWs = `${location.protocol === "https:" ? "wss" : "ws"}://${location.hostname}:8766/ingest`;
  wsInput.value = localStorage.getItem("robot-ws-url") || defaultWs;

  function setConnection(connected, label) {
    connectionDot.classList.toggle("ready", connected);
    connectionLabel.textContent = label;
  }

  function setState(label, text, mode = "") {
    stateLabel.textContent = label;
    transcript.textContent = text;
    panel.classList.toggle("listening", mode === "listening");
  }

  function floatToPcm16(samples) {
    const pcm = new Int16Array(samples.length);
    for (let i = 0; i < samples.length; i += 1) {
      const value = Math.max(-1, Math.min(1, samples[i]));
      pcm[i] = value < 0 ? value * 0x8000 : value * 0x7fff;
    }
    return pcm.buffer;
  }

  function downsample(samples, inputRate) {
    if (inputRate === SAMPLE_RATE) return samples;
    const ratio = inputRate / SAMPLE_RATE;
    const outputLength = Math.round(samples.length / ratio);
    const output = new Float32Array(outputLength);
    for (let i = 0; i < outputLength; i += 1) {
      const position = i * ratio;
      const left = Math.floor(position);
      const right = Math.min(left + 1, samples.length - 1);
      const weight = position - left;
      output[i] = samples[left] * (1 - weight) + samples[right] * weight;
    }
    return output;
  }

  function sendSilence() {
    if (socket?.readyState !== WebSocket.OPEN) return;
    socket.send(new ArrayBuffer(Math.round(SAMPLE_RATE * (SILENCE_MS / 1000)) * 2));
  }

  function handleEvent(event) {
    let data;
    try { data = JSON.parse(event.data); } catch { return; }
    if (data.type === "ready") {
      setConnection(true, "接続中");
      hint.textContent = "押している間に話してください";
    } else if (data.type === "partial") {
      setState("聞き取り中…", data.text || "", "listening");
    } else if (data.type === "final" || data.type === "refine") {
      setState("聞こえたよ", data.text || "");
      hint.textContent = data.type === "final" ? "もう一度話すと続けられます" : hint.textContent;
    }
  }

  async function openSocket() {
    const url = wsInput.value.trim();
    if (!url) throw new Error("WebSocketの接続先が空です");
    socket = new WebSocket(url);
    socket.binaryType = "arraybuffer";
    await new Promise((resolve, reject) => {
      socket.addEventListener("open", resolve, { once: true });
      socket.addEventListener("error", () => reject(new Error("Hayamimiへ接続できません")), { once: true });
    });
    socket.addEventListener("message", handleEvent);
    socket.addEventListener("close", () => setConnection(false, "未接続"));
    socket.send(JSON.stringify({ sr: SAMPLE_RATE, format: "pcm_s16le", channels: 1 }));
  }

  async function startTalking(event) {
    event?.preventDefault();
    if (isTalking || stopping) return;
    isTalking = true;
    button.classList.add("pressed");
    setState("聞いてるよ", "話しかけてね", "listening");
    hint.textContent = "話し終わったらボタンを離してください";
    try {
      if (!audioContext) audioContext = new AudioContext();
      if (audioContext.state === "suspended") await audioContext.resume();
      if (!mediaStream) mediaStream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      await openSocket();
      source = audioContext.createMediaStreamSource(mediaStream);
      processor = audioContext.createScriptProcessor(2048, 1, 1);
      processor.onaudioprocess = (audioEvent) => {
        if (!isTalking || socket?.readyState !== WebSocket.OPEN) return;
        const mono = audioEvent.inputBuffer.getChannelData(0);
        socket.send(floatToPcm16(downsample(mono, audioContext.sampleRate)));
      };
      source.connect(processor);
      processor.connect(audioContext.destination);
    } catch (error) {
      isTalking = false;
      button.classList.remove("pressed");
      setState("マイクを使えません", "設定を確認して、もう一度試してね");
      hint.textContent = error.message || "マイクの使用を許可してください";
      setConnection(false, "未接続");
    }
  }

  function stopTalking(event) {
    event?.preventDefault();
    if (!isTalking) return;
    isTalking = false;
    stopping = true;
    button.classList.remove("pressed");
    if (source) source.disconnect();
    if (processor) { processor.disconnect(); processor.onaudioprocess = null; }
    sendSilence();
    setState("考え中…", "ちゃんと聞こえたかな？");
    hint.textContent = "返事を考えています";
    clearTimeout(closeTimer);
    closeTimer = setTimeout(() => {
      socket?.close();
      socket = null;
      stopping = false;
      setConnection(false, "待機中");
    }, FINAL_WAIT_MS);
  }

  button.addEventListener("pointerdown", startTalking);
  button.addEventListener("pointerup", stopTalking);
  button.addEventListener("pointercancel", stopTalking);
  button.addEventListener("pointerleave", (event) => { if (isTalking) stopTalking(event); });
  button.addEventListener("keydown", (event) => { if ((event.key === "Enter" || event.key === " ") && !event.repeat) startTalking(event); });
  button.addEventListener("keyup", (event) => { if (event.key === "Enter" || event.key === " ") stopTalking(event); });
  $("save-settings").addEventListener("click", () => {
    localStorage.setItem("robot-ws-url", wsInput.value.trim());
    hint.textContent = "接続先を保存しました";
  });
  window.addEventListener("beforeunload", () => {
    clearTimeout(silenceTimer);
    clearTimeout(closeTimer);
    socket?.close();
    mediaStream?.getTracks().forEach((track) => track.stop());
  });
  setConnection(false, "待機中");
})();
