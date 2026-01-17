# presence_api.py
# Minimal Presence API for Flask (non-breaking). Provides /api/presence GET/POST.
#
# Integrate by importing register_presence_api(app, db_conn_factory) from app.py.
# db_conn_factory should return a sqlite3.Connection (with row_factory sqlite3.Row).

from __future__ import annotations
import json
import time
import sqlite3
from typing import Callable, Any, Dict
from flask import request, jsonify

def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS presence (
      user_id TEXT NOT NULL,
      session_id TEXT NOT NULL,
      updated_at INTEGER NOT NULL,
      state_json TEXT NOT NULL,
      PRIMARY KEY (user_id, session_id)
    )
    """)
    conn.commit()

def register_presence_api(app, db_conn_factory: Callable[[], sqlite3.Connection]) -> None:
    @app.before_request
    def _presence_db_init():
        # Ensure table exists once per process (best-effort).
        try:
            conn = db_conn_factory()
            _ensure_tables(conn)
        except Exception:
            pass

    @app.get("/api/presence")
    def get_presence():
        user_id = request.args.get("userId") or request.headers.get("X-User-Id") or "web"
        session_id = request.args.get("sessionId") or request.headers.get("X-Session-Id") or "default"

        conn = db_conn_factory()
        _ensure_tables(conn)
        row = conn.execute(
            "SELECT state_json FROM presence WHERE user_id=? AND session_id=?",
            (user_id, session_id),
        ).fetchone()

        if not row:
            return jsonify({"userId": user_id, "sessionId": session_id, "state":"idle","emotion":"neutral","focus":"user"})

        state = json.loads(row["state_json"])
        state.update({"userId": user_id, "sessionId": session_id})
        return jsonify(state)

    @app.post("/api/presence")
    def post_presence():
        payload: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        user_id = payload.get("userId") or request.headers.get("X-User-Id") or "web"
        session_id = payload.get("sessionId") or request.headers.get("X-Session-Id") or "default"

        patch = payload.get("patch") if isinstance(payload.get("patch"), dict) else payload
        state = patch.get("state") or patch.get("mode") or "idle"
        emotion = patch.get("emotion") or "neutral"
        focus = patch.get("focus") or "user"

        state_obj = {"state": state, "emotion": emotion, "focus": focus}
        for k, v in patch.items():
            if k not in ("userId","sessionId","patch"):
                state_obj[k] = v

        conn = db_conn_factory()
        _ensure_tables(conn)
        conn.execute(
            "INSERT INTO presence(user_id, session_id, updated_at, state_json) VALUES(?,?,?,?) "
            "ON CONFLICT(user_id, session_id) DO UPDATE SET updated_at=excluded.updated_at, state_json=excluded.state_json",
            (user_id, session_id, int(time.time()), json.dumps(state_obj)),
        )
        conn.commit()
        state_obj.update({"userId": user_id, "sessionId": session_id})
        return jsonify(state_obj)
