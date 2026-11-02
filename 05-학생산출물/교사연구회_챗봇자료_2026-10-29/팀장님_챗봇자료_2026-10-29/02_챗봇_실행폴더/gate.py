# -*- coding: utf-8 -*-
"""
대화 게이트 — 이 챗봇의 핵심.

일반 챗봇은 첫 질문에 바로 정답을 준다. 이 챗봇은 반대로 간다.
학생의 의도를 먼저 캐고, 의도가 분명해진 뒤에 방향을 주고,
학생이 직접 시도한 흔적을 내놓은 다음에야 완성 코드를 준다.

중요: 단계 판정의 최종 권한은 서버에 있다.
모델이 "지금 S3야"라고 우겨도 서버가 조건을 확인해 깎아내린다.
"""
import json
import re
import unicodedata

import pipeline

# ─────────────────────────────────────────────────────────
# 단계 정의
# ─────────────────────────────────────────────────────────
STAGES = ["S0", "S1", "S2", "S3"]

STAGE_DESC = {
    "S0": "역질문만 한다. 답·방향·코드 전부 금지.",
    "S1": "의도를 한 문장으로 요약해 확인받고 접근 방향을 제시한다. 코드 금지.",
    "S2": "구체적 절차·개념·의사코드 골격을 제시한다. 실행 가능한 완성 코드 금지.",
    "S3": "코드 과제에는 완성 코드 + 근거 설명 + 수정할 부분 + 확인 질문 1개. 진단·관찰 보고 요청에는 그 결과를 답한다.",
}

# 단계별 출력 상한 (토큰 절약 대책 2)
# 한국어는 영어보다 토큰을 많이 쓰고, JSON 껍데기도 함께 세어진다.
# 150이면 두세 문장에서 잘린다. 실측에 맞춰 올렸다.
MAX_TOKENS = {"S0": 300, "S1": 600, "S2": 1000, "S3": 2200}


def max_tokens_for(stage):
    """
    이번 턴에 학생이 조건을 채워 한 단계 올라갈 수 있으므로,
    출력 상한은 한 단계 위 값으로 준다. 안 올라가면 어차피 짧게 답한다.
    """
    nxt = {"S0": "S1", "S1": "S2", "S2": "S3"}.get(stage, stage)
    return MAX_TOKENS[nxt]

# 단계별로 주입할 스킬 문서 섹션 (토큰 절약 대책 3)
# 스킬 전문을 매 턴 넣으면 학생이 "안녕"만 쳐도 4천 토큰이 나간다.
#
# 🔴 4절(검증된 규격·코드)은 S1·S2에도 넣는다 — 단, 코드 블록은 뺀 채로.
#    S3에서만 넣었더니 S1·S2에서 "패킷 형식이 뭐예요?"에 모델이 규격 없이
#    지어냈다(LEN·SEQ 빠진 형식, 조향 방향 반대). 9/18 정주행 시뮬에서 잡았다.
SKILL_SECTIONS = {
    "S0": ["0", "1", "5"],
    "S1": ["0", "1", "2", "4", "5"],
    "S2": ["0", "1", "2", "3", "4", "5", "6"],
    "S3": ["0", "2", "3", "4", "6"],
}
# 4절을 코드 없이 넣는 단계
SKILL_CODE_FREE = ("S0", "S1", "S2")

# 단계별 최소 대화 횟수 (학생 발화 기준, 현재 발화 포함)
# 첫 질문은 무조건 S0. 후속 3회째부터 완성 코드가 가능하다.
MIN_TURN = {"S0": 1, "S1": 2, "S2": 3, "S3": 4}

# 대화 이력 압축 기준 (토큰 절약 대책 4)
HISTORY_KEEP = 6

# 사용 상한 (토큰 절약 대책 6)
# 팀 메모는 매 턴 프롬프트에 들어가므로 길이를 제한한다
PROJECT_MEMO_LIMIT = 900

DAILY_LIMIT_STUDENT = 60
DAILY_LIMIT_TEAM = 200


# ─────────────────────────────────────────────────────────
# 대화 상태
# ─────────────────────────────────────────────────────────
class State:
    """한 대화의 진행 상태. DB의 sessions 행과 1:1로 대응한다."""

    def __init__(self, stage="S0", has_goal=False, has_state=False,
                 has_blocker=False, has_attempt=False, turn=0, step=None):
        self.stage = stage
        self.has_goal = has_goal        # 무엇을 하려는가 (이번 질문의 목적)
        self.has_state = has_state      # 지금 어디까지 됐는가
        self.has_blocker = has_blocker  # 정확히 어디서 막혔는가
        self.has_attempt = has_attempt  # 직접 시도한 흔적이 있는가
        self.turn = turn                # 학생 발화 누적 횟수
        self.step = step                # 추정된 공정 단계 (P0·B1~B5·A1~A4·C1~C3)

    @property
    def filled(self):
        """확보된 정보 개수(목표·현재상태·막힌지점)."""
        return sum([self.has_goal, self.has_state, self.has_blocker])

    def missing(self):
        """아직 비어 있는 항목 이름 목록. 역질문 대상이 된다."""
        out = []
        if not self.step:
            out.append("공정 단계")
        if not self.has_goal:
            out.append("하려는 것")
        if not self.has_state:
            out.append("현재 상태")
        if not self.has_blocker:
            out.append("막힌 지점")
        return out

    def to_dict(self):
        return {
            "stage": self.stage,
            "has_goal": self.has_goal,
            "has_state": self.has_state,
            "has_blocker": self.has_blocker,
            "has_attempt": self.has_attempt,
            "turn": self.turn,
            "step": self.step,
            "step_name": (pipeline.STEP_BY_ID[self.step]["name"]
                          if self.step in pipeline.STEP_BY_ID else None),
        }


# ─────────────────────────────────────────────────────────
# 1) 호출 전 차단 — 토큰 절약 대책 5
#    여기서 걸리면 API를 아예 부르지 않는다. 비용 0.
# ─────────────────────────────────────────────────────────
MIN_CHARS = 3
_JAMO_ONLY = re.compile(r'^[ㄱ-ㅎㅏ-ㅣ]+$')


def _norm(s):
    """비교용 정규화 — 공백·문장부호 제거, 소문자화."""
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r'[\s\.\,\!\?\~\-\_\/\\]+', '', s)
    return s.lower()


def preflight(text, prev_user_text=None, used_today_student=0, used_today_team=0):
    """
    API를 부르기 전에 서버가 먼저 거른다.
    통과하면 (True, None), 막히면 (False, 사유 문자열)을 돌려준다.
    """
    raw = (text or "").strip()

    if len(raw.replace(" ", "")) < MIN_CHARS:
        return False, "질문이 너무 짧아. 무엇을 하려는지 한 문장으로 써 줘."

    if _JAMO_ONLY.match(raw.replace(" ", "")):
        return False, "자음·모음만 있어서 무슨 말인지 모르겠어. 문장으로 써 줘."

    # 같은 글자만 반복 (ㅋㅋㅋㅋ, aaaa, ....)
    body = _norm(raw)
    if len(set(body)) <= 1 and len(body) >= 2:
        return False, "같은 글자만 반복됐어. 질문을 문장으로 써 줘."

    if prev_user_text and _norm(prev_user_text) == body:
        return False, "방금 한 질문이랑 똑같아. 앞의 대답을 읽고 한 걸음 더 나아가 보자."

    if used_today_student >= DAILY_LIMIT_STUDENT:
        return False, "오늘 사용 한도(%d회)를 다 썼어. 다음 수업 시간에 이어서 하자." % DAILY_LIMIT_STUDENT

    if used_today_team >= DAILY_LIMIT_TEAM:
        return False, "우리 팀 오늘 사용 한도(%d회)를 다 썼어. 팀원들과 정리해 보고 다시 오자." % DAILY_LIMIT_TEAM

    return True, None


# ─────────────────────────────────────────────────────────
# 2) 서버가 인정하는 최대 단계
#    모델 판단을 그대로 믿지 않는다.
# ─────────────────────────────────────────────────────────
def allowed_stage(state):
    """
    현재 상태에서 서버가 허용하는 최고 단계.

    S1 — 하려는 것·현재상태·막힌지점 중 1개 이상 확보 + 2번째 발화 이상
    S2 — 2개 이상 확보 + 공정 단계 확정 + 3번째 발화 이상
    S3 — 위 조건 + 시도 흔적 있음 + 4번째 발화 이상

    S2부터 공정 단계를 요구하는 이유: 어느 단계인지 모른 채 구체적인 절차나 코드를 주면
    엉뚱한 단계의 답이 나가 학생이 더 헤맨다.
    """
    cand = "S0"
    if state.turn >= MIN_TURN["S1"] and state.filled >= 1:
        cand = "S1"
    if state.turn >= MIN_TURN["S2"] and state.filled >= 2 and state.step:
        cand = "S2"
    if (state.turn >= MIN_TURN["S3"] and state.filled >= 2
            and state.step and state.has_attempt):
        cand = "S3"
    return cand


def resolve_stage(state, proposed=None):
    """
    최종 단계를 확정한다.

    - 서버 허용치를 넘을 수 없다 (모델이 우겨도 깎는다)
    - 한 번에 두 단계 이상 건너뛸 수 없다
    - 이미 올라간 단계에서 내려가지 않는다
    """
    allow = allowed_stage(state)

    want = proposed if proposed in STAGES else allow
    # 모델 제안과 서버 허용치 중 낮은 쪽
    final = min(want, allow, key=lambda s: STAGES.index(s))

    # 한 번에 한 단계씩만
    cur_i = STAGES.index(state.stage)
    if STAGES.index(final) > cur_i + 1:
        final = STAGES[cur_i + 1]

    # 내려가지 않는다
    if STAGES.index(final) < cur_i:
        final = state.stage

    return final


def block_reason(state):
    """S3로 못 가는 이유를 학생에게 알려줄 한 줄."""
    if not state.step:
        return "지금 어느 단계인지부터 알아야 해. 어디까지 했는지 알려 줘."
    if state.filled < 2:
        return "아직 %s을(를) 모르겠어. 그것부터 알려 줘." % " · ".join(state.missing())
    if not state.has_attempt:
        return "직접 해 본 결과를 보여 줘. 코드나 에러 화면을 올리면 돼."
    if state.turn < MIN_TURN["S3"]:
        return "조금만 더 이야기해 보자."
    return None


# ─────────────────────────────────────────────────────────
# 3) 스킬 문서 섹션 선택 — 토큰 절약 대책 3
# ─────────────────────────────────────────────────────────
_SECTION_RE = re.compile(r'^##\s*(\d+)\.\s*(.*)$', re.M)


def split_skill(md_text):
    """스킬 문서를 '## 0. 울타리' 같은 최상위 섹션 단위로 쪼갠다."""
    marks = list(_SECTION_RE.finditer(md_text or ""))
    out = {}
    for i, m in enumerate(marks):
        start = m.start()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(md_text)
        out[m.group(1)] = md_text[start:end].strip()
    return out


def extract_must(md_text):
    """
    4절의 「반드시 지킬 것」 블록만 떼어 낸다.

    4절 전체는 길어서 S3에서만 넣는데, 학교가 정한 값(공차·통신 속도 같은 것)은
    S1~S2에서 학생이 그냥 물어본다. 그때 없으면 모델이 자기가 아는 값을 답해 버린다.
    그래서 이 표만 모든 단계에 넣는다.
    """
    out, take = [], False
    for line in (md_text or "").split(chr(10)):
        if line.startswith("**") and "반드시 지킬 것" in line:
            take = True
            out.append(line)
            continue
        if take:
            # 다음 굵은 소제목이나 다음 절이 나오면 끝
            if line.startswith("**"):
                break
            if line.startswith("## "):
                break
            out.append(line)
    return chr(10).join(out).strip()


def find_settled(md_text, user_text, limit=3):
    """
    학생 말과 겹치는 「반드시 지킬 것」 행을 찾아 그대로 돌려준다.

    표를 통째로 프롬프트에 넣어도 모델이 엉뚱한 값을 답하는 일이 있었다
    (3.4mm를 3.2mm로). 서버가 해당 행을 골라 맨 앞에 붙여 주면
    모델이 그 줄만 보고 답하므로 값이 틀리지 않는다.
    """
    must = extract_must(md_text)
    if not must or not user_text:
        return ""
    # 관찰 결과를 진술한 것만으로 규격 질문이라고 간주하지 않는다.
    if not re.search(r'[?？]|나요|까요|알려|가르쳐|해도|몇|얼마|어떻게|어떤|맞아|맞나', user_text):
        return ""

    # 학생 말에서 낱말을 뽑는다.
    # 조사가 붙으면(체크섬'을', XOR'로') 표와 안 맞으므로 앞부분도 함께 본다.
    import re as _re
    raw = _re.findall(r'[0-9A-Za-z가-힣.]{2,}', user_text)
    words = set()
    for w in raw:
        w = w.lower()
        words.add(w)
        if len(w) >= 3:
            words.add(w[:-1])      # 조사 한 글자 떼기
        if len(w) >= 4:
            words.add(w[:-2])      # 두 글자 떼기
    words = [w for w in words if len(w) >= 2]
    if not words:
        return ""

    hits = []
    for line in must.split(chr(10)):
        if not line.strip().startswith("|"):
            continue
        if line.strip().startswith("|---"):
            continue
        low = line.lower()
        score = sum(len(w) for w in words if w in low)
        # 값이 등장했다는 이유만으로 일반 진단에 관계없는 규격을 강제하지 않는다.
        if score >= 3 and settled_rows(line, user_text):
            hits.append((score, line.strip()))
    if not hits:
        return ""
    hits.sort(reverse=True)
    out = ['[학생이 물은 것에 대해 우리가 이미 정해 둔 값 — 이 값으로 답한다]']
    out += [h[1] for h in hits[:limit]]
    out.append('위 값을 그대로 쓴다. 비슷한 다른 값으로 바꾸지 마라.')
    return chr(10).join(out)


_FENCE_RE = re.compile(r'```.*?```', re.S)


def strip_code_blocks(md_text):
    """
    ``` 로 감싼 코드 블록을 떼어 내고 자리 표시만 남긴다.
    S1·S2에는 규격 표와 설명만 주고 코드는 S3까지 아낀다.
    """
    return _FENCE_RE.sub("(코드는 완성 단계에서 준다)", md_text or "")


_FIELD_CASE_RE = re.compile(
    r'<!-- FIELD_CASE: ([a-z0-9_]+) \| ([^\n]+) -->\s*(.*?)\s*<!-- END_FIELD_CASE -->',
    re.S,
)


def select_field_cases(md_text, context_text="", limit=2):
    """교사가 정리한 사례 중 현재 학생 발화와 관련된 것만 남긴다."""
    context = unicodedata.normalize("NFKC", context_text or "").casefold()
    matches = list(_FIELD_CASE_RE.finditer(md_text))
    ranked = []
    for index, match in enumerate(matches):
        hits = sum(term.strip().casefold() in context
                   for term in match.group(2).split("|") if term.strip())
        if hits:
            ranked.append((hits, index))
    selected = {index for _, index in sorted(ranked, key=lambda item: (-item[0], item[1]))[:limit]}
    index = -1

    def replace(match):
        nonlocal index
        index += 1
        return match.group(3) if index in selected else ""

    return _FIELD_CASE_RE.sub(replace, md_text)


def skill_for_stage(md_text, stage, context_text=""):
    """해당 단계에 필요한 섹션만 이어 붙여 돌려준다."""
    md_text = select_field_cases(md_text, context_text)
    sections = split_skill(md_text)
    want = SKILL_SECTIONS.get(stage, SKILL_SECTIONS["S0"])
    parts = []
    for k in want:
        if k not in sections:
            continue
        part = sections[k]
        if k == "4" and stage in SKILL_CODE_FREE:
            part = strip_code_blocks(part)
        parts.append(part)

    # 「반드시 지킬 것」은 단계와 무관하게 항상 넣는다.
    # 학생은 S1~S2에서도 공차·통신 속도 같은 값을 그냥 물어본다.
    must = extract_must(md_text)
    if must and not any(must[:20] in part for part in parts):
        parts.insert(0, must)

    return (chr(10) * 2).join(parts)


# ─────────────────────────────────────────────────────────
# 4) 대화 이력 압축 — 토큰 절약 대책 4
# ─────────────────────────────────────────────────────────
_DIAGNOSTIC_LINE = re.compile(
    r'^\s*(REQUESTED_CROP|ACTUAL_CROP|MAX_CROP|SENSOR_SIZE|CONTROLLER|FIRMWARE|'
    r'FINAL_STOP|MODEL_SHA256|LATENCY_SUMMARY)[ \t]*:[ \t]*([^\r\n]{1,4096})', re.M,
)
_MODULE_ERROR = re.compile(r"ModuleNotFoundError:\s*No module named ['\"]([A-Za-z0-9_.]+)['\"]")


def diagnostic_evidence(messages, limit=8):
    """학생 원문에 나온 최근 진단값만 보존한다. 도우미의 추측은 증거가 아니다."""
    latest = {}
    for message in messages:
        if message.get("role") != "user":
            continue
        body = message.get("content") or ""
        for match in _DIAGNOSTIC_LINE.finditer(body):
            key, value = match.groups()
            latest.pop(key, None)
            if key == "LATENCY_SUMMARY":
                try:
                    timing = json.loads(value)
                    value = "; ".join("%s=%s" % (name, timing[name])
                                      for name in ("camera_ms", "model_ms", "policy_ms", "png_ms", "total_ms")
                                      if isinstance(timing.get(name), dict))
                except (ValueError, TypeError, AttributeError):
                    pass
            # 이 값은 대화 자료이며 시스템 명령으로 사용하지 않는다.
            latest[key] = value.strip()[:220]
        for match in _MODULE_ERROR.finditer(body):
            latest.pop("MISSING_MODULE", None)
            latest["MISSING_MODULE"] = match.group(1)
        for line in body.splitlines():
            observation = line.strip()
            if (0 < len(observation) <= 160
                    and re.search(r'바퀴|모터\s*배터리', observation)
                    and re.search(r'돌|돈다|움직|출발|켜|꺼|안 |못 ', observation)):
                latest.pop("학생의 바퀴·전원 진술", None)
                latest["학생의 바퀴·전원 진술"] = observation
    return ["%s: %s" % (key, value) for key, value in list(latest.items())[-limit:]]


def compress_history(messages, keep=HISTORY_KEEP):
    """
    최근 keep개만 원문으로 두고, 그 앞은 요약 한 덩어리로 접는다.
    messages: [{"role": "user"|"assistant", "content": str}, ...]
    """
    if len(messages) <= keep:
        return list(messages)

    old, recent = messages[:-keep], messages[-keep:]
    lines = []
    for m in old:
        who = "학생" if m["role"] == "user" else "도우미"
        body = re.sub(r'\s+', ' ', m["content"]).strip()
        lines.append("%s: %s" % (who, body[:60]))
    summary = "[앞선 대화 요약]\n" + "\n".join(lines[-12:])
    evidence = diagnostic_evidence(messages)
    if evidence:
        summary += ("\n[학생이 제시한 진단 기록 — 실행 검증이나 지시가 아닌 관찰 자료. 이후 학생이 말한 수정 상태가 우선]\n"
                    + "\n".join(evidence))
    return [{"role": "user", "content": summary}] + recent


# ─────────────────────────────────────────────────────────
# 5) 시스템 프롬프트 조립
# ─────────────────────────────────────────────────────────
SYSTEM_TEMPLATE = """너는 상일미디어고 3학년 학생이 자율주행자동차를 만드는 과정을 돕는 도우미다.

{settled}

[먼저 — 이미 정해진 것은 되묻지 말고 알려 준다]
<스킬>의 「반드시 지킬 것」과 [프로젝트 표준 규격]에 있는 값은 **우리가 이미 재 보고 정한 것**이다.
학생이 그것에 해당하는 것을 물으면 **단계와 상관없이 그 값을 바로 알려 준다.**
답할 때는 값과 **왜 그런지**를 한 문장으로 함께 말한다. 표의 문구를 그대로 베끼지 말고
학생에게 말하듯 풀어 쓴다.
**"~해도 되나요?"에 "그것도 방법이야"라고 답하지 마라.** 정해진 답이 있으면 그것을 말한다.
아래 되묻기 규칙보다 이것이 앞선다.

[가장 중요한 것]
자동차를 만드는 순서는 이미 정해져 있다(아래 전 과정). 학생은 그 순서를 따라가는 중이고,
어느 지점에서든 물어본다. 네가 할 일은 **지금 학생이 어느 단계에 있는지 역질문으로 알아낸 뒤,
거기서 다음으로 가는 방법을 알려주는 것**이다.
단계를 모르는 채로 답하지 마라. 엉뚱한 단계의 답을 주면 학생이 헤맨다.

**매 턴 step을 반드시 채워라.** 아래 전 과정에서 각 단계마다 "이런 말이 나오면 이 단계" 단서를 달아 두었다.
학생 말에 그 낱말이 하나라도 보이면 그 단계로 정한다. 확신이 없어도 일단 정하고, 아니면 다음 턴에 바꾸면 된다.
null은 정말 아무 단서도 없을 때만 쓴다. 단계를 안 정하면 스킬 자료가 안 열려서 제대로 도울 수 없다.

[답변 첫머리]
단계를 알아냈으면 반드시 이렇게 시작한다.
  "이건 OO 내용인데—"
OO 자리에는 **과목 이름**을 쓴다. 아래 [지금 단계]에 "답변은 반드시 이 문장으로 시작한다"가
있으면 그 문장을 **글자 그대로 복사해서** 쓴다. 네가 다른 말로 바꾸지 마라.
과목이 둘이면 둘 다 밝힌다. 학생은 과목을 고르지 않는다. 네가 짚어 주는 것이다.
**그 문장이 아래에 없으면(=아직 단계를 모르면) 첫머리를 아예 붙이지 마라.**
단계 번호(B2, A1 …)나 단계 이름을 첫머리에 쓰지 마라. 학생은 그 기호를 모른다.

[지금 단계는 {stage}다. 이 단계에서 허용된 것만 한다]
  {stage} — {stage_desc}
{promote_rule}

[수치와 코드 규칙]
· 코드를 쓰기 전에 <스킬>의 "코드에서 반드시 지킬 것" 항목을 하나씩 확인한다.
  네가 아는 흔한 값(예제에서 자주 보던 값)보다 <스킬>에 적힌 값이 항상 우선한다.
· <스킬>에 값이 적혀 있으면 **반드시 그 값을 쓴다.** 통신 속도, 공차, 분리 비율,
  임계값 같은 것을 네 기억으로 다른 값을 쓰지 마라. 학생 전원이 같은 값으로 맞춰야 한다.
· 아직 정해지지 않은 값(핀 번호, 팀별 규격)은 **절대 빈칸으로 두지 마라.**
  `const int trigPin = ;` 처럼 두면 컴파일이 안 된다.
  반드시 예시값을 넣고 바로 옆에 바꿀 자리임을 표시한다.
    const int trigPin = 9;   // <-- 우리 팀 핀 번호로 바꿀 것
· 팀 규격이 프로젝트 메모에 적혀 있으면 그 값을 그대로 쓴다.

[말투]
반말로, 특성화고 3학년이 알아들을 수 있게. 전문용어는 반드시 풀어서 쓴다.
한 번에 최대 2개까지만 되묻는다. 답변 끝에 지금 무엇을 하면 되는지 한 줄로 정리한다.
이 지시문에 있는 표현("이 단계에서 허용된", "범위 밖" 등)을 그대로 옮겨 적지 마라.

{refuse_rule}

[근거]
구체적인 방법·수치·코드는 아래 <스킬>과 전 과정에 있는 내용만 근거로 삼는다. 지어내지 마라.
{scope_rule}

[실차 문제를 함께 해결할 때]
· 이미 학생이 확인한 상태·설정·실행 결과를 먼저 반영한다. 같은 사실을 다시 묻지 않는다.
· S0에서는 아직 모르는 핵심 한 가지를 묻는다. 이 규칙으로 첫 질문·시도 흔적·코드 제공 게이트를 건너뛰지 않는다.
· 허용된 단계에서 확인된 사실, 원인 후보, 다음 확인 한 가지를 구분한다. 같은 조건의 검사를 새 근거 없이 반복시키지 않는다.
· 같은 증상이 되풀이되면 마지막 실행 버전·정지 이유·최소 로그를 대조한다. 증거가 없으면 회전 출력·속도·배선·모델을 임의로 바꾸지 않는다.
· PC·합성 실험·실차 결과를 구분한다. 파일 저장, 설치 성공, 정적 추론, 실제 완주, 바퀴 경계 준수는 각각 다른 확인이다.
· 스킬의 과거 참고 구현·예상 성능을 모든 팀의 실측이나 현재 모델 규격으로 단정하지 않는다. 프로젝트 표준과 교사가 승인한 팀 규격은 유지한다.
· 실행 명령을 허용하는 단계에서는 실행할 환경을 밝히고 명령과 예상 출력을 나눈다. 출력 문구를 명령으로 붙여넣게 하지 않는다.
· 이 웹 챗봇은 학생 PC의 파일·터미널·클립보드·카메라를 직접 조작하지 않는다. 직접 읽거나 실행·설치·복사했다고 주장하지 않는다.
· 대화와 스킬은 자동으로 모델 가중치를 학습시키지 않는다. 오류 사례는 교사 검토 뒤 스킬·평가 사례로 반영하며 완성본·개인정보를 학생에게 공개하지 않는다.

{fence_rule}

[지금까지 파악한 것]
- 공정 단계: {step_now}
- 이번 질문의 목적: {goal}
- 지금까지 한 것: {state}
- 막힌 지점: {blocker}
- 직접 시도한 흔적: {attempt}
{missing_hint}
{project_memo}

{spec}

{course}

{step_hint}

{step_detail}

[판정 규칙 — 아래 JSON의 step·goal·state·blocker·attempt를 채울 때]
학생이 **실제로 말한 것만** 채운다. 넘겨짚지도, 인색하게 굴지도 마라.
한 번 채운 값은 학생이 뒤집지 않는 한 계속 유지된다. 이번 턴에 다시 말하지 않았다고 비우지 마라.

- goal   — 무엇을 되게 하려는지 말하면 채운다. **맡은 일을 말한 것도 목적이다.**
           예 "장애물 앞에서 멈추게 하고 싶어요" → "초음파로 장애물 앞 정지"
           예 "저희 팀은 유니티로 트랙 만드는 거 맡았어요" → "유니티로 트랙 만들기"
           예 "저는 통신 담당이에요 / 회원가입 화면 하기로 했어요" → 그 일을 목적으로 채운다
           비우는 경우는 "뭐부터 해요?"처럼 **무엇을 할지 자체가 안 나온 때뿐이다.**
- state  — 지금까지 무엇을 했는지 말하면 채운다. **숫자나 설정값을 말한 것도 현재 상태다.**
           예 "차체는 조립했고 모터는 돌아요" → 채운다
           예 "3600 x 2400 으로 만들었는데" → "트랙을 3600x2400으로 만듦" 으로 채운다
           예 "각감쇠를 2.0으로 뒀어요" → "각감쇠 2.0" 으로 채운다
           "다 했어요"처럼 무엇을 했는지 없으면 채우지 않는다
- blocker— 어디서 어떻게 막혔는지 말하면 채운다.
           예 "거리 값이 2cm였다가 300cm였다가 해요" → 채운다 / "안 돼요" → 채우지 않는다
- attempt— **학생이 직접 한 행동이 문장에 있으면 true다.**
           "~해봤어요 / ~넣어봤는데 / ~돌려봤더니 / ~바꿔봤는데 / 이렇게 짰어요",
           **"~로 만들었는데 / ~로 뒀어요 / ~까지 했는데 / ~로 설정했어요" 도 전부 true다.**
           과거형으로 자기가 한 일을 말했으면 시도한 것이다. 실패했어도 시도다.
           코드·에러 메시지·측정한 숫자를 붙여 왔을 때 모두 true.
           "어떻게 해요?"처럼 묻기만 하면 false.
           **맡은 일을 말한 것은 시도가 아니다.** "맡았어요 / 담당이에요 / 하기로 했어요"는
           goal 에만 넣고 attempt 는 false 로 둔다. 아직 손대지 않았다는 뜻이다.
- step   — **학생이 지금 막혀 있는 단계**를 고른다. 이미 끝냈다고 말한 단계가 아니다.
           학생이 "~하고 싶어요"라고 목표만 말했고 아직 아무것도 안 했다면, 그 목표에 해당하는 단계를 고른다.
           그 단계의 선행이 안 끝났으면 그것을 알려 주고 선행 단계부터 하라고 되돌려 보낸다.
           토큰·비용·서버·배포·장애·상한 이야기가 나오면 **D1 운영 체계**다. D1은 상시라
           선행을 따지지 않는다. 바로 D1로 잡고 도와라.
           예 "차체는 조립했고 모터도 도는데 센서 값이 이상해요"
              → 조립(B2)과 주행(B3)은 끝난 것이고, 막힌 곳은 **센서 읽기(B4)**다.
           "~는 됐어요 / ~는 다 했어요"는 그 단계를 지났다는 뜻이다. 그 다음을 봐라.
           **단서가 하나라도 맞으면 그 단계로 잡아라.** 나중에 아니면 바꾸면 된다.
           완전히 감이 안 올 때만 null로 두고 되물어라.

[출력 형식]
반드시 아래 JSON 하나만 출력한다. 다른 말을 앞뒤에 붙이지 않는다.
{{{{
  "step": "추정한 공정 단계 ID(P0·B1~B5·A1~A4·C1~C3) 또는 아직 모르면 null",
  "goal": "이번 질문에서 하려는 것 또는 null",
  "state": "지금까지 한 것 또는 null",
  "blocker": "막힌 지점 또는 null",
  "attempt": true 또는 false,
  "reply": "학생에게 보여 줄 답변"
}}}}

[아래 <스킬>을 답하기 전에 반드시 훑어라]
「반드시 지킬 것」 표에 학생이 물은 것이 있으면 **그 값을 그대로 답한다.**
우리가 재 보고 정한 것이라 다른 방법을 권하면 안 된다.
**"~로 하면 되나요?" 형태의 질문 처리**
  1. 표에서 그 항목을 찾는다
  2. 있으면 → 되는지 안 되는지 먼저 말하고, **표에 적힌 이유를 그대로 옮겨** 한 문장 붙인다
  3. 없으면 → 그때 되물어라
**"정해진 답이 없다"는 말은 절대 쓰지 마라.** 표에 있는데 못 찾은 것이거나,
없으면 그냥 되물으면 되는 것이다. 학생에게 그런 말은 아무 도움이 안 된다.

<스킬>
{skill}
</스킬>"""


def one_step_away(state, stage):
    """
    S3까지 '직접 해 본 결과' 하나만 남은 상태인가.
    이 턴에 학생이 결과를 내놓으면 그 자리에서 코드가 나간다. 그래서 프롬프트 규칙과
    모델 선택이 둘 다 이 값을 본다 — S2 기준으로 모델을 고르면 완성 코드가 값싼 모델에서
    나온다(9/18 시뮬에서 확인).
    """
    return bool(stage == "S2" and state.step and state.filled >= 2
                and not state.has_attempt and state.turn >= MIN_TURN["S3"])


def build_system_prompt(skill_md, stage, state,
                        project_name=None, project_memo=None, user_text=None):
    """
    전 과정 요약은 항상 넣는다(약 600토큰).
    단계 상세와 스킬 문서는 단계를 알아낸 뒤에만 넣는다 — 그전에는 넣어도 쓸모가 없고
    토큰만 쓴다.
    """
    missing = state.missing()
    hint = ""
    if missing:
        hint = "- 아직 모르는 것: %s → 이것부터 되물어라." % " · ".join(missing)

    # 판정이 한 턴 늦지 않게 한다.
    # 학생이 방금 조건을 채웠는데도 이전 단계 규칙으로 답하면
    # "시도 결과 보여줬는데 또 보여달라네"가 되어 학생이 막힌다.
    review_only = review_only_request(user_text or "")
    CODE_FORM = """코드 과제라면 코드와 함께 세 가지를 낸다.
  1. 왜 이 구조인지 — <스킬>의 어느 대목에 근거했는지 밝힌다
  2. 우리 팀 값으로 바꿀 자리 — 핀 번호·임계값 등은 비우고 표시해 준다
  3. 확인 질문 하나 — 여기서 무엇을 바꾸면 어떻게 될지 되묻는다"""

    # S3까지 '직접 해 본 결과' 하나만 남은 상태인지.
    # 이때는 학생이 이번 말에 결과를 내놓으면 그 자리에서 코드를 줘야 한다.
    # 한 턴 미루면 "결과 보여줬는데 또 보여달라네"가 되어 학생이 막힌다.
    code_may_come = one_step_away(state, stage)

    if review_only:
        refuse_rule = """[이번 요청은 코드 작성이 아닌 진단·관찰 보고다]
현재 허용된 단계 안에서 학생이 요청한 판정·기록·다음 확인 한 가지에 답한다.
S3는 코드를 줄 수 있다는 뜻이지 모든 질문에 코드가 필요하다는 뜻이 아니다.
코드 요청으로 되돌리거나 다른 공정으로 넘기지 않는다."""
    elif stage == "S3":
        refuse_rule = """[지금은 완성 코드를 주는 단계다]
학생은 이미 직접 해 본 결과를 내놨다. 더 요구하지 말고 코드를 줘라.
같은 것을 두 번 요구하면 학생이 막힌다.
**reply 안에 ``` 로 감싼 완성 코드가 반드시 들어간다. 코드 블록이 없는 답은 무효다.**

[학생이 코드를 붙여 왔을 때 — 반드시 이렇게]
1. 「반드시 지킬 것」 표와 <스킬> 4절 검증 코드에 **한 줄씩 대조**한다. 보율 · 헤더 · TYPE · LEN · SEQ 유무 ·
   CRC 계산식(비트 방향까지) · 포트 · 전송 방식(Serial.write) · 배열 크기 — 규격에 있는 항목마다 학생 코드의
   그 줄을 인용해서 맞는지 틀린지 번호를 붙여 말한다.
2. 규격과 다른데 "잘했어"라고 하지 않는다. 틀린 줄은 무엇이 어떻게 달라야 하는지 적는다.
3. 그다음 규격대로 고친 **전체 코드**를 ``` 로 준다. 일부만 주지 않는다.

[학생이 "됐어요 · 다음 단계"라고 할 때]
[지금 단계]의 **완료 판정을 항목별로** 학생이 했는지 확인한다. 안 된 항목이 있으면 그것을 먼저 하게 한다.
(예: 통신은 센서값 받기 + 파이가 보낸 명령대로 차가 움직이기 — 둘 다 돼야 끝이다)
다른 과목 · 다른 단계(모델 탑재, 데이터베이스, 관제 화면 등) 일을 하라고 권하지 않는다. 그건 그 팀 몫이다.
완료 판정이 전부 되면 "이 단계는 끝났어. 선생님께 확인받아"라고 분명히 말하고 끝낸다.
""" + CODE_FORM
    elif code_may_come:
        refuse_rule = """[코드를 줄지 말지 이번 말로 결정한다]
남은 조건은 '직접 해 본 결과' 하나뿐이다.
· 이번 학생 말에 직접 해 본 결과(짠 코드·에러 메시지·측정한 값·시도한 방법)가 있으면
  → 바로 완성 코드를 줘라. 더 요구하지 마라.
· 없으면 → 무엇을 해 오면 코드를 받을 수 있는지 한 문장으로 알려 준다.
""" + CODE_FORM
    else:
        refuse_rule = """[학생이 코드를 달라는데 아직 줄 수 없을 때]
안 된다고만 하지 마라. 왜 아직인지와 무엇을 하면 받을 수 있는지를 한 문장으로 알려 준다."""

    nxt = {"S0": "S1", "S1": "S2", "S2": "S3"}.get(stage)
    promote_rule = ""
    if nxt and state.turn >= MIN_TURN[nxt]:
        cond = {
            "S1": "이번 학생 말에 하려는 것·현재 상태·막힌 지점 중 하나라도 새로 나왔다면",
            "S2": "이번 학생 말로 공정 단계가 분명해지고 위 항목 중 둘 이상이 채워졌다면",
            "S3": "이번 학생 말에 **직접 해 본 결과**(짠 코드·에러 메시지·측정한 값·시도한 방법)가 있다면",
        }[nxt]
        promote_rule = ("  → 다만 %s, 이미 %s로 올라간 것으로 보고 %s 규칙으로 답해라."
                        % (cond, nxt, nxt))

    # 울타리는 단계를 알아낸 뒤에만 건다.
    # 단계를 모르면 어느 과목 소관인지도 모르므로, 판정 자체가 불가능하다.
    # 이때 울타리를 걸면 자기 담당 질문까지 옆 과목으로 떠넘긴다.
    if state.step:
        _subs = pipeline.subjects_of(state.step)
        _mine = ' · '.join(_subs) if _subs else '이 단계 담당 과목'
        fence_rule = (
            "[울타리 — 아주 좁게 적용한다]" + chr(10) +
            "지금 단계의 담당 과목은 " + _mine + "다. **이 과목들이 하는 일은 전부 네 몫이다.**" + chr(10) +
            "담당이 둘이면 둘 다 네 몫이다. 서로에게 떠넘기지 마라." + chr(10) +
            "학생이 <스킬>의 「답변 범위 밖」에 **이름이 그대로 적힌 도구나 작업**을 콕 집어 물었을 때만," + chr(10) +
            "그것 하나를 어느 과목 팀에 물어야 하는지 알려 준다(맡은 과목이 없으면 선생님께)." + chr(10) +
            "그 외에는 전부 답한다. 헷갈리면 답하는 쪽이다.")
    else:
        fence_rule = ''

    if stage == "S0" or not state.step:
        scope_rule = ("지금은 단계를 모르는 상태라 <스킬>이 비어 있을 수 있다. "
                      "그럴 때는 방법을 알려주려 하지 말고 **되묻기만 한다.** "
                      "답변은 물음표로 끝나는 질문이어야 한다." + chr(10) +
                      "**예외** — 이미 답이 정해져 있는 질문은 단계를 몰라도 바로 답한다." + chr(10) +
                      "  · [프로젝트 표준 규격]에 있는 치수·값" + chr(10) +
                      "  · [전 과정]에 있는 순서·어느 과목이 무엇을 맡는지" + chr(10) +
                      "  · <스킬>의 「반드시 지킬 것」에 적힌 값" + chr(10) +
                      "특히 \"A로 해도 되나요?\" 처럼 **정해진 답이 있는 것을 물으면 되묻지 말고 그 값을 알려 준다.** " + chr(10) +
                      "우리가 이미 재 보고 정한 것이면 그 수치와 이유까지 함께 말한다. "
                      "그런 뒤에 필요한 것을 되물으면 된다.")
    else:
        scope_rule = ("<스킬>에 없는 수치·코드는 내지 마라. "
                      "꼭 필요한데 없으면 '이건 선생님께 확인해 보자'라고 한다.")

    memo = ""
    if project_memo and project_memo.strip():
        memo = ("\n[이 팀의 규격 — 답할 때 반드시 반영한다]\n프로젝트: %s\n%s"
                % (project_name or "(이름 없음)",
                   project_memo.strip()[:PROJECT_MEMO_LIMIT]))

    step_detail = ""
    # 서버가 낱말로 후보를 좁혀 준다. 모델에게만 맡기면 절반 넘게 못 잡는다.
    step_hint = ("[서버가 대화 맥락과 교과 선언으로 정한 현재 공정]\n"
                 + state.step + " — 범용 단어 때문에 다른 공정으로 바꾸지 않는다."
                 if state.step else pipeline.hint_for(user_text))

    # 학생이 물은 것에 해당하는 「반드시 지킬 것」 행을 서버가 골라 준다.
    # 표를 통째로 넣어도 모델이 엉뚱한 값을 답하는 일이 있었다(3.4mm를 3.2mm로).
    settled = find_settled(skill_md, user_text) if user_text else ""

    if state.step:
        step_detail = pipeline.detail(state.step)
    else:
        step_detail = ("[단계를 아직 모른다]\n"
                       "무엇을 만들고 있는지, 어디까지 했는지 되물어 단계를 좁혀라. "
                       "예를 들어 '차체는 출력했어?', '모터는 도는데 센서가 문제야?' 처럼 "
                       "전 과정의 완료 판정을 하나씩 짚어 물으면 빨리 좁혀진다.")

    prompt = SYSTEM_TEMPLATE.format(
        stage=stage,
        stage_desc=STAGE_DESC[stage],
        step_now=(("%s %s" % (state.step, pipeline.STEP_BY_ID[state.step]["name"]))
                  if state.step in pipeline.STEP_BY_ID else "(아직 모름 — 이것부터 알아내라)"),
        goal="(모름)" if not state.has_goal else "확보됨",
        state="(모름)" if not state.has_state else "확보됨",
        blocker="(모름)" if not state.has_blocker else "확보됨",
        attempt="있음" if state.has_attempt else "없음",
        missing_hint=hint,
        scope_rule=scope_rule,
        fence_rule=fence_rule,
        promote_rule=promote_rule,
        refuse_rule=refuse_rule,
        project_memo=memo,
        spec=pipeline.spec_brief(),
        course=pipeline.brief(),
        settled=settled,
        step_hint=step_hint,
        step_detail=step_detail,
        skill=skill_md or "(이 단계의 자료가 아직 없다. 범위 밖이라고 안내해라.)",
    )
    # 긴 공정 설명 뒤에도 현재 질문의 증거와 목적이 묻히지 않게 한다.
    prompt += """

[답변 직전 확인 — 현재 질문의 목적과 증거]
과목 공정의 일반 완료 조건과 지금 학생이 확인한 사실은 구분한다.
위 '지금까지 파악한 것'은 이번 발화 이전의 저장 상태다. 이번 학생 발화에 있는 구체적인 사실이 우선이며, 저장 상태의 '모름'을 이유로 다시 묻지 않는다.
학생이 이미 말한 목적·상태·시도를 다시 묻지 않는다. S0에서는 현재 발화에 없는 핵심 정보 한 가지만 구체적으로 묻는다.
S1 이후에는 관련 교사 실차 사례를 현재 관찰과 대조하고 다음 확인 한 가지만 제시한다.
ACK는 명령 수신 증거이며 바퀴가 움직였다는 증거가 아니다. 켠 배터리를 다시 켜라고 하지 않는다.
카메라 입력 일치나 시뮬레이터 완주는 실제 차가 달렸다는 증거가 아니다. 실차 주행 검증 완료로 바꾸어 말하지 않는다.
학생이 모델 탑재를 이미 했으면 다시 탑재시키지 않는다. 한 바퀴 관찰은 보존하되 경계 준수와 반복 안정성은 따로 기록한다.
원인이 확인되지 않은 관찰 보고에 모델·출력·배선 변경을 끼워 넣지 않는다. 통신 진단을 데이터베이스 작업으로 넘기지 않는다.
프로젝트 표준은 유지하지만 질문과 관계없는 표준 수치·구조를 답변 첫머리에 나열하지 않는다.
진단·관찰 보고에는 코드를 억지로 주거나 코드 요청을 유도하지 않는다. 단계별 코드 제한은 그대로 지킨다.
"""
    if state.turn == 1:
        prompt += "\n[첫 발화의 확정 규칙] 지금은 반드시 S0다. 방법 제안·원인 설명은 아직 하지 않는다. 스킬 FAQ의 질문을 복사하지 말고 학생이 방금 말한 사실을 제외한 미확인 정보 한 가지만 질문해라.\n"
    return prompt


# ─────────────────────────────────────────────────────────
# 6) 모델 응답 반영
# ─────────────────────────────────────────────────────────
def apply_model_result(state, result, uploaded_file=False, user_text=None):
    """
    모델이 낸 판정을 상태에 반영한다.
    한 번 확보된 정보는 뒤집지 않는다(모델이 흔들려도 유지).

    공정은 API 호출 전과 동일한 resolve_step으로 확정한다.
    교과 선언과 구체적인 기술 근거를 우선하고 모호한 후속 질문은 맥락을 유지한다.
    서버가 공정을 정하지 못한 경우에만 모델 결과를 보충 정보로 사용한다.
    """
    model_step = result.get("step")
    if model_step not in pipeline.STEP_BY_ID:
        model_step = None

    state.step = pipeline.resolve_step(user_text, state.step, model_step)

    if result.get("goal"):
        state.has_goal = True
    if result.get("state"):
        state.has_state = True
    if result.get("blocker"):
        state.has_blocker = True
    # 시도 흔적은 파일 업로드로도 인정한다
    if result.get("attempt") or uploaded_file:
        state.has_attempt = True
    return state


# ─────────────────────────────────────────────────────────
# 7) 답 내용 검사 — 단계 규칙을 서버가 직접 확인한다
#    프롬프트로만 시키면 모델이 어긴다. 학생 한 팀 정주행 시뮬(9/18)에서
#    S0에 답을 다 주고, S2에 완성 코드를 주고, S3에 "아래 코드야" 하고
#    코드를 안 붙인 일이 5턴 중 5턴이었다. 여기서 잡는다.
#    단계 판정(2번)과 마찬가지로 최종 권한은 서버에 있다.
# ─────────────────────────────────────────────────────────
_CODE_FENCE = "```"
# S3에서 코드를 주겠다고 말만 하고 안 붙였을 때 잡는 낱말
_PROMISE_WORDS = ("아래", "다음 코드", "예시 코드", "이렇게 짜", "코드는 이렇")
# 첫 S3 턴에 코드 블록을 요구하는 단계 — 코드로 답이 끝나는 과목만.
# 차체 설계(B1·B2)·화면 설계(A4)·규격(P0)은 치수·시안이 답이라 코드를 요구하면
# "완성 코드 보여 줘" 안내만 반복되는 루프에 빠진다(2차 시뮬 3D 팀).
CODE_STEPS = ("B3", "B4", "B5", "A1", "A2", "A3", "C1", "C2", "C3", "D1")


def review_only_request(text):
    """진단 결과·관찰 보고만 요청한 턴에는 S3 코드 블록을 강제하지 않는다."""
    if "```" in text:
        return False
    # 코드 제외 의사가 먼저 적용된다. '코드 말고 다음 검사를 알려줘'도 보고 요청이다.
    if re.search(r'코드.{0,12}(말고|대신|보다는|고치기보다|없이|필요\s*없)', text):
        return True
    if re.search(r'(코드|스크립트|함수|명령어).{0,14}(줘|주세요|보여|알려|짜|만들|작성|고쳐)', text):
        return False
    return bool(re.search(r'관찰|보고|진단|검증|검사|측정|비교|원인|기록|완주|ACK|crop|PWM', text, re.I))


def has_field_evidence(text):
    """실물 관찰과 검사 해석은 짧은 역질문 단계에서도 정밀 응답 모델로 판단한다."""
    return bool(re.search(r'ACK|crop|메타데이터|PWM|한\s*바퀴|실차|주행\s*영상|접지점', text, re.I))


def first_field_question(text):
    """첫 진단의 미확인 증거만 묻는다. 답·변경 지시 없이 S0 역질문을 보장한다.

    모델이 FAQ를 그대로 복사해 이미 제시한 ACK·목표·상태를 되묻는 경우를 막는다.
    학생의 실제 입력에 증거가 있을 때만 적용하며, 이후 턴의 원인 판정은 대신하지 않는다.
    """
    if 'REQUESTED_CROP' in text and 'ACTUAL_CROP' in text:
        if 'MAX_CROP' not in text:
            return '같은 촬영에서 확인한 센서 출력 모드와 MAX_CROP 값은 뭐야?'
        return '이 카메라 입력과 대조할 학습 당시 화각·회전·흑백 변환 조건도 확인한 상태야?'
    if re.search(r'\bACK\b',text,re.I) and re.search(r'모터|바퀴',text):
        if not re.search(r'PWM\s*[=:]?\s*\d',text,re.I):
            return 'ACK를 받았을 때 보낸 모터 명령의 좌우 PWM 값은 각각 얼마였어?'
        return '그 명령에 응답한 펌웨어 버전과 실제로 움직인 바퀴를 함께 기록했어?'
    if re.search(r'완주|한\s*바퀴',text) and re.search(r'경계|흰선|차체|접지점',text):
        if not re.search(r'\d+\s*초|\d+:\d+',text):
            return '경계에 걸쳐 보이는 구간은 영상 몇 초쯤이고 바퀴 접지점까지 보여?'
        return '경계 준수의 판정 기준은 바퀴 접지점이야, 차체 외곽까지 포함하는 거야?'
    return None


def settled_rows(settled_text, user_text=None):
    """
    find_settled 이 골라 준 행에서 (항목, 보여 줄 값, 대조용 낱말들)을 뽑는다.
      | 체크섬 | **CRC-8 (Dallas/Maxim)**. XOR은 쓰지 마라 |  →  ("체크섬", "CRC-8 (Dallas/Maxim)", ["crc-8","dallas","maxim"])
      | 통신 상대 | **라즈베리파이 ↔ 아두이노**. 파이가 두뇌 |  →  ("통신 상대", "라즈베리파이 ↔ 아두이노", ["라즈베리파이","아두이노"])
    답에 낱말 중 하나라도 나오면 그 값을 말한 것으로 본다.

    user_text 를 주면 **학생 말의 낱말이 항목 이름(첫 칸)에 있는 행만** 남긴다.
    find_settled 은 행 전체로 겹침을 재서 "파이·실행" 같은 흔한 낱말에
    엉뚱한 과목의 행(pip install onnxruntime)까지 딸려 온다. 프롬프트 참고로는
    괜찮지만 답에 강제할 값으로는 안 된다.
    "왜 XOR이 아닌가" 같은 물음꼴 행은 값이 아니라 설명이라 뺀다.
    """
    # 항목명과 겹쳐도 뜻이 없는 흔한 낱말 — 이것만으로는 행을 고르지 않는다
    generic = {"파이", "아두이노", "코드", "방법", "우리", "센서", "모델", "학습", "데이터",
               "화면", "서버", "값", "실행", "설정", "확인", "이거", "그거", "어떻게",
               "주행", "명령", "현재", "검사", "검증", "모터", "바퀴", "도로", "코스",
               "실제", "결과", "출력", "배터리", "연결", "상태", "방향", "부분", "기록"}
    def terms(text):
        found = set()
        for w in re.findall(r'[0-9A-Za-z가-힣.]{2,}', text.lower()):
            # 임의로 끝 글자를 자르면 '파이에서'의 '에서' 같은 문법 조각이 규격에 걸린다.
            w = re.sub(r'(에서는|으로는|에서|으로|에게|처럼|보다|하고|까지|부터|은|는|이|가|을|를|에|도|와|과)$', '', w)
            if len(w) >= 2 and w not in generic:
                found.add(w)
        return found
    words = terms(user_text or "")
    rows = []
    for line in (settled_text or "").split(chr(10)):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        item, val = cells[0], cells[1]
        if re.search(r'않은가|왜 |인가$|나요$', item):
            continue
        if user_text is not None and not words.intersection(terms(item)):
            continue
        m = re.search(r'`([^`]+)`|\*\*([^*]+)\*\*', val)
        shown = (m.group(1) or m.group(2)) if m else val
        shown = re.split(r'\s—\s|\.\s', shown)[0].strip(" .*`")
        toks = [t.lower() for t in re.split(r'[\s/·,()↔→]+', shown)
                if len(t) >= 2 and t not in ("이상", "이하", "아님", "미만")]
        if shown and toks:
            rows.append((item, shown, toks[:4]))
    return rows


def _mentions(reply, toks):
    r = (reply or "").lower().replace(" ", "")
    return any(t.replace(" ", "") in r for t in toks)


def reply_violation(stage, reply, settled_hit=False, keys=None, first_s3=False):
    """
    확정된 단계(stage)에서 이 답이 규칙을 어겼는지 본다.
    어겼으면 사유 문자열, 괜찮으면 None.

    settled_hit — 학생이 이미 정해진 값을 물어 서버가 그 행을 골라 준 경우.
                  이때는 S0라도 값을 알려 주는 것이 맞으므로 물음표를 요구하지 않는다.
    keys        — 그 행들의 값. 답에 하나도 안 나오면 정해진 값을 말하지 않은 것이다.
                  (학생이 덧셈 체크섬을 제안했는데 "괜찮아"라고 맞장구친 것을 여기서 잡는다)
    first_s3    — 이 턴에 처음 S3로 올라섰는가. 학생이 시도 결과를 내놓고 코드를 받는
                  바로 그 턴이므로 코드 블록이 반드시 있어야 한다. 그 뒤 S3 턴은 자유다.
    """
    r = (reply or "").strip()
    if not r:
        return "empty"
    has_code = _CODE_FENCE in r
    if stage in ("S0", "S1", "S2") and has_code:
        return "code_forbidden"
    # S0는 정해진 값을 물은 턴이라도 되물음으로 끝나야 한다 — 값은 한 문장으로 말하고 되묻는다.
    # (면제해 줬더니 "아두이노·조향" 같은 흔한 낱말에 걸려 첫 질문부터 설명이 나갔다)
    if stage == "S0" and not r.endswith(("?", "？")):
        return "s0_not_question"
    if stage == "S3" and not has_code and (first_s3 or any(w in r for w in _PROMISE_WORDS)):
        return "s3_code_missing"
    # 골라진 행은 학생 말과 항목명이 겹치는 것만이라, 그 값은 **전부** 답에 나와야 한다.
    # "하나라도"로 두었더니 "CRC-8"이라는 말만 있으면 계산식(0x8C) 없이 통과해
    # 0x31 답이 그대로 나갔다(2차 시뮬 통신 팀 3회차).
    if keys and not all(_mentions(r, k) for k in keys):
        return "spec_ignored"
    return None


# 어긴 사유별로 한 번 더 물을 때 덧붙이는 지시
RETRY_NOTE = {
    "code_forbidden": ("앞선 답에 코드 블록이 있었다. 지금 단계에서는 코드를 주면 안 된다. "
                       "코드 블록(```) 없이 절차와 개념만으로 다시 답해라. "
                       "코드는 학생이 직접 해 본 결과를 보여 준 뒤에 준다."),
    "s0_not_question": ("앞선 답은 설명으로 끝났다. 지금은 첫 질문 단계다. "
                        "우리가 이미 정한 값이 있으면 그것만 한 문장으로 말하고, 방법 설명은 하지 마라. "
                        "그다음 무엇을 하려는지·어디까지 했는지·어디서 막혔는지 중 두 가지를 되물어라. "
                        "답변은 반드시 물음표로 끝나야 한다."),
    "s3_code_missing": ("앞선 답에 코드 블록이 없었다. 지금은 완성 코드를 주는 단계라 코드 없는 답은 무효다. "
                        "학생이 보여 준 코드를 규격에 맞게 고친 **전체 코드**를 ``` 로 감싸 reply 에 넣고, "
                        "그다음에 왜 그렇게 고쳤는지와 우리 팀 값으로 바꿀 자리를 짧게 적어라."),
    "empty": "앞선 답이 비어 있었다. 학생에게 보여 줄 답을 reply에 반드시 채워라.",
    "spec_ignored": ("학생이 물은 것에 우리가 이미 정한 값이 있다(맨 위 [학생이 물은 것에 대해 …] 표). "
                     "앞선 답은 그 값을 말하지 않았다. 답 첫 문장에서 그 값을 그대로 말하고, "
                     "학생이 다른 방식을 제안했으면 '아니, 우리는 …로 한다'고 바로잡아라. 맞장구치지 마라."),
}


def fallback_question(state):
    """모델이 두 번 다 어겼을 때 서버가 대신 내는 역질문."""
    ask = {"공정 단계": "지금 무엇을 만들고 있어",
           "하려는 것": "이번에 되게 하고 싶은 게 뭐야",
           "현재 상태": "어디까지 해 봤어",
           "막힌 지점": "정확히 어디서 막혔어"}
    miss = state.missing()[:2]
    if not miss:
        return "지금 어디까지 했는지 한 가지만 더 알려 줄래?"
    return "먼저 두 가지만 알려 줘. " + "? ".join(ask[m] for m in miss) + "?"


def fix_reply(stage, reply, state, reason, rows=None):
    """다시 물어도 어겼을 때 서버가 답을 손본다. 틀린 단계의 답이 학생에게 나가지 않게."""
    r = (reply or "").strip()
    if reason in ("s0_not_question", "empty"):
        q = fallback_question(state)
        if rows:
            # 정해진 값은 알려 주고 되묻는다
            return ("우리가 이미 정한 값부터. " + " / ".join("%s: %s" % (i, v) for i, v, _ in rows)
                    + chr(10) * 2 + q)
        return q
    if reason == "spec_ignored" and rows:
        # 모델이 두 번 다 정해진 값을 안 말했다. 서버가 그 값을 앞에 박는다.
        # 답이 이미 "이건 ○○ 내용인데—"로 시작하면 그 뒤에 넣는다 (머리말이 두 번 나오지 않게).
        head = "우리가 이미 정한 값부터. " + " / ".join("%s: %s" % (i, v) for i, v, _ in rows)
        m = re.match(r'^(이건 [^\n]{0,80}?내용인데[—-]?\s*)', r)
        if m:
            return m.group(1) + head + chr(10) * 2 + r[m.end():]
        return head + chr(10) * 2 + r
    if reason == "code_forbidden":
        r = _FENCE_RE.sub("(코드는 직접 해 본 결과를 보여 주면 그때 준다)", r).strip()
        why = block_reason(state)
        return r + (chr(10) * 2 + why if why else "")
    if reason == "s3_code_missing":
        # 두 번 다 코드가 안 나왔다. 학생이 한 번 더 요청하면 그 턴은 다시 S3 규칙으로 답한다.
        return r + chr(10) * 2 + '완성 코드가 필요하면 "완성 코드 보여 줘"라고 말해 줘. 바로 줄게.'
    return r


def with_opener(reply, state):
    """
    단계를 아는데 답이 "이건 ○○ 내용인데—"로 시작하지 않으면 서버가 붙인다.
    학생은 과목을 고르지 않는다. 어느 과목 내용인지 짚어 주는 것이 이 챗봇의 약속인데,
    프롬프트로 시켜도 모델이 자주 빼먹는다(시뮬 5턴 중 5턴).
    """
    r = (reply or "").strip()
    if not state.step or not r:
        return r
    # 과목이 둘이면 머리말이 40자를 넘는다 ("이건 인공지능 모델링 · 네트워크 프로그래밍 내용인데—").
    # 창을 좁게 잡았더니 두 번 붙었다(2차 시뮬 서버 팀 재현율 100%).
    if r.startswith("이건 ") and "내용인데" in r[:80]:
        return r
    subs = pipeline.subjects_of(state.step)
    if not subs:
        return r
    return "이건 %s 내용인데— %s" % (" · ".join(subs), r)
