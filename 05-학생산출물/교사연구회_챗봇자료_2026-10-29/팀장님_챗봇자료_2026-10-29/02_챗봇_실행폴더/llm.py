# -*- coding: utf-8 -*-
"""OpenAI 호출부. 모델을 바꾸려면 이 파일만 손대면 된다.

API 키가 없으면 모의 모드로 돌아간다. 키 없이도 화면과 게이트를 확인할 수 있다.
"""
import json
import os
import re

MOCK = False
_client = None

# 답변 모드 — 화면의 '+ → 답변 모드'에서 고른다
TIERS = {
    "fast":  {"label": "빠르게", "model": os.getenv("MODEL_FAST",  "gpt-4o-mini")},
    "std":   {"label": "표준",   "model": os.getenv("MODEL_STD",   "gpt-4o-mini")},
    "deep":  {"label": "꼼꼼히", "model": os.getenv("MODEL_DEEP",  "gpt-4o")},
}
DEFAULT_TIER = "std"

# 단계 판정은 저렴한 모델로 (토큰 절약 대책 7)
JUDGE_MODEL = os.getenv("MODEL_JUDGE", "gpt-4o-mini")


def init():
    """앱 시작 시 한 번 호출. 키가 없으면 모의 모드로 전환한다."""
    global MOCK, _client
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        MOCK = True
        return False
    try:
        from openai import OpenAI
        # max_retries — 분당 토큰 한도(429)에 걸리면 라이브러리가 먼저 몇 번 기다렸다 다시 부른다.
        # 기본 2회로는 수업 중 6팀이 몰릴 때 모자랐다(9/21 정주행 시뮬에서 500).
        _client = OpenAI(api_key=key, max_retries=4, timeout=90)
        MOCK = False
        return True
    except Exception:
        MOCK = True
        return False


_TIER_ENV = {"fast": "MODEL_FAST", "std": "MODEL_STD", "deep": "MODEL_DEEP"}


def pick_model(stage, tier):
    """
    단계별 모델 선택.
    완성 코드를 내는 S3만 좋은 모델을 쓰고, 나머지는 저렴한 모델로 처리한다.

    모델 이름은 부를 때마다 환경변수에서 읽는다. 위 TIERS 는 import 시점 값이라
    .env 를 그보다 늦게 읽는 경로(python app.py)에서는 .env 의 MODEL_* 가 무시됐다.
    """
    if stage == "S3":
        t = tier if tier in TIERS else DEFAULT_TIER
        return os.getenv(_TIER_ENV[t], TIERS[t]["model"])
    return os.getenv("MODEL_JUDGE", JUDGE_MODEL)


def ask(system_prompt, history, user_text, stage, max_tokens, tier=DEFAULT_TIER,
        extra_system=None):
    """
    모델에 물어보고 구조화된 결과를 돌려준다.
    반환: (result_dict, tokens_in, tokens_out, model_name)

    extra_system — 서버가 답 내용 검사에서 걸린 뒤 다시 물을 때 덧붙이는 지시.
    """
    model = pick_model(stage, tier)

    if MOCK:
        return _mock(user_text, stage), 0, 0, "mock"

    msgs = [{"role": "system", "content": system_prompt}]
    msgs += history
    msgs.append({"role": "user", "content": user_text})

    def _call(msgs_, extra_system=None):
        mm = list(msgs_)
        if extra_system:
            # 본 지시문 바로 뒤에 붙인다. 대화에 가까울수록 모델이 잘 따른다
            mm = [mm[0], {"role": "system", "content": extra_system}] + mm[1:]
        r = _client.chat.completions.create(
            model=model,
            messages=mm,
            max_tokens=max_tokens,
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        u = getattr(r, "usage", None)
        return (r.choices[0].message.content,
                getattr(u, "prompt_tokens", 0) or 0,
                getattr(u, "completion_tokens", 0) or 0)

    try:
        raw, tin, tout = _call(msgs, extra_system)
    except Exception as e:                       # 학생에게 500 대신 말로 알린다
        return _error_result(e, stage), 0, 0, model
    out = _parse(raw, stage)

    # JSON이 깨졌으면 한 번만 다시 묻는다.
    # 학생에게 "다시 한번 말해 줄래?"가 나가는 것을 막는다.
    if out.pop("_parse_failed", False):
        raw2, tin2, tout2 = _call(
            msgs,
            ((extra_system + chr(10)) if extra_system else "") +
            "앞선 답이 형식을 어겼다. 이번에는 다른 말을 일절 붙이지 말고 "
            "지정된 JSON 객체 하나만 출력해라.")
        tin += tin2; tout += tout2
        out2 = _parse(raw2, stage)
        if not out2.pop("_parse_failed", False):
            out = out2
        elif not out.get("reply"):
            out["reply"] = "다시 한번 말해 줄래?"

    return out, tin, tout, model


def classify_step(user_text):
    """첫 질문 전용 의미 분류. 수업 답변 프롬프트의 규격/스킬과 분리한다."""
    system = '''[공정 의미 분류]
학생이 해결하려는 작업 자체를 분류해 JSON {"step":"ID 또는 null"}만 반환한다.
단어 하나보다 문장 전체의 목적을 본다. 모델링이라는 단어가 있어도 AI는 B1이 아니다.
A1: Unity 게임, 점프, 체력, 트리거, 애니메이션, 가상 물리, 씬/이벤트/게임 상태.
A2: 주행 데이터 수집·라벨링 자체. A3: 인공지능 모델 학습·손실·평가·전처리·모델 선택·성능 측정(추론 워밍업도 모델 성능 실험이면 A3).
A4: 와이어프레임·스타일 가이드. C1: 학습 모델을 실제 차량에 연결해 제어하는 작업.
B1: CAD 차체/부품 설계·치수·간섭·회전 여유·나사 접근성·설계 공차. B2: 이미 설계된 부품의 프린터 출력·필라멘트·노즐·조립 시험.
B3: 실제 모터 배선·기본 구동. B4: 실제 센서값 읽기.
B5: 장치 통신·TCP/UDP·SEQ·CRC·프레임·재접속 백오프·ACK·DNS·RTO·시리얼. 재부팅을 언급해도 패킷 시간/SEQ 문제면 B5.
C2: 웹 앱/JSP/DB/화면 구현. C3: 실제 차량 통합 주행시험.
D1: 서버 운영·권한·프록시·백업·복구·용량·배포·관리 포트·종료 유예·무결성 감시.
P0: 공통 규격이나 준비물 합의. 불명확하면 null.
예상 정답이나 평가 라벨은 제공되지 않는다. 학생 질문만 판정한다.'''
    try:
        response = _client.chat.completions.create(
            model=pick_model('S0', DEFAULT_TIER),
            messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': user_text}],
            temperature=0, max_tokens=80, response_format={'type': 'json_object'})
        usage = response.usage
        try:
            step = json.loads(response.choices[0].message.content).get('step')
        except (ValueError, AttributeError):
            step = None
        return step, usage.prompt_tokens, usage.completion_tokens
    except Exception:
        return None, 0, 0


def _error_result(e, stage):
    """
    OpenAI 호출이 끝내 실패했을 때 학생에게 보여 줄 말. 단계는 올리지 않고 턴도 세지 않는다.
    어떤 오류인지는 서버 창(로그)에 남겨 교사가 본다.
    """
    import re as _re
    import time as _time
    name = type(e).__name__
    msg = str(e)
    print("[OpenAI 오류] %s: %s" % (name, msg[:300]))
    if "RateLimit" in name or "429" in msg:
        m = _re.search(r"try again in ([\d.]+)s", msg)
        wait = int(float(m.group(1))) + 2 if m else 10
        if "insufficient_quota" in msg or "billing" in msg.lower():
            reply = "지금 챗봇 사용 잔액이 없어서 답을 못 만들어. 선생님께 말씀드려 줘."
        else:
            reply = ("지금 질문이 한꺼번에 몰려서 잠깐 기다려야 해. 약 %d초 뒤에 방금 말을 그대로 다시 보내 줘. "
                     "(네가 쓴 건 지워지지 않았어)" % max(wait, 5))
    elif "Authentication" in name or "401" in msg or "invalid_api_key" in msg:
        reply = "챗봇 설정(API 키)에 문제가 있어서 답을 못 만들어. 선생님께 말씀드려 줘."
    elif "Connection" in name or "Timeout" in name:
        reply = "챗봇 서버가 인터넷에 연결되지 않아 답을 못 만들었어. 잠깐 뒤에 다시 보내 줘. 계속 그러면 선생님께."
    else:
        reply = "답을 만들다 문제가 생겼어. 방금 말을 그대로 한 번 더 보내 줘. 계속 그러면 선생님께 말씀드려 줘."
    return {"goal": None, "state": None, "blocker": None, "attempt": False,
            "next_stage": stage, "reply": reply, "_error": name}


def _parse(raw, stage):
    """JSON 파싱 실패 시에도 대화가 끊기지 않게 한다."""
    try:
        d = json.loads(raw)
    except Exception:
        m = re.search(r'\{.*\}', raw or "", re.S)
        if m:
            try:
                d = json.loads(m.group(0))
            except Exception:
                d = None
        else:
            d = None

    if not isinstance(d, dict):
        # 파싱 실패 — 단계를 올리지 않고 답변만 그대로 보여 준다
        return {"goal": None, "state": None, "blocker": None,
                "attempt": False, "next_stage": stage,
                "reply": (raw or "").strip(),
                "_parse_failed": True}

    d.setdefault("goal", None)
    d.setdefault("state", None)
    d.setdefault("blocker", None)
    d.setdefault("attempt", False)
    d.setdefault("next_stage", stage)
    d.setdefault("reply", "")
    # 형식은 맞는데 답변이 비어 있으면 그것도 실패다
    if not (d.get("reply") or "").strip():
        d["_parse_failed"] = True
    return d


# ── 모의 모드 ────────────────────────────────────────────
# 낱말만 보고 공정 단계를 대충 찍는다. 진짜 모델은 대화 맥락으로 판단하지만,
# 키 없이 화면과 게이트 흐름을 확인하려면 이 정도로 충분하다.
_MOCK_STEPS = [
    ("B1", ["차체", "모델링", "퓨전", "fusion", "파트", "스케치", "구속"]),
    ("B2", ["출력", "조립", "후처리", "간섭", "슬라이", "프린트"]),
    ("B3", ["모터", "전진", "후진", "조향", "바퀴", "드라이버", "결선"]),
    ("B4", ["초음파", "조도", "센서", "시리얼", "카메라", "거리", "차선"]),
    ("B5", ["통신", "패킷", "블루투스", "와이파이", "프로토콜", "전송", "텔레메트리"]),
    ("A1", ["유니티", "unity", "시뮬", "트랙", "충돌", "물리"]),
    ("A2", ["데이터", "라벨", "수집", "이미지"]),
    ("A3", ["학습", "인식", "정확도", "모델", "알고리즘", "인자"]),
    ("A4", ["와이어프레임", "시안", "스타일", "화면 설계", "정보 구조", "ux"]),
    ("C1", ["탑재", "추론", "정지선", "표지판"]),
    ("C2", ["서버", "배포", "토큰", "관제", "조회", "디비", "db"]),
    ("C3", ["최적화", "지연", "유실", "대회", "완주", "미션"]),
]


def _guess_step(text):
    t = (text or "").lower()
    for sid, words in _MOCK_STEPS:
        if any(w in t for w in words):
            return sid
    return None


def _mock(user_text, stage):
    """키가 없을 때 쓰는 가짜 응답. 게이트 흐름을 눈으로 확인하는 용도."""
    t = (user_text or "").strip()
    long_enough = len(t) >= 12

    replies = {
        "S0": "지금 어디까지 했는지 두 가지만 알려 줘. 차체는 나왔어? 모터는 돌아?",
        "S1": "정리하면 이런 거 맞아? 맞으면 어떤 순서로 갈지 알려 줄게.",
        "S2": "이런 순서로 가면 돼. 먼저 여기까지 해 보고 결과를 가져와 줘.",
        "S3": "자, 코드는 이렇게 돼. 우리 팀 값으로 바꿔야 할 부분을 표시해 뒀어.",
    }
    return {
        "step": _guess_step(t),
        "goal": t[:40] if long_enough else None,
        "state": t[:40] if len(t) >= 25 else None,
        "blocker": t[:40] if len(t) >= 40 else None,
        # 모의 모드용 대충 판정. 실제 모델은 문맥으로 훨씬 정확히 잡는다
        "attempt": any(w in t for w in
                       ("에러", "해봤", "해 봤", "했는데", "봤는데", "안 돼", "안돼",
                        "넣어봤", "돌려봤", "찍어봤", "결과가")),
        "next_stage": stage,
        "reply": "[모의 응답] " + replies.get(stage, replies["S0"]),
    }
