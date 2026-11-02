(function () {
  const messages = document.getElementById("messages");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("message-input");
  const sendButton = document.getElementById("send-button");
  const statusBadge = document.getElementById("server-status");
  let session = null;

  try {
    session = JSON.parse(localStorage.getItem("autonet-session") || "null");
  } catch (_) {}

  if (!session || !/^\d{5}$/.test(session.id || "") || !session.team) {
    session = { id: "30101", team: "CAR2" };
    try { localStorage.setItem("autonet-session", JSON.stringify(session)); } catch (_) {}
  }

  document.getElementById("student-info").textContent = `학번 ${session.id} · ${session.team}`;

  function addMessage(role, text) {
    const empty = messages.querySelector(".empty");
    if (empty) empty.remove();
    const element = document.createElement("div");
    element.className = `message ${role}`;
    element.textContent = text;
    messages.appendChild(element);
    messages.scrollTop = messages.scrollHeight;
  }

  function findOfflineAnswer(query) {
    const seed = window.AUTONET_SEED || [];
    const tokens = query.toLowerCase().split(/[^0-9a-zA-Z가-힣]+/).filter(t => t.length >= 2);
    let best = null;
    let bestScore = -1;
    for (const item of seed) {
      const hay = `${item.question} ${item.answer}`.toLowerCase();
      let score = 0;
      for (const tok of tokens) {
        if (hay.includes(tok)) score += 1;
      }
      if (score > bestScore) {
        bestScore = score;
        best = item;
      }
    }
    if (best && bestScore > 0) {
      return best.answer;
    }
    return `[네트워크프로그래밍 실습 도우미 · ${session.team}]\n질문하신 "${query}"에 대해 확인해보세요:\n1) 패킷 헤더(SOF·VER·TYPE·SEQ·LEN·PAYLOAD·CRC16)의 필드 길이와 바이트 순서가 명세와 일치하는지 점검합니다.\n2) AUTO-NET LAB 시뮬레이터에서 10회 반복 측정한 평균 RTT와 손실률(SEQ 건너뜀)을 비교하여 안전 정지 조건(300ms 초과 시 STOP)을 검증하세요.`;
  }

  async function init() {
    const seed = window.AUTONET_SEED || [];
    if (location.protocol === "file:" || location.hostname.endsWith("github.io")) {
      statusBadge.textContent = `실습 기록 ${seed.length}건 연동 완료 · 즉시 질문 가능`;
      const myRecords = seed.filter(r => r.studentId === session.id).slice(0, 3);
      for (const r of myRecords) {
        addMessage("user", r.question);
        addMessage("assistant", r.answer);
      }
      return;
    }
    try {
      const response = await fetch("/api/health", { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error();
      statusBadge.textContent = `기존 기록 ${data.seedRecords}건 연결 · 사용 가능`;
    } catch (_) {
      statusBadge.textContent = `실습 기록 ${seed.length}건 연동 완료 (오프라인 데모 모드)`;
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    addMessage("user", message);
    input.value = "";
    input.disabled = true;
    sendButton.disabled = true;
    sendButton.textContent = "답변 중";
    try {
      if (location.protocol !== "file:" && !location.hostname.endsWith("github.io")) {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ studentId: session.id, team: session.team, message }),
        });
        if (response.ok) {
          const data = await response.json();
          addMessage("assistant", data.answer);
          return;
        }
      }
      await new Promise(r => setTimeout(r, 250));
      addMessage("assistant", findOfflineAnswer(message));
    } catch (_) {
      addMessage("assistant", findOfflineAnswer(message));
    } finally {
      input.disabled = false;
      sendButton.disabled = false;
      sendButton.textContent = "전송";
      input.focus();
    }
  });

  init();
})();
