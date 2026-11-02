/* 교사연구회 에이전트 — 화면 동작
   흐름: 시작 → 영상 → 타이틀 → 채팅 */

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const S = {
  team: '',
  step: null,
  stepName: '',
  session: null,
  code: '',             // 접속 코드 (서버가 요구할 때만)
  project: null,        // 선택된 프로젝트 id
  projectName: '',
  tier: 'std',
  busy: false,
};

/* ══════════════════════════════════════════════
   타이틀 사운드

   영상 소리는 영상에서 끝난다. 로고로 끌고 오지 않는다.
   로고에는 짧은 임팩트 하나와 그 여운만 둔다.

   저음 사인파는 노트북 스피커에서 재생되지 않으므로
   왜곡으로 배음을 만들어 100~250Hz에 살을 붙인다.
   ══════════════════════════════════════════════ */
let AC = null;
let NOISE = null;

function wakeAudio() {
  try {
    if (!AC) AC = new (window.AudioContext || window.webkitAudioContext)();
    if (AC.state === 'suspended') AC.resume();
    if (!NOISE) {
      const n = Math.floor(AC.sampleRate * 1.5);
      NOISE = AC.createBuffer(1, n, AC.sampleRate);
      const d = NOISE.getChannelData(0);
      for (let i = 0; i < n; i++) d[i] = Math.random() * 2 - 1;
    }
  } catch (e) { AC = null; }
}

/* 살짝 뭉개는 왜곡 — 배음을 만들어 작은 스피커에서도 들리게 한다 */
function shaper(amount) {
  const n = 1024, c = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const x = (i * 2) / n - 1;
    c[i] = ((1 + amount) * x) / (1 + amount * Math.abs(x));
  }
  const ws = AC.createWaveShaper();
  ws.curve = c; ws.oversample = '2x';
  return ws;
}

/* 임팩트 — 클릭 + 배음 있는 몸통 + 서브 */
function sfxImpact(at, vol, pitch) {
  if (!AC) return;
  const t = AC.currentTime + at;
  const k = pitch || 1;
  const out = AC.createGain();
  out.gain.value = vol;
  out.connect(AC.destination);

  if (NOISE) {                       // 때리는 순간의 날
    const src = AC.createBufferSource(); src.buffer = NOISE;
    const hp = AC.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 2000;
    const g = AC.createGain();
    g.gain.setValueAtTime(0.7, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.05);
    src.connect(hp); hp.connect(g); g.connect(out);
    src.start(t); src.stop(t + 0.09);
  }

  const ws = shaper(8);              // 몸통
  const lp = AC.createBiquadFilter(); lp.type = 'lowpass';
  lp.frequency.setValueAtTime(3000 * k, t);
  lp.frequency.exponentialRampToValueAtTime(220 * k, t + 0.8);
  const bg = AC.createGain();
  bg.gain.setValueAtTime(0.0001, t);
  bg.gain.linearRampToValueAtTime(0.5, t + 0.015);
  bg.gain.exponentialRampToValueAtTime(0.0001, t + 1.1);
  ws.connect(lp); lp.connect(bg); bg.connect(out);
  [110, 147, 221].forEach((f, i) => {
    const o = AC.createOscillator();
    o.type = 'sawtooth';
    o.frequency.setValueAtTime(f * 1.9 * k, t);
    o.frequency.exponentialRampToValueAtTime(f * 0.62 * k, t + 0.5);
    o.detune.value = (i - 1) * 11;
    o.connect(ws); o.start(t); o.stop(t + 1.15);
  });

  const sub = AC.createOscillator(), sg = AC.createGain();   // 서브
  sub.type = 'sine';
  sub.frequency.setValueAtTime(96 * k, t);
  sub.frequency.exponentialRampToValueAtTime(42 * k, t + 0.6);
  sg.gain.setValueAtTime(0.0001, t);
  sg.gain.linearRampToValueAtTime(0.45, t + 0.02);
  sg.gain.exponentialRampToValueAtTime(0.0001, t + 1.4);
  sub.connect(sg); sg.connect(out);
  sub.start(t); sub.stop(t + 1.45);
}

/* 오토바이가 지나간다 — 쑤웅

   도플러를 흉내낸다.
     · 다가올 때는 음이 높고, 지나가면 뚝 떨어진다
     · 가까울수록 크고 밝고, 멀어지면 작고 먹먹해진다
     · 소리가 왼쪽에서 오른쪽으로 건너간다
   거리감은 1/(1+d²)로 잡았다. 실제로 소리가 줄어드는 방식이다. */
function sfxPassBy(at, dur, vol, f0) {
  if (!AC) return;
  const t = AC.currentTime + at;
  const N = 200, P = 0.44;          // P = 눈앞을 지나가는 지점
  const base = f0 || 148;
  const amp = new Float32Array(N), frq = new Float32Array(N);
  const cut = new Float32Array(N), pan = new Float32Array(N);
  const nz  = new Float32Array(N);

  for (let i = 0; i < N; i++) {
    const u = i / (N - 1), d = u - P;
    const near = 1 / (1 + Math.pow(d * 7.2, 2));            // 거리감
    const tail = d > 0 ? Math.exp(-d * 1.5) : 1;            // 멀어질수록 더 줄어듦
    amp[i] = Math.max(0.0001, near * tail);
    frq[i] = base * (1 + 0.26 * Math.tanh(-d * 11));        // 도플러
    cut[i] = 520 + 5600 * near;                             // 가까우면 밝게
    pan[i] = Math.tanh(d * 6.2);                            // 왼쪽 → 오른쪽
    nz[i]  = Math.max(0.0001, near * tail * 0.5);           // 바람·배기음
  }

  const out = AC.createGain(); out.gain.value = vol;
  let node = out;
  if (AC.createStereoPanner) {
    const pn = AC.createStereoPanner();
    pn.pan.setValueCurveAtTime(pan, t, dur);
    out.connect(pn); pn.connect(AC.destination);
  } else {
    out.connect(AC.destination);
  }

  // 엔진 — 디튠된 톱니를 왜곡시켜 배기음의 거친 배음을 만든다
  const ws = shaper(6);
  const lp = AC.createBiquadFilter(); lp.type = 'lowpass'; lp.Q.value = 0.9;
  lp.frequency.setValueCurveAtTime(cut, t, dur);
  const eg = AC.createGain();
  eg.gain.setValueCurveAtTime(amp, t, dur);
  ws.connect(lp); lp.connect(eg); eg.connect(node);

  [[1, 0], [1.004, 9], [0.996, -9], [2, 4], [0.5, 0]].forEach(([mul, det], i) => {
    const o = AC.createOscillator();
    o.type = i === 4 ? 'square' : 'sawtooth';
    o.detune.value = det;
    const f = new Float32Array(N);
    for (let k = 0; k < N; k++) f[k] = frq[k] * mul;
    o.frequency.setValueCurveAtTime(f, t, dur);
    const g = AC.createGain();
    g.gain.value = i === 4 ? 0.5 : (i === 3 ? 0.18 : 0.34);
    o.connect(g); g.connect(ws);
    o.start(t); o.stop(t + dur + 0.05);
  });

  // 엔진 떨림 — 실린더가 터지는 거친 맛
  const lfo = AC.createOscillator(), lg = AC.createGain();
  lfo.type = 'sawtooth'; lfo.frequency.value = 33;
  lg.gain.value = 0.22;
  lfo.connect(lg); lg.connect(eg.gain);
  lfo.start(t); lfo.stop(t + dur);

  // 바람 — 스쳐 지나가는 소리
  if (NOISE) {
    const src = AC.createBufferSource(); src.buffer = NOISE; src.loop = true;
    const bp = AC.createBiquadFilter(); bp.type = 'bandpass'; bp.Q.value = 0.8;
    bp.frequency.setValueCurveAtTime(cut, t, dur);
    const ng = AC.createGain();
    ng.gain.setValueCurveAtTime(nz, t, dur);
    src.connect(bp); bp.connect(ng); ng.connect(node);
    src.start(t); src.stop(t + dur + 0.05);
  }
}

/* 로고 사운드 — 임팩트로 열고, 오토바이가 지나가며 닫는다 */
function playTitleSting() {
  sfxImpact(0.00, 0.62, 1);        // 진입 한 방
  sfxPassBy(1.25, 2.70, 0.80);     // 2.44초쯤 눈앞을 지나간다
}

/* ── 화면 전환 ───────────────────────────────── */
function show(id) {
  $$('.screen').forEach((el) => el.classList.toggle('on', el.id === id));
}

/* '오늘 하루 안 보기' — 날짜를 저장해 두고 같은 날이면 건너뛴다 */
const todayKey = () => new Date().toISOString().slice(0, 10);
const skipToday = () => localStorage.getItem('skipIntroDate') === todayKey();

let titleShown = false;      // 로고가 두 번 뜨지 않도록 잠근다

function toClip() {
  if (skipToday()) return toTitle();
  show('clip');

  const v = $('#vid'), bg = $('#vidBg');
  v.currentTime = 0;
  v.volume = 1;
  if (bg) { bg.currentTime = 0; bg.play().catch(() => {}); }

  v.onended = toTitle;
  v.onerror = toTitle;
  v.play().catch(() => {
    v.muted = true;
    v.play().catch(toTitle);
  });

  setTimeout(() => {
    if ($('#clip').classList.contains('on') && v.readyState === 0) toTitle();
  }, 1500);
}

function toTitle() {
  if (titleShown) return;          // 중복 호출 차단
  titleShown = true;

  const v = $('#vid'), bg = $('#vidBg');
  try { v.onended = null; v.onerror = null; v.pause(); } catch (e) {}
  try { if (bg) bg.pause(); } catch (e) {}

  // 검정에서 시작하도록 애니메이션을 처음부터 돌린다
  const intro = $('#intro');
  intro.classList.remove('on');
  void intro.offsetWidth;
  show('intro');
  playTitleSting();

  let armed = false;
  setTimeout(() => { armed = true; }, 2400);
  const go = () => {
    if (!armed) return;
    document.removeEventListener('keydown', go);
    intro.removeEventListener('click', go);
    toApp();
  };
  document.addEventListener('keydown', go);
  intro.addEventListener('click', go);
  setTimeout(() => { if (intro.classList.contains('on')) { armed = true; go(); } }, 8500);
}

function toApp() {
  show('app');
  $('#teamBadge').textContent = '팀 ' + S.team;
  loadProjects();
  loadConvs();
}

/* ── 시작 화면 ───────────────────────────────── */
$('#btnStart').onclick = () => {
  const t = $('#teamInput').value.trim().toUpperCase();
  if (!t) { $('#gateNote').textContent = '팀 코드를 입력해 주세요.'; $('#teamInput').focus(); return; }
  S.team = t;
  const codeEl = $('#codeInput');
  if (codeEl) {
    S.code = codeEl.value.trim();
    if (!S.code) { $('#gateNote').textContent = '접속 코드를 입력해 주세요.'; codeEl.focus(); return; }
    sessionStorage.setItem('code', S.code);
  }
  localStorage.setItem('team', t);
  wakeAudio();          // 사용자 동작 안에서 오디오를 깨워 둔다
  toClip();
};
$('#teamInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('#btnStart').click(); });
$('#teamInput').value = localStorage.getItem('team') || '';
S.code = sessionStorage.getItem('code') || '';
if ($('#codeInput')) $('#codeInput').value = S.code;

$('#btnSkip').onclick = toTitle;
$('#btnToday').onclick = () => {
  localStorage.setItem('skipIntroDate', todayKey());
  toTitle();
};

/* ── 사이드바 ────────────────────────────────── */
const fold = () => $('#side').classList.toggle('fold');
$('#btnFold').onclick = fold;
$('#btnFold2').onclick = fold;

$('#btnLogout').onclick = () => { localStorage.removeItem('team'); location.reload(); };

$('#btnNew').onclick = () => newChat();

async function newChat() {
  const r = await api('/api/session', {
    method: 'POST',
    body: { team_code: S.team, project_id: S.project, access_code: S.code },
  });
  if (r.error) return toast(r.error);
  S.session = r.session_id;
  S.step = null;
  $('#log').innerHTML = '';
  addBlank();
  paintState(r.state, null);
  $('#input').focus();
}

async function loadConvs() {
  let url = '/api/sessions?team_code=' + encodeURIComponent(S.team);
  if (S.project) url += '&project_id=' + S.project;
  const r = await api(url);
  const box = $('#convs');
  if (!r.items || !r.items.length) { box.innerHTML = '<p class="empty">아직 없습니다</p>'; return; }
  box.innerHTML = '';
  r.items.forEach((it) => {
    const b = document.createElement('button');
    b.className = 'item' + (it.id === S.session ? ' on' : '');
    b.textContent = it.title || '새 대화';
    b.onclick = () => openConv(it.id);
    box.appendChild(b);
  });
}

async function syncProjectTag(pid) {
  const tag = $('#projTag');
  if (!pid) { tag.hidden = true; return; }
  const r = await api('/api/projects/' + pid + '?team_code=' + encodeURIComponent(S.team));
  if (r.error) { tag.hidden = true; return; }
  tag.hidden = false;
  tag.textContent = r.name;
}

/* ── 프로젝트 ────────────────────────────────── */
async function loadProjects() {
  const r = await api('/api/projects?team_code=' + encodeURIComponent(S.team));
  const box = $('#projs');
  if (!r.items || !r.items.length) {
    box.innerHTML = '<p class="empty">＋로 만들어 보세요</p>';
    return;
  }
  box.innerHTML = '';
  r.items.forEach((p) => {
    const b = document.createElement('button');
    b.className = 'item' + (p.id === S.project ? ' on' : '');
    b.innerHTML = '<span class="nm">' + esc(p.name) + '</span>' +
      '<span class="n">' + p.n + '</span><span class="edit">✎</span>';
    b.onclick = (e) => {
      if (e.target.classList.contains('edit')) return editProject(p);
      pickProject(p.id === S.project ? null : p);
    };
    box.appendChild(b);
  });
}

function pickProject(p) {
  S.project = p ? p.id : null;
  S.projectName = p ? p.name : '';
  const tag = $('#projTag');
  tag.hidden = !p;
  tag.textContent = p ? p.name : '';
  loadProjects();
  loadConvs();
  if (p) toast('프로젝트: ' + p.name + ' — 새 대화는 여기에 담깁니다');
}

$('#btnNewProj').onclick = (e) => {
  e.stopPropagation();
  editProject(null);
};

function editProject(p) {
  const isNew = !p;
  openModal(isNew ? '프로젝트 만들기' : '프로젝트 수정',
    '<label>이름</label>' +
    '<input id="pName" maxlength="40" placeholder="예: 1차 주행 테스트" value="' + esc(p ? p.name : '') + '">' +
    '<label>팀 메모 — 모든 과목 도우미가 이 내용을 알고 답합니다</label>' +
    '<textarea id="pMemo" placeholder="우리 팀만의 조건을 적어 두세요.&#10;예)&#10;- 보드: 아두이노 우노&#10;- 초음파 센서 핀: Trig D9, Echo D10&#10;- 모터 드라이버: L298N&#10;- 차체 폭 120mm로 확정">' + esc(p ? p.memo : '') + '</textarea>' +
    '<p style="color:#98938a;font-size:12px;margin-top:8px">핀 번호나 부품처럼 매번 다시 설명해야 하는 것을 적어 두면, 같은 말을 반복하지 않아도 됩니다.</p>',
    isNew
      ? '<button class="btn" data-x="close">취소</button><button class="btn primary" data-x="save">만들기</button>'
      : '<button class="btn danger" data-x="del">삭제</button><button class="btn" data-x="close">취소</button><button class="btn primary" data-x="save">저장</button>'
  );
  $('#pName').focus();

  // 새 프로젝트면 표준 규격을 메모에 미리 넣어 준다.
  // 팀은 자기가 바꾼 값만 고치면 되고, 그 메모가 모든 과목 답변에 반영된다.
  if (isNew) {
    api('/api/spec').then((r) => {
      const box = $('#pMemo');
      if (r && r.memo && box && !box.value.trim()) box.value = r.memo;
    });
  }

  $$('#modalFoot .btn').forEach((b) => {
    b.onclick = async () => {
      const x = b.dataset.x;
      if (x === 'close') return $('#modal').classList.remove('on');

      if (x === 'del') {
        if (!confirm('프로젝트를 지울까요? 대화는 남습니다.')) return;
        await api('/api/projects/' + p.id, { method: 'DELETE', body: { team_code: S.team } });
        if (S.project === p.id) pickProject(null);
        $('#modal').classList.remove('on');
        loadProjects();
        return toast('지웠습니다');
      }

      const name = $('#pName').value.trim();
      const memo = $('#pMemo').value.trim();
      if (!name) return toast('이름을 적어 주세요');

      let r;
      if (isNew) {
        r = await api('/api/projects', { method: 'POST', body: { team_code: S.team, name, memo } });
      } else {
        r = await api('/api/projects/' + p.id, { method: 'PATCH', body: { team_code: S.team, name, memo } });
      }
      if (r.error) return toast(r.error);
      $('#modal').classList.remove('on');
      await loadProjects();
      pickProject({ id: r.id, name: r.name });
      toast(isNew ? '프로젝트를 만들었습니다' : '저장했습니다');
    };
  });
}

async function openConv(sid) {
  const r = await api('/api/history/' + sid + '?team_code=' + encodeURIComponent(S.team));
  if (r.error) return toast(r.error);
  S.session = sid;
  $('#log').innerHTML = '';
  r.messages.forEach((m) => addTurn(m.role, m.content, m.blocked));
  paintState(r.state, r.block_reason);
  syncProjectTag(r.project_id);
  loadConvs();
  scrollDown();
}

/* ── 대화 ────────────────────────────────────── */
function addBlank() {
  $('#log').innerHTML =
    '<div class="blank"><h3>무엇을 하다가 막혔나요?</h3>' +
    '<p>지금 어디까지 했는지 알려 주면, 거기서부터 같이 갑니다.<br>' +
    '과목은 고르지 않아도 됩니다. 물어보면 어느 과목 내용인지 알려 드립니다.</p></div>';
}

function addTurn(role, text, blocked) {
  const blank = $('#log .blank');
  if (blank) blank.remove();
  const d = document.createElement('div');
  d.className = 'turn ' + (role === 'user' ? 'me' : 'ai') + (blocked ? ' blocked' : '');
  d.innerHTML = (role === 'user' ? '' : '<div class="who">도</div>') +
    '<div class="bubble">' + md(text) + '</div>';
  $('#log').appendChild(d);
  scrollDown();
  return d;
}

function scrollDown() { const l = $('#log'); l.scrollTop = l.scrollHeight; }

async function send() {
  const box = $('#input');
  const text = box.value.trim();
  if (!text || S.busy) return;
  if (!S.session) { await newChat(); }

  box.value = ''; box.style.height = 'auto';
  addTurn('user', text, 0);
  S.busy = true; $('#btnSend').disabled = true;

  const wait = addTurn('assistant', '생각 중…', 0);
  wait.querySelector('.bubble').classList.add('typing');

  const r = await api('/api/message', {
    method: 'POST',
    body: { session_id: S.session, team_code: S.team, text, tier: S.tier },
  });
  wait.remove();

  if (r.error) { toast(r.error); }
  else {
    addTurn('assistant', r.reply, r.blocked ? 1 : 0);
    paintState(r.state, r.block_reason);
    $('#stageBadge').textContent = r.stage;
    loadConvs();
  }
  S.busy = false; $('#btnSend').disabled = false;
  box.focus();
}

$('#btnSend').onclick = send;
$('#input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
});
$('#input').addEventListener('input', function () {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 180) + 'px';
});

/* ── 진행 표시 ───────────────────────────────── */
function paintState(st, reason) {
  if (!st) return;
  S.step = st.step || null;
  S.stepName = st.step_name || '';
  $('#stepName').textContent = st.step
    ? (st.step + '  ' + st.step_name)
    : '어디까지 왔는지 알려 주세요';
  const map = { step: !!st.step, goal: st.has_goal, state: st.has_state,
                blocker: st.has_blocker, attempt: st.has_attempt };
  $$('#progress span').forEach((el) => {
    const on = !!map[el.dataset.k];
    el.classList.toggle('done', on);
    el.querySelector('b').textContent = on ? '✓' : '✗';
  });
  $('#stageBadge').textContent = st.stage || 'S0';
  $('#reason').textContent = reason || '';
}

/* ── ＋ 메뉴 ─────────────────────────────────── */
function closePops() { $$('.pop').forEach((p) => p.classList.remove('on')); }
$('#btnPlus').onclick = (e) => {
  e.stopPropagation();
  const on = $('#plusMenu').classList.contains('on');
  closePops();
  if (!on) $('#plusMenu').classList.add('on');
};
document.addEventListener('click', closePops);
$$('.pop').forEach((p) => p.addEventListener('click', (e) => e.stopPropagation()));

$$('#plusMenu button').forEach((b) => {
  b.onclick = () => {
    const act = b.dataset.act;
    closePops();
    if (act === 'upload') return $('#filePick').click();
    if (act === 'mode') return $('#modeMenu').classList.add('on');
    if (act === 'search') return openSearch();
    if (act === 'guide') return openGuide();
  };
});

$$('.mode').forEach((b) => {
  b.onclick = () => {
    S.tier = b.dataset.tier;
    $$('.mode').forEach((x) => x.classList.toggle('on', x === b));
    closePops();
    toast('답변 모드: ' + b.textContent.replace(/[⚡⚖️🎓]/g, '').trim());
  };
});

/* ── 파일 업로드 = 시도 흔적 제출 ────────────── */
$('#filePick').onchange = async function () {
  const f = this.files[0];
  if (!f) return;
  if (!S.session) { toast('먼저 과목을 골라 주세요'); this.value = ''; return; }

  const fd = new FormData();
  fd.append('file', f);
  fd.append('session_id', S.session);
  fd.append('team_code', S.team);

  const res = await fetch('/api/upload', { method: 'POST', body: fd });
  const r = await res.json();
  this.value = '';
  if (r.error) return toast(r.error);

  addTurn('user', '📎 ' + r.filename, 0);
  paintState(r.state, r.block_reason);
  toast('올렸어요. 직접 해 본 결과로 인정됩니다');
};

/* ── 모달 (검색 · 지침) ──────────────────────── */
function openModal(title, html, footHtml) {
  $('#modalTitle').textContent = title;
  $('#modalBody').innerHTML = html;
  const f = $('#modalFoot');
  f.innerHTML = footHtml || '';
  f.hidden = !footHtml;
  $('#modal').classList.add('on');
}
$('#modalX').onclick = () => $('#modal').classList.remove('on');
$('#modal').onclick = (e) => { if (e.target.id === 'modal') $('#modal').classList.remove('on'); };

function openSearch() {
  openModal('자료에서 찾기',
    '<input id="q" placeholder="찾을 낱말을 입력하고 Enter">' +
    '<div id="hits" class="hits"><p style="color:#98938a">이 검색은 AI를 부르지 않습니다. 토큰을 쓰지 않아요.</p></div>');
  const q = $('#q'); q.focus();
  q.onkeydown = async (e) => {
    if (e.key !== 'Enter') return;
    const r = await api('/api/search?q=' + encodeURIComponent(q.value.trim()));
    $('#hits').innerHTML = (r.items && r.items.length)
      ? r.items.map((h) => '<div class="hit"><b style="color:#1f3b63">' + esc(h.subject) +
          '</b><br>' + esc(h.text) + '</div>').join('')
      : '<p style="color:#98938a">찾은 내용이 없어요.</p>';
  };
}

async function openGuide() {
  const r = await api('/api/course');
  if (r.error) return toast(r.error);
  let cur = '';
  const rows = r.steps.map((s) => {
    let head = '';
    if (s.course !== cur) { cur = s.course; head = '<h5 style="margin:14px 0 6px">' + esc(cur) + '</h5>'; }
    const on = (s.id === S.step) ? ' style="background:#e7edf5;border-radius:8px"' : '';
    return head + '<div class="hit"' + on + '><b>' + s.id + ' ' + esc(s.name) + '</b>' +
      ' <span style="color:#98938a">' + esc(s.subjects.join(' · ')) + '</span><br>' +
      '<span style="color:#6e6a62">끝나면 — ' + esc(s.done) + '</span></div>';
  }).join('');
  openModal('전 과정 — 자동차를 만드는 순서',
    '<p style="color:#6e6a62;margin-bottom:6px">A코스와 B코스가 나란히 진행되다가 뒤에서 만납니다.' +
    (S.step ? ' 지금은 <b>' + S.step + ' ' + esc(S.stepName) + '</b> 입니다.' : '') + '</p>' + rows);
}

/* ── 유틸 ────────────────────────────────────── */
async function api(url, opt) {
  const o = { headers: { 'Content-Type': 'application/json' } };
  if (opt && opt.method) o.method = opt.method;
  if (opt && opt.body) o.body = JSON.stringify(opt.body);
  try {
    const res = await fetch(url, o);
    return await res.json();
  } catch (e) {
    return { error: '서버에 연결하지 못했어요.' };
  }
}

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/* 아주 가벼운 마크다운 — 코드블록·인라인코드·굵게만 */
function md(s) {
  let t = esc(s);
  t = t.replace(/```([\s\S]*?)```/g, (m, c) => '<pre>' + c.replace(/^\w*\n/, '') + '</pre>');
  t = t.replace(/`([^`\n]+)`/g, '<code>$1</code>');
  t = t.replace(/\*\*([^*\n]+)\*\*/g, '<b>$1</b>');
  return t;
}

let toastTimer;
function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.add('on');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('on'), 2200);
}
