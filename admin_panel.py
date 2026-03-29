#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
admin_panel.py
卡密管理面板（查询 & 作废）
- 不修改 app.py / worker.py / redeem_api.py
- 复用 licenses.json.lock，避免并发覆盖（和 redeem_api.py 同一把锁）
"""

import os
import json
import fcntl
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Set, Tuple

import streamlit as st

# ========= 文件路径（与原系统保持一致：均为 /opt/gpt_pro 下的相对路径） =========
QUEUE_FILE = "queue.txt"
LICENSE_FILE = "licenses.json"
LICENSE_LOCK_FILE = LICENSE_FILE + ".lock"  # redeem_api.py 也用这个锁文件
HISTORY_FILE = "history.txt"
INVITE_LOG_FILE = "invite_log.txt"
REDEEM_LOG_FILE = "redeem_log.txt"
REVOKE_LOG_FILE = "revoke_log.txt"          # 本面板新增，不影响原系统

BJ_TZ = timezone(timedelta(hours=8))


# ========= 锁工具 =========
@contextmanager
def locked_open(path: str, mode: str):
    """
    给 queue.txt 用的简单文件锁封装（fcntl.flock）。
    注意：如果文件不存在且 mode 需要读写，会先创建空文件。
    """
    if "r" in mode and "+" not in mode and not os.path.exists(path):
        raise FileNotFoundError(path)

    if ("+" in mode or "a" in mode or "w" in mode) and not os.path.exists(path):
        open(path, "a", encoding="utf-8").close()

    f = open(path, mode, encoding="utf-8")
    try:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield f
    finally:
        try:
            fcntl.flock(f, fcntl.LOCK_UN)
        finally:
            f.close()


@contextmanager
def locked_license():
    """
    对 licenses.json 的互斥锁：使用 licenses.json.lock 文件。
    redeem_api.py 也用同名锁文件，所以能和兑换接口互斥。
    """
    f = open(LICENSE_LOCK_FILE, "w", encoding="utf-8")
    try:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(f, fcntl.LOCK_UN)
        finally:
            f.close()


# ========= 通用工具 =========
def bj_now_str() -> str:
    return datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S %z")


def safe_read_lines(path: str, max_lines: Optional[int] = None) -> List[str]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [l.rstrip("\n") for l in f.readlines() if l.strip()]
    if max_lines is not None:
        return lines[-max_lines:]
    return lines


def load_licenses() -> Dict[str, Any]:
    if not os.path.exists(LICENSE_FILE):
        return {}
    try:
        with open(LICENSE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def save_licenses(data: Dict[str, Any]) -> None:
    tmp_path = LICENSE_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, LICENSE_FILE)


def get_status_from_entry(entry: Any) -> Optional[str]:
    if entry is None:
        return None
    if isinstance(entry, dict):
        status = entry.get("status", "used")
    else:
        status = entry
    if not isinstance(status, str):
        status = str(status)
    return status.strip().lower()


def normalize_entry(entry: Any) -> Dict[str, Any]:
    if isinstance(entry, dict):
        return dict(entry)
    status = get_status_from_entry(entry) or "used"
    return {"status": status}


def parse_history_emails() -> Set[str]:
    emails: Set[str] = set()
    for line in safe_read_lines(HISTORY_FILE):
        parts = line.split("\t")
        if parts:
            e = (parts[0] or "").strip()
            if e:
                emails.add(e.lower())
    return emails


def parse_invite_log_emails() -> Set[str]:
    emails: Set[str] = set()
    for line in safe_read_lines(INVITE_LOG_FILE):
        parts = line.split("\t")
        if len(parts) >= 3:
            e = (parts[2] or "").strip()
            if e:
                emails.add(e.lower())
        elif parts:
            e = (parts[-1] or "").strip()
            if "@" in e:
                emails.add(e.lower())
    return emails


def load_queue() -> List[str]:
    if not os.path.exists(QUEUE_FILE):
        return []
    with locked_open(QUEUE_FILE, "r") as f:
        return [l.strip() for l in f.readlines() if l.strip()]


def remove_from_queue(emails: List[str]) -> int:
    if not emails:
        return 0
    if not os.path.exists(QUEUE_FILE):
        return 0

    remove_set = {e.strip().lower() for e in emails if e and e.strip()}
    if not remove_set:
        return 0

    with locked_open(QUEUE_FILE, "r+") as f:
        f.seek(0)
        lines = [l.strip() for l in f.readlines() if l.strip()]
        kept = [x for x in lines if x.strip().lower() not in remove_set]

        f.seek(0)
        f.truncate()
        if kept:
            f.write("\n".join(kept) + "\n")
        f.flush()

    return len(lines) - len(kept)


def append_revoke_log(code: str, email: str, reason: str, operator: str) -> None:
    try:
        ts = bj_now_str()
        line = f"{ts}\t{code}\t{email}\t{reason}\t{operator}\n"
        with open(REVOKE_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def code_info(code: str) -> Optional[Dict[str, Any]]:
    code = (code or "").strip().upper()
    if not code:
        return None

    with locked_license():
        db = load_licenses()
        entry = db.get(code)

    if entry is None:
        return {"code": code, "exists": False}

    e = normalize_entry(entry)
    status = get_status_from_entry(e)

    email = (e.get("email") or "").strip()
    redeem_time = (e.get("time") or "").strip()

    revoked = bool(e.get("revoked"))
    revoked_time = (e.get("revoked_time") or "").strip()
    revoked_reason = (e.get("revoked_reason") or "").strip()
    revoked_by = (e.get("revoked_by") or "").strip()

    q = load_queue()
    in_queue = False
    queue_pos = None
    if email:
        email_l = email.lower()
        for i, x in enumerate(q):
            if x.lower() == email_l:
                in_queue = True
                queue_pos = i + 1
                break

    invited_emails = parse_invite_log_emails()
    history_emails = parse_history_emails()
    invited = (email.lower() in invited_emails) if email else False
    in_history = (email.lower() in history_emails) if email else False

    return {
        "code": code,
        "exists": True,
        "status": status,
        "email": email,
        "redeem_time": redeem_time,
        "revoked": revoked,
        "revoked_time": revoked_time,
        "revoked_reason": revoked_reason,
        "revoked_by": revoked_by,
        "in_queue": in_queue,
        "queue_pos": queue_pos,
        "invited": invited,
        "in_history": in_history,
        "raw_entry": e,
    }


def find_by_email(email: str, limit: int = 200) -> Optional[Dict[str, Any]]:
    email = (email or "").strip()
    if not email:
        return None

    email_l = email.lower()
    with locked_license():
        db = load_licenses()

    matched: List[Dict[str, Any]] = []
    for code, entry in db.items():
        if isinstance(entry, dict):
            if (entry.get("email") or "").strip().lower() == email_l:
                e = normalize_entry(entry)
                matched.append(
                    {
                        "code": str(code).upper(),
                        "status": get_status_from_entry(e),
                        "redeem_time": (e.get("time") or "").strip(),
                        "revoked": bool(e.get("revoked")),
                        "revoked_time": (e.get("revoked_time") or "").strip(),
                        "revoked_reason": (e.get("revoked_reason") or "").strip(),
                    }
                )
        if len(matched) >= limit:
            break

    q = load_queue()
    in_queue = any(x.lower() == email_l for x in q)
    queue_pos = None
    if in_queue:
        for i, x in enumerate(q):
            if x.lower() == email_l:
                queue_pos = i + 1
                break

    invited = email_l in parse_invite_log_emails()
    in_history = email_l in parse_history_emails()

    return {
        "email": email,
        "matched_codes": matched,
        "in_queue": in_queue,
        "queue_pos": queue_pos,
        "invited": invited,
        "in_history": in_history,
        "queue_len": len(q),
    }


def revoke_code(code: str, reason: str, operator: str, try_remove_queue: bool = True) -> Tuple[bool, str]:
    code = (code or "").strip().upper()
    if not code:
        return False, "卡密不能为空"

    reason = (reason or "").strip()
    operator = (operator or "").strip() or "admin"
    removed_note = ""

    with locked_license():
        db = load_licenses()
        entry = db.get(code)
        if entry is None:
            return False, f"卡密不存在：{code}"

        e = normalize_entry(entry)
        status = get_status_from_entry(e)
        if status == "unused":
            # 作废未用卡密：把 unused 改成 used，确保兑换接口必然拒绝
            e["status"] = "used"

        e["revoked"] = True
        e["revoked_time"] = bj_now_str()
        e["revoked_reason"] = reason
        e["revoked_by"] = operator

        email = (e.get("email") or "").strip()
        db[code] = e
        save_licenses(db)

    append_revoke_log(code, email, reason, operator)

    # 如已绑定 email，可尝试从队列删除（但如果已经邀请成功，就不删）
    if try_remove_queue and email:
        email_l = email.lower()
        invited = email_l in parse_invite_log_emails() or email_l in parse_history_emails()
        if invited:
            removed_note = "（该邮箱已出现成功邀请/历史记录：不再从队列移除）"
        else:
            removed = remove_from_queue([email])
            if removed > 0:
                removed_note = f"（已从 queue.txt 移除 {email}）"
            else:
                removed_note = "（队列中未找到该邮箱，无需移除）"

    return True, f"已作废：{code} {removed_note}".strip()


# ========= 页面 =========
st.set_page_config(page_title="卡密管理（作废/查询）", layout="wide", page_icon="🧯")

st.sidebar.title("🔐 管理员登录")
pwd_env = (os.environ.get("ADMIN_PANEL_PASSWORD") or "").strip()
pwd_input = st.sidebar.text_input(
    "密码（可选）",
    type="password",
    help="如设置了环境变量 ADMIN_PANEL_PASSWORD，则必须输入正确密码才能操作。",
)

if pwd_env and pwd_input != pwd_env:
    st.sidebar.error("需要管理员密码")
    st.info("已启用管理员密码保护。请在左侧输入密码后继续。")
    st.stop()

operator = st.sidebar.text_input(
    "操作人标记（写入作废日志）",
    value=os.environ.get("ADMIN_OPERATOR", "admin"),
)

st.title("🧯 卡密作废 & 查询面板")
st.caption("不改动原系统逻辑，只对 licenses.json / queue.txt 做最小安全写入。")

tab_overview, tab_query, tab_revoke, tab_queue, tab_logs = st.tabs(
    ["📊 总览", "🔎 查询", "🚫 作废", "📬 队列管理", "📜 日志"]
)

with tab_overview:
    c1, c2, c3, c4, c5 = st.columns(5)
    with locked_license():
        db = load_licenses()

    total = len(db)
    unused = 0
    used = 0
    revoked = 0

    for _, entry in db.items():
        e = normalize_entry(entry)
        s = get_status_from_entry(e)
        if s == "unused":
            unused += 1
        else:
            used += 1
        if isinstance(e, dict) and e.get("revoked"):
            revoked += 1

    q = load_queue()
    invite_tail = safe_read_lines(INVITE_LOG_FILE, max_lines=1)
    last_invite = invite_tail[-1] if invite_tail else ""

    c1.metric("卡密总数", total)
    c2.metric("未使用", unused)
    c3.metric("已使用/不可用", used)
    c4.metric("已作废", revoked)
    c5.metric("当前队列人数", len(q))

    if last_invite:
        st.caption(f"最近一条 invite_log：{last_invite}")

with tab_query:
    colA, colB = st.columns(2)

    with colA:
        st.subheader("按卡密查询")
        code_in = st.text_input("卡密", placeholder="例如 GPT-ABCD1234", key="q_code")
        if st.button("查询卡密", use_container_width=True):
            info = code_info(code_in)
            if not info:
                st.warning("请输入卡密")
            elif not info.get("exists"):
                st.error(f"卡密不存在：{info.get('code')}")
            else:
                st.success(f"找到卡密：{info['code']}")
                st.json(
                    {
                        "status": info["status"],
                        "email": info["email"],
                        "redeem_time": info["redeem_time"],
                        "revoked": info["revoked"],
                        "revoked_time": info["revoked_time"],
                        "revoked_reason": info["revoked_reason"],
                        "revoked_by": info["revoked_by"],
                        "in_queue": info["in_queue"],
                        "queue_pos": info["queue_pos"],
                        "invited": info["invited"],
                        "in_history": info["in_history"],
                    },
                    expanded=True,
                )

    with colB:
        st.subheader("按邮箱查询")
        email_in = st.text_input("邮箱", placeholder="user@example.com", key="q_email")
        if st.button("查询邮箱", use_container_width=True):
            res = find_by_email(email_in)
            if not res:
                st.warning("请输入邮箱")
            else:
                st.success(f"邮箱：{res['email']}")
                st.json(
                    {
                        "in_queue": res["in_queue"],
                        "queue_pos": res["queue_pos"],
                        "queue_len": res["queue_len"],
                        "invited": res["invited"],
                        "in_history": res["in_history"],
                        "matched_codes_count": len(res["matched_codes"]),
                    },
                    expanded=True,
                )
                if res["matched_codes"]:
                    st.caption("该邮箱关联的卡密（最多显示 200 条）")
                    st.dataframe(res["matched_codes"], use_container_width=True, hide_index=True)
                else:
                    st.info("licenses.json 中找不到该邮箱关联的卡密（可能未兑换，或是老格式卡密没有记录 email）。")

with tab_revoke:
    st.subheader("作废卡密")
    st.write("作废后，该卡密将无法再被兑换接口使用；若已绑定邮箱，可选尝试从 queue.txt 移除（未邀请成功才会移除）。")

    col1, col2 = st.columns([2, 1])
    with col1:
        revoke_code_in = st.text_input("要作废的卡密", placeholder="GPT-XXXX", key="rv_code")
        revoke_reason = st.text_input("作废原因（可选）", placeholder="例如：退款/风控/重复发放", key="rv_reason")
    with col2:
        try_remove = st.checkbox("尝试从队列移除邮箱", value=True)
        st.caption("若该邮箱已在 invite_log/history 出现，则不会移除。")

    if st.button("🚫 立即作废", type="primary", use_container_width=True):
        ok, msg = revoke_code(revoke_code_in, revoke_reason, operator, try_remove_queue=try_remove)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

    st.markdown("---")
    st.subheader("批量作废（逐行一个卡密）")
    batch = st.text_area("批量卡密列表", height=120, placeholder="GPT-AAA\nGPT-BBB\n...", key="rv_batch")
    batch_reason = st.text_input("批量作废原因（可选）", key="rv_batch_reason")

    if st.button("🚫 批量作废", use_container_width=True):
        codes = [x.strip().upper() for x in batch.splitlines() if x.strip()]
        if not codes:
            st.warning("没有可处理的卡密")
        else:
            results = []
            for c in codes:
                ok, msg = revoke_code(c, batch_reason, operator, try_remove_queue=try_remove)
                results.append({"code": c, "ok": ok, "message": msg})
            st.dataframe(results, use_container_width=True, hide_index=True)

with tab_queue:
    st.subheader("队列查看 / 手动删除邮箱")
    q = load_queue()
    st.caption(f"当前 queue.txt 行数：{len(q)}")
    if q:
        st.dataframe([{"pos": i + 1, "email": e} for i, e in enumerate(q)], use_container_width=True, hide_index=True)

    st.markdown("---")
    email_rm = st.text_input("要从队列删除的邮箱", placeholder="user@example.com", key="q_rm_email")
    if st.button("删除该邮箱（仅队列）", use_container_width=True):
        if not email_rm.strip():
            st.warning("请输入邮箱")
        else:
            removed = remove_from_queue([email_rm.strip()])
            if removed:
                st.success(f"已从队列删除：{email_rm.strip()}（删除 {removed} 条）")
            else:
                st.info("队列中未找到该邮箱")

with tab_logs:
    st.subheader("日志（最近 200 行）")

    colL1, colL2, colL3 = st.columns(3)
    with colL1:
        st.caption("redeem_log.txt（兑换记录）")
        st.code("\n".join(safe_read_lines(REDEEM_LOG_FILE, max_lines=200)) or "(空)")
    with colL2:
        st.caption("invite_log.txt（邀请成功）")
        st.code("\n".join(safe_read_lines(INVITE_LOG_FILE, max_lines=200)) or "(空)")
    with colL3:
        st.caption("revoke_log.txt（作废记录，本面板新增）")
        st.code("\n".join(safe_read_lines(REVOKE_LOG_FILE, max_lines=200)) or "(空)")
