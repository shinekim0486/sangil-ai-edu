# -*- coding: utf-8 -*-
"""
교사연구회 에이전트 — 자율주행자동차 프로젝트 지원 챗봇

실행:
    pip install -r requirements.txt
    python app.py      → http://127.0.0.1:5000
"""
import os
import re
import uuid

# .env를 먼저 읽는다. 이게 없으면 키를 저장해도 모의 모드로 돈다.
try:
    from dotenv import load_dotenv
    # override=True — .env 를 고친 뒤 자동 리로드되면 새 값을 써야 한다.
    # 기본값(False)은 이미 있는 환경변수를 안 덮어써서, MODEL_STD 를 바꿔도 옛 모델이 계속 불렸다.
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)
except ImportError:
    pass

from flask import Flask, jsonify, render_template, request, send_from_directory

import db
import gate
import llm
import pipeline

BASE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(BASE, "skills")
UPLOAD_DIR = os.path.join(db.DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── 접속 제한 ────────────────────────────────────────────
# ACCESS_CODE  수업용 공통 접속 코드. 비워 두면 제한하지 않는다.
# TEAM_CODES   허용할 팀 코드 목록(쉼표 구분). 비워 두면 아무 코드나 허용.
# ADMIN_KEY    기록 내려받기용 열쇠.
ACCESS_CODE = (os.getenv("ACCESS_CODE") or "").strip()
TEAM_CODES = [t.strip().upper() for t in (os.getenv("TEAM_CODES") or "").split(",") if t.strip()]
ADMIN_KEY = (os.getenv("ADMIN_KEY") or "").strip()


def check_entry(team, code):
    """팀 코드와 접속 코드를 검사한다. 통과하면 None."""
    if ACCESS_CODE and (code or "").strip() != ACCESS_CODE:
        return "접속 코드가 맞지 않아."
    if TEAM_CODES and team not in TEAM_CODES:
        return "등록되지 않은 팀 코드야."
    return None

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8MB

# ── 과목(스킬) 목록 — 화면 좌측 '과목' 자리에 뿌린다 ──────
SKILLS = [
    ("skill_3d",      "3D 프린터용 제품 제작"),
    ("skill_game",    "게임 프로그래밍"),
    ("skill_ai",      "인공지능 모델링"),
    ("skill_network", "네트워크 프로그래밍"),
    ("skill_appux",   "스마트 문화 앱 콘텐츠 제작"),
    ("skill_server",  "응용 프로그래밍 개발 — 서버"),
    ("skill_ui",      "응용 프로그래밍 개발 — 화면"),
    ("skill_ops",     "시스템 운영 및 네트워크 운영"),
]
SKILL_NAME = dict(SKILLS)

_skill_cache = {}


def load_skill(skill_id):
    """스킬 문서를 읽어 온다. 파일이 없으면 빈 문자열."""
    path = os.path.join(SKILL_DIR, skill_id + ".md")
    try:
        info = os.stat(path)
    except FileNotFoundError:
        _skill_cache.pop(skill_id, None)
        return ""
    signature = (info.st_mtime_ns, info.st_size)
    cached = _skill_cache.get(skill_id)
    if cached and cached[0] == signature:
        return cached[1]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    _skill_cache[skill_id] = (signature, text)
    return text


def skills_for_step(step_id, stage, context_text=""):
    """
    추정된 공정 단계에 걸린 과목들의 스킬 문서를, 대화 단계에 필요한 섹션만 골라 합친다.
    단계를 아직 모르면 아무것도 넣지 않는다 — 넣어도 못 쓰고 토큰만 나간다.
    """
    if not step_id:
        return ""
    parts = []
    for sid in pipeline.skills_for(step_id):
        md = load_skill(sid)
        if not md:
            continue
        cut = gate.skill_for_stage(md, stage, context_text)
        if cut.strip():
            parts.append(cut)
    return "\n\n".join(parts)


def state_of(row):
    return gate.State(
        stage=row["stage"],
        has_goal=bool(row["has_goal"]),
        has_state=bool(row["has_state"]),
        has_blocker=bool(row["has_blocker"]),
        has_attempt=bool(row["has_attempt"]),
        turn=row["turn"],
        step=row["step"],
    )


# ── 화면 ────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", skills=SKILLS, mock=llm.MOCK,
                           need_code=bool(ACCESS_CODE))


@app.get("/healthz")
def healthz():
    """Render 상태 점검용."""
    return jsonify(ok=True, mock=llm.MOCK)


@app.route("/uploads/<path:name>")
def uploaded(name):
    return send_from_directory(UPLOAD_DIR, name)


# ── API ─────────────────────────────────────────────────
@app.post("/api/session")
def api_new_session():
    """새 대화 시작."""
    d = request.get_json(force=True)
    team = (d.get("team_code") or "").strip().upper()
    pid = d.get("project_id") or None
    if not team:
        return jsonify(error="팀 코드를 입력해 줘."), 400
    bad = check_entry(team, d.get("access_code"))
    if bad:
        return jsonify(error=bad), 403
    if pid:
        pr = db.get_project(pid)
        if not pr or pr["team_code"] != team:
            pid = None

    sid = uuid.uuid4().hex[:12]
    db.create_session(sid, team, pid)
    return jsonify(session_id=sid, project_id=pid, state=gate.State().to_dict())


@app.get("/api/sessions")
def api_sessions():
    """좌측 '지난 대화' 목록."""
    team = (request.args.get("team_code") or "").strip().upper()
    pid = request.args.get("project_id") or None
    if not team:
        return jsonify(items=[])
    return jsonify(items=db.list_sessions(team, pid))


# ── 프로젝트 ────────────────────────────────────────────
@app.get("/api/projects")
def api_projects():
    team = (request.args.get("team_code") or "").strip().upper()
    if not team:
        return jsonify(items=[])
    return jsonify(items=db.list_projects(team))


@app.post("/api/projects")
def api_project_create():
    """
    프로젝트 = 팀이 만드는 작업 묶음.
    메모에 적은 팀 규격(핀 번호·부품·결정 사항)은 모든 과목 챗봇 답변에 반영된다.
    """
    d = request.get_json(force=True)
    team = (d.get("team_code") or "").strip().upper()
    name = (d.get("name") or "").strip()
    memo = (d.get("memo") or "").strip()
    if not team:
        return jsonify(error="팀 코드가 없어."), 400
    if not name:
        return jsonify(error="프로젝트 이름을 적어 줘."), 400

    pid = uuid.uuid4().hex[:12]
    db.create_project(pid, team, name[:40], memo[:1200])
    return jsonify(id=pid, name=name[:40], memo=memo[:1200], n=0)


@app.route("/api/projects/<pid>", methods=["GET", "PATCH", "DELETE"])
def api_project_one(pid):
    team = ((request.args.get("team_code") if request.method == "GET"
             else (request.get_json(silent=True) or {}).get("team_code")) or "").strip().upper()
    pr = db.get_project(pid)
    if not pr:
        return jsonify(error="없는 프로젝트야."), 404
    if pr["team_code"] != team:
        return jsonify(error="우리 팀 프로젝트가 아니야."), 403

    if request.method == "GET":
        return jsonify(pr)

    if request.method == "DELETE":
        db.delete_project(pid)
        return jsonify(ok=True)

    d = request.get_json(force=True)
    fields = {}
    if "name" in d:
        fields["name"] = (d.get("name") or "").strip()[:40]
    if "memo" in d:
        fields["memo"] = (d.get("memo") or "").strip()[:1200]
    db.update_project(pid, **fields)
    return jsonify(db.get_project(pid))


@app.get("/api/history/<sid>")
def api_history(sid):
    """대화 복원. 다른 팀 코드로는 열 수 없다."""
    row = db.get_session(sid)
    if not row:
        return jsonify(error="없는 대화야."), 404
    team = (request.args.get("team_code") or "").strip().upper()
    if row["team_code"] != team:
        return jsonify(error="우리 팀 대화가 아니야."), 403

    st = state_of(row)
    return jsonify(
        session_id=sid, project_id=row["project_id"],
        title=row["title"], state=st.to_dict(),
        messages=db.get_messages(sid),
        block_reason=gate.block_reason(st),
    )


@app.get("/api/course")
def api_course():
    """'+ → 전 과정 보기' — 자율주행차를 어떤 순서로 만드는지 보여 준다."""
    out = []
    for st in pipeline.STEPS:
        out.append({
            "id": st["id"],
            "course": pipeline.COURSES[st["course"]],
            "name": st["name"],
            "subjects": pipeline.subjects_of(st["id"]) or ["전 과목"],
            "does": st["does"],
            "done": st["done"],
        })
    return jsonify(steps=out, stages={k: gate.STAGE_DESC[k] for k in gate.STAGES})


@app.get("/api/spec")
def api_spec():
    """프로젝트를 새로 만들 때 메모에 미리 채워 넣을 표준 규격."""
    return jsonify(memo=pipeline.spec_memo(), brief=pipeline.spec_brief())


@app.get("/api/search")
def api_search():
    """'+ → 자료에서 찾기' — 전 과목 자료를 뒤진다. API를 부르지 않으니 토큰 0."""
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify(items=[])
    hits = []
    for sid, name in SKILLS:
        for line in load_skill(sid).split("\n"):
            if q.lower() in line.lower() and line.strip():
                hits.append({"subject": name, "text": line.strip()[:180]})
                if len(hits) >= 40:
                    return jsonify(items=hits)
    return jsonify(items=hits)


@app.post("/api/upload")
def api_upload():
    """
    파일 업로드 — 이것이 S2→S3 게이트의 '시도 흔적' 제출 경로다.
    말로만 '해봤어요'가 아니라 결과물을 올려야 완성 코드로 넘어간다.
    """
    sid = request.form.get("session_id")
    team = (request.form.get("team_code") or "").strip().upper()
    row = db.get_session(sid) if sid else None
    if not row:
        return jsonify(error="대화를 먼저 시작해 줘."), 400
    if row["team_code"] != team:
        return jsonify(error="우리 팀 대화가 아니야."), 403

    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="파일이 없어."), 400

    name = "%s_%s" % (uuid.uuid4().hex[:8], os.path.basename(f.filename))
    f.save(os.path.join(UPLOAD_DIR, name))

    db.update_session(sid, has_attempt=1)
    db.add_message(sid, "user", "[파일 첨부] %s" % f.filename,
                   stage=row["stage"])

    row = db.get_session(sid)
    st = state_of(row)
    return jsonify(ok=True, filename=f.filename, saved=name,
                   state=st.to_dict(), block_reason=gate.block_reason(st))


@app.post("/api/message")
def api_message():
    """대화 한 턴. 게이트가 여기서 작동한다."""
    d = request.get_json(force=True)
    sid = d.get("session_id")
    team = (d.get("team_code") or "").strip().upper()
    text = (d.get("text") or "").strip()
    tier = d.get("tier") or llm.DEFAULT_TIER

    row = db.get_session(sid) if sid else None
    if not row:
        return jsonify(error="대화를 먼저 시작해 줘."), 400
    if row["team_code"] != team:
        return jsonify(error="우리 팀 대화가 아니야."), 403

    st = state_of(row)

    # ① 호출 전 차단 — 여기서 걸리면 API 비용 0
    ok, why = gate.preflight(
        text,
        prev_user_text=db.last_user_message(sid),
        used_today_student=db.usage_today(session_id=sid),
        used_today_team=db.usage_today(team_code=team),
    )
    if not ok:
        db.add_message(sid, "user", text, stage=st.stage, blocked=1)
        db.add_message(sid, "assistant", why, stage=st.stage, blocked=1)
        return jsonify(reply=why, blocked=True, state=st.to_dict(),
                       stage=st.stage, block_reason=gate.block_reason(st))

    # ② 학생 발화 기록
    st.turn += 1
    db.add_message(sid, "user", text, stage=st.stage)

    # ③ 이 턴에 허용되는 단계로 프롬프트를 만든다
    #
    # 스킬 문서는 "이번 턴 질문"에 맞는 단계로 골라야 한다.
    # 예전에는 첫 턴에만 추정해서, 3D 차체로 시작한 학생이 통신 질문을 하면
    # 3D 스킬이 실린 채로 답이 나갔다. 모델은 CRC-8 자료를 못 받으니
    # "XOR도 괜찮다"처럼 자기 짐작으로 답했다(XOR·정지선·M3 오답의 원인).
    #
    # 교과 선언과 기술 화제 근거를 보되 범용 낱말로는 앞 공정을 바꾸지 않는다.
    # 응답 뒤 모델 판정 반영에도 같은 resolve_step을 사용한다.
    route_in = route_out = 0
    if st.turn == 1 and not pipeline.declared_step(text) and not llm.MOCK:
        semantic_step, route_in, route_out = llm.classify_step(text)
        st.step = (semantic_step if semantic_step in pipeline.STEP_BY_ID
                   else pipeline.resolve_step(text, st.step))
    else:
        st.step = pipeline.resolve_step(text, st.step)
    stage_for_prompt = gate.resolve_stage(st, None)
    raw_history = [{"role": m["role"], "content": m["content"]}
                   for m in db.get_messages(sid) if not m["blocked"]][:-1]
    # 사례 검색은 현재 팀·대화의 학생 발화에만 한정한다.
    case_context = "\n".join(m["content"][-500:] for m in raw_history[-4:]
                             if m["role"] == "user") + "\n" + text
    skill_md = skills_for_step(st.step, stage_for_prompt, case_context)
    pr = db.get_project(row["project_id"]) if row["project_id"] else None
    system = gate.build_system_prompt(
        skill_md, stage_for_prompt, st,
        project_name=(pr or {}).get("name"),
        project_memo=(pr or {}).get("memo"),
        user_text=text)

    history = gate.compress_history(raw_history)

    # 어느 모델에 보낼지. llm.ask 의 stage 는 모델 선택용이라 "S3"면 완성 코드용 모델이다.
    # 값싼 모델로는 안 되는 턴 세 가지(9/18 시뮬에서 확인):
    #   · 코드가 나갈 수 있는 턴 — S3, 또는 S2에서 시도 결과만 남은 턴
    #   · 학생이 코드를 붙여 온 턴 — 규격과 맞는지 판정해야 한다
    #   · 학생이 정해진 값을 물은 턴 — 값싼 모델은 표를 보고도 학생 제안에 맞장구친다
    #   S0·S1은 되묻기·방향 제시뿐이라 값싼 모델로 두고, 정해진 값은 아래 ⑤ 검사가 지킨다.
    #   (모든 턴에 좋은 모델을 붙였더니 턴당 30~60초가 걸렸다)
    settled_txt = gate.find_settled(skill_md, text)
    strong = (gate.one_step_away(st, stage_for_prompt)
              or gate.has_field_evidence(text)
              or "```" in text
              or (bool(settled_txt) and stage_for_prompt in ("S2", "S3")))
    model_stage = "S3" if strong else stage_for_prompt
    result, tin, tout, model = llm.ask(
        system, history, text, model_stage,
        gate.max_tokens_for(stage_for_prompt), tier)
    tin += route_in
    tout += route_out

    # OpenAI 호출이 끝내 실패한 턴 — 단계·조건·턴 수를 바꾸지 않고 안내만 보낸다.
    # (분당 토큰 한도 429 · 키 오류 · 인터넷 끊김). 학생은 같은 말을 다시 보내면 된다.
    if result.get("_error"):
        db.add_message(sid, "assistant", result["reply"], stage=st.stage, blocked=1)
        return jsonify(reply=result["reply"], blocked=True, stage=st.stage,
                       state=state_of(row).to_dict(), block_reason=None,
                       error=result["_error"])

    # ④ 모델이 뽑아낸 정보만 반영하고, 단계는 서버가 조건으로 정한다.
    #    모델의 next_stage 주장은 기록만 하고 판단에 쓰지 않는다.
    gate.apply_model_result(st, result, user_text=text)
    prev_stage = st.stage
    st.stage = gate.resolve_stage(st, None)
    # 답에 코드 블록을 요구하는 턴 — 코드로 답이 끝나는 단계(CODE_STEPS)에서
    #   · 이 턴에 처음 S3 로 올라섰거나
    #   · S3 에서 학생이 코드를 붙여 왔거나(고친 전체 코드를 줘야 한다) 코드를 달라고 했을 때
    # (9/21 정주행 시뮬: 학생 코드가 틀렸는데 "잘했어"만 하고 24턴 동안 코드를 한 번도 안 줬다)
    asks_code = bool(re.search(r"코드.{0,14}(줘|주세요|보여|알려|짜|만들어)", text)) or "```" in text
    first_s3 = (st.step in gate.CODE_STEPS and not gate.review_only_request(text) and
                ((prev_stage != "S3" and st.stage == "S3") or (st.stage == "S3" and asks_code)))

    reply = result.get("reply") or "다시 한번 말해 줄래?"

    # ⑤ 답 내용 검사 — 확정된 단계의 규칙을 서버가 확인한다.
    #    모의·가짜 응답(토큰 0)은 건너뛴다. 실제 모델 답만 본다.
    #    어겼으면 한 번만 다시 묻고, 그래도 어기면 서버가 답을 손본다.
    #    (S0에 답을 주고 S2에 완성 코드를 주는 일이 시뮬 5턴 중 5턴이었다)
    if tin > 0:
        settled_hit = bool(settled_txt)
        rows = gate.settled_rows(settled_txt, text)    # 답에 꼭 나와야 할 (항목, 값, 낱말들) — 학생 말과 항목명이 겹치는 행만
        keys = [toks for _, _, toks in rows]
        why = gate.reply_violation(st.stage, reply, settled_hit, keys, first_s3)
        if why:
            result2, tin2, tout2, _ = llm.ask(
                system, history, text, model_stage,
                gate.max_tokens_for(stage_for_prompt), tier,
                extra_system=gate.RETRY_NOTE[why])
            tin += tin2
            tout += tout2
            reply2 = (result2.get("reply") or "").strip()
            why2 = gate.reply_violation(st.stage, reply2, settled_hit, keys, first_s3)
            if reply2 and not why2:
                reply = reply2
                print("[답 검사] %s %s → 재생성으로 해결" % (st.stage, why))
            else:
                reply = gate.fix_reply(st.stage, reply2 or reply, st, why2 or why, rows)
                print("[답 검사] %s %s → 서버가 보정" % (st.stage, why2 or why))
    if st.turn == 1 and st.stage == 'S0':
        # 증거가 충분한 첫 진단에서 이미 확인한 내용을 재질문하는 반복을 차단한다.
        reply = gate.first_field_question(text) or reply
    reply = gate.with_opener(reply, st)

    db.add_message(sid, "assistant", reply, stage=st.stage,
                   tokens_in=tin, tokens_out=tout, model=model)

    title = row["title"]
    if title == "새 대화":
        title = text[:24]
    db.update_session(
        sid, stage=st.stage, turn=st.turn, title=title, step=st.step,
        has_goal=int(st.has_goal), has_state=int(st.has_state),
        has_blocker=int(st.has_blocker), has_attempt=int(st.has_attempt))

    return jsonify(reply=reply, blocked=False, stage=st.stage,
                   state=st.to_dict(), block_reason=gate.block_reason(st),
                   tokens={"in": tin, "out": tout}, model=model)


@app.get("/admin/export")
def admin_export():
    """
    대화 기록 전체를 CSV로 내려받는다.
    학생 프롬프트 로그가 연구 산출물이므로 수시로 받아 두는 것이 안전하다.
    /admin/export?key=<ADMIN_KEY>
    """
    if not ADMIN_KEY or request.args.get("key") != ADMIN_KEY:
        return jsonify(error="권한이 없어."), 403

    import csv
    import io as _io
    buf = _io.StringIO()
    w = csv.writer(buf)
    w.writerow(["일시", "팀", "과목", "프로젝트", "대화제목", "단계",
                "역할", "내용", "차단", "입력토큰", "출력토큰", "모델"])
    with db.conn() as c:
        rows = c.execute(
            "SELECT m.created_at, s.team_code, s.skill_id, p.name proj, s.title,"
            "       m.stage_at_time, m.role, m.content, m.blocked,"
            "       m.tokens_in, m.tokens_out, m.model"
            " FROM messages m JOIN sessions s ON m.session_id=s.id"
            " LEFT JOIN projects p ON s.project_id=p.id"
            " ORDER BY m.id").fetchall()
    for r in rows:
        w.writerow([r[0], r[1], SKILL_NAME.get(r[2], r[2]), r[3] or "", r[4],
                    r[5], r[6], r[7], r[8], r[9], r[10], r[11]])
    out = buf.getvalue().encode("utf-8-sig")   # 엑셀에서 한글이 깨지지 않게
    return app.response_class(
        out, mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=chat_log.csv"})


@app.get("/api/usage")
def api_usage():
    """토큰 사용량 — 시스템 운영 과목 대시보드의 데이터원."""
    return jsonify(items=db.usage_summary())


# gunicorn으로 띄울 때도 초기화가 되도록 모듈 수준에서 실행한다
db.init()
llm.init()

def _lan_ips():
    """이 PC 의 내부망 주소들. 학생이 접속할 주소를 화면에 찍기 위해서다."""
    import socket
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith(("127.", "169.254.")):
                ips.add(ip)
    except Exception:
        pass
    return sorted(ips)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print("=" * 56)
    print("  교사연구회 에이전트")
    print("  모드: %s" % ("OpenAI 연결됨" if not llm.MOCK else "모의 응답 (OPENAI_API_KEY 없음)"))
    print("  접속 코드: %s" % ("설정됨" if ACCESS_CODE else "없음"))
    print("  팀 코드: %s" % (", ".join(TEAM_CODES) if TEAM_CODES else "제한 없음"))
    print("  이 PC 에서: http://127.0.0.1:%d" % port)
    for ip in _lan_ips():
        print("  학생 접속 주소: http://%s:%d   ← 칠판에 적을 주소" % (ip, port))
    if not _lan_ips():
        print("  학생 접속 주소: (내부망 주소를 못 찾음 — ipconfig 로 IPv4 주소를 확인하세요)")
    print("=" * 56)
    # 로컬에서 python app.py로 띄울 때는 자동 새로고침을 켠다.
    # 배포(Render)는 gunicorn이 app 객체를 직접 잡으므로 이 블록을 타지 않는다.
    app.run(debug=(os.getenv("FLASK_DEBUG", "1") == "1"),
            host="0.0.0.0", port=port)
