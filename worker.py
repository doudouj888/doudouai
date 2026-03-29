import time
import os
import json
import sys
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import undetected_chromedriver as uc
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from pyvirtualdisplay import Display

try:
    import cloudscraper
except Exception:
    cloudscraper = None

try:
    from curl_cffi.requests import Session as CurlSession
except Exception:
    CurlSession = None

import fcntl
from contextlib import contextmanager

# ---------------- 基本配置 ----------------
QUEUE_FILE = "queue.txt"
HISTORY_FILE = "history.txt"
STATE_FILE = "state.json"
ACCOUNTS_DB_FILE = "accounts_db.json"
AT_FAIL_STATE_FILE = "at_fail_state.json"
AT_FAIL_LOG_FILE = "at_fail_log.txt"
AT_FAIL_SKIP_THRESHOLD = 4
LOG_FILE = "worker.log"
WORKER_LOCK_FILE = "worker.lock"
INVITE_LOG_FILE = "invite_log.txt"
INVALID_EMAIL_LOG_FILE = "invalid_email_log.txt"
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")

BJ_TZ = timezone(timedelta(hours=8))  # 北京时间
CHATGPT_BASE_URL = "https://chatgpt.com"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


def get_chatgpt_proxy():
    return (
        os.getenv("CHATGPT_API_PROXY", "").strip()
        or os.getenv("HTTPS_PROXY", "").strip()
        or os.getenv("HTTP_PROXY", "").strip()
    )


class BeijingFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=BJ_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]


_worker_formatter = BeijingFormatter("%(asctime)s - %(levelname)s - %(message)s")
_worker_handlers = [
    logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
    logging.StreamHandler(sys.stdout),
]
for _handler in _worker_handlers:
    _handler.setFormatter(_worker_formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=_worker_handlers,
    force=True,
)


def log(msg, level="INFO"):
    logging.log(getattr(logging, level, logging.INFO), msg)


def summarize_emails(items, limit=5):
    values = [str(x).strip() for x in (items or []) if str(x).strip()]
    if not values:
        return "-"
    if len(values) <= limit:
        return ", ".join(values)
    return ", ".join(values[:limit]) + f" ... (+{len(values) - limit})"


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


def extract_invalid_email_entries(items):
    invalid = []
    for raw in items or []:
        email, reason = validate_email_candidate(raw)
        if reason:
            invalid.append({
                "email": email or str(raw or "").strip(),
                "reason": reason,
            })
    return invalid


def append_invite_status_record(email, label, status="成功", source="", code="", reason="", group_key="", mode=""):
    now_str = datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S %z")
    line = "\t".join([
        now_str,
        str(label or "").strip(),
        str(email or "").strip(),
        str(status or "").strip(),
        str(source or "").strip(),
        str(code or "").strip(),
        str(reason or "").strip(),
        str(group_key or "").strip(),
        str(mode or "").strip(),
    ])
    try:
        with open(INVITE_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def append_invalid_email_record(email, reason, source="系统校验"):
    now_str = datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S %z")
    line = "\t".join([
        now_str,
        str(source or "").strip(),
        str(email or "").strip(),
        str(reason or "").strip(),
    ])
    try:
        with open(INVALID_EMAIL_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------------- 文件锁工具 ----------------


@contextmanager
def locked_open(path, mode):
    """
    简单文件锁封装：
    - 所有对 queue.txt 的读写，都用这个函数，避免多进程同时改导致丢数据
    """
    # 注意：这里统一加 utf-8 编码
    f = open(path, mode, encoding="utf-8")
    try:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield f
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


# ---------------- 工具函数 ----------------


def load_accounts_db():
    if not os.path.exists(ACCOUNTS_DB_FILE):
        return {}
    try:
        with open(ACCOUNTS_DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_accounts_db(data):
    with open(ACCOUNTS_DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_at_fail_state():
    if not os.path.exists(AT_FAIL_STATE_FILE):
        return {}
    try:
        with open(AT_FAIL_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_at_fail_state(data):
    with open(AT_FAIL_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data if isinstance(data, dict) else {}, f, ensure_ascii=False, indent=2)


def get_at_fail_key(account):
    return str((account or {}).get("team_id") or "").strip()


def normalize_at_fail_meta(meta):
    today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
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


def record_at_failure(account, emails, error_text=""):
    team_id = get_at_fail_key(account)
    if not team_id:
        return None

    state = load_at_fail_state()
    meta = normalize_at_fail_meta(state.get(team_id))
    unique_emails = []
    seen = set()
    for value in emails or []:
        email = str(value or "").strip().lower()
        if email and email not in seen:
            seen.add(email)
            unique_emails.append(email)

    now = datetime.now(BJ_TZ).isoformat()
    meta["consecutive_failures"] += 1
    meta["today_fail_batches"] += 1
    meta["today_failed_emails"] += len(unique_emails)
    meta["last_failed_at"] = now
    meta["last_failed_count"] = len(unique_emails)
    meta["last_failed_emails"] = unique_emails[:20]
    meta["last_failure_error"] = str(error_text or "").strip()
    meta["skip_marked"] = meta["consecutive_failures"] >= AT_FAIL_SKIP_THRESHOLD
    meta["skip_reason"] = "consecutive_retry_failures" if meta["skip_marked"] else ""
    state[team_id] = meta
    save_at_fail_state(state)

    try:
        with open(AT_FAIL_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "time": now,
                "team_id": team_id,
                "email": str((account or {}).get("email") or "").strip(),
                "consecutive_failures": meta["consecutive_failures"],
                "today_fail_batches": meta["today_fail_batches"],
                "today_failed_emails": meta["today_failed_emails"],
                "skip_marked": meta["skip_marked"],
                "failed_emails": unique_emails,
                "error": meta["last_failure_error"],
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass

    return meta


def clear_at_fail_state(account, note=""):
    team_id = get_at_fail_key(account)
    if not team_id:
        return None

    state = load_at_fail_state()
    meta = normalize_at_fail_meta(state.get(team_id))
    meta["consecutive_failures"] = 0
    meta["skip_marked"] = False
    meta["skip_reason"] = ""
    meta["last_cleared_at"] = datetime.now(BJ_TZ).isoformat()
    state[team_id] = meta
    save_at_fail_state(state)
    return meta


def sync_at_account_snapshot(account, account_id, session, token):
    team_id = str((account or {}).get("team_id") or "").strip()
    if not team_id:
        return
    db = load_accounts_db()
    if not isinstance(db, dict):
        return
    items = db.get("accounts", [])
    if not isinstance(items, list):
        return

    users = fetch_account_items(session, token, account_id, "users")
    invites = fetch_account_items(session, token, account_id, "invites")
    joined_count = len(users)
    invited_count = len(invites)
    current_members = joined_count + invited_count
    max_per_group = int((account or {}).get("max_per_group", 4) or 4)
    sync_status = "full" if current_members >= max_per_group else "active"
    last_sync = datetime.now(timezone.utc).isoformat()

    changed = False
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("team_id") or "").strip() != team_id:
            continue
        item["current_members"] = current_members
        item["joined_count"] = joined_count
        item["invited_count"] = invited_count
        item["sync_status"] = sync_status
        item["last_sync"] = last_sync
        item["last_error"] = ""
        changed = True
        break

    if changed:
        save_accounts_db(db)


def sync_at_account_snapshot_live(account):
    team_id = str((account or {}).get("team_id") or "").strip()
    if not team_id:
        return
    session = create_chatgpt_session((account or {}).get("cookies", "") or "", target_uuid=team_id)
    token = get_api_access_token(session, preset_token=(account or {}).get("access_token", "") or "")
    if not token:
        return
    candidate_ids = resolve_candidate_account_ids(session, token, team_id, mode="at", team_id=team_id)
    if not candidate_ids:
        return
    sync_at_account_snapshot(account, candidate_ids[0], session, token)


def load_state():
    """读取 state.json（支持老版本 / 新版本 accounts 结构）"""
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def parse_accounts():
    """
    返回统一列表：
    - cookie 模式：{"mode":"cookie","cookies":"...","ids":[...],"max_per_group":4}
    - at 模式：{"mode":"at","access_token":"...","team_id":"...","max_per_group":4}
    """
    cfg = load_state()
    accounts = []

    # 1) 旧 state.json（cookie/ids）
    cookie_seq = 1
    if cfg:
        if isinstance(cfg, dict) and "accounts" in cfg:
            for item in cfg.get("accounts", []):
                if not isinstance(item, dict):
                    continue
                cookies = (item.get("cookies") or "").strip()
                ids_raw = (item.get("ids") or "").replace("\r", "\n")
                ids = [x.strip() for x in ids_raw.split("\n") if x.strip()]
                try:
                    max_per_group = int(item.get("max_per_group", 4) or 4)
                except Exception:
                    max_per_group = 4
                if max_per_group <= 0:
                    max_per_group = 4
                if cookies and ids:
                    accounts.append({"mode":"cookie","cookies":cookies,"ids":ids,"max_per_group":max_per_group,"runtime_label":f"CK节点{cookie_seq}"})
                    cookie_seq += 1
        else:
            cookies = (cfg.get("cookies") or "").strip()
            ids_raw = (cfg.get("ids") or "").replace("\r", "\n")
            ids = [x.strip() for x in ids_raw.split("\n") if x.strip()]
            try:
                max_per_group = int(cfg.get("max_per_group", 4) or 4)
            except Exception:
                max_per_group = 4
            if max_per_group <= 0:
                max_per_group = 4
            if cookies and ids:
                accounts.append({"mode":"cookie","cookies":cookies,"ids":ids,"max_per_group":max_per_group,"runtime_label":f"CK节点{cookie_seq}"})
                cookie_seq += 1

    # 2) accounts_db.json（at/team_id/access_token）
    db = load_accounts_db()
    db_list = db.get("accounts", []) if isinstance(db, dict) else []

    fallback_cookies = ""
    for a in accounts:
        if a.get("mode") == "cookie" and a.get("cookies"):
            fallback_cookies = a["cookies"]
            break

    at_seq = 1
    for item in db_list:
        if not isinstance(item, dict):
            continue
        if (item.get("mode") or "at").strip().lower() != "at":
            continue
        if not bool(item.get("enabled", True)):
            continue
        team_id = (item.get("team_id") or "").strip()
        if not team_id:
            continue
        access_token = (item.get("access_token") or "").strip()
        cookies = (item.get("cookies") or "").strip() or fallback_cookies
        if not access_token and not cookies:
            continue
        try:
            max_per_group = int(item.get("max_per_group", 4) or 4)
        except Exception:
            max_per_group = 4
        if max_per_group <= 0:
            max_per_group = 4
        accounts.append({
            "mode": "at",
            "cookies": cookies,
            "ids": [team_id],
            "team_id": team_id,
            "access_token": access_token,
            "email": (item.get("email") or "").strip(),
            "max_per_group": max_per_group,
            "sync_status": (item.get("sync_status") or "").strip(),
            "current_members": int(item.get("current_members", 1) or 1),
            "joined_count": int(item.get("joined_count", 1) or 1),
            "invited_count": int(item.get("invited_count", 0) or 0),
            "runtime_label": f"AT节点{at_seq}",
        })
        at_seq += 1

    return accounts

    # 新结构：{"accounts":[{ cookies, ids, max_per_group }...]}
    if isinstance(cfg, dict) and "accounts" in cfg:
        for item in cfg.get("accounts", []):
            if not isinstance(item, dict):
                continue
            cookies = (item.get("cookies") or "").strip()
            ids_raw = (item.get("ids") or "").replace("\r", "\n")
            ids = [x.strip() for x in ids_raw.split("\n") if x.strip()]
            try:
                max_per_group = int(item.get("max_per_group", 4) or 4)
            except Exception:
                max_per_group = 4
            if max_per_group <= 0:
                max_per_group = 4

            if cookies and ids:
                accounts.append(
                    {
                        "cookies": cookies,
                        "ids": ids,
                        "max_per_group": max_per_group,
                    }
                )
    else:
        # 兼容老版本：直接 cookies / ids / max_per_group
        cookies = (cfg.get("cookies") or "").strip()
        ids_raw = (cfg.get("ids") or "").replace("\r", "\n")
        ids = [x.strip() for x in ids_raw.split("\n") if x.strip()]
        try:
            max_per_group = int(cfg.get("max_per_group", 4) or 4)
        except Exception:
            max_per_group = 4
        if max_per_group <= 0:
            max_per_group = 4

        if cookies and ids:
            accounts.append(
                {
                    "cookies": cookies,
                    "ids": ids,
                    "max_per_group": max_per_group,
                }
            )

    return accounts


def load_queue():
    """
    读取当前队列（仅读，不修改），带锁，避免读到半截。
    """
    if not os.path.exists(QUEUE_FILE):
        return []
    with locked_open(QUEUE_FILE, "r") as f:
        ordered = []
        seen = set()
        for line in f:
            email = line.strip()
            if not email:
                continue
            key = email.lower()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(email)
        return ordered


def remove_from_queue(emails):
    """
    安全地从 queue.txt 中删除指定邮箱列表：
    - 上锁
    - 重新读取最新的 queue.txt
    - 删除成功的邮箱
    - 覆盖写回
    这样不会把新追加进来的邮箱覆盖掉。
    """
    if not emails:
        return

    if not os.path.exists(QUEUE_FILE):
        return

    remove_set = {str(email).strip().lower() for email in emails if str(email).strip()}

    with locked_open(QUEUE_FILE, "r+") as f:
        lines = [l.strip() for l in f if l.strip()]
        remaining = [x for x in lines if x.strip().lower() not in remove_set]

        f.seek(0)
        f.truncate()

        if remaining:
            f.write("\n".join(remaining) + "\n")
        else:
            # 写空文件
            f.write("")


def load_history_entries():
    """
    读取 history.txt
    兼容两种格式：
    - 旧格式：email \t account_index \t group_index
    - 新格式：email \t account_index \t group_index \t group_key \t mode
    """
    entries = []
    if not os.path.exists(HISTORY_FILE):
        return entries
    with locked_open(HISTORY_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            email = parts[0]
            try:
                acc_idx = int(parts[1]) if len(parts) >= 2 else 0
            except Exception:
                acc_idx = 0
            try:
                group_idx = int(parts[2]) if len(parts) >= 3 else 0
            except Exception:
                group_idx = 0
            entries.append(
                {
                    "email": email,
                    "account_index": acc_idx,
                    "group_index": group_idx,
                    "group_key": parts[3].strip() if len(parts) >= 4 else "",
                    "mode": parts[4].strip() if len(parts) >= 5 else "",
                }
            )
    return entries


def build_group_key(account, target_id, group_index):
    mode = str((account or {}).get("mode") or "cookie").strip().lower()
    if mode == "at":
        team_id = str((account or {}).get("team_id") or target_id or "").strip()
        return f"at:{team_id}" if team_id else f"at-index:{group_index}"
    stable_id = str(target_id or "").strip()
    return f"ck:{stable_id}" if stable_id else f"ck-index:{group_index}"


def append_history(email, account_index, group_index, account=None, target_id=""):
    """
    记录成功邀请：
    - history.txt：给程序自己算组数用（新格式会追加稳定组标识）
    - invite_log.txt：给你人工查看（带北京时间 + 母号 + 组号）
    """
    mode = str((account or {}).get("mode") or "cookie").strip().lower()
    group_key = build_group_key(account, target_id, group_index)

    # 程序用
    with locked_open(HISTORY_FILE, "a") as f:
        f.write(f"{email}\t{account_index}\t{group_index}\t{group_key}\t{mode}\n")

    append_invite_status_record(
        email=email,
        label=f"母号{account_index + 1}-组{group_index + 1}",
        status="成功",
        group_key=group_key,
        mode=mode,
    )


# ---------------- API 邀请辅助 ----------------


def parse_cookie_list(cookie_data):
    try:
        cookies = json.loads(cookie_data) if cookie_data.strip().startswith("[") else []
    except Exception:
        cookies = []
    return cookies if isinstance(cookies, list) else []


def create_chatgpt_session(cookie_data, target_uuid=None):
    proxy = get_chatgpt_proxy()
    if CurlSession is not None:
        session = CurlSession(
            impersonate="chrome110",
            proxies={"http": proxy, "https": proxy} if proxy else None,
            timeout=30,
            verify=False if proxy else True,
        )
    elif cloudscraper is not None:
        session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        if proxy:
            session.proxies.update({"http": proxy, "https": proxy})
    else:
        session = requests.Session()
        if proxy:
            session.proxies.update({"http": proxy, "https": proxy})
    session.headers.update(
        {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": f"{CHATGPT_BASE_URL}/",
            "Origin": CHATGPT_BASE_URL,
        }
    )

    has_account_cookie = False
    for cookie in parse_cookie_list(cookie_data):
        name = cookie.get("name")
        value = cookie.get("value")
        if not name or value is None:
            continue
        if name == "_account":
            has_account_cookie = True
        session.cookies.set(
            name,
            value,
            domain=cookie.get("domain") or ".chatgpt.com",
            path=cookie.get("path") or "/",
        )

    if target_uuid and not has_account_cookie:
        session.cookies.set("_account", target_uuid, domain=".chatgpt.com", path="/")

    return session


def get_api_access_token(session, preset_token=""):
    preset_token = (preset_token or "").strip()
    if preset_token:
        return preset_token
    try:
        resp = session.get(f"{CHATGPT_BASE_URL}/api/auth/session", timeout=20)
    except Exception as e:
        log(f"⚠️ 获取 access token 失败: {e}", level="ERROR")
        return ""

    if resp.status_code != 200:
        log(f"⚠️ /api/auth/session 返回 HTTP {resp.status_code}", level="ERROR")
        return ""

    try:
        data = resp.json()
    except Exception as e:
        log(f"⚠️ 解析 access token 响应失败: {e}", level="ERROR")
        return ""

    token = (data or {}).get("accessToken", "") or ""
    if not token:
        log("⚠️ 会话没有返回 accessToken，Cookie 可能已经过期", level="ERROR")
    return token


def normalize_accounts_payload(data):
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    for key in ("accounts", "items", "data"):
        value = data.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return list(value.values())

    return [data]


def parse_account_entry(item):
    account = item.get("account", {}) if isinstance(item, dict) else {}
    top = item if isinstance(item, dict) else {}
    name = (account.get("name") or top.get("name") or "").strip()
    structure = (account.get("structure") or top.get("structure") or "").strip().lower()
    account_type = (account.get("account_type") or top.get("account_type") or "").strip().lower()
    org_id = (
        account.get("account_id")
        or account.get("id")
        or top.get("account_id")
        or top.get("id")
        or ""
    ).strip()
    workspace_id = (
        top.get("account_user_id")
        or account.get("account_user_id")
        or top.get("workspace_id")
        or account.get("workspace_id")
        or ""
    ).strip()
    is_personal = (structure == "personal") or ("personal" in account_type) or ("个人" in name)
    return {
        "name": name,
        "org_id": org_id,
        "workspace_id": workspace_id,
        "is_personal": is_personal,
    }


def resolve_candidate_account_ids(session, token, target_uuid, mode="cookie", team_id=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Referer": f"{CHATGPT_BASE_URL}/",
        "Origin": CHATGPT_BASE_URL,
        "User-Agent": DEFAULT_USER_AGENT,
    }

    desired = (team_id if mode == "at" else target_uuid or "").strip()

    try:
        resp = session.get(f"{CHATGPT_BASE_URL}/backend-api/accounts", headers=headers, timeout=20)
    except Exception as e:
        log(f"⚠️ 获取工作区列表失败: {e}", level="ERROR")
        return [desired] if desired else []

    if resp.status_code != 200:
        log(f"⚠️ /backend-api/accounts 返回 HTTP {resp.status_code}", level="ERROR")
        return [desired] if desired else []

    try:
        items = normalize_accounts_payload(resp.json())
    except Exception as e:
        log(f"⚠️ 解析工作区列表失败: {e}", level="ERROR")
        return [desired] if desired else []

    parsed = [parse_account_entry(item) for item in items]
    chosen = None
    if desired:
        for item in parsed:
            if desired in [item["workspace_id"], item["org_id"]]:
                chosen = item
                break

    if not chosen:
        for item in parsed:
            if not item["is_personal"] and (item["workspace_id"] or item["org_id"]):
                chosen = item
                break

    if not chosen and parsed:
        chosen = parsed[0]

    candidate_ids = []
    if chosen:
        if chosen.get("workspace_id"):
            candidate_ids.append(chosen["workspace_id"])
        if chosen.get("org_id") and chosen["org_id"] not in candidate_ids:
            candidate_ids.append(chosen["org_id"])
        log(
            f"🔎 选中工作区: {chosen.get('name') or 'Unknown'} "
            f"(workspace={chosen.get('workspace_id') or '-'}, org={chosen.get('org_id') or '-'})"
        )

    if desired and desired not in candidate_ids:
        candidate_ids.append(desired)

    return candidate_ids


def extract_invite_results(data):
    success = []
    failed = []
    account_invites = []
    errored_emails = []

    if isinstance(data, dict):
        account_invites = data.get("account_invites") or data.get("invites") or []
        errored_emails = data.get("errored_emails") or data.get("errors") or []

    if isinstance(account_invites, list):
        for item in account_invites:
            if isinstance(item, dict):
                email = (
                    item.get("email_address")
                    or item.get("email")
                    or item.get("address")
                    or ""
                ).strip()
            else:
                email = str(item).strip()
            if email:
                success.append(email)

    if isinstance(errored_emails, list):
        for item in errored_emails:
            if isinstance(item, dict):
                email = (
                    item.get("email")
                    or item.get("email_address")
                    or item.get("address")
                    or ""
                ).strip()
                error = (
                    item.get("error")
                    or item.get("message")
                    or item.get("detail")
                    or json.dumps(item, ensure_ascii=False)
                )
            else:
                email = ""
                error = str(item)
            failed.append({"email": email, "error": error})

    return success, failed


def is_terminal_invite_error(error_text):
    text = (error_text or "").lower()
    terminal_markers = [
        "already invited",
        "already a member",
        "already member",
        "member already exists",
        "already exists",
        "user is already",
        "duplicate",
        "pending invite",
        "already on team",
    ]
    return any(marker in text for marker in terminal_markers)



def fetch_account_items(session, token, account_id, endpoint):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Referer": f"{CHATGPT_BASE_URL}/",
        "Origin": CHATGPT_BASE_URL,
        "User-Agent": DEFAULT_USER_AGENT,
        "chatgpt-account-id": account_id,
    }
    url = f"{CHATGPT_BASE_URL}/backend-api/accounts/{account_id}/{endpoint}"
    if endpoint in ("users", "invites"):
        url += "?limit=100&offset=0"

    resp = session.get(url, headers=headers, timeout=30)
    if resp.status_code != 200:
        return []
    try:
        data = resp.json()
    except Exception:
        return []
    return data.get("items", []) if isinstance(data, dict) else []


def has_email_in_account(session, token, account_id, email):
    email_key = str(email or "").strip().lower()
    if not email_key:
        return False

    members = fetch_account_items(session, token, account_id, "users")
    for item in members:
        member_email = str(item.get("email") or "").strip().lower()
        if member_email == email_key:
            return True

    invites = fetch_account_items(session, token, account_id, "invites")
    for item in invites:
        invite_email = str(item.get("email_address") or item.get("email") or "").strip().lower()
        if invite_email == email_key:
            return True

    return False


def email_already_in_target(account, target_uuid, email):
    email_key = str(email or "").strip()
    if not email_key:
        return False

    session = create_chatgpt_session((account or {}).get("cookies", "") or "", target_uuid=target_uuid)
    token = get_api_access_token(session, preset_token=(account or {}).get("access_token", "") or "")
    if not token:
        return False

    candidate_ids = resolve_candidate_account_ids(
        session,
        token,
        target_uuid,
        mode=(account or {}).get("mode", "cookie"),
        team_id=(account or {}).get("team_id"),
    )
    if not candidate_ids:
        return False

    return has_email_in_account(session, token, candidate_ids[0], email_key)


def verify_invited_emails(session, token, account_id, expected_emails, attempts=3, sleep_seconds=5):
    expected = {email.lower(): email for email in expected_emails}
    verified = set()

    for attempt in range(attempts):
        members = fetch_account_items(session, token, account_id, "users")
        invites = fetch_account_items(session, token, account_id, "invites")

        seen = set()
        for item in members:
            email = (item.get("email") or "").strip().lower()
            if email:
                seen.add(email)
        for item in invites:
            email = (item.get("email_address") or item.get("email") or "").strip().lower()
            if email:
                seen.add(email)

        for email_lower in expected:
            if email_lower in seen:
                verified.add(expected[email_lower])

        if len(verified) == len(expected):
            break

        if attempt < attempts - 1:
            time.sleep(sleep_seconds)

    missing = [original for lower, original in expected.items() if original not in verified]
    return sorted(verified), missing


def run_one_session_api(target_uuid, email_batch, cookie_data, mode="cookie", team_id=None, access_token=""):
    result = {"success": [], "terminal": [], "terminal_details": [], "failed": []}
    if not email_batch:
        return result

    log_prefix = f"🔗 [...{(target_uuid or team_id or 'unknown')[-6:]}]"
    session = create_chatgpt_session(cookie_data or "", target_uuid=target_uuid)
    token = get_api_access_token(session, preset_token=access_token)
    if not token:
        result["failed"] = [{"email": email, "error": "Missing access token", "verify": True} for email in email_batch]
        return result

    candidate_ids = resolve_candidate_account_ids(session, token, target_uuid, mode=mode, team_id=team_id)
    if not candidate_ids:
        result["failed"] = [{"email": email, "error": "No workspace/account id found", "verify": True} for email in email_batch]
        return result

    def uniq_emails(items):
        seen = set()
        ordered = []
        for email in items or []:
            email = str(email or "").strip()
            if email and email not in seen:
                seen.add(email)
                ordered.append(email)
        return ordered

    def uniq_failures(items):
        seen = set()
        ordered = []
        for item in items or []:
            email = str(item.get("email", "") or "").strip()
            error = str(item.get("error", "") or "").strip()
            verify = bool(item.get("verify", True))
            key = (email, error, verify)
            if key in seen:
                continue
            seen.add(key)
            ordered.append({"email": email, "error": error, "verify": verify})
        return ordered

    def extract_invalid_email_failures(body, batch):
        errors = body
        if isinstance(body, dict):
            errors = body.get("detail") or body.get("errors") or body.get("message") or []
        if not isinstance(errors, list):
            return []
        invalid = []
        for item in errors:
            if not isinstance(item, dict):
                continue
            loc = item.get("loc") or []
            if len(loc) >= 3 and str(loc[0]) == "body" and str(loc[1]) == "email_addresses":
                try:
                    idx = int(loc[2])
                except Exception:
                    continue
                if idx < 0 or idx >= len(batch):
                    continue
                invalid.append({
                    "email": str(batch[idx] or "").strip(),
                    "error": str(item.get("msg") or item.get("reason") or "invalid email").strip(),
                    "verify": False,
                })
        return uniq_failures(invalid)

    def submit_invites(candidate_id, batch):
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": f"{CHATGPT_BASE_URL}/",
            "Origin": CHATGPT_BASE_URL,
            "User-Agent": DEFAULT_USER_AGENT,
            "chatgpt-account-id": candidate_id,
        }
        try:
            resp = session.post(
                f"{CHATGPT_BASE_URL}/backend-api/accounts/{candidate_id}/invites",
                headers=headers,
                json={
                    "email_addresses": batch,
                    "role": "standard-user",
                    "resend_emails": False,
                },
                timeout=30,
            )
        except Exception as e:
            log(f"{log_prefix} API 请求异常: {e}", level="ERROR")
            return None, [], [], [{"email": email, "error": str(e), "verify": True} for email in batch]

        body = None
        try:
            body = resp.json()
        except Exception:
            body = None

        if resp.status_code not in (200, 201):
            detail = ""
            if isinstance(body, (dict, list)):
                try:
                    detail = json.dumps(body, ensure_ascii=False)
                except Exception:
                    detail = str(body)
            elif body:
                detail = str(body)
            log(f"{log_prefix} API 邀请失败，HTTP {resp.status_code}" + (f", {detail}" if detail else ""), level="ERROR")
            invalid_terminal = extract_invalid_email_failures(body, batch) if resp.status_code == 422 else []
            invalid_emails = {item.get("email", "") for item in invalid_terminal}
            retry_items = [
                {"email": email, "error": f"HTTP {resp.status_code}" + (f": {detail}" if detail else ""), "verify": True}
                for email in batch
                if email not in invalid_emails
            ]
            return None, [item.get("email", "") for item in invalid_terminal], invalid_terminal, uniq_failures(retry_items)

        success, failed = extract_invite_results(body)
        success = uniq_emails(success)
        success_set = set(success)
        terminal_details = []
        retryable = []
        for item in failed:
            email = str(item.get("email", "") or "").strip()
            error = str(item.get("error", "") or "").strip()
            if email and is_terminal_invite_error(error):
                terminal_details.append({"email": email, "error": error, "verify": True})
            else:
                retryable.append({"email": email, "error": error, "verify": True})

        terminal_set = {item.get("email", "") for item in terminal_details}
        known_retryable = {item.get("email", "") for item in retryable}
        for email in batch:
            if email not in success_set and email not in terminal_set and email not in known_retryable:
                retryable.append({"email": email, "error": "Invite result unclear", "verify": True})

        verification_targets = uniq_emails(success + [item.get("email", "") for item in terminal_details if item.get("verify", True)])
        if verification_targets:
            verified, ghost = verify_invited_emails(session, token, candidate_id, verification_targets)
            verified_set = set(verified)
            success = [email for email in success if email in verified_set]
            terminal_details = [item for item in terminal_details if (not item.get("verify", True)) or item.get("email", "") in verified_set]
            for email in ghost:
                retryable.append({
                    "email": email,
                    "error": "ghost_success: API returned success but members/invites did not contain the email",
                    "verify": True,
                })

        terminal = uniq_emails([item.get("email", "") for item in terminal_details])
        return uniq_emails(success), terminal, uniq_failures(terminal_details), uniq_failures(retryable)

    pending_batch = uniq_emails(email_batch)
    last_failures = []
    last_terminals = []
    last_terminal_details = []

    for candidate_id in candidate_ids:
        if not pending_batch:
            break

        log(f"{log_prefix} API 准备邀请 {len(pending_batch)} 个邮箱 -> 工作区 {candidate_id} | {summarize_emails(pending_batch)}")
        success, terminal, terminal_details, retryable = submit_invites(candidate_id, pending_batch)

        if success is None:
            last_terminals = uniq_emails(last_terminals + (terminal or []))
            last_terminal_details = uniq_failures(last_terminal_details + (terminal_details or []))
            last_failures = uniq_failures(last_failures + (retryable or []))
            pending_batch = uniq_emails([item.get("email", "") for item in (retryable or [])])
            continue

        ghost_emails = uniq_emails([item.get("email", "") for item in retryable if str(item.get("error", "")).startswith("ghost_success:")])
        retryable = [item for item in retryable if not str(item.get("error", "")).startswith("ghost_success:")]

        if ghost_emails:
            log(f"{log_prefix} 检测到 {len(ghost_emails)} 个假成功，立即补发一次。", level="WARNING")
            retry_success, retry_terminal, retry_terminal_details, retry_failed = submit_invites(candidate_id, ghost_emails)
            if retry_success is not None:
                success = uniq_emails(success + retry_success)
                terminal = uniq_emails((terminal or []) + (retry_terminal or []))
                terminal_details = uniq_failures((terminal_details or []) + (retry_terminal_details or []))
                for item in retry_failed or []:
                    if str(item.get("error", "")).startswith("ghost_success:"):
                        item = dict(item)
                        item["error"] = "ghost_success_after_retry: API returned success twice but members/invites still did not contain the email"
                    retryable.append(item)
            else:
                terminal = uniq_emails((terminal or []) + (retry_terminal or []))
                terminal_details = uniq_failures((terminal_details or []) + (retry_terminal_details or []))
                retryable.extend(retry_failed or [])

        result["success"] = uniq_emails(success)
        result["terminal"] = uniq_emails(last_terminals + (terminal or []))
        result["terminal_details"] = uniq_failures(last_terminal_details + (terminal_details or []))
        result["failed"] = uniq_failures(retryable)
        log(
            f"{log_prefix} API 结果 success={len(result['success'])} terminal={len(result['terminal'])} retry={len(result['failed'])} | "
            f"success: {summarize_emails(result['success'])} | terminal: {summarize_emails(result['terminal'])} | "
            f"retry: {summarize_emails([item.get('email', '') for item in result['failed']])}"
        )
        if result["success"] or result["terminal"] or not result["failed"]:
            return result

        last_failures = uniq_failures(last_failures + result["failed"])
        last_terminals = result["terminal"]
        last_terminal_details = result["terminal_details"]
        pending_batch = uniq_emails([item.get("email", "") for item in result["failed"]])

    result["terminal"] = uniq_emails(last_terminals)
    result["terminal_details"] = uniq_failures(last_terminal_details)
    result["failed"] = last_failures or [{"email": email, "error": "API invite failed", "verify": True} for email in email_batch]
    return result


def run_one_session_browser_ui(target_uuid, email_batch, cookie_data, mode='cookie', team_id=None):
    """
    老的页面点击邀请流程，保留做兜底，不再作为默认主路径。
    """
    log_prefix = f"🎯 [...{target_uuid[-6:]}]"
    log(f"{log_prefix} 启动 UI 兜底会话，目标 {len(email_batch)} 人")

    display = None
    driver = None
    success_emails = []

    if not email_batch:
        return success_emails

    try:
        display = Display(visible=0, size=(1600, 900))
        display.start()

        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1600,900")
        options.add_argument("--lang=en-US")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-background-networking")
        options.add_argument("--blink-settings=imagesEnabled=false")

        driver = uc.Chrome(options=options)
        driver.set_page_load_timeout(60)

        clist = parse_cookie_list(cookie_data)
        driver.get("https://chatgpt.com/404")
        for c in clist:
            if c.get("name") == "_account":
                continue
            c_dict = {k: v for k, v in c.items() if k in ["name", "value", "domain", "path"]}
            if "domain" not in c_dict:
                c_dict["domain"] = ".chatgpt.com"
            try:
                driver.add_cookie(c_dict)
            except Exception:
                pass

        driver.get("https://chatgpt.com/")
        time.sleep(2)
        if "Just a moment" in driver.title:
            end = time.time() + 20
            while "Just a moment" in driver.title and time.time() < end:
                time.sleep(1)

        if mode == 'cookie':
            try:
                driver.add_cookie({'name':'_account','value':target_uuid,'domain':'chatgpt.com','path':'/','secure':False})
            except Exception:
                pass
            driver.get('https://chatgpt.com/admin/members?tab=members')
        else:
            if not team_id:
                return success_emails
            driver.get(f"https://chatgpt.com/admin/members?tab=members&at={team_id}")

        xpath_invite = (
            "//button[contains(., 'Invite') or contains(., 'Add member') or contains(., '邀请')]"
        )
        WebDriverWait(driver, 25).until(EC.element_to_be_clickable((By.XPATH, xpath_invite)))

        for email in email_batch:
            try:
                driver.find_element(By.XPATH, xpath_invite).click()
                inp = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
                )
                inp.clear()
                inp.send_keys(email)
                time.sleep(0.5)
                inp.send_keys(Keys.ENTER)
                for btn in driver.find_elements(
                    By.XPATH,
                    "//button[contains(., 'Send') or contains(., 'Invite') or contains(., '发送')]",
                ):
                    if btn.is_displayed() and btn.is_enabled():
                        btn.click()
                        success_emails.append(email)
                        break
                time.sleep(4)
            except Exception as e:
                log(f"{log_prefix} UI 兜底失败: {email} / {str(e)[:80]}", level="ERROR")
                driver.refresh()
                time.sleep(2)

        return success_emails
    except Exception as e:
        log(f"{log_prefix} UI 兜底异常: {e}", level="ERROR")
        return success_emails
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass
        try:
            if display:
                display.stop()
        except Exception:
            pass


def run_one_session_browser(target_uuid, email_batch, cookie_data, mode='cookie', team_id=None):
    result = {"success": [], "terminal": [], "failed": []}
    if not email_batch:
        return result

    log_prefix = f"🚀 [...{(target_uuid or team_id or 'unknown')[-6:]}]"
    display = None
    driver = None

    try:
        display = Display(visible=0, size=(1280, 800))
        display.start()

        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1280,800")
        options.add_argument("--lang=en-US")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-background-networking")
        options.add_argument("--blink-settings=imagesEnabled=false")

        driver = uc.Chrome(options=options)
        driver.set_page_load_timeout(60)

        driver.get("https://chatgpt.com/404")
        for cookie in parse_cookie_list(cookie_data):
            if cookie.get("name") == "_account":
                continue
            cookie_dict = {k: v for k, v in cookie.items() if k in ["name", "value", "domain", "path"]}
            if "domain" not in cookie_dict:
                cookie_dict["domain"] = ".chatgpt.com"
            try:
                driver.add_cookie(cookie_dict)
            except Exception:
                pass

        if mode == "cookie":
            try:
                driver.add_cookie(
                    {"name": "_account", "value": target_uuid, "domain": "chatgpt.com", "path": "/", "secure": False}
                )
            except Exception as e:
                log(f"{log_prefix} 设置 _account 失败: {e}", level="ERROR")

        log(f"{log_prefix} 打开 ChatGPT 首页准备浏览器内 API 邀请...")
        driver.get("https://chatgpt.com/")
        time.sleep(2)

        if "Just a moment" in driver.title:
            log(f"{log_prefix} 遇到盾，等待放行...")
            end = time.time() + 20
            while "Just a moment" in driver.title and time.time() < end:
                time.sleep(1)

        browser_result = driver.execute_async_script(
            """
            const done = arguments[0];
            const desiredId = arguments[1];
            const emails = arguments[2];
            const mode = arguments[3];
            const teamId = arguments[4];

            (async () => {
              const base = "https://chatgpt.com";
              const baseHeaders = {
                "Accept": "application/json",
                "Content-Type": "application/json"
              };

              const sessionRes = await fetch(base + "/api/auth/session", {
                method: "GET",
                credentials: "include",
                headers: { "Accept": "application/json" }
              });
              const sessionText = await sessionRes.text();
              let sessionData = {};
              try { sessionData = JSON.parse(sessionText); } catch (_) {}
              const token = sessionData.accessToken || "";
              if (!token) {
                done({ok: false, stage: "session", status: sessionRes.status, body: sessionText.slice(0, 500)});
                return;
              }

              const accountRes = await fetch(base + "/backend-api/accounts", {
                method: "GET",
                credentials: "include",
                headers: {
                  "Accept": "application/json",
                  "Authorization": "Bearer " + token
                }
              });
              const accountText = await accountRes.text();
              let accountData = {};
              try { accountData = JSON.parse(accountText); } catch (_) {}
              if (accountRes.status !== 200) {
                done({ok: false, stage: "accounts", status: accountRes.status, body: accountText.slice(0, 500)});
                return;
              }

              const rawAccounts = Array.isArray(accountData)
                ? accountData
                : Array.isArray(accountData.accounts)
                  ? accountData.accounts
                  : accountData.accounts && typeof accountData.accounts === "object"
                    ? Object.values(accountData.accounts)
                    : Array.isArray(accountData.items)
                      ? accountData.items
                      : Array.isArray(accountData.data)
                        ? accountData.data
                        : [accountData];

              const parsed = rawAccounts.map((item) => {
                const account = item && typeof item === "object" ? (item.account || {}) : {};
                const top = item && typeof item === "object" ? item : {};
                const name = (account.name || top.name || "").trim();
                const structure = (account.structure || top.structure || "").toLowerCase();
                const accountType = (account.account_type || top.account_type || "").toLowerCase();
                const orgId = (account.account_id || account.id || top.account_id || top.id || "").trim();
                const workspaceId = (top.account_user_id || account.account_user_id || top.workspace_id || account.workspace_id || "").trim();
                const isPersonal = structure === "personal" || accountType.includes("personal") || name.includes("个人");
                return {name, orgId, workspaceId, isPersonal};
              });

              const wanted = (mode === "at" ? teamId : desiredId || "").trim();
              let chosen = null;
              if (wanted) {
                chosen = parsed.find((item) => [item.workspaceId, item.orgId].includes(wanted)) || null;
              }
              if (!chosen) {
                chosen = parsed.find((item) => !item.isPersonal && (item.workspaceId || item.orgId)) || null;
              }
              if (!chosen && parsed.length) {
                chosen = parsed[0];
              }

              const candidateIds = [];
              if (chosen) {
                if (chosen.workspaceId) candidateIds.push(chosen.workspaceId);
                if (chosen.orgId && !candidateIds.includes(chosen.orgId)) candidateIds.push(chosen.orgId);
              }
              if (wanted && !candidateIds.includes(wanted)) {
                candidateIds.push(wanted);
              }

              if (!candidateIds.length) {
                done({ok: false, stage: "resolve", body: "No candidate account ids"});
                return;
              }

              let lastFailure = null;
              for (const candidateId of candidateIds) {
                const inviteRes = await fetch(base + `/backend-api/accounts/${candidateId}/invites`, {
                  method: "POST",
                  credentials: "include",
                  headers: {
                    ...baseHeaders,
                    "Accept": "application/json",
                    "Authorization": "Bearer " + token,
                    "chatgpt-account-id": candidateId
                  },
                  body: JSON.stringify({
                    email_addresses: emails,
                    role: "standard-user",
                    resend_emails: false
                  })
                });
                const inviteText = await inviteRes.text();
                let inviteData = {};
                try { inviteData = JSON.parse(inviteText); } catch (_) {}
                if (inviteRes.status === 200 || inviteRes.status === 201) {
                  done({
                    ok: true,
                    stage: "invite",
                    status: inviteRes.status,
                    candidateId,
                    body: inviteData
                  });
                  return;
                }
                lastFailure = {
                  ok: false,
                  stage: "invite",
                  status: inviteRes.status,
                  candidateId,
                  body: inviteData && Object.keys(inviteData).length ? inviteData : inviteText.slice(0, 500)
                };
              }

              done(lastFailure || {ok: false, stage: "invite", body: "Unknown failure"});
            })().catch((error) => {
              done({ok: false, stage: "runtime", body: String(error)});
            });
            """,
            target_uuid,
            email_batch,
            mode,
            team_id,
        )

        if not browser_result.get("ok"):
            error_text = (
                f"{browser_result.get('stage') or 'unknown'} "
                f"HTTP {browser_result.get('status') or '-'} "
                f"{browser_result.get('body')}"
            )
            result["failed"] = [{"email": email, "error": error_text} for email in email_batch]
            log(f"{log_prefix} 浏览器内 API 邀请失败: {error_text}", level="ERROR")
            return result

        body = browser_result.get("body") or {}
        success, failed = extract_invite_results(body if isinstance(body, dict) else {})
        success_set = set(success)
        terminal = []
        retryable = []
        for item in failed:
            email = item.get("email", "")
            if email and is_terminal_invite_error(item.get("error", "")):
                terminal.append(email)
            else:
                retryable.append(item)

        terminal_set = set(terminal)
        for email in email_batch:
            if email not in success_set and email not in terminal_set:
                if not any(entry.get("email") == email for entry in retryable):
                    retryable.append({"email": email, "error": "Invite result unclear"})

        result["success"] = success
        result["terminal"] = terminal
        result["failed"] = retryable
        log(
            f"{log_prefix} 浏览器内 API 返回 success={len(success)} terminal={len(terminal)} retry={len(retryable)}"
        )
        return result

    except Exception as e:
        result["failed"] = [{"email": email, "error": str(e)} for email in email_batch]
        log(f"{log_prefix} 浏览器内 API 异常: {e}", level="ERROR")
        return result
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass
        try:
            if display:
                display.stop()
        except Exception:
            pass


def run_one_session(target_uuid, email_batch, cookie_data, mode='cookie', team_id=None, access_token=""):
    if not email_batch:
        return {"success": [], "terminal": [], "failed": []}

    result = run_one_session_api(
        target_uuid,
        email_batch,
        cookie_data,
        mode=mode,
        team_id=team_id,
        access_token=access_token,
    )

    if result["success"] or result["terminal"]:
        return result

    if access_token and not cookie_data:
        return result

    if os.getenv("INVITE_ALLOW_UI_FALLBACK", "1") != "1":
        return result

    log("⚠️ API 没有确认成功，准备尝试 UI 兜底邀请。", level="WARNING")
    success_emails = run_one_session_browser_ui(
        target_uuid,
        email_batch,
        cookie_data,
        mode=mode,
        team_id=team_id,
    )
    return {
        "success": success_emails,
        "terminal": [],
        "failed": [],
    }


# ---------------- 主循环 ----------------

if __name__ == "__main__":
    log("🔥 多母号机器人启动...")

    # 单实例锁，防止误启动多个 worker 进程
    singleton_lock = None
    try:
        singleton_lock = open(WORKER_LOCK_FILE, "w", encoding="utf-8")
        fcntl.flock(singleton_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        singleton_lock.write(str(os.getpid()))
        singleton_lock.flush()
    except OSError:
        log("❌ 检测到已有一个 worker.py 在运行，本进程自动退出。", level="ERROR")
        sys.exit(1)

    # 确保队列 / 历史文件存在
    if not os.path.exists(QUEUE_FILE):
        open(QUEUE_FILE, "w", encoding="utf-8").close()
    if not os.path.exists(HISTORY_FILE):
        open(HISTORY_FILE, "w", encoding="utf-8").close()

    try:
        while True:
            try:
                accounts = parse_accounts()
                if not accounts:
                    log("⚠️ 未配置任何母号，请先在控制台填写 Cookie 和 UUID。")
                    time.sleep(10)
                    continue

                queue = load_queue()
                if queue:
                    invalid_queue_entries = extract_invalid_email_entries(queue)
                    if invalid_queue_entries:
                        invalid_removed = []
                        for item in invalid_queue_entries:
                            email = str(item.get("email", "") or "").strip()
                            reason = str(item.get("reason", "") or "非法邮箱").strip()
                            if not email:
                                continue
                            invalid_removed.append(email)
                            append_invalid_email_record(email, reason, source="队列预检")
                            append_invite_status_record(
                                email=email,
                                label="队列预检",
                                status="失败",
                                reason=reason,
                                mode="queue_validation",
                            )
                        if invalid_removed:
                            remove_from_queue(invalid_removed)
                            log(
                                f"⚠️ 队列预检移除了 {len(invalid_removed)} 个非法邮箱 | {summarize_emails(invalid_removed)}",
                                level="WARNING",
                            )
                            queue = load_queue()
                if not queue:
                    time.sleep(5)
                    continue
                queue_head_email = str(queue[0] or "").strip()

                history_entries = load_history_entries()
                at_fail_state = load_at_fail_state()

                # 统计每个组已用多少个座位
                # - CK：优先按稳定 group_id 统计，兼容老 history 的索引格式
                # - AT：按同步回来的官方成员/待邀请数统计，不再受旧索引 history 干扰
                legacy_used_per_group = {}
                stable_used_per_group = {}

                for h in history_entries:
                    group_key = str(h.get("group_key") or "").strip()
                    if group_key:
                        stable_used_per_group[group_key] = stable_used_per_group.get(group_key, 0) + 1
                    else:
                        key = (h["account_index"], h["group_index"])
                        legacy_used_per_group[key] = legacy_used_per_group.get(key, 0) + 1

                # 选出下一个要用的母号 & 组
                chosen_acc_index = None
                chosen_group_index = None
                capacity = 0
                duplicate_skip_cache = {}
                skipped_available_at_groups = []

                for acc_index, acc in enumerate(accounts):
                    max_per_group = acc.get("max_per_group", 4) or 4
                    if max_per_group <= 0:
                        max_per_group = 4
                    if acc.get("mode") == "at":
                        team_id = get_at_fail_key(acc)
                        fail_meta = normalize_at_fail_meta(at_fail_state.get(team_id))
                        sync_used = int(acc.get("joined_count", 0) or 0) + int(acc.get("invited_count", 0) or 0)
                        current_members = int(acc.get("current_members", 0) or 0)
                        used = max(sync_used, current_members, 1)
                        group_index = 0
                        if group_index >= len(acc["ids"]):
                            continue
                        capacity_left = max(max_per_group - used, 0)
                        if capacity_left <= 0:
                            continue
                        if fail_meta.get("skip_marked"):
                            skipped_available_at_groups.append({
                                "label": str(acc.get("runtime_label") or acc.get("email") or team_id or "AT"),
                                "failures": int(fail_meta.get("consecutive_failures", 0) or 0),
                            })
                            continue
                        target_id = acc["ids"][group_index]
                        if queue_head_email:
                            dup_key = (acc.get("mode"), str(acc.get("team_id") or target_id), queue_head_email.lower())
                            already_here = duplicate_skip_cache.get(dup_key)
                            if already_here is None:
                                try:
                                    already_here = email_already_in_target(acc, target_id, queue_head_email)
                                except Exception as e:
                                    log(f"⚠️ 队首邮箱重复检测失败（AT）: {e}", level="WARNING")
                                    already_here = False
                                duplicate_skip_cache[dup_key] = already_here
                            if already_here:
                                log(
                                    f"ℹ️ 队首邮箱 {queue_head_email} 已在 母号{acc_index + 1}-组{group_index + 1}，跳过当前组。"
                                )
                                continue
                        chosen_acc_index = acc_index
                        chosen_group_index = group_index
                        capacity = capacity_left
                        break

                    chosen_group_for_ck = None
                    chosen_capacity_for_ck = 0
                    for group_index, target_id in enumerate(acc["ids"]):
                        stable_key = f"ck:{str(target_id).strip()}"
                        used = stable_used_per_group.get(stable_key)
                        if used is None:
                            used = legacy_used_per_group.get((acc_index, group_index), 0)
                        capacity_left = max(max_per_group - used, 0)
                        if capacity_left <= 0:
                            continue
                        if queue_head_email:
                            dup_key = (acc.get("mode"), str(target_id).strip(), queue_head_email.lower())
                            already_here = duplicate_skip_cache.get(dup_key)
                            if already_here is None:
                                try:
                                    already_here = email_already_in_target(acc, target_id, queue_head_email)
                                except Exception as e:
                                    log(f"⚠️ 队首邮箱重复检测失败（CK）: {e}", level="WARNING")
                                    already_here = False
                                duplicate_skip_cache[dup_key] = already_here
                            if already_here:
                                log(
                                    f"ℹ️ 队首邮箱 {queue_head_email} 已在 母号{acc_index + 1}-组{group_index + 1}，跳过当前组。"
                                )
                                continue
                        chosen_group_for_ck = group_index
                        chosen_capacity_for_ck = capacity_left
                        break

                    if chosen_group_for_ck is None:
                        continue

                    chosen_acc_index = acc_index
                    chosen_group_index = chosen_group_for_ck
                    capacity = chosen_capacity_for_ck
                    break  # 先用第一个还有空位的母号

                if chosen_acc_index is None:
                    if skipped_available_at_groups:
                        log(
                            "⚠️ 当前有 "
                            f"{len(skipped_available_at_groups)} 个 AT 组因连续失败已临时跳过，"
                            "请在后台检查异常标记后再恢复。 | "
                            f"{summarize_emails([x['label'] for x in skipped_available_at_groups])}",
                            level="WARNING",
                        )
                        time.sleep(30)
                        continue
                    log("✅ 所有母号的所有组都已满座，暂不再处理队列。")
                    time.sleep(60)
                    continue

                acc = accounts[chosen_acc_index]
                target_uuid = acc["ids"][chosen_group_index]

                # 本轮要处理的邮箱
                batch = queue[:capacity]
                if not batch:
                    time.sleep(5)
                    continue

                log(
                    f"🎯 准备使用母号 {chosen_acc_index + 1}，工作组 {chosen_group_index + 1}，本轮 {len(batch)} 个。"
                )

                invite_result = run_one_session(
                    target_uuid,
                    batch,
                    acc["cookies"],
                    mode=acc.get("mode", "cookie"),
                    team_id=acc.get("team_id"),
                    access_token=acc.get("access_token"),
                )
                success_emails = invite_result.get("success", []) or []
                terminal_emails = invite_result.get("terminal", []) or []
                terminal_details = invite_result.get("terminal_details", []) or []
                retryable_errors = invite_result.get("failed", []) or []
                group_key = build_group_key(acc, target_uuid, chosen_group_index)
                label = f"母号{chosen_acc_index + 1}-组{chosen_group_index + 1}"
                mode_value = str(acc.get("mode") or "").strip().lower()

                if success_emails:
                    for email in success_emails:
                        append_history(email, chosen_acc_index, chosen_group_index, account=acc, target_id=target_uuid)

                    if acc.get("mode") == "at":
                        clear_at_fail_state(acc, note="invite_success")
                        try:
                            sync_at_account_snapshot_live(acc)
                        except Exception as e:
                            log(f"AT 组同步快照失败: {e}", level="WARNING")

                    remove_from_queue(success_emails)
                    log(
                        f"✅ 本轮成功 {len(success_emails)} 个（母号 {chosen_acc_index + 1}-组 {chosen_group_index + 1}） | {summarize_emails(success_emails)}"
                    )

                if terminal_emails:
                    terminal_map = {
                        str(item.get("email", "") or "").strip().lower(): item
                        for item in terminal_details
                        if str(item.get("email", "") or "").strip()
                    }
                    for email in terminal_emails:
                        item = terminal_map.get(str(email or "").strip().lower(), {"email": email, "error": "terminal result"})
                        append_invite_status_record(
                            email=email,
                            label=label,
                            status=derive_terminal_status(item.get("error", "")),
                            reason=str(item.get("error", "") or "").strip(),
                            group_key=group_key,
                            mode=mode_value,
                        )
                    if acc.get("mode") == "at":
                        clear_at_fail_state(acc, note="terminal_cleanup")
                    remove_from_queue(terminal_emails)
                    log(
                        f"ℹ️ 本轮移除 {len(terminal_emails)} 个终态邮箱，避免卡住队列。 | {summarize_emails(terminal_emails)}"
                    )

                if retryable_errors:
                    sample = retryable_errors[0]
                    log(
                        f"⚠️ 本轮仍有 {len(retryable_errors)} 个待重试，示例 {sample.get('email') or '-'} / {sample.get('error') or 'unknown'}",
                        level="WARNING",
                    )

                if not success_emails and not terminal_emails:
                    if acc.get("mode") == "at":
                        failure_error = ""
                        if retryable_errors:
                            sample = retryable_errors[0]
                            failure_error = str(sample.get("error") or "").strip()
                        else:
                            failure_error = "No success and no terminal result"
                        fail_meta = record_at_failure(acc, batch, failure_error) or {}
                        if fail_meta.get("skip_marked"):
                            failure_reason = f"AT组连续失败达到阈值: {failure_error or 'retry only'}"
                            for email in batch:
                                append_invite_status_record(
                                    email=email,
                                    label=label,
                                    status="失败",
                                    reason=failure_reason,
                                    group_key=group_key,
                                    mode=mode_value,
                                )
                            log(
                                "🚫 AT组连续失败达到阈值，已标记异常并临时跳过。 | "
                                f"{str(acc.get('runtime_label') or acc.get('email') or acc.get('team_id') or '-')}"
                                f" | 连续失败 {int(fail_meta.get('consecutive_failures', 0) or 0)} 次"
                                f" | 今日失败批次 {int(fail_meta.get('today_fail_batches', 0) or 0)}"
                                f" | 失败邮箱 {summarize_emails(batch)}",
                                level="WARNING",
                            )
                    log("⚠️ 本轮没有成功的邀请，稍后重试。")

                time.sleep(5)

            except Exception as e:
                log(f"❌ 调度错误: {e}", level="ERROR")
                time.sleep(10)
    finally:
        # 程序退出时释放单例锁
        try:
            if singleton_lock:
                fcntl.flock(singleton_lock, fcntl.LOCK_UN)
                singleton_lock.close()
        except Exception:
            pass
