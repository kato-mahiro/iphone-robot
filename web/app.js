(() => {
  "use strict";

  const SAMPLE_RATE = 16000;
  const SILENCE_MS = 900;
  const FINAL_WAIT_MS = 3000;
  const $ = (id) => document.getElementById(id);
  const button = $("talk-button");
  const panel = document.querySelector(".face-panel");
  const stateLabel = $("state-label");
  const transcript = $("transcript");
  const hint = $("hint");
  const connectionDot = $("connection-dot");
  const connectionLabel = $("connection-label");
  const debugLog = $("debug-log");
  const bellyMain = $("belly-main");
  const diagnostics = $("diagnostics");

  let audioContext;
  let mediaStream;
  let source;
  let processor;
  let socket;
  let isTalking = false;
  let stopping = false;
  let silenceTimer;
  let closeTimer;
  let audioChunks = 0;
  let startAttempt = 0;
  let receivedFinalThisPress = false;

  const wsUrl = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ingest`;
  const events = new EventSource("/events");

  function log(message) {
    const time = new Date().toLocaleTimeString("ja-JP", { hour12: false });
    const line = `${time} ${message}`;
    debugLog.textContent += `${line}\n`;
    debugLog.scrollTop = debugLog.scrollHeight;
    fetch(`/client-log?message=${encodeURIComponent(line)}`, { method: "POST", keepalive: true }).catch(() => {});
  }

  function setConnection(connected, label) {
    connectionDot.classList.toggle("ready", connected);
    connectionLabel.textContent = label;
  }

  function setState(label, text, mode = "") {
    stateLabel.textContent = label;
    transcript.textContent = text;
    panel.classList.toggle("listening", mode === "listening");
  }

  function closeSocket() {
    log(`WSSを閉じます（音声 ${audioChunks} chunks）`);
    socket?.close();
    socket = null;
    stopping = false;
    setConnection(false, "待機中");
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
    if (socket?.readyState !== WebSocket.OPEN) {
      log(`無音送信失敗: WSS state=${socket?.readyState ?? "なし"}`);
      return;
    }
    socket.send(new ArrayBuffer(Math.round(SAMPLE_RATE * (SILENCE_MS / 1000)) * 2));
    log(`${SILENCE_MS}msの無音を送信`);
  }

  function handleEvent(event) {
    let data;
    try { data = JSON.parse(event.data); } catch {
      log("受信JSONを解析できません");
      return;
    }
    if (data.type !== "partial") log(`受信: ${data.type}${data.text ? `「${data.text}」` : ""}`);
    if (data.type === "ready") {
      setConnection(true, "接続中");
      hint.textContent = "押している間に話してください";
    } else if (data.type === "partial") {
      setState("聞き取り中…", "話しかけてね", "listening");
    } else if (data.type === "final" || data.type === "refine") {
      receivedFinalThisPress = true;
      clearTimeout(closeTimer);
      setState("聞こえたよ", data.text || "");
      hint.textContent = data.type === "final" ? "もう一度話すと続けられます" : hint.textContent;
      if (stopping) closeTimer = setTimeout(closeSocket, 300);
    }
  }

  events.addEventListener("open", () => log("文字起こし結果の受信接続成功"));
  events.addEventListener("message", handleEvent);
  events.addEventListener("error", () => log("文字起こし結果の受信接続エラー"));

  async function openSocket() {
    log(`WSS接続開始: ${wsUrl}`);
    socket = new WebSocket(wsUrl);
    socket.binaryType = "arraybuffer";
    await new Promise((resolve, reject) => {
      socket.addEventListener("open", () => {
        log("WSS接続成功");
        resolve();
      }, { once: true });
      socket.addEventListener("error", () => reject(new Error("Hayamimiへ接続できません")), { once: true });
    });
    socket.addEventListener("close", (event) => {
      log(`WSS切断: code=${event.code}`);
      socket = null;
      setConnection(false, "未接続");
    });
    socket.addEventListener("message", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "ready") {
          log("音声送信準備完了");
          setConnection(true, "接続中");
        }
      } catch {}
    });
    socket.send(JSON.stringify({ sr: SAMPLE_RATE, format: "pcm_s16le", channels: 1 }));
  }

  async function startTalking(event) {
    event?.preventDefault();
    if (event?.pointerId != null) button.setPointerCapture(event.pointerId);
    log(`${event?.type || "操作"}: 録音開始要求`);
    if (isTalking || stopping) {
      log(`開始を無視: isTalking=${isTalking}, stopping=${stopping}`);
      return;
    }
    isTalking = true;
    const attempt = ++startAttempt;
    audioChunks = 0;
    receivedFinalThisPress = false;
    clearTimeout(closeTimer);
    button.classList.add("pressed");
    setState("聞いてるよ", "話しかけてね", "listening");
    hint.textContent = "話し終わったらボタンを離してください";
    try {
      if (!audioContext) audioContext = new AudioContext();
      const resume = audioContext.state === "suspended" ? audioContext.resume() : Promise.resolve();
      let microphone = Promise.resolve(mediaStream);
      if (!mediaStream) {
        log("マイク許可を要求");
        microphone = navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      }
      [mediaStream] = await Promise.all([microphone, resume]);
      log(`マイク取得成功 / AudioContext: ${audioContext.state}, ${audioContext.sampleRate}Hz`);
      if (!isTalking || attempt !== startAttempt) {
        log("録音開始をキャンセル: 準備中にボタンが離されました");
        return;
      }
      await openSocket();
      if (!isTalking || attempt !== startAttempt) {
        log("録音開始をキャンセル: WSS接続中にボタンが離されました");
        return;
      }
      source = audioContext.createMediaStreamSource(mediaStream);
      processor = audioContext.createScriptProcessor(2048, 1, 1);
      processor.onaudioprocess = (audioEvent) => {
        if (!isTalking || socket?.readyState !== WebSocket.OPEN) return;
        const mono = audioEvent.inputBuffer.getChannelData(0);
        socket.send(floatToPcm16(downsample(mono, audioContext.sampleRate)));
        audioChunks += 1;
        if (audioChunks === 1 || audioChunks % 25 === 0) log(`音声送信: ${audioChunks} chunks`);
      };
      source.connect(processor);
      processor.connect(audioContext.destination);
    } catch (error) {
      log(`エラー: ${error.name || "Error"}: ${error.message || error}`);
      if (attempt !== startAttempt) return;
      isTalking = false;
      button.classList.remove("pressed");
      setState("マイクを使えません", "設定を確認して、もう一度試してね");
      hint.textContent = error.message || "マイクの使用を許可してください";
      setConnection(false, "未接続");
    }
  }

  function stopTalking(event) {
    event?.preventDefault();
    log(`${event?.type || "操作"}: 録音終了要求`);
    if (!isTalking) {
      log("終了を無視: 録音中ではありません");
      return;
    }
    isTalking = false;
    button.classList.remove("pressed");
    if (source) source.disconnect();
    if (processor) { processor.disconnect(); processor.onaudioprocess = null; }
    if (audioChunks === 0) {
      startAttempt += 1;
      socket?.close();
      socket = null;
      stopping = false;
      setState("まだ準備中でした", "もう一度、押したまま話してね");
      hint.textContent = "マイク準備後に話し始めます";
      return;
    }
    stopping = true;
    sendSilence();
    clearTimeout(closeTimer);
    if (receivedFinalThisPress) {
      closeTimer = setTimeout(closeSocket, 300);
    } else {
      setState("認識中…", "文字起こしを待っています");
      hint.textContent = "そのまま少し待ってください";
      closeTimer = setTimeout(() => {
        setState("聞き取れませんでした", "もう一度話してね");
        closeSocket();
      }, FINAL_WAIT_MS);
    }
  }

  button.addEventListener("pointerdown", startTalking);
  button.addEventListener("pointerup", stopTalking);
  button.addEventListener("pointercancel", stopTalking);
  button.addEventListener("pointerleave", (event) => { if (isTalking) stopTalking(event); });
  button.addEventListener("keydown", (event) => { if ((event.key === "Enter" || event.key === " ") && !event.repeat) startTalking(event); });
  button.addEventListener("keyup", (event) => { if (event.key === "Enter" || event.key === " ") stopTalking(event); });
  document.querySelectorAll(".belly-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const showLog = tab.dataset.view === "log";
      bellyMain.hidden = showLog;
      diagnostics.hidden = !showLog;
      document.querySelectorAll(".belly-tab").forEach((item) => item.classList.toggle("selected", item === tab));
      if (showLog) debugLog.scrollTop = debugLog.scrollHeight;
    });
  });
  window.addEventListener("beforeunload", () => {
    clearTimeout(silenceTimer);
    clearTimeout(closeTimer);
    socket?.close();
    mediaStream?.getTracks().forEach((track) => track.stop());
  });
  setConnection(false, "待機中");
  log(`起動: secure=${window.isSecureContext}, mediaDevices=${Boolean(navigator.mediaDevices)}`);
})();
