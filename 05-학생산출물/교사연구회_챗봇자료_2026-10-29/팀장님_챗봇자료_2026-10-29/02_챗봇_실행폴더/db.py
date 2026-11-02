# -*- coding: utf-8 -*-
"""SQLite 저장소. 대화 로그와 토큰 사용량을 남긴다.

여기 쌓이는 기록이 두 가지 산출물이 된다.
  1) messages  → 학생 프롬프트 로그 (연구 산출물)
  2) tokens_*  → 시스템 운영 과목의 실습 데이터
"""
import os
import sqlite3
import datetime
from contextlib import contextmanager

# 배포 시 DATA_DIR을 영구 디스크 경로로 지정한다 (예: /var/data)
DATA_DIR = os.getenv("DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "data.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id            TEXT PRIMARY KEY,
  team_code     TEXT NOT NULL,
  name          TEXT NOT NULL,
  memo          TEXT DEFAULT '',
  created_at    TEXT,
  updated_at    TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
  id            TEXT PRIMARY KEY,
  team_code     TEXT NOT NULL,
  project_id    TEXT,
  step          TEXT,
  title         TEXT DEFAULT '새 대화',
  stage         TEXT DEFAULT 'S0',
  has_goal      INTEGER DEFAULT 0,
  has_state     INTEGER DEFAULT 0,
  has_blocker   INTEGER DEFAULT 0,
  has_attempt   INTEGER DEFAULT 0,
  turn          INTEGER DEFAULT 0,
  created_at    TEXT,
  updated_at    TEXT
);

CREATE TABLE IF NOT EXISTS messages (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id    TEXT NOT NULL,
  role          TEXT NOT NULL,
  content       TEXT NOT NULL,
  stage_at_time TEXT,
  blocked       INTEGER DEFAULT 0,
  tokens_in     INTEGER DEFAULT 0,
  tokens_out    INTEGER DEFAULT 0,
  model         TEXT,
  created_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_sess_team   ON sessions(team_code);
CREATE INDEX IF NOT EXISTS idx_proj_team   ON projects(team_code);
"""

# 기존 DB에 뒤늦게 추가된 컬럼
MIGRATIONS = [
    ("sessions", "project_id", "TEXT"),
    ("sessions", "step", "TEXT"),
]

# 더는 쓰지 않는 컬럼. 과목 선택을 없애면서 skill_id가 남았는데,
# 옛 DB에는 NOT NULL로 걸려 있어 새 대화를 못 만든다. 떼어 낸다.
DROPPED = [
    ("sessions", "skill_id"),
]


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today():
    return datetime.date.today().isoformat()


@contextmanager
def conn():
    """
    연결을 열고 — 정상 종료면 커밋, 예외면 롤백, 어느 쪽이든 닫는다.

    주의: sqlite3.Connection을 그냥 with에 넣으면 커밋만 하고 닫지 않는다.
    그러면 호출마다 연결이 새어 파일 디스크립터가 쌓인다.
    """
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA busy_timeout=15000")
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def init():
    with conn() as c:
        c.executescript(SCHEMA)
        # 여러 스레드가 동시에 읽고 쓰므로 WAL로 둔다
        c.execute("PRAGMA journal_mode=WAL")
        # 이미 만들어진 DB에도 새 컬럼을 붙인다
        for table, col, typ in MIGRATIONS:
            cols = [r["name"] for r in c.execute("PRAGMA table_info(%s)" % table)]
            if col not in cols:
                c.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, col, typ))
        # 안 쓰는 옛 컬럼을 떼어 낸다
        for table, col in DROPPED:
            cols = [r["name"] for r in c.execute("PRAGMA table_info(%s)" % table)]
            if col in cols:
                c.execute("ALTER TABLE %s DROP COLUMN %s" % (table, col))


# ── 프로젝트 ────────────────────────────────────────────
def create_project(pid, team_code, name, memo=""):
    with conn() as c:
        c.execute(
            "INSERT INTO projects (id, team_code, name, memo, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?)",
            (pid, team_code, name, memo, now(), now()))


def get_project(pid):
    with conn() as c:
        r = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        return dict(r) if r else None


def list_projects(team_code):
    with conn() as c:
        rows = c.execute(
            "SELECT p.*, (SELECT COUNT(*) FROM sessions s WHERE s.project_id=p.id) n"
            " FROM projects p WHERE p.team_code=? ORDER BY p.updated_at DESC",
            (team_code,)).fetchall()
        return [dict(r) for r in rows]


def update_project(pid, **kw):
    if not kw:
        return
    kw["updated_at"] = now()
    sets = ", ".join("%s=?" % k for k in kw)
    with conn() as c:
        c.execute("UPDATE projects SET %s WHERE id=?" % sets,
                  list(kw.values()) + [pid])


def delete_project(pid):
    """대화는 지우지 않는다. 프로젝트에서만 떼어 낸다."""
    with conn() as c:
        c.execute("UPDATE sessions SET project_id=NULL WHERE project_id=?", (pid,))
        c.execute("DELETE FROM projects WHERE id=?", (pid,))


# ── 세션 ────────────────────────────────────────────────
def create_session(sid, team_code, project_id=None):
    with conn() as c:
        c.execute(
            "INSERT INTO sessions (id, team_code, project_id, created_at, updated_at)"
            " VALUES (?,?,?,?,?)",
            (sid, team_code, project_id, now(), now()))


def get_session(sid):
    with conn() as c:
        r = c.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        return dict(r) if r else None


def list_sessions(team_code, project_id=None, limit=60):
    q = "SELECT * FROM sessions WHERE team_code=?"
    args = [team_code]
    if project_id:
        q += " AND project_id=?"
        args.append(project_id)
    q += " ORDER BY updated_at DESC LIMIT ?"
    args.append(limit)
    with conn() as c:
        return [dict(r) for r in c.execute(q, args).fetchall()]


def update_session(sid, **kw):
    if not kw:
        return
    kw["updated_at"] = now()
    sets = ", ".join("%s=?" % k for k in kw)
    with conn() as c:
        c.execute("UPDATE sessions SET %s WHERE id=?" % sets,
                  list(kw.values()) + [sid])


# ── 메시지 ──────────────────────────────────────────────
def add_message(session_id, role, content, stage=None, blocked=0,
                tokens_in=0, tokens_out=0, model=None):
    with conn() as c:
        c.execute(
            "INSERT INTO messages"
            " (session_id, role, content, stage_at_time, blocked,"
            "  tokens_in, tokens_out, model, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (session_id, role, content, stage, blocked,
             tokens_in, tokens_out, model, now()))


def get_messages(session_id):
    with conn() as c:
        rows = c.execute(
            "SELECT role, content, stage_at_time, blocked FROM messages"
            " WHERE session_id=? ORDER BY id", (session_id,)).fetchall()
        return [dict(r) for r in rows]


def last_user_message(session_id):
    with conn() as c:
        r = c.execute(
            "SELECT content FROM messages WHERE session_id=? AND role='user'"
            " ORDER BY id DESC LIMIT 1", (session_id,)).fetchone()
        return r["content"] if r else None


# ── 사용량 (시스템 운영 과목의 데이터원) ─────────────────
def usage_today(team_code=None, session_id=None):
    """오늘 호출 횟수. 차단된 요청은 세지 않는다."""
    q = ("SELECT COUNT(*) n FROM messages m JOIN sessions s ON m.session_id=s.id"
         " WHERE m.role='assistant' AND m.blocked=0 AND date(m.created_at)=?")
    args = [today()]
    if team_code:
        q += " AND s.team_code=?"
        args.append(team_code)
    if session_id:
        q += " AND m.session_id=?"
        args.append(session_id)
    with conn() as c:
        return c.execute(q, args).fetchone()["n"]


def usage_summary(days=30):
    """토큰 대시보드용 집계."""
    with conn() as c:
        rows = c.execute(
            "SELECT date(m.created_at) d, s.team_code,"
            "       COUNT(*) calls,"
            "       SUM(m.tokens_in) tin, SUM(m.tokens_out) tout,"
            "       SUM(m.blocked) blocked"
            " FROM messages m JOIN sessions s ON m.session_id=s.id"
            " WHERE m.role='assistant'"
            " GROUP BY d, s.team_code ORDER BY d DESC LIMIT ?", (days * 20,)
        ).fetchall()
        return [dict(r) for r in rows]
