(() => {
  "use strict";

  const SAMPLE_RATE = 16000;
  const SILENCE_MS = 900;
  const FINAL_WAIT_MS = 3000;
  const EMOTION_DECAY_MS = 15000;
  const EMOTION_VISIBLE_THRESHOLD = 0.15;
  const BEEP_COOLDOWN_MS = 800;
  const $ = (id) => document.getElementById(id);
  const button = $("talk-button");
  const panel = document.querySelector(".face-panel");
  const stateLabel = $("state-label");
  const transcript = $("transcript");
  const hint = $("hint");
  const connectionDot = $("connection-dot");
  const connectionLabel = $("connection-label");
  const thinkingIndicator = $("thinking-indicator");
  const debugLog = $("debug-log");
  const bellyMain = $("belly-main");
  const diagnostics = $("diagnostics");
  const eyeContexts = [$("eye-left"), $("eye-right")].map((canvas) => canvas.getContext("2d"));
  const emotionLabels = { joy: "喜", anger: "怒", sadness: "哀", fun: "楽" };
  const emotionColors = { joy: "#b7ff5a", anger: "#ff4b45", sadness: "#57a8ff", fun: "#ffd84a" };
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  let audioContext;
  let mediaStream;
  let source;
  let processor;
  let socket;
  let isTalking = false;
  let stopping = false;
  let silenceTimer;
  let closeTimer;
  let beepTimer;
  let audioChunks = 0;
  let startAttempt = 0;
  let receivedFinalThisPress = false;
  let finalParts = [];
  let emotionRequest = 0;
  let responseRequest = 0;
  let responseController;
  let isResponding = false;
  let isThinking = false;
  let faceMode = "neutral";
  let faceEmotion = "";
  let faceArousal = 0;
  let faceValence = 0;
  let faceStartedAt = 0;
  let lastBeepAt = 0;
  let lastTypingBeepAt = 0;
  let activeEmotion = "";

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

  function setFace(mode, emotion = "", arousal = 0, valence = 0) {
    if (mode !== "emotion") clearTimeout(beepTimer);
    faceMode = mode;
    faceEmotion = emotion;
    faceArousal = Math.max(0, Math.min(1, arousal));
    faceValence = Math.max(-1, Math.min(1, valence));
    faceStartedAt = performance.now();
    panel.style.setProperty("--eye-glow", `${emotionColors[emotion] || "#55f6c7"}88`);
  }

  function setThinking(thinking) {
    isThinking = thinking;
    thinkingIndicator.hidden = !thinking;
    if (thinking) clearTimeout(beepTimer);
  }

  function drawSprite(context, rows, color, accent = "#eafffb") {
    context.clearRect(0, 0, 8, 8);
    rows.forEach((row, y) => [...row].forEach((pixel, x) => {
      if (pixel === ".") return;
      context.fillStyle = pixel === "+" ? accent : color;
      context.fillRect(x, y, 1, 1);
    }));
  }

  function neutralSprite(now) {
    const blink = !reducedMotion && now % 4200 > 4020;
    return blink
      ? ["........", "........", "........", ".######.", "........", "........", "........", "........"]
      : ["........", "..####..", ".######.", ".##++##.", ".##++##.", ".######.", "..####..", "........"];
  }

  function faceSprite(side, now, arousal = faceArousal) {
    const speed = 1 + arousal * 2;
    const tick = reducedMotion ? 0 : Math.floor(now / (180 / speed));
    if (faceMode === "listening") {
      const size = tick % 4;
      return Array.from({ length: 8 }, (_, y) => Array.from({ length: 8 }, (_, x) => {
        const distance = Math.max(Math.abs(x - 3.5), Math.abs(y - 3.5));
        return Math.abs(distance - (size + .5)) < .3 ? "#" : ".";
      }).join(""));
    }
    if (faceMode === "emotion" && faceEmotion === "joy") {
      const smile = ["........", "...##...", "..#..#..", ".#....#.", "#......#", "........", side === 0 ? "+......." : ".......+", "........"];
      return tick % 4 < 2 ? smile : [...smile.slice(1), "........"];
    }
    if (faceMode === "emotion" && faceEmotion === "anger") {
      const left = ["##......", "####....", "..####..", "...###..", "...###..", "...###..", "........", "........"];
      const rows = side === 0 ? left : left.map((row) => [...row].reverse().join(""));
      if (!reducedMotion && tick % 2) return rows.map((row) => side === 0 ? `.${row.slice(0, 7)}` : `${row.slice(1)}.`);
      return rows;
    }
    if (faceMode === "emotion" && faceEmotion === "sadness") {
      const left = ["......##", "....####", "..####..", "..###...", "..###...", "........", "........", "........"];
      const rows = side === 0 ? left : left.map((row) => [...row].reverse().join(""));
      if (!reducedMotion) rows[5 + (tick % 3)] = side === 0 ? "...#...." : "....#...";
      return rows;
    }
    if (faceMode === "emotion" && faceEmotion === "fun") {
      if ((tick >> 2) % 2 === side) return ["........", "........", "........", ".######.", "........", "........", "........", "........"];
      return ["...+....", "...#....", ".#.#.#..", "..###...", "#######.", "..###...", ".#.#.#..", "...#...."];
    }
    return neutralSprite(now);
  }

  function currentEmotionScores(now = performance.now()) {
    const remaining = Math.max(0, 1 - (now - faceStartedAt) / EMOTION_DECAY_MS);
    return { remaining, valence: faceValence * remaining, arousal: faceArousal * remaining };
  }

  function renderFace(now) {
    const color = faceMode === "emotion" ? emotionColors[faceEmotion] : "#55f6c7";
    if (faceMode === "emotion") {
      const scores = currentEmotionScores(now);
      if (scores.remaining <= EMOTION_VISIBLE_THRESHOLD) {
        setFace("neutral");
        stateLabel.textContent = "ニュートラル  V=0.00 A=0.00";
        log("感情: ニュートラル");
      } else {
        stateLabel.textContent = `${isThinking ? "考え中… / " : ""}気持ち: ${emotionLabels[faceEmotion]} V=${scores.valence >= 0 ? "+" : ""}${scores.valence.toFixed(2)} A=${scores.arousal.toFixed(2)}`;
        eyeContexts.forEach((context, side) => drawSprite(context, faceSprite(side, now, scores.arousal), color));
      }
    }
    if (faceMode !== "emotion") eyeContexts.forEach((context, side) => drawSprite(context, faceSprite(side, now), color));
    requestAnimationFrame(renderFace);
  }

  function playEmotionBeep(emotion, arousal) {
    if (!audioContext || Date.now() - lastBeepAt < BEEP_COOLDOWN_MS) return;
    const patterns = {
      joy: [[0, 523, .11, "triangle"], [.12, 659, .15, "triangle"]],
      anger: [[0, 180, .09, "square"], [.11, 140, .12, "square"]],
      sadness: [[0, 330, .18, "triangle"], [.2, 247, .26, "triangle"]],
      fun: [[0, 440, .07, "square"], [.08, 660, .07, "square"], [.16, 880, .12, "square"]],
    };
    const notes = patterns[emotion];
    if (!notes) return;
    lastBeepAt = Date.now();
    const play = () => notes.forEach(([delay, frequency, duration, type]) => {
      const oscillator = audioContext.createOscillator();
      const gain = audioContext.createGain();
      const start = audioContext.currentTime + delay;
      oscillator.type = type;
      oscillator.frequency.value = frequency * (.9 + arousal * .2);
      gain.gain.setValueAtTime(.0001, start);
      gain.gain.exponentialRampToValueAtTime(.75 + arousal * .25, start + .015);
      gain.gain.exponentialRampToValueAtTime(.0001, start + duration);
      oscillator.connect(gain).connect(audioContext.destination);
      oscillator.start(start);
      oscillator.stop(start + duration + .02);
    });
    if (audioContext.state === "suspended") audioContext.resume().then(play).catch(() => {}); else play();
  }

  function scheduleEmotionBeeps(emotion, request) {
    clearTimeout(beepTimer);
    const arousal = currentEmotionScores().arousal;
    const delay = 1000 + Math.random() * (2500 - arousal * 1000);
    beepTimer = setTimeout(() => {
      if (request !== emotionRequest || faceMode !== "emotion") return;
      playEmotionBeep(emotion, currentEmotionScores().arousal);
      scheduleEmotionBeeps(emotion, request);
    }, delay);
  }

  function playTypingBeep(index) {
    if (!audioContext || Date.now() - lastTypingBeepAt < 65) return;
    const sounds = {
      joy: [720, "triangle"],
      anger: [185, "square"],
      sadness: [300, "sine"],
      fun: [index % 2 ? 780 : 520, "square"],
    };
    const [frequency, type] = sounds[activeEmotion] || [440, "triangle"];
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();
    const start = audioContext.currentTime;
    oscillator.type = type;
    oscillator.frequency.value = frequency;
    gain.gain.setValueAtTime(.65, start);
    gain.gain.exponentialRampToValueAtTime(.0001, start + .045);
    oscillator.connect(gain).connect(audioContext.destination);
    oscillator.start(start);
    oscillator.stop(start + .05);
    lastTypingBeepAt = Date.now();
  }

  function setState(label, text, mode = "") {
    stateLabel.textContent = label;
    transcript.textContent = text;
    if (mode) setFace(mode);
  }

  async function showEmotion(text) {
    if (!text) return;
    const request = ++emotionRequest;
    const responseAtStart = responseRequest;
    setThinking(true);
    setState("気持ちを考え中…", text);
    try {
      const response = await fetch("/emotion", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "感情を判定できませんでした");
      if (request !== emotionRequest) return;
      activeEmotion = result.emotion;
      setFace("emotion", result.emotion, result.arousal, result.valence);
      if (!isResponding) setThinking(false);
      playEmotionBeep(result.emotion, result.arousal);
      if (!isResponding) scheduleEmotionBeeps(result.emotion, request);
      if (responseAtStart === responseRequest) setState(`気持ち: ${emotionLabels[result.emotion] || result.emotion}`, text);
      log(`感情: ${emotionLabels[result.emotion] || result.emotion} / V=${result.valence.toFixed(2)} A=${result.arousal.toFixed(2)}`);
    } catch (error) {
      if (request !== emotionRequest) return;
      if (responseAtStart === responseRequest) {
        setThinking(false);
        setFace("neutral");
        setState("気持ちを判定できませんでした", text);
      }
      log(`感情判定エラー: ${error.message || error}`);
    }
  }

  function closeSocket() {
    log(`WSSを閉じます（音声 ${audioChunks} chunks）`);
    socket?.close();
    socket = null;
    stopping = false;
    setConnection(false, "待機中");
  }

  async function respondToSpeech() {
    const text = finalParts.join(" ").trim();
    if (!text) return;
    const request = ++responseRequest;
    isResponding = true;
    responseController?.abort();
    responseController = new AbortController();
    clearTimeout(beepTimer);
    setThinking(true);
    setState("考え中…", "返事を考えています");
    hint.textContent = "もう少し待ってね";
    log(`応答入力: ${text}`);
    try {
      const response = await fetch("/response", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text }),
        signal: responseController.signal,
      });
      if (!response.ok || !response.body) throw new Error(await response.text() || "応答を生成できませんでした");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let answer = "";
      let index = 0;
      setState("ロボットの返事", "");
      while (true) {
        const { value, done } = await reader.read();
        const chunk = decoder.decode(value, { stream: !done });
        for (const character of chunk) {
          if (request !== responseRequest) return;
          if (!answer) setThinking(false);
          answer += character;
          transcript.textContent = answer;
          if (!/\s/.test(character)) playTypingBeep(index++);
          if (!reducedMotion) await new Promise((resolve) => setTimeout(resolve, 35));
        }
        if (done) break;
      }
      log(`ロボット応答: ${answer}`);
      isResponding = false;
      setThinking(false);
      hint.textContent = "ボタンを押して話を続けてね";
    } catch (error) {
      if (error.name === "AbortError" || request !== responseRequest) return;
      isResponding = false;
      setThinking(false);
      setFace("neutral");
      setState("返事を作れませんでした", "もう一度話しかけてね");
      hint.textContent = error.message || "応答サーバーを確認してください";
      log(`応答エラー: ${error.message || error}`);
    }
  }

  function finishPress() {
    closeSocket();
    respondToSpeech();
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
      if (data.type === "final" && data.text) finalParts.push(data.text);
      clearTimeout(closeTimer);
      setState("聞こえたよ", data.text || "");
      if (data.type === "final") showEmotion(data.text);
      hint.textContent = data.type === "final" ? "もう一度話すと続けられます" : hint.textContent;
      if (stopping) closeTimer = setTimeout(finishPress, 300);
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
    finalParts = [];
    activeEmotion = "";
    isResponding = false;
    setThinking(false);
    emotionRequest += 1;
    responseRequest += 1;
    responseController?.abort();
    clearTimeout(closeTimer);
    clearTimeout(beepTimer);
    setFace("listening");
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
      setFace("neutral");
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
      setFace("neutral");
      setState("まだ準備中でした", "もう一度、押したまま話してね");
      hint.textContent = "マイク準備後に話し始めます";
      return;
    }
    stopping = true;
    sendSilence();
    clearTimeout(closeTimer);
    if (receivedFinalThisPress) {
      closeTimer = setTimeout(finishPress, 300);
    } else {
      setState("認識中…", "文字起こしを待っています");
      setThinking(true);
      hint.textContent = "そのまま少し待ってください";
      closeTimer = setTimeout(() => {
        setState("聞き取れませんでした", "もう一度話してね");
        setThinking(false);
        setFace("neutral");
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
    clearTimeout(beepTimer);
    responseController?.abort();
    socket?.close();
    mediaStream?.getTracks().forEach((track) => track.stop());
  });
  setConnection(false, "待機中");
  requestAnimationFrame(renderFace);
  log(`起動: secure=${window.isSecureContext}, mediaDevices=${Boolean(navigator.mediaDevices)}`);
})();
