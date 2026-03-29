# -*- coding: utf-8 -*-
import streamlit as st
import time
import json
import os
import subprocess
import datetime
import fcntl
import random
import string
import re
import html
import requests
import pandas as pd
from contextlib import contextmanager

# ================= 1. 环境配置 (SRE 补丁：绝对路径) =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_DIR, filename)

QUEUE_FILE = get_path("queue.txt")
HISTORY_FILE = get_path("history.txt")
STATE_FILE = get_path("state.json")
ACCOUNTS_DB_FILE = get_path("accounts_db.json")
AT_FAIL_STATE_FILE = get_path("at_fail_state.json")
WORKER_LOG_FILE = get_path("worker_output.log")
LICENSE_FILE = get_path("licenses.json")
LICENSE_LOCK_FILE = get_path("licenses.json.lock")
REDEEM_LOG_FILE = get_path("redeem_log.txt")
INVITE_LOG_FILE = get_path("invite_log.txt")
INVALID_EMAIL_LOG_FILE = get_path("invalid_email_log.txt")
START_SCRIPT = get_path("start_worker.sh")
CURSOR_FILE = get_path("cursor.txt")
CN_TZ = datetime.timezone(datetime.timedelta(hours=8))
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")

st.set_page_config(
    page_title="方木木团队运营后台",
    layout="wide",
    page_icon="SYS",
    initial_sidebar_state="expanded"
)

# ================= 2. 核心安全工具 =================

@contextmanager
def locked_open(path, mode="r+"):
    """安全文件锁"""
    if "w" in mode and "r+" not in mode:
        raise ValueError("Critical Security Error: Do not use 'w' with locked_open!")

    if not os.path.exists(path):
        open(path, "a", encoding="utf-8").close()

    f = open(path, mode, encoding="utf-8", errors="ignore")
    try:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield f
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()

@contextmanager
def locked_license():
    """License 专用锁"""
    f = open(LICENSE_LOCK_FILE, "w", encoding="utf-8")
    try:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()

def safe_read_lines(path):
    try:
        with locked_open(path, "r") as f:
            return [l.strip() for l in f if l.strip()]
    except: return []


def split_email_input_text(raw_text):
    items = []
    for line in str(raw_text or "").replace("\r", "\n").split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = [x.strip() for x in line.split(",") if x.strip()]
        if parts:
            items.extend(parts)
        else:
            items.append(line)
    return items


def validate_email_candidate(raw_email):
    email = str(raw_email or "").strip()
    if not email:
        return "", "空白邮箱"
    if any(ch.isspace() for ch in email):
        return email, "包含空格"
    if "/" in email or "\\" in email:
        return email, "包含非法字符 / 或 \\"
    if email.count("@") != 1:
        return email, "@ 数量不正确"
    local, domain = email.rsplit("@", 1)
    if not local:
        return email, "@ 前不能为空"
    if not domain:
        return email, "@ 后不能为空"
    if "." not in domain:
        return email, "域名缺少顶级后缀"
    if ".." in email:
        return email, "包含连续点号"
    if not EMAIL_REGEX.fullmatch(email):
        return email, "邮箱格式不合法"
    return email, ""


def split_valid_invalid_emails(items):
    valid = []
    invalid = []
    seen_valid = set()
    for raw in items or []:
        email, reason = validate_email_candidate(raw)
        if reason:
            invalid.append({"email": email or str(raw or "").strip(), "reason": reason})
            continue
        email_key = email.lower()
        if email_key in seen_valid:
            continue
        seen_valid.add(email_key)
        valid.append(email)
    return valid, invalid


def append_invalid_email_record(email, reason, source="队列预检"):
    ts = datetime.datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M:%S %z")
    line = "\t".join([ts, str(source or "").strip(), str(email or "").strip(), str(reason or "").strip()])
    try:
        with locked_open(INVALID_EMAIL_LOG_FILE, "a+") as f:
            f.write(line + "\n")
            f.flush()
    except Exception:
        pass


@st.cache_data(show_spinner=False)
def load_invalid_email_records(_invalid_sig):
    records = []
    if not os.path.exists(INVALID_EMAIL_LOG_FILE):
        return records
    for idx, line in enumerate(safe_read_lines(INVALID_EMAIL_LOG_FILE), 1):
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        ts, source, email, reason = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
        dt = parse_log_datetime(ts)
        records.append({
            "id": idx,
            "time": ts,
            "dt": dt,
            "source": source or "队列预检",
            "email": email,
            "reason": reason,
        })
    return list(reversed(records))


def find_invalid_queue_entries(queue_lines, limit=None):
    invalid = []
    for idx, raw in enumerate(queue_lines or []):
        if limit is not None and idx >= limit:
            break
        email, reason = validate_email_candidate(raw)
        if reason:
            invalid.append({
                "index": idx,
                "email": email or str(raw or "").strip(),
                "reason": reason,
            })
    return invalid


def purge_invalid_queue_entries(limit=None, source="队列清理"):
    queue_lines = safe_read_lines(QUEUE_FILE)
    invalid = find_invalid_queue_entries(queue_lines, limit=limit)
    if not invalid:
        return 0, []
    invalid_indexes = {item["index"] for item in invalid}
    kept = [line for idx, line in enumerate(queue_lines) if idx not in invalid_indexes]
    try:
        with locked_open(QUEUE_FILE, "r+") as f:
            f.seek(0)
            f.truncate(0)
            if kept:
                f.write("\n".join(kept) + "\n")
            f.flush()
        for item in invalid:
            append_invalid_email_record(item["email"], item["reason"], source=source)
        return len(invalid), invalid
    except Exception:
        return 0, []

def load_json_safe(path):
    if not os.path.exists(path): return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {}

def save_json_safe(path, data):
    """原子写入，返回布尔值"""
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        return True
    except Exception as e:
        st.error(f"Critical Save Failed: {e}")
        return False

def get_worker_pid():
    try:
        cmd = "pgrep -f 'worker.py' || true"
        pid = subprocess.check_output(cmd, shell=True).decode().strip()
        return pid or None
    except: return None

# ================= 3. 运维动作逻辑 =================

def reset_history_for_account(target_idx):
    try:
        with locked_open(HISTORY_FILE, "r+") as f:
            lines = f.readlines()
            new_lines = []
            for line in lines:
                parts = line.strip().split("\t")
                idx = 0
                if len(parts) >= 2:
                    try: idx = int(parts[1])
                    except: idx = 0
                if idx != target_idx:
                    new_lines.append(line)
            f.seek(0); f.truncate(0); f.writelines(new_lines)
        return True
    except: return False

def restart_worker_safely():
    """安全重启"""
    os.system("pkill -f worker.py || true")
    time.sleep(1)
    start_cmd = f"cd {BASE_DIR} && bash {START_SCRIPT} > /dev/null 2>&1 &"
    fallback_cmd = f"cd {BASE_DIR} && nohup ./myenv/bin/python worker.py > worker_output.log 2>&1 &"
    if os.path.exists(START_SCRIPT): os.system(start_cmd)
    else: os.system(fallback_cmd)

# ================= 4. Dashboard Theme =================
st.markdown("""
<style>
    .stApp {
        background: #ffffff;
        color: #111827;
    }
    html, body, [class*="css"] {
        font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    }
    .block-container {
        max-width: 1380px;
        padding-top: 1rem;
        padding-bottom: 2rem;
    }
    section[data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid #e5e7eb;
    }
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 0.8rem 1rem;
        box-shadow: none;
    }
    div.stButton > button,
    button[kind="secondary"],
    button[kind="primary"] {
        min-height: 2.6rem;
        border-radius: 10px;
        border: 1px solid #d1d5db;
        background: #ffffff !important;
        color: #111827 !important;
        box-shadow: none !important;
    }
    div.stButton > button:hover,
    button[kind="secondary"]:hover,
    button[kind="primary"]:hover {
        border-color: #9ca3af !important;
        color: #111827 !important;
        transform: none;
    }
    .stTextInput input,
    .stTextArea textarea,
    .stDateInput input,
    .stNumberInput input,
    .stSelectbox [data-baseweb="select"] > div {
        border-radius: 10px !important;
        border: 1px solid #d1d5db !important;
        background: #ffffff !important;
        color: #111827 !important;
        box-shadow: none !important;
    }
    [data-testid="stExpander"] {
        border: 1px solid #e5e7eb !important;
        border-radius: 12px !important;
        background: #ffffff !important;
        box-shadow: none;
    }
    [data-testid="stDataFrame"] {
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        box-shadow: none;
        background: #ffffff;
    }
    [data-testid="stInfo"],
    [data-testid="stSuccess"],
    [data-testid="stWarning"],
    [data-testid="stError"] {
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ================= 5. 业务统计 =================

def get_accounts_config():
    cfg = load_json_safe(STATE_FILE)
    accounts = []
    raw_list = []
    if isinstance(cfg, dict) and "accounts" in cfg: raw_list = cfg.get("accounts", [])
    elif cfg: raw_list = [cfg]
    for item in raw_list:
        if not isinstance(item, dict): continue
        c = item.get("cookies", "")
        raw_ids = item.get("ids", "")
        if isinstance(raw_ids, list): ids_str = "\n".join([str(x) for x in raw_ids])
        else: ids_str = str(raw_ids)
        try: m = int(item.get("max_per_group", 4))
        except: m = 4
        accounts.append({"cookies": c, "ids_str": ids_str, "max_per_group": m})
    return accounts

def get_runtime_accounts_config():
    runtime_accounts = []
    base_accounts = get_accounts_config()
    fail_state = load_at_fail_state_safe()

    for idx, item in enumerate(base_accounts, 1):
        ids_list = [x.strip() for x in str(item.get("ids_str", "")).splitlines() if x.strip()]
        runtime_accounts.append({
            "mode": "cookie",
            "label": f"CK节点{idx}",
            "cookies": str(item.get("cookies", "") or "").strip(),
            "ids_list": ids_list,
            "max_per_group": int(item.get("max_per_group", 4) or 4),
        })

    at_db = load_accounts_db_safe()
    at_items = at_db.get("accounts", []) if isinstance(at_db, dict) else []
    at_seq = 1
    for item in at_items:
        if not isinstance(item, dict):
            continue
        if (item.get("mode") or "at").strip().lower() != "at":
            continue
        if not bool(item.get("enabled", True)):
            continue

        team_id = str(item.get("team_id") or "").strip()
        if not team_id:
            continue

        try:
            max_per_group = int(item.get("max_per_group", 4) or 4)
        except Exception:
            max_per_group = 4
        if max_per_group <= 0:
            max_per_group = 4

        try:
            sync_used = int(item.get("current_members", 0) or 0)
        except Exception:
            sync_used = 0
        if sync_used <= 0:
            try:
                sync_used = int(item.get("joined_count", 0) or 0) + int(item.get("invited_count", 0) or 0)
            except Exception:
                sync_used = 0
        if sync_used <= 0:
            sync_used = 1

        display_name = str(item.get("email") or "").strip() or f"AT节点{at_seq}"
        fail_meta = normalize_at_fail_meta(fail_state.get(team_id))
        runtime_accounts.append({
            "mode": "at",
            "label": f"AT节点{at_seq}",
            "display_name": display_name,
            "team_id": team_id,
            "max_per_group": max_per_group,
            "sync_used": max(sync_used, 0),
            "sync_status": str(item.get("sync_status") or "").strip(),
            "last_sync": str(item.get("last_sync") or "").strip(),
            "created_at": str(item.get("created_at") or "").strip(),
            "skip_marked": bool(fail_meta.get("skip_marked")),
            "consecutive_failures": int(fail_meta.get("consecutive_failures", 0) or 0),
            "today_fail_batches": int(fail_meta.get("today_fail_batches", 0) or 0),
            "today_failed_emails": int(fail_meta.get("today_failed_emails", 0) or 0),
            "last_failed_at": str(fail_meta.get("last_failed_at") or "").strip(),
            "last_failed_emails": list(fail_meta.get("last_failed_emails") or []),
            "last_failure_error": str(fail_meta.get("last_failure_error") or "").strip(),
        })
        at_seq += 1

    return runtime_accounts

def normalize_ids_text(raw_ids):
    import re
    if raw_ids is None:
        return ""
    if isinstance(raw_ids, list):
        text = "\n".join([str(x) for x in raw_ids if str(x).strip()])
    else:
        text = str(raw_ids)

    text = text.replace("\r", "\n")
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("，", ",").replace("；", ";")
    parts = re.split(r"[\n,;|]+", text)

    out = []
    seen = set()
    for p in parts:
        v = p.strip()
        if not v:
            continue
        if v not in seen:
            seen.add(v)
            out.append(v)
    return "\n".join(out)

def extract_json_objects(text):
    decoder = json.JSONDecoder()
    out = []
    i = 0
    n = len(text)
    while i < n:
        while i < n and text[i] not in "[{":
            i += 1
        if i >= n:
            break
        try:
            obj, j = decoder.raw_decode(text, i)
        except Exception:
            i += 1
            continue
        if isinstance(obj, dict):
            out.append(obj)
        elif isinstance(obj, list):
            out.extend([x for x in obj if isinstance(x, dict)])
        i = j
    return out

def parse_bulk_accounts_payload(payload, default_mpg=4):
    import json

    def _norm_mpg(v):
        try:
            n = int(v)
        except Exception:
            try:
                n = int(default_mpg)
            except Exception:
                n = 4
        return n if n > 0 else 4

    def _cookie_list_from_any(v):
        if isinstance(v, list) and all(isinstance(x, dict) for x in v):
            return v
        if isinstance(v, str):
            t = v.strip()
            if not t:
                return []
            try:
                obj = json.loads(t)
                if isinstance(obj, list) and all(isinstance(x, dict) for x in obj):
                    return obj
            except Exception:
                return []
        return []

    def _extract_ids(item, cookies_list):
        vals = []
        if isinstance(item, dict):
            for k in ("workspace_id","workspaceId","team_id","teamId","group_id","groupId","ids","ids_str","group_ids","groupIds","workspace_ids","workspaceIds"):
                vv = item.get(k)
                if vv is not None and str(vv).strip():
                    vals.append(vv)

            acc = item.get("account")
            if isinstance(acc, dict):
                for k in ("id","workspace_id","workspaceId"):
                    vv = acc.get(k)
                    if vv is not None and str(vv).strip():
                        vals.append(vv)

        for ck in cookies_list:
            if not isinstance(ck, dict):
                continue
            n = str(ck.get("name","")).strip()
            v = str(ck.get("value","")).strip()
            if n in ("_account","account_id","workspace_id") and v:
                vals.append(v)

        return normalize_ids_text(vals)

    def _mk_record(name, cookies_list, ids_raw, mpg):
        ids_str = normalize_ids_text(ids_raw)
        if not ids_str or not cookies_list:
            return None
        cookies_pretty = json.dumps(cookies_list, ensure_ascii=False, indent=2)
        return {
            "name": (name or "").strip() or "Node",
            "cookies": cookies_pretty,
            "cookies_str": cookies_pretty,
            "ids_str": ids_str,
            "max_per_group": _norm_mpg(mpg),
        }

    raw = (payload or "").strip()
    if not raw:
        return [], "empty"

    try:
        obj = json.loads(raw)
    except Exception:
        obj = None

    if obj is not None:
        if isinstance(obj, list) and obj and all(isinstance(x, dict) and "name" in x and "value" in x for x in obj):
            ids_str = _extract_ids({}, obj)
            rec = _mk_record("Node1", obj, ids_str, default_mpg)
            return ([rec] if rec else []), "json-cookie-array"

        if isinstance(obj, dict) and isinstance(obj.get("accounts"), list):
            obj = obj["accounts"]

        items = obj if isinstance(obj, list) else [obj]
        parsed = []
        for idx, it in enumerate(items, 1):
            if not isinstance(it, dict):
                continue
            cookies_list = _cookie_list_from_any(it.get("cookies"))
            if not cookies_list and {"domain","name","value"}.issubset(set(it.keys())):
                cookies_list = [it]
            ids_str = _extract_ids(it, cookies_list)
            rec = _mk_record(it.get("name", f"Node{idx}"), cookies_list, ids_str, it.get("max_per_group", default_mpg))
            if rec:
                parsed.append(rec)
        if parsed:
            return parsed, "json-accounts"

    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < 3:
            continue
        name = cols[0].strip() or f"Node{len(rows)+1}"
        cookies_list = _cookie_list_from_any(cols[1].strip())
        ids_str = normalize_ids_text(cols[2].strip())
        mpg = cols[3].strip() if len(cols) >= 4 else default_mpg
        rec = _mk_record(name, cookies_list, ids_str, mpg)
        if rec:
            rows.append(rec)

    return rows, ("tsv" if rows else "none")


def load_accounts_db_safe():
    data = load_json_safe(ACCOUNTS_DB_FILE)
    if not isinstance(data, dict):
        return {"version": 1, "accounts": []}
    accounts = data.get("accounts", [])
    if not isinstance(accounts, list):
        accounts = []
    return {"version": int(data.get("version", 1) or 1), "accounts": accounts}


def save_accounts_db_safe(accounts):
    return save_json_safe(ACCOUNTS_DB_FILE, {"version": 1, "accounts": accounts})


def load_at_fail_state_safe():
    data = load_json_safe(AT_FAIL_STATE_FILE)
    return data if isinstance(data, dict) else {}


def save_at_fail_state_safe(data):
    return save_json_safe(AT_FAIL_STATE_FILE, data if isinstance(data, dict) else {})


def normalize_at_fail_meta(meta):
    today = datetime.datetime.now(CN_TZ).strftime("%Y-%m-%d")
    if not isinstance(meta, dict):
        meta = {}
    meta_day = str(meta.get("day") or today)
    today_fail_batches = int(meta.get("today_fail_batches", 0) or 0) if meta_day == today else 0
    today_failed_emails = int(meta.get("today_failed_emails", 0) or 0) if meta_day == today else 0
    return {
        "day": today,
        "consecutive_failures": max(int(meta.get("consecutive_failures", 0) or 0), 0),
        "today_fail_batches": max(today_fail_batches, 0),
        "today_failed_emails": max(today_failed_emails, 0),
        "skip_marked": bool(meta.get("skip_marked", False)),
        "skip_reason": str(meta.get("skip_reason") or "").strip(),
        "last_failed_at": str(meta.get("last_failed_at") or "").strip(),
        "last_failed_count": max(int(meta.get("last_failed_count", 0) or 0), 0),
        "last_failed_emails": [str(x).strip() for x in (meta.get("last_failed_emails") or []) if str(x).strip()],
        "last_failure_error": str(meta.get("last_failure_error") or "").strip(),
        "last_cleared_at": str(meta.get("last_cleared_at") or "").strip(),
    }


def clear_at_fail_mark_safe(team_id):
    team_id = str(team_id or "").strip()
    if not team_id:
        return False
    data = load_at_fail_state_safe()
    meta = normalize_at_fail_meta(data.get(team_id))
    meta["consecutive_failures"] = 0
    meta["skip_marked"] = False
    meta["skip_reason"] = ""
    meta["last_cleared_at"] = datetime.datetime.now(CN_TZ).isoformat()
    data[team_id] = meta
    return save_at_fail_state_safe(data)


def parse_at_bulk_accounts_payload(payload, default_mpg=4):
    def _norm_mpg(v):
        try:
            n = int(v)
        except Exception:
            n = 4
        return n if n > 0 else 4

    raw = html.unescape((payload or "").strip())
    if not raw:
        return [], "empty"

    cleaned = re.sub(r"<[^>]+>", " ", raw)
    objects = extract_json_objects(cleaned)
    parsed = []

    for idx, obj in enumerate(objects, 1):
        if not isinstance(obj, dict):
            continue
        account = obj.get("account") if isinstance(obj.get("account"), dict) else {}
        user = obj.get("user") if isinstance(obj.get("user"), dict) else {}
        access_token = str(obj.get("accessToken") or obj.get("access_token") or "").strip()
        team_id = str(
            account.get("id")
            or obj.get("team_id")
            or obj.get("workspace_id")
            or obj.get("workspaceId")
            or ""
        ).strip()
        email = str(user.get("email") or obj.get("email") or "").strip()
        expires = str(obj.get("expires") or "").strip()
        if not access_token or not team_id:
            continue
        parsed.append({
            "mode": "at",
            "enabled": True,
            "email": email,
            "team_id": team_id,
            "access_token": access_token,
            "expires": expires,
            "max_per_group": _norm_mpg(default_mpg),
            "name": email or f"AT-{idx:03d}",
        })

    return parsed, ("at-json" if parsed else "none")


def parse_log_datetime(value):
    raw = (value or "").strip()
    if not raw:
        return None
    patterns = [
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S",
    ]
    for pattern in patterns:
        try:
            dt = datetime.datetime.strptime(raw, pattern)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=CN_TZ)
            return dt.astimezone(CN_TZ)
        except Exception:
            continue
    return None


def resolve_date_range_from_preset(preset, date_from=None, date_to=None):
    if date_from or date_to:
        return date_from, date_to
    today = datetime.datetime.now(CN_TZ).date()
    if preset == "今天":
        return today, today
    if preset == "昨天":
        yesterday = today - datetime.timedelta(days=1)
        return yesterday, yesterday
    if preset == "最近3天":
        return today - datetime.timedelta(days=2), today
    if preset == "最近7天":
        return today - datetime.timedelta(days=6), today
    return date_from, date_to


def build_history_usage_maps():
    legacy_used_per_runtime_account = {}
    stable_used_per_group_key = {}
    for line in safe_read_lines(HISTORY_FILE):
        parts = line.split("\t")
        if len(parts) >= 4:
            group_key = str(parts[3] or "").strip()
            if group_key:
                stable_used_per_group_key[group_key] = stable_used_per_group_key.get(group_key, 0) + 1
        try:
            idx = int(parts[1]) if len(parts) >= 2 else 0
        except Exception:
            idx = 0
        legacy_used_per_runtime_account[idx] = legacy_used_per_runtime_account.get(idx, 0) + 1
    return legacy_used_per_runtime_account, stable_used_per_group_key


def compute_period_stats(records):
    now = datetime.datetime.now(CN_TZ)
    today = now.date()
    week_start = today - datetime.timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    return {
        "total": len(records),
        "today": sum(1 for r in records if r.get("dt") and r["dt"].date() == today),
        "week": sum(1 for r in records if r.get("dt") and r["dt"].date() >= week_start),
        "month": sum(1 for r in records if r.get("dt") and r["dt"].date() >= month_start),
    }


def paginate_records(records, page_size, page_num):
    total = len(records)
    if total <= 0:
        return [], 1
    total_pages = max(1, (total + page_size - 1) // page_size)
    page_num = max(1, min(page_num, total_pages))
    start = (page_num - 1) * page_size
    end = start + page_size
    return records[start:end], total_pages


def extract_account_group_numbers(label):
    nums = re.findall(r"\d+", str(label or ""))
    if len(nums) >= 2:
        try:
            return int(nums[0]), int(nums[1])
        except Exception:
            return None, None
    return None, None


def resolve_team_id_from_label(label):
    account_no, group_no = extract_account_group_numbers(label)
    if not account_no or not group_no:
        return ""
    runtime_accounts = get_runtime_accounts_config()
    idx = account_no - 1
    if idx < 0 or idx >= len(runtime_accounts):
        return ""
    acc = runtime_accounts[idx]
    if str(acc.get("type")) == "at":
        return str(acc.get("team_id") or "")
    ids_list = [x.strip() for x in str(acc.get("ids_str", "")).splitlines() if x.strip()]
    gid = group_no - 1
    if gid < 0 or gid >= len(ids_list):
        return ""
    return ids_list[gid]


def resolve_group_display_from_label(label):
    account_no, group_no = extract_account_group_numbers(label)
    if not account_no or not group_no:
        return str(label or "")
    runtime_accounts = get_runtime_accounts_config()
    idx = account_no - 1
    if idx < 0 or idx >= len(runtime_accounts):
        return str(label or "")
    acc = runtime_accounts[idx]
    if str(acc.get("type")) == "at":
        at_label = str(acc.get("label") or f"AT节点{account_no}")
        at_email = str(acc.get("display_name") or acc.get("email") or "").strip()
        suffix = f" {at_email}" if at_email else ""
        return f"母号{account_no}《{at_label}》{suffix}"
    return f"母号{account_no}-组{group_no}"


def get_file_signature(path):
    try:
        stat = os.stat(path)
        return int(stat.st_mtime), int(stat.st_size)
    except Exception:
        return 0, 0


@st.cache_data(show_spinner=False)
def build_redeem_history_by_email(_redeem_sig):
    redeem_map = {}
    if not os.path.exists(REDEEM_LOG_FILE):
        return redeem_map
    for line in safe_read_lines(REDEEM_LOG_FILE):
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        ts, code, email = parts[0].strip(), parts[1].strip(), parts[2].strip()
        email_key = str(email or "").strip().lower()
        if not email_key or not code:
            continue
        redeem_map.setdefault(email_key, []).append({
            "time": ts,
            "dt": parse_log_datetime(ts),
            "code": code,
        })
    return redeem_map


def resolve_redeem_code_for_invite(email, invite_dt, redeem_map):
    email_key = str(email or "").strip().lower()
    items = redeem_map.get(email_key, [])
    if not items:
        return ""
    if invite_dt:
        matched = [item for item in items if item.get("dt") and item["dt"] <= invite_dt]
        if matched:
            return str(matched[-1].get("code") or "")
    return str(items[-1].get("code") or "")


def derive_invite_source(code_value):
    code = str(code_value or "").strip()
    return "卡密" if code and code != "手动" else "手动"


def normalize_invite_status(raw_status):
    value = str(raw_status or "").strip().lower()
    if value in {"success", "ok", "done", "成功"}:
        return "成功"
    if value in {"pending", "invited", "queued", "待邀请"}:
        return "待邀请"
    if value in {"failed", "error", "invalid", "失败"}:
        return "失败"
    return "成功"


@st.cache_data(show_spinner=False)
def load_invite_records(_invite_sig, _redeem_sig):
    records = []
    if not os.path.exists(INVITE_LOG_FILE):
        return records
    redeem_map = build_redeem_history_by_email(_redeem_sig)
    for idx, line in enumerate(safe_read_lines(INVITE_LOG_FILE), 1):
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        ts, label, email = parts[0].strip(), parts[1].strip(), parts[2].strip()
        dt = parse_log_datetime(ts)
        status = normalize_invite_status(parts[3].strip() if len(parts) >= 4 else "成功")
        source = parts[4].strip() if len(parts) >= 5 else ""
        explicit_code = parts[5].strip() if len(parts) >= 6 else ""
        reason = parts[6].strip() if len(parts) >= 7 else ""
        code = explicit_code or resolve_redeem_code_for_invite(email, dt, redeem_map) or "手动"
        source = source or derive_invite_source(code)
        records.append({
            "id": idx,
            "time": ts,
            "dt": dt,
            "email": email,
            "code": code,
            "source": source,
            "status": status,
            "reason": reason,
            "group_label": label,
            "group_label_display": resolve_group_display_from_label(label),
            "team_id": resolve_team_id_from_label(label),
        })
    return list(reversed(records))


@st.cache_data(show_spinner=False)
def load_redeem_records(_redeem_sig):
    records = []
    if not os.path.exists(REDEEM_LOG_FILE):
        return records
    for idx, line in enumerate(safe_read_lines(REDEEM_LOG_FILE), 1):
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        ts, code, email = parts[0].strip(), parts[1].strip(), parts[2].strip()
        dt = parse_log_datetime(ts)
        records.append({
            "id": idx,
            "time": ts,
            "dt": dt,
            "code": code,
            "email": email,
        })
    return list(reversed(records))


def filter_invite_records(records, email_kw="", team_kw="", date_from=None, date_to=None):
    out = []
    email_kw = (email_kw or "").strip().lower()
    team_kw = (team_kw or "").strip().lower()
    for item in records:
        if email_kw and email_kw not in str(item.get("email") or "").lower():
            continue
        haystack = " ".join([
            str(item.get("code") or ""),
            str(item.get("group_label") or ""),
            str(item.get("group_label_display") or ""),
            str(item.get("team_id") or ""),
        ]).lower()
        if team_kw and team_kw not in haystack:
            continue
        dt = item.get("dt")
        if date_from and (not dt or dt.date() < date_from):
            continue
        if date_to and (not dt or dt.date() > date_to):
            continue
        out.append(item)
    return out


def filter_redeem_records(records, email_kw="", code_kw="", date_from=None, date_to=None):
    out = []
    email_kw = (email_kw or "").strip().lower()
    code_kw = (code_kw or "").strip().lower()
    for item in records:
        if email_kw and email_kw not in str(item.get("email") or "").lower():
            continue
        if code_kw and code_kw not in str(item.get("code") or "").lower():
            continue
        dt = item.get("dt")
        if date_from and (not dt or dt.date() < date_from):
            continue
        if date_to and (not dt or dt.date() > date_to):
            continue
        out.append(item)
    return out


def sync_single_at_account_record(item):
    try:
        import worker as invite_worker
    except Exception as e:
        return {
            "ok": False,
            "error": f"worker import failed: {e}",
            "status": "error",
        }

    team_id = str(item.get("team_id") or "").strip()
    access_token = str(item.get("access_token") or "").strip()
    cookies = str(item.get("cookies") or "").strip()
    max_per_group = int(item.get("max_per_group", 4) or 4)
    if not team_id:
        return {"ok": False, "error": "missing team_id", "status": "error"}
    if not access_token and not cookies:
        return {"ok": False, "error": "missing access token/cookies", "status": "error"}

    try:
        session = invite_worker.create_chatgpt_session(cookies, target_uuid=team_id)
        token = invite_worker.get_api_access_token(session, preset_token=access_token)
        if not token:
            return {"ok": False, "error": "missing valid access token", "status": "expired"}

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Referer": f"{invite_worker.CHATGPT_BASE_URL}/",
            "Origin": invite_worker.CHATGPT_BASE_URL,
            "User-Agent": invite_worker.DEFAULT_USER_AGENT,
        }
        resp = session.get(f"{invite_worker.CHATGPT_BASE_URL}/backend-api/accounts", headers=headers, timeout=20)
        if resp.status_code != 200:
            status = "expired" if resp.status_code in (401, 403) else "error"
            return {"ok": False, "error": f"accounts http {resp.status_code}", "status": status}

        payload = invite_worker.normalize_accounts_payload(resp.json())
        matched = None
        for raw in payload:
            parsed = invite_worker.parse_account_entry(raw)
            if team_id in [parsed.get("workspace_id"), parsed.get("org_id")]:
                matched = parsed
                break
        if not matched and payload:
            matched = invite_worker.parse_account_entry(payload[0])

        candidate_id = None
        if matched:
            candidate_id = matched.get("workspace_id") or matched.get("org_id") or team_id
        else:
            candidate_id = team_id

        users = invite_worker.fetch_account_items(session, token, candidate_id, "users")
        invites = invite_worker.fetch_account_items(session, token, candidate_id, "invites")
        joined_count = len(users)
        invited_count = len(invites)
        current_members = joined_count + invited_count

        expires = str(item.get("expires") or "").strip()
        status = "active"
        if current_members >= max_per_group:
            status = "full"
        if expires:
            try:
                expiry_dt = datetime.datetime.fromisoformat(expires.replace("Z", "+00:00"))
                if expiry_dt < datetime.datetime.now(datetime.timezone.utc):
                    status = "expired"
            except Exception:
                pass

        return {
            "ok": True,
            "status": status,
            "name": matched.get("name") if matched else (item.get("name") or ""),
            "joined_count": joined_count,
            "invited_count": invited_count,
            "current_members": current_members,
            "last_sync": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "error": "",
        }
    except requests.RequestException as e:
        return {"ok": False, "error": str(e), "status": "error"}
    except Exception as e:
        return {"ok": False, "error": str(e), "status": "error"}


def get_at_local_used(item):
    _, stable_used_per_group_key = build_history_usage_maps()
    team_id = str(item.get("team_id") or "").strip()
    stable_used = stable_used_per_group_key.get(f"at:{team_id}", 0)
    current_members = int(item.get("current_members", 0) or 0)
    joined_invited = int(item.get("joined_count", 0) or 0) + int(item.get("invited_count", 0) or 0)
    synced_used = max(current_members, joined_invited, 0)
    has_sync_state = bool(str(item.get("last_sync") or "").strip() or str(item.get("sync_status") or "").strip())
    if has_sync_state:
        return max(synced_used, 1)
    return max(stable_used, synced_used, 1)


def is_synced_full_at_group(item):
    if not isinstance(item, dict):
        return False
    if (item.get("mode") or "at").strip().lower() != "at":
        return False
    sync_status = str(item.get("sync_status") or "").strip().lower()
    last_sync = str(item.get("last_sync") or "").strip()
    if not (sync_status or last_sync):
        return False
    try:
        max_per_group = int(item.get("max_per_group", 4) or 4)
    except Exception:
        max_per_group = 4
    current_members = int(item.get("current_members", 0) or 0)
    joined_invited = int(item.get("joined_count", 0) or 0) + int(item.get("invited_count", 0) or 0)
    synced_used = max(current_members, joined_invited, 0)
    return synced_used >= max(max_per_group, 1)

def compute_stats():
    accounts = get_accounts_config()
    runtime_accounts = get_runtime_accounts_config()
    legacy_used_per_runtime_account, stable_used_per_group_key = build_history_usage_maps()
    used_list = [legacy_used_per_runtime_account.get(i, 0) for i in range(len(runtime_accounts))]
    history_total = sum(legacy_used_per_runtime_account.values())
    queue = safe_read_lines(QUEUE_FILE)
    invite_log = safe_read_lines(INVITE_LOG_FILE)
    bj_now = datetime.datetime.now(CN_TZ)
    today_str = bj_now.strftime("%Y-%m-%d")
    today_invites = 0
    for line in invite_log:
        if line.startswith(today_str):
            today_invites += 1
    active_count = 0
    total_seats = 0
    current_group_display = "Full"
    used_in_current = 0
    max_in_current = 4
    occupied_seats = 0
    remaining_seats = 0
    next_groups = []
    runtime_groups = []
    at_total_groups = 0
    at_synced_groups = 0
    at_remaining_seats = 0
    at_next_groups = []
    at_skipped_groups = 0

    for i, acc in enumerate(runtime_accounts):
        mode = acc.get("mode")
        max_per_group = int(acc.get("max_per_group", 4) or 4)
        history_used = legacy_used_per_runtime_account.get(i, 0)

        if mode == "cookie":
            ids_list = acc.get("ids_list", [])
            if not ids_list or not acc.get("cookies"):
                continue

            active_count += 1
            total_seats += len(ids_list) * max_per_group

            for g_idx, _group_id in enumerate(ids_list):
                group_key = f"ck:{str(_group_id).strip()}"
                stable_used = stable_used_per_group_key.get(group_key)
                if stable_used is not None:
                    group_used = stable_used
                else:
                    group_used = history_used - (g_idx * max_per_group)
                    if group_used < 0:
                        group_used = 0
                if group_used > max_per_group:
                    group_used = max_per_group
                remaining = max(max_per_group - group_used, 0)
                occupied_seats += group_used
                remaining_seats += remaining
                runtime_groups.append({
                    "label": f"{acc.get('label', f'CK节点{i+1}')}-组{g_idx+1}",
                    "used": group_used,
                    "capacity": max_per_group,
                    "remaining": remaining,
                })
        else:
            at_total_groups += 1
            skip_marked = bool(acc.get("skip_marked"))
            sync_used = int(acc.get("sync_used", 0) or 0)
            is_synced = bool(str(acc.get("sync_status") or "").strip() or str(acc.get("last_sync") or "").strip())
            stable_used = stable_used_per_group_key.get(f"at:{str(acc.get('team_id') or '').strip()}", 0)
            group_used = max(sync_used if is_synced else 1, stable_used, history_used if not is_synced else 0, 1)
            if group_used > max_per_group:
                group_used = max_per_group
            remaining = max(max_per_group - group_used, 0)
            if skip_marked:
                at_skipped_groups += 1
                continue
            active_count += 1
            total_seats += max_per_group
            occupied_seats += group_used
            remaining_seats += remaining
            at_group = {
                "label": f"{str(acc.get('label') or f'AT节点{i+1}')} | {str(acc.get('display_name') or acc.get('team_id') or '-')}",
                "used": group_used,
                "capacity": max_per_group,
                "remaining": remaining,
                "synced": is_synced,
            }
            if is_synced:
                at_synced_groups += 1
                at_remaining_seats += remaining
            runtime_groups.append(at_group)
            at_next_groups.append(at_group)

    for idx, group in enumerate(runtime_groups):
        if group["remaining"] > 0:
            current_group_display = group["label"]
            used_in_current = group["used"]
            max_in_current = group["capacity"]
            next_groups = runtime_groups[idx + 1: idx + 6]
            break

    return {
        "queue": len(queue),
        "success": history_total,
        "total_seats": total_seats,
        "occupied_seats": occupied_seats,
        "remaining_seats": remaining_seats,
        "active_nodes": active_count,
        "accounts": accounts,
        "runtime_accounts": runtime_accounts,
        "used_list": used_list,
        "cur_group": current_group_display,
        "cur_used": used_in_current,
        "cur_max": max_in_current,
        "next_groups": next_groups,
        "at_total_groups": at_total_groups,
        "at_synced_groups": at_synced_groups,
        "at_unsynced_groups": max(at_total_groups - at_synced_groups, 0),
        "at_remaining_seats": at_remaining_seats,
        "at_next_groups": [g for g in at_next_groups if g["remaining"] > 0][:3],
        "at_skipped_groups": at_skipped_groups,
        "today_invites": today_invites,
        "bj_now_text": bj_now.strftime("%Y-%m-%d %H:%M:%S"),
        "today_label": today_str,
    }

# ================= 6. UI 渲染 =================
stats = compute_stats()
pid = get_worker_pid()

with st.sidebar:
    st.markdown("### 控制中心")
    if pid:
        if st.button("停止引擎", use_container_width=True):
            os.system("pkill -f worker.py"); time.sleep(1); st.rerun()
        st.caption("点击停止后台进程")
    else:
        if st.button("启动引擎", type="primary", use_container_width=True):
            restart_worker_safely(); time.sleep(1); st.rerun()
        st.caption("启动后台工作进程")
    
    st.markdown("---")
    st.markdown("#### 运行概览")
    st.metric("总剩余空位", f"{stats['remaining_seats']}", delta=f"已占用 {stats['occupied_seats']} / {stats['total_seats']}")
    if stats["cur_group"] != "Full":
        st.info(f"当前运行组：**{stats['cur_group']}**")
        remains = stats['cur_max'] - stats['cur_used']
        st.progress(stats['cur_used'] / stats['cur_max'])
        st.caption(f"已用 {stats['cur_used']} / {stats['cur_max']} · 剩余 {remains}")
    else:
        st.success("所有小组已满")

    st.markdown("---")
    st.markdown("#### 即将轮到")
    if stats["next_groups"]:
        for idx, group in enumerate(stats["next_groups"], 1):
            st.markdown(
                f"**{idx}. {group['label']}** <span style='float:right;color:#666'>{group['used']}/{group['capacity']}</span>",
                unsafe_allow_html=True,
            )
            st.progress(group["used"] / group["capacity"] if group["capacity"] else 0)
            st.caption(f"剩余 {group['remaining']}")
    else:
        st.caption("后续暂无可用分组")

    st.markdown("---")
    st.markdown("#### 统计信息")
    st.caption(f"活动组数：{stats['active_nodes']}")
    st.caption(f"待处理队列：{stats['queue']}")
    st.caption(f"历史邀请数：{stats['success']}")
    if stats.get("at_skipped_groups"):
        st.caption(f"AT异常跳过：{stats['at_skipped_groups']}")

@st.fragment(run_every="30s")
def render_live_overview():
    live_stats = compute_stats()
    live_pid = get_worker_pid()
    status_text = "引擎运行中" if live_pid else "引擎已停止"
    st.title("方木木团队运营后台")
    st.caption(
        f"{status_text} | 北京时间今日已邀请 {live_stats['today_invites']} 人 | "
        f"当前剩余空位 {live_stats['remaining_seats']} 个 | "
        f"刷新时间 {live_stats['bj_now_text']} | 概览约每30秒自动更新"
    )

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric("待处理队列", f"{live_stats['queue']}")
    with k2:
        pct = int((live_stats['occupied_seats'] / live_stats['total_seats'] * 100)) if live_stats['total_seats'] > 0 else 0
        st.metric("容量使用情况", f"{pct}%", delta=f"{live_stats['occupied_seats']} / {live_stats['total_seats']}")
    with k3:
        st.metric("今日邀请", f"{live_stats['today_invites']}")
    with k4:
        st.metric("剩余空位", f"{live_stats['remaining_seats']}")
    with k5:
        st.metric("异常AT组", f"{live_stats['at_skipped_groups']}")

    last_inv = "暂无"
    if os.path.exists(INVITE_LOG_FILE):
        try:
            line = subprocess.check_output(f"tail -n 1 {INVITE_LOG_FILE}", shell=True).decode().strip()
            if line:
                last_inv = line.split("\t")[-1]
        except:
            pass
    st.caption(f"最后受邀者：{last_inv[:40]+'...' if len(last_inv)>40 else last_inv}")


render_live_overview()
st.markdown("---")

main_view = st.radio(
    "后台区域",
    ["后台配置", "任务运维", "记录中心"],
    horizontal=True,
    label_visibility="collapsed",
)

if main_view == "后台配置":
    st.markdown("### 账号与节点配置")
    st.caption("先导入 AT 主号，再管理分组、同步状态和节点配置。")
    st.info("安全模式：绝对路径 + 字符串 ID。")
    current_accs = list(stats["accounts"])
    at_db = load_accounts_db_safe()
    at_accounts = [
        item for item in at_db.get("accounts", [])
        if isinstance(item, dict) and (item.get("mode") or "at").strip().lower() == "at"
    ]

    with st.expander("AT 主号 / 单组导入", expanded=False):
        st.caption("把导出的 accessToken 原始文本整体贴进来，每个 JSON 块都会自动变成一个独立 AT 组。")
        st.caption(f"当前已导入 AT 组：{len(at_accounts)}")
        at_bulk_text = st.text_area("粘贴 AT 原始数据", height=220, key="bulk_at_payload")
        at_default_mpg = st.number_input("默认每组最大人数", min_value=1, max_value=1000, value=4, key="bulk_at_default_mpg")
        if st.button("一键导入 AT 组", key="bulk_at_import_btn"):
            parsed_at, mode = parse_at_bulk_accounts_payload(at_bulk_text, int(at_default_mpg))
            if not parsed_at:
                st.error(f"没有解析到有效的 AT 账号（模式：{mode}）。")
            else:
                import_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                def normalize_at_item(item, fallback_created_at=""):
                    try:
                        max_per_group = int(item.get("max_per_group", at_default_mpg) or at_default_mpg)
                    except Exception:
                        max_per_group = int(at_default_mpg)
                    if max_per_group <= 0:
                        max_per_group = int(at_default_mpg)
                    created_at = str(item.get("created_at") or fallback_created_at or import_now).strip()
                    updated_at = str(item.get("updated_at") or import_now).strip()
                    return {
                        "mode": "at",
                        "enabled": bool(item.get("enabled", True)),
                        "email": str(item.get("email") or "").strip(),
                        "team_id": str(item.get("team_id") or "").strip(),
                        "access_token": str(item.get("access_token") or "").strip(),
                        "expires": str(item.get("expires") or "").strip(),
                        "max_per_group": max_per_group,
                        "current_members": int(item.get("current_members", 1) or 1),
                        "joined_count": int(item.get("joined_count", 1) or 1),
                        "invited_count": int(item.get("invited_count", 0) or 0),
                        "sync_status": str(item.get("sync_status") or ""),
                        "created_at": created_at,
                        "updated_at": updated_at,
                    }

                merged = []
                merged_index = {}
                for item in at_accounts:
                    team_id = str(item.get("team_id") or "").strip()
                    if not team_id or team_id in merged_index:
                        continue
                    merged_index[team_id] = len(merged)
                    merged.append(normalize_at_item(item))

                new_count = 0
                updated_count = 0
                imported_team_ids = set()
                for item in parsed_at:
                    team_id = str(item.get("team_id") or "").strip()
                    if not team_id:
                        continue
                    imported_team_ids.add(team_id)
                    existing_idx = merged_index.get(team_id)
                    existing_created_at = ""
                    if existing_idx is not None:
                        existing_created_at = str(merged[existing_idx].get("created_at") or "").strip()
                    normalized = normalize_at_item(item, fallback_created_at=existing_created_at)
                    if existing_idx is not None:
                        merged[existing_idx] = normalized
                        updated_count += 1
                    else:
                        merged_index[team_id] = len(merged)
                        merged.append(normalized)
                        new_count += 1

                synced_count = 0
                sync_ok_count = 0
                if imported_team_ids:
                    synced_merged = []
                    for item in merged:
                        updated_item = dict(item)
                        if str(updated_item.get("team_id") or "").strip() in imported_team_ids:
                            sync_res = sync_single_at_account_record(updated_item)
                            updated_item.update({
                                "name": sync_res.get("name") or updated_item.get("name") or updated_item.get("email") or updated_item.get("team_id"),
                                "sync_status": sync_res.get("status", "error"),
                                "current_members": int(sync_res.get("current_members", updated_item.get("current_members", 1)) or 0),
                                "joined_count": int(sync_res.get("joined_count", updated_item.get("joined_count", 1)) or 0),
                                "invited_count": int(sync_res.get("invited_count", updated_item.get("invited_count", 0)) or 0),
                                "last_sync": sync_res.get("last_sync", updated_item.get("last_sync", "")),
                                "last_error": sync_res.get("error", ""),
                            })
                            synced_count += 1
                            if sync_res.get("ok"):
                                sync_ok_count += 1
                        synced_merged.append(updated_item)
                    merged = synced_merged

                if save_accounts_db_safe(merged):
                    st.success(
                        f"AT 导入完成：识别 {len(parsed_at)} 个，新增 {new_count} 个，更新 {updated_count} 个，自动同步 {sync_ok_count}/{synced_count} 个，当前总数 {len(merged)}。"
                    )
                    time.sleep(1)
                    st.rerun()

        if at_accounts:
            preview = []
            for idx, item in enumerate(at_accounts[:20], 1):
                preview.append(
                    f"{idx:03d} | {item.get('email') or '-'} | {item.get('team_id') or '-'} | mpg={item.get('max_per_group', 4)} | added={item.get('created_at') or '-'}"
                )
            st.text_area("AT 组导入预览", "\n".join(preview), height=180, key="at_preview", disabled=True)

    with st.expander("AT 组管理", expanded=bool(at_accounts)):
        fail_state = load_at_fail_state_safe()
        total_at = len(at_accounts)
        enabled_at = sum(1 for item in at_accounts if bool(item.get("enabled", True)))
        disabled_at = total_at - enabled_at
        skipped_at = sum(
            1
            for item in at_accounts
            if normalize_at_fail_meta(fail_state.get(str(item.get("team_id") or "").strip())).get("skip_marked")
        )
        st.caption("同步组状态 = 去官方工作区查询成员和待邀请人数，并刷新本地的成员数、状态、剩余空位。它不会发邀请。")
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("AT组总数", total_at)
        with m2:
            st.metric("启用中", enabled_at)
        with m3:
            st.metric("已禁用", disabled_at)
        with m4:
            st.metric("异常跳过", skipped_at)

        search_kw = st.text_input("搜索邮箱 / 组ID", key="at_manage_search")
        status_filter = st.selectbox(
            "状态筛选",
            ["全部", "启用中", "已禁用", "未同步", "可用", "已满员", "空组", "异常跳过"],
            key="at_manage_status",
        )
        if skipped_at:
            alert_col1, alert_col2 = st.columns([3, 1])
            with alert_col1:
                st.error(f"当前有 {skipped_at} 个 AT 组处于异常跳过状态。")
            with alert_col2:
                if st.button("只看异常组", key="at_filter_skipped_quick_btn"):
                    st.session_state["at_manage_status"] = "异常跳过"
                    st.rerun()

        filtered_at = []
        search_lower = search_kw.strip().lower()
        for idx, item in enumerate(at_accounts):
            team_id = str(item.get("team_id") or "").strip()
            fail_meta = normalize_at_fail_meta(fail_state.get(team_id))
            skip_marked = bool(fail_meta.get("skip_marked"))
            enabled_flag = bool(item.get("enabled", True))
            sync_status = str(item.get("sync_status") or "").strip().lower()
            current_members = get_at_local_used(item)
            max_per_group = int(item.get("max_per_group", 4) or 4)
            remaining_slots = max(max_per_group - current_members, 0)
            if status_filter == "启用中" and not enabled_flag:
                continue
            if status_filter == "已禁用" and enabled_flag:
                continue
            if status_filter == "未同步" and sync_status:
                continue
            if status_filter == "可用" and (remaining_slots <= 0 or skip_marked):
                continue
            if status_filter == "已满员" and remaining_slots > 0:
                continue
            if status_filter == "空组" and current_members != 0:
                continue
            if status_filter == "异常跳过" and not skip_marked:
                continue
            haystack = " ".join([
                str(item.get("email") or ""),
                str(item.get("team_id") or ""),
                str(item.get("expires") or ""),
                sync_status,
                "skip" if skip_marked else "",
            ]).lower()
            if search_lower and search_lower not in haystack:
                continue
            filtered_at.append((idx, item, fail_meta))

        c_bulk1, c_bulk2 = st.columns(2)
        with c_bulk1:
            if st.button("批量禁用当前筛选", key="at_disable_filtered_btn", disabled=not filtered_at):
                new_accounts = list(at_accounts)
                for idx, item, _fail_meta in filtered_at:
                    updated = dict(new_accounts[idx])
                    updated["enabled"] = False
                    new_accounts[idx] = updated
                if save_accounts_db_safe(new_accounts):
                    st.success(f"已禁用 {len(filtered_at)} 个 AT 组。")
                    time.sleep(1)
                    st.rerun()
        with c_bulk2:
            if st.button("删除已禁用AT组", key="at_delete_disabled_btn", disabled=disabled_at == 0):
                new_accounts = [item for item in at_accounts if bool(item.get("enabled", True))]
                removed = len(at_accounts) - len(new_accounts)
                if save_accounts_db_safe(new_accounts):
                    st.success(f"已删除 {removed} 个已禁用 AT 组。")
                    time.sleep(1)
                    st.rerun()
        c_bulk3, c_bulk4 = st.columns(2)
        with c_bulk3:
            if st.button("同步筛选组状态", key="at_sync_filtered_btn", disabled=not filtered_at):
                new_accounts = list(at_accounts)
                ok_count = 0
                for idx, item, _fail_meta in filtered_at:
                    sync_res = sync_single_at_account_record(item)
                    updated = dict(new_accounts[idx])
                    updated.update({
                        "name": sync_res.get("name") or updated.get("name") or updated.get("email") or updated.get("team_id"),
                        "sync_status": sync_res.get("status", "error"),
                        "current_members": int(sync_res.get("current_members", 0) or 0),
                        "joined_count": int(sync_res.get("joined_count", 0) or 0),
                        "invited_count": int(sync_res.get("invited_count", 0) or 0),
                        "last_sync": sync_res.get("last_sync", ""),
                        "last_error": sync_res.get("error", ""),
                    })
                    new_accounts[idx] = updated
                    if sync_res.get("ok"):
                        ok_count += 1
                if save_accounts_db_safe(new_accounts):
                    st.success(f"已同步 {ok_count}/{len(filtered_at)} 个 AT 组。")
                    time.sleep(1)
                    st.rerun()
        synced_full_count = sum(1 for item in at_accounts if is_synced_full_at_group(item))
        with c_bulk4:
            if st.button("批量删除已满员AT组", key="at_delete_full_btn", disabled=synced_full_count == 0):
                st.session_state["confirm_delete_full_at"] = True

        if st.session_state.get("confirm_delete_full_at"):
            st.warning("仅删除本地 AT 记录，不会影响已卖卡密，也不会移除 OpenAI 里的成员。")
            st.caption("删除范围：仅限已同步且已判定满员的 AT 组。")
            confirm_col1, confirm_col2 = st.columns(2)
            with confirm_col1:
                if st.button(f"确认删除 {synced_full_count} 个已满员AT组", key="at_delete_full_confirm_btn"):
                    new_accounts = [item for item in at_accounts if not is_synced_full_at_group(item)]
                    removed = len(at_accounts) - len(new_accounts)
                    st.session_state["confirm_delete_full_at"] = False
                    if save_accounts_db_safe(new_accounts):
                        st.success(f"已删除 {removed} 个已满员 AT 组。")
                        time.sleep(1)
                        st.rerun()
            with confirm_col2:
                if st.button("取消", key="at_delete_full_cancel_btn"):
                    st.session_state["confirm_delete_full_at"] = False
                    st.info("已取消。")

        st.caption(f"当前显示 {len(filtered_at)} / {len(at_accounts)} 个 AT 组")
        if not filtered_at:
            st.info("当前筛选条件下没有匹配的 AT 组。")

        for idx, item, fail_meta in filtered_at:
            enabled_flag = bool(item.get("enabled", True))
            badge = "已启用" if enabled_flag else "已禁用"
            if bool(fail_meta.get("skip_marked")):
                badge += " / 异常跳过"
            title = f"AT节点 {idx+1:03d} | {badge} | {item.get('email') or '-'}"
            with st.expander(title, expanded=False):
                info1, info2, info3 = st.columns([2, 3, 2])
                with info1:
                    st.text_input("邮箱", value=str(item.get("email") or ""), key=f"at_email_{idx}", disabled=True)
                    edited_max_per_group = st.number_input(
                        "每组最大人数",
                        min_value=1,
                        max_value=500,
                        step=1,
                        value=int(item.get("max_per_group", 4) or 4),
                        key=f"at_mpg_edit_{idx}",
                    )
                    st.text_input("添加时间", value=str(item.get("created_at") or ""), key=f"at_created_{idx}", disabled=True)
                with info2:
                    st.text_input("组 ID", value=str(item.get("team_id") or ""), key=f"at_teamid_{idx}", disabled=True)
                    st.text_input("到期时间", value=str(item.get("expires") or ""), key=f"at_expires_{idx}", disabled=True)
                with info3:
                    token = str(item.get("access_token") or "")
                    masked = token[:18] + "..." + token[-12:] if len(token) > 40 else token
                    st.text_input("访问令牌", value=masked, key=f"at_token_{idx}", disabled=True)

                current_members = get_at_local_used(item)
                max_per_group = int(item.get("max_per_group", 4) or 4)
                remaining_slots = max(max_per_group - current_members, 0)
                raw_sync_status = str(item.get("sync_status") or "-").strip().lower()
                sync_status_map = {
                    "full": "已满",
                    "active": "可用",
                    "available": "可用",
                    "empty": "空组",
                    "error": "异常",
                    "-": "未同步",
                    "": "未同步",
                }
                sync_status_text = sync_status_map.get(raw_sync_status, raw_sync_status or "未同步")

                s1, s2, s3, s4, s5 = st.columns(5)
                with s1:
                    st.text_input("组状态", value=sync_status_text, key=f"at_sync_status_{idx}", disabled=True)
                with s2:
                    st.text_input("当前占位", value=str(current_members), key=f"at_members_{idx}", disabled=True)
                with s3:
                    st.text_input("已加入 / 待邀请", value=f"{int(item.get('joined_count', 0) or 0)}/{int(item.get('invited_count', 0) or 0)}", key=f"at_join_inv_{idx}", disabled=True)
                with s4:
                    st.text_input("剩余空位", value=str(remaining_slots), key=f"at_remaining_{idx}", disabled=True)
                with s5:
                    st.text_input("上次同步", value=str(item.get("last_sync") or ""), key=f"at_last_sync_{idx}", disabled=True)
                if item.get("last_error"):
                    st.warning(str(item.get("last_error")))
                f1, f2, f3, f4 = st.columns(4)
                with f1:
                    st.text_input("连续失败", value=str(int(fail_meta.get("consecutive_failures", 0) or 0)), key=f"at_fail_seq_{idx}", disabled=True)
                with f2:
                    st.text_input("今日失败批次", value=str(int(fail_meta.get("today_fail_batches", 0) or 0)), key=f"at_fail_batches_{idx}", disabled=True)
                with f3:
                    st.text_input("今日失败邮箱", value=str(int(fail_meta.get("today_failed_emails", 0) or 0)), key=f"at_fail_emails_{idx}", disabled=True)
                with f4:
                    st.text_input("上次失败", value=str(fail_meta.get("last_failed_at") or ""), key=f"at_fail_last_{idx}", disabled=True)
                if bool(fail_meta.get("skip_marked")):
                    st.error("已标记异常跳过：连续失败已达到 4 次，当前调度会先跳过这个 AT 组。")
                if fail_meta.get("last_failed_emails"):
                    st.caption("最近失败邮箱：" + ", ".join(list(fail_meta.get("last_failed_emails") or [])[:5]))
                if fail_meta.get("last_failure_error"):
                    st.caption("最近失败原因：" + str(fail_meta.get("last_failure_error") or ""))
                st.caption("说明：当前占位 = 已加入 + 待邀请；剩余空位为 0 代表这个组已经不能继续发邀请。")

                action1, action2, action3, action4, action5 = st.columns(5)
                with action1:
                    btn_label = "禁用" if enabled_flag else "启用"
                    if st.button(btn_label, key=f"at_toggle_{idx}"):
                        new_accounts = list(at_accounts)
                        updated = dict(new_accounts[idx])
                        updated["enabled"] = not enabled_flag
                        new_accounts[idx] = updated
                        if save_accounts_db_safe(new_accounts):
                            st.success(f"{btn_label}成功：{item.get('email') or item.get('team_id')}")
                            time.sleep(1)
                            st.rerun()
                with action2:
                    if st.button("删除", key=f"at_delete_{idx}"):
                        new_accounts = [x for j, x in enumerate(at_accounts) if j != idx]
                        if save_accounts_db_safe(new_accounts):
                            st.success(f"已删除：{item.get('email') or item.get('team_id')}")
                            time.sleep(1)
                            st.rerun()
                with action3:
                    if st.button("同步组状态", key=f"at_sync_{idx}"):
                        sync_res = sync_single_at_account_record(item)
                        new_accounts = list(at_accounts)
                        updated = dict(new_accounts[idx])
                        updated.update({
                            "name": sync_res.get("name") or updated.get("name") or updated.get("email") or updated.get("team_id"),
                            "sync_status": sync_res.get("status", "error"),
                            "current_members": int(sync_res.get("current_members", 0) or 0),
                            "joined_count": int(sync_res.get("joined_count", 0) or 0),
                            "invited_count": int(sync_res.get("invited_count", 0) or 0),
                            "last_sync": sync_res.get("last_sync", ""),
                            "last_error": sync_res.get("error", ""),
                        })
                        new_accounts[idx] = updated
                        if save_accounts_db_safe(new_accounts):
                            if sync_res.get("ok"):
                                st.success(f"已同步：{item.get('email') or item.get('team_id')}")
                            else:
                                st.warning(f"同步失败：{sync_res.get('error') or 'unknown'}")
                            time.sleep(1)
                            st.rerun()
                with action4:
                    if st.button("清除异常标记", key=f"at_clear_fail_{idx}", disabled=not bool(fail_meta.get("skip_marked"))):
                        if clear_at_fail_mark_safe(item.get("team_id")):
                            st.success(f"已清除异常标记：{item.get('email') or item.get('team_id')}")
                            time.sleep(1)
                            st.rerun()
                with action5:
                    if st.button("保存人数", key=f"at_save_mpg_{idx}"):
                        new_accounts = list(at_accounts)
                        updated = dict(new_accounts[idx])
                        updated["max_per_group"] = int(edited_max_per_group)
                        if int(updated.get("current_members", 0) or 0) >= int(edited_max_per_group):
                            updated["sync_status"] = "full"
                        elif str(updated.get("last_sync") or "").strip():
                            updated["sync_status"] = "active"
                        new_accounts[idx] = updated
                        if save_accounts_db_safe(new_accounts):
                            st.success(f"已更新每组最大人数：{item.get('email') or item.get('team_id')} -> {int(edited_max_per_group)}")
                            time.sleep(1)
                            st.rerun()

    st.session_state["accounts_slots"] = max(int(st.session_state.get("accounts_slots", 5)), len(current_accs), 5)

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if st.button("➕ Add Slot", key="slot_add_btn"):
            st.session_state["accounts_slots"] = min(100, int(st.session_state["accounts_slots"]) + 1)
    with c2:
        if st.button("➖ Remove Slot", key="slot_del_btn"):
            st.session_state["accounts_slots"] = max(1, int(st.session_state["accounts_slots"]) - 1)
    with c3:
        st.session_state["accounts_slots"] = int(st.number_input(
            "Visible Slots (max 100)", min_value=1, max_value=100,
            value=int(st.session_state["accounts_slots"]), step=1, key="slot_num_input"
        ))

    while len(current_accs) < int(st.session_state["accounts_slots"]):
        current_accs.append({"cookies": "", "ids_str": "", "max_per_group": 4})

    with st.form("safe_config_form"):
        save_list = []
        for i in range(int(st.session_state["accounts_slots"])):
            acc = current_accs[i]
            with st.expander(f"Node {i+1} Configuration", expanded=(i == 0)):
                c_a, c_b = st.columns([3, 1])
                with c_a:
                    ck = st.text_area("Cookies JSON", value=str(acc.get("cookies", "")), height=80, key=f"c{i}")
                    ids = st.text_area("Group IDs (One per line)", value=str(acc.get("ids_str", "")), height=100, key=f"i{i}")
                with c_b:
                    mp = st.number_input("Max Per Group", value=int(acc.get("max_per_group", 4) or 4), min_value=1, max_value=1000, key=f"m{i}")
                save_list.append({"cookies": ck.strip(), "ids": ids.strip(), "max_per_group": int(mp)})

        if st.form_submit_button("Save Configuration", type="primary"):
            final_data = []
            for item in save_list:
                ids_norm = normalize_ids_text(item.get("ids", ""))
                if item["cookies"] and ids_norm:
                    final_data.append({
                        "cookies": item["cookies"],
                        "ids": ids_norm,
                        "max_per_group": int(item["max_per_group"]),
                    })
            if not final_data:
                st.error("Must have at least 1 node."); st.stop()
            if save_json_safe(STATE_FILE, {"accounts": final_data}):
                st.success(f"Configuration Saved. nodes={len(final_data)}")
                time.sleep(1)
                st.rerun()


elif main_view == "任务运维":
    c_ops, c_view = st.columns([1, 1])
    with c_ops:
        st.markdown("#### 批量添加到队列")
        if "batch_emails_input_reset" in st.session_state:
            st.session_state["batch_emails_input"] = st.session_state.pop("batch_emails_input_reset")
        batch_emails = st.text_area(
            "电子邮件（每行一封，也支持逗号分隔）",
            height=100,
            placeholder="user1@a.com\nuser2@a.com",
            key="batch_emails_input",
        )
        parsed_inputs = split_email_input_text(batch_emails)
        _, invalid_preview = split_valid_invalid_emails(parsed_inputs)
        if invalid_preview:
            st.warning(f"检测到 {len(invalid_preview)} 个明显非法邮箱，加入队列时会直接拦下。")
            st.caption("示例：" + "；".join([f"{item['email']}（{item['reason']}）" for item in invalid_preview[:3]]))
        if st.button("加入队列"):
            added_count = 0
            duplicate_count = 0
            invalid_count = 0
            if parsed_inputs:
                valid_inputs, invalid_inputs = split_valid_invalid_emails(parsed_inputs)
                invalid_count = len(invalid_inputs)
                try:
                    existing_queue = safe_read_lines(QUEUE_FILE)
                    existing_lower = {str(x or "").strip().lower() for x in existing_queue if str(x or "").strip()}
                    deduped_valid = []
                    for email in valid_inputs:
                        email_key = email.lower()
                        if email_key in existing_lower:
                            duplicate_count += 1
                            continue
                        existing_lower.add(email_key)
                        deduped_valid.append(email)
                    if deduped_valid:
                        with locked_open(QUEUE_FILE, "a+") as f:
                            for email in deduped_valid:
                                f.write(email + "\n")
                                added_count += 1
                            f.flush()
                    for item in invalid_inputs:
                        append_invalid_email_record(item["email"], item["reason"], source="手动加入队列")
                    if invalid_inputs:
                        st.session_state["batch_emails_input_reset"] = "\n".join([item["email"] for item in invalid_inputs])
                    else:
                        st.session_state["batch_emails_input_reset"] = ""
                    st.success(f"已加入 {added_count} 个邮箱。")
                    if duplicate_count:
                        st.info(f"跳过重复邮箱 {duplicate_count} 个。")
                    if invalid_count:
                        st.warning(f"拦截明显非法邮箱 {invalid_count} 个，已写入无效邮箱区。")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"添加失败：{e}")
        
        st.markdown("#### Maintenance")
        if st.button("Clear Queue"):
            try:
                with locked_open(QUEUE_FILE, "r+") as f: f.seek(0); f.truncate(0)
                st.toast("Queue Cleared.")
            except: pass
        if st.button("Reset All History"):
            try:
                with locked_open(HISTORY_FILE, "r+") as f: f.seek(0); f.truncate(0)
                st.toast("All History Reset.")
            except: pass
            
        if st.button("Clear Worker Logs (Restart)"):
             try:
                 os.system("pkill -f worker.py || true"); time.sleep(1)
                 with open(WORKER_LOG_FILE, 'w'): pass
                 restart_worker_safely()
                 st.toast("Logs cleared & Worker restarted.")
                 time.sleep(1); st.rerun()
             except Exception as e: st.error(f"Error: {e}")
             
        if st.button("Reset Cursor (Force Retry)"):
            try: open(CURSOR_FILE, 'w').close(); st.toast("Cursor Reset.")
            except: pass
            
    with c_view:
        st.markdown("#### 队列预览")
        q_lines = safe_read_lines(QUEUE_FILE)
        invalid_top200 = find_invalid_queue_entries(q_lines, limit=200)
        invalid_all = find_invalid_queue_entries(q_lines, limit=None)
        if q_lines:
            st.text_area("队列前 200 名", "\n".join(q_lines[:200]), height=200)
        else:
            st.caption("空")
        qbtn1, qbtn2 = st.columns(2)
        with qbtn1:
            if st.button("清理前200非法邮箱", disabled=not invalid_top200):
                removed, _items = purge_invalid_queue_entries(limit=200, source="前200非法邮箱清理")
                if removed:
                    st.success(f"已清理前 200 名中的 {removed} 个非法邮箱。")
                    time.sleep(1)
                    st.rerun()
        with qbtn2:
            if st.button("清理全部非法邮箱", disabled=not invalid_all):
                removed, _items = purge_invalid_queue_entries(limit=None, source="全量非法邮箱清理")
                if removed:
                    st.success(f"已清理全部队列中的 {removed} 个非法邮箱。")
                    time.sleep(1)
                    st.rerun()
        if invalid_top200:
            st.warning(f"当前前 200 名里检测到 {len(invalid_top200)} 个非法邮箱。")
            st.dataframe(
                pd.DataFrame([
                    {"邮箱": item["email"], "原因": item["reason"]}
                    for item in invalid_top200[:20]
                ]),
                use_container_width=True,
                hide_index=True,
            )
        invalid_records = load_invalid_email_records(get_file_signature(INVALID_EMAIL_LOG_FILE))
        if invalid_records:
            st.markdown("#### 失败 / 无效邮箱")
            st.dataframe(
                pd.DataFrame([
                    {
                        "时间": row["time"],
                        "来源": row["source"],
                        "邮箱": row["email"],
                        "原因": row["reason"],
                    }
                    for row in invalid_records[:50]
                ]),
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("#### 工作日志")
        if st.button("刷新"): st.rerun()
        log_txt = "暂无日志。"
        if os.path.exists(WORKER_LOG_FILE):
            try: log_txt = subprocess.check_output(f"tail -n 50 {WORKER_LOG_FILE}", shell=True).decode('utf-8', errors='ignore')
            except: pass
        st.code(log_txt, language="bash")

else:
    st.markdown("### 记录中心")
    rec_head1, rec_head2 = st.columns([5, 1])
    with rec_head1:
        st.caption("这里集中查看兑换记录、邀请记录，以及生成新卡密。")
    with rec_head2:
        if st.button("刷新记录", key="refresh_records_btn"):
            st.cache_data.clear()
            st.rerun()
    record_view = st.radio(
        "记录页",
        ["兑换记录", "邀请记录", "卡密生成"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if record_view == "兑换记录":
        redeem_records = load_redeem_records(get_file_signature(REDEEM_LOG_FILE))
        redeem_stats = compute_period_stats(redeem_records)
        rs1, rs2, rs3, rs4 = st.columns(4)
        with rs1:
            st.metric("总数", redeem_stats["total"])
        with rs2:
            st.metric("今日", redeem_stats["today"])
        with rs3:
            st.metric("本周", redeem_stats["week"])
        with rs4:
            st.metric("本月", redeem_stats["month"])

        rf1, rf2, rf3, rf4 = st.columns(4)
        with rf1:
            redeem_email_kw = st.text_input("邮箱", key="redeem_email_kw")
        with rf2:
            redeem_code_kw = st.text_input("兑换码", key="redeem_code_kw")
        with rf3:
            redeem_date_from = st.date_input("开始日期", value=None, key="redeem_date_from")
        with rf4:
            redeem_date_to = st.date_input("结束日期", value=None, key="redeem_date_to")
        redeem_preset = st.radio("快捷日期", ["全部", "今天", "昨天", "最近3天", "最近7天"], horizontal=True, key="redeem_date_preset")
        redeem_date_from, redeem_date_to = resolve_date_range_from_preset(redeem_preset, redeem_date_from, redeem_date_to)

        filtered_redeems = filter_redeem_records(
            redeem_records,
            email_kw=redeem_email_kw,
            code_kw=redeem_code_kw,
            date_from=redeem_date_from,
            date_to=redeem_date_to,
        )
        st.caption(f"匹配到 {len(filtered_redeems)} 条记录")
        redeem_page = int(st.number_input("兑换记录页码", min_value=1, value=1, step=1, key="redeem_page"))
        redeem_rows, redeem_total_pages = paginate_records(filtered_redeems, 20, redeem_page)
        st.caption(f"第 {min(redeem_page, redeem_total_pages)} / {redeem_total_pages} 页 · 每页 20 条")
        if redeem_rows:
            st.dataframe(
                pd.DataFrame([
                    {
                        "时间": row["time"],
                        "兑换码": row["code"],
                        "邮箱": row["email"],
                    }
                    for row in redeem_rows
                ]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("当前筛选条件下没有匹配的兑换记录。")

    elif record_view == "邀请记录":
        invite_records = load_invite_records(
            get_file_signature(INVITE_LOG_FILE),
            get_file_signature(REDEEM_LOG_FILE),
        )
        invite_stats = compute_period_stats(invite_records)
        is1, is2, is3, is4 = st.columns(4)
        with is1:
            st.metric("总数", invite_stats["total"])
        with is2:
            st.metric("今日", invite_stats["today"])
        with is3:
            st.metric("本周", invite_stats["week"])
        with is4:
            st.metric("本月", invite_stats["month"])

        if1, if2, if3, if4 = st.columns(4)
        with if1:
            invite_email_kw = st.text_input("邮箱", key="invite_email_kw")
        with if2:
            invite_team_kw = st.text_input("卡密 / 分组", key="invite_team_kw")
        with if3:
            invite_date_from = st.date_input("开始日期", value=None, key="invite_date_from")
        with if4:
            invite_date_to = st.date_input("结束日期", value=None, key="invite_date_to")
        invite_preset = st.radio("快捷日期", ["全部", "今天", "昨天", "最近3天", "最近7天"], horizontal=True, key="invite_date_preset")
        invite_date_from, invite_date_to = resolve_date_range_from_preset(invite_preset, invite_date_from, invite_date_to)

        filtered_invites = filter_invite_records(
            invite_records,
            email_kw=invite_email_kw,
            team_kw=invite_team_kw,
            date_from=invite_date_from,
            date_to=invite_date_to,
        )
        invite_filters_active = bool(
            str(invite_email_kw or "").strip()
            or str(invite_team_kw or "").strip()
            or invite_date_from
            or invite_date_to
        )
        if not invite_filters_active:
            filtered_invites = filtered_invites[:200]
            st.caption("默认仅展示最近 200 条邀请记录；使用搜索或日期筛选可查看更早记录。")
        st.caption(f"匹配到 {len(filtered_invites)} 条记录")
        invite_page = int(st.number_input("邀请记录页码", min_value=1, value=1, step=1, key="invite_page"))
        invite_rows, invite_total_pages = paginate_records(filtered_invites, 20, invite_page)
        st.caption(f"第 {min(invite_page, invite_total_pages)} / {invite_total_pages} 页 · 每页 20 条")
        if invite_rows:
            invite_df = pd.DataFrame([
                {
                    "时间": row["time"],
                    "邮箱": row["email"],
                    "分组": row.get("group_label_display") or row["group_label"],
                    "来源": row.get("source") or "手动",
                    "状态": row.get("status") or "成功",
                    "兑换码": row.get("code") or "-",
                    "失败原因": row.get("reason") or "-",
                }
                for row in invite_rows
            ])

            def _style_source(value):
                if value == "卡密":
                    return "background-color: #ecfdf3; color: #047857; font-weight: 600;"
                return "background-color: #f3f4f6; color: #4b5563; font-weight: 600;"

            def _style_status(value):
                if value == "失败":
                    return "background-color: #fef2f2; color: #b91c1c; font-weight: 600;"
                if value == "待邀请":
                    return "background-color: #fffbeb; color: #b45309; font-weight: 600;"
                return "background-color: #eff6ff; color: #1d4ed8; font-weight: 600;"

            invite_styler = (
                invite_df.style
                .applymap(_style_source, subset=["来源"])
                .applymap(_style_status, subset=["状态"])
            )
            st.dataframe(invite_styler, use_container_width=True, hide_index=True)
        else:
            st.info("当前筛选条件下没有匹配的邀请记录。")

    else:
        c_gen, c_out = st.columns(2)
        with c_gen:
            st.markdown("#### 生成许可证")
            prefix = st.text_input("前缀", value="GPT-TEAM")
            qty = st.number_input("数量", 1, 100, 5)
            if st.button("生成卡密", type="primary"):
                with locked_license():
                    db = load_json_safe(LICENSE_FILE)
                    out = []
                    for _ in range(qty):
                        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
                        k = f"{prefix}-{suffix}"
                        if k not in db:
                            db[k] = "unused"
                            out.append(k)
                    if save_json_safe(LICENSE_FILE, db):
                        st.session_state["gen_keys"] = "\n".join(out)
                        st.success(f"已生成 {qty} 个卡密。")

        with c_out:
            st.markdown("#### 导出结果")
            res = st.session_state.get("gen_keys", "")
            st.text_area("结果", res, height=100)
            if res:
                st.download_button("下载 .txt", res, "licenses.txt", "text/plain")
