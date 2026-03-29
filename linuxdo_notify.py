#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LinuxDO Credit 异步通知接收器 + 支付成功页（方案A）
- notify:   /linuxdo/notify  (LinuxDO 服务器回调，验签成功后生成 redeem_code 并保存)
- success:  /pay/success     (用户浏览器跳回查询页/展示兑换码)

关键修复：
- 支付成功生成 redeem_code 后，自动写入 /opt/gpt_pro/licenses.json（status=unused）
  使得 /api/redeem 能识别该兑换码（否则会提示“卡密不存在或填写错误”）。
- 启动时会从 sqlite 里把历史 TRADE_SUCCESS 的兑换码补入 licenses.json（不覆盖已存在记录）。
"""

import os
import time
import json
import hashlib
import sqlite3
import secrets
import fcntl
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from html import escape as h

from flask import Flask, request, Response

# ---------------------------
# 基础路径
# ---------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

DB_PATH = os.path.join(LOG_DIR, "linuxdo_pay.sqlite3")
NOTIFY_LOG_FILE = os.path.join(LOG_DIR, "linuxdo_notify.log")

# 你的站点域名（按钮会跳回这里让用户去兑换）
REDEEM_URL = os.environ.get("REDEEM_URL", "https://example.com/")

# 兑换系统的卡密库（/api/redeem 只认它）
LICENSE_FILE = os.path.join(BASE_DIR, "licenses.json")
LICENSE_LOCK_FILE = LICENSE_FILE + ".lock"

BJ_TZ = timezone(timedelta(hours=8))

app = Flask(__name__)


def normalize_trade_no(x: str) -> str:
    """订单号清洗：去空格/非数字/前导0。"""
    if not x:
        return ""
    x = "".join(ch for ch in str(x).strip() if ch.isdigit())
    return x.lstrip("0")

# ---------------------------
# LOG
# ---------------------------
def log_line(msg: str):
    try:
        ts = datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S %z")
        with open(NOTIFY_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


# ---------------------------
# 文件锁：licenses.json
# ---------------------------
@contextmanager
def locked_license():
    """
    对 licenses.json 的简单互斥锁：
    - 使用单独的 lock 文件，避免直接锁数据文件出问题
    - 所有修改 licenses.json 的操作都放到这个上下文里做
    """
    f = open(LICENSE_LOCK_FILE, "w", encoding="utf-8")
    try:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(f, fcntl.LOCK_UN)
        except Exception:
            pass
        f.close()


def load_licenses() -> dict:
    """读取 licenses.json，失败则返回空字典。"""
    if not os.path.exists(LICENSE_FILE):
        return {}
    try:
        with open(LICENSE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_licenses(data: dict):
    """安全地写回 licenses.json（先写临时文件，再替换）。"""
    tmp_path = LICENSE_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, LICENSE_FILE)


def get_status_from_entry(entry) -> str:
    """
    兼容两种格式：
    1）老格式： "CODE": "unused" / "used"
    2）新格式： "CODE": {"status": "used", "email": "...", "time": "...", ...}
    返回统一的小写状态字符串，例如 "unused" / "used"
    """
    if entry is None:
        return None
    if isinstance(entry, dict):
        status = entry.get("status", "used")
    else:
        status = entry
    if not isinstance(status, str):
        status = str(status)
    return status.strip().lower()


def beijing_time_str() -> str:
    return datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S %z")


def ensure_code_in_licenses(code: str, trade_no: str = "", money: str = "", source: str = "linuxdo") -> bool:
    """
    确保兑换码写入 licenses.json（status=unused）
    - 不覆盖已存在且已 used 的记录
    - 不破坏老格式
    """
    if not code:
        return False
    code = str(code).strip().upper()
    if not code:
        return False

    try:
        with locked_license():
            data = load_licenses()

            existing = data.get(code)
            st = get_status_from_entry(existing)

            # 已存在且已使用：绝不覆盖
            if st == "used":
                return True

            # 已存在但不是 used：尽量补齐为新格式（不强行改成 used）
            now = beijing_time_str()
            if isinstance(existing, dict):
                existing.setdefault("status", "unused")
                existing.setdefault("source", source)
                existing.setdefault("gen_time", now)
                if trade_no and not existing.get("trade_no"):
                    existing["trade_no"] = trade_no
                if money and not existing.get("money"):
                    existing["money"] = money
                data[code] = existing
            else:
                # 老格式字符串 or None：写成新格式（更利于后台查询）
                data[code] = {
                    "status": "unused" if st != "used" else "used",
                    "source": source,
                    "gen_time": now,
                    "trade_no": trade_no or "",
                    "money": money or "",
                }

            save_licenses(data)
        return True
    except Exception as e:
        log_line(f"ensure_code_in_licenses FAILED code={code} err={e}")
        return False


# ---------------------------
# SQLite：订单库
# ---------------------------
def db_conn():
    return sqlite3.connect(DB_PATH, timeout=10)

def db_init():
    conn = db_conn()
    try:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                trade_no      TEXT PRIMARY KEY,
                out_trade_no  TEXT,
                money         TEXT,
                trade_status  TEXT,
                redeem_code   TEXT,
                created_at    INTEGER
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

def db_get_by_trade_no(trade_no: str):
    """
    通过 trade_no 查订单。兼容用户粘贴的“带前导0/带空格/带非数字/粘贴多了内容”情况。
    """
    tn_raw = trade_no or ""
    tn = normalize_trade_no(tn_raw)

    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()

        # 1) 优先用清洗后的 trade_no 精确查
        if tn:
            cur.execute("SELECT * FROM orders WHERE trade_no=? LIMIT 1", (tn,))
            row = cur.fetchone()
            if row:
                return dict(row)

        # 2) 再试原始字符串（极少数情况下平台真的带0存）
        raw = tn_raw.strip()
        if raw and raw != tn:
            cur.execute("SELECT * FROM orders WHERE trade_no=? LIMIT 1", (raw,))
            row = cur.fetchone()
            if row:
                return dict(row)

        # 3) 兜底：用户可能复制多了前缀/描述，尝试“最后 17 位”
        digits = "".join(ch for ch in tn_raw if ch.isdigit())
        if len(digits) > 17:
            cand = digits[-17:].lstrip("0")
            if cand and cand != tn:
                cur.execute("SELECT * FROM orders WHERE trade_no=? LIMIT 1", (cand,))
                row = cur.fetchone()
                if row:
                    return dict(row)

        return None
    finally:
        conn.close()



def db_get_by_out_trade_no(out_trade_no: str):
    if not out_trade_no:
        return None
    conn = db_conn()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT trade_no,out_trade_no,money,trade_status,redeem_code,created_at FROM orders WHERE out_trade_no=? LIMIT 1",
            (out_trade_no,),
        )
        r = c.fetchone()
        if not r:
            return None
        return {
            "trade_no": r[0],
            "out_trade_no": r[1],
            "money": r[2],
            "trade_status": r[3],
            "redeem_code": r[4],
            "created_at": r[5],
        }
    finally:
        conn.close()

def db_upsert_order(trade_no: str, out_trade_no: str, money: str, trade_status: str, redeem_code: str):
    now = int(time.time())
    conn = db_conn()
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO orders(trade_no,out_trade_no,money,trade_status,redeem_code,created_at)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(trade_no) DO UPDATE SET
              out_trade_no=excluded.out_trade_no,
              money=excluded.money,
              trade_status=excluded.trade_status,
              redeem_code=COALESCE(orders.redeem_code, excluded.redeem_code),
              created_at=COALESCE(orders.created_at, excluded.created_at)
            """,
            (trade_no, out_trade_no, money, trade_status, redeem_code, now),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------
# LinuxDO 验签
# ---------------------------
def md5_hex(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def canonical_query(params: dict) -> str:
    items = []
    for k in sorted(params.keys()):
        v = params.get(k)
        if v is None:
            continue
        items.append(f"{k}={v}")
    return "&".join(items)

def verify_linuxdo_sign(all_params: dict, secret: str) -> (bool, str, str, str):
    """
    兼容两种常见签名拼接方式（你日志里也出现过）：
    A) md5(payload + secret)
    B) md5(payload + "&key=" + secret)
    """
    recv = str(all_params.get("sign", "")).strip().lower()
    p = {k: all_params.get(k) for k in all_params.keys()
     if k not in ("sign", "sign_type") and all_params.get(k) not in (None, "")}

    payload = canonical_query(p)

    a = md5_hex(payload + secret).lower()
    b = md5_hex(payload + "&key=" + secret).lower()
    ok = (recv == a) or (recv == b)
    return ok, payload, a, b


# ---------------------------
# 兑换码生成
# ---------------------------
def gen_redeem_code(length=16) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 去掉易混淆字符
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ---------------------------
# 启动时：把历史订单补入 licenses.json（不覆盖）
# ---------------------------
def bootstrap_sync_licenses(limit: int = 5000):
    try:
        conn = db_conn()
        try:
            c = conn.cursor()
            c.execute(
                """
                SELECT trade_no, money, redeem_code
                FROM orders
                WHERE trade_status IN ('TRADE_SUCCESS','TRADE_FINISHED')
                  AND redeem_code IS NOT NULL AND redeem_code != ''
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = c.fetchall()
        finally:
            conn.close()

        n_ok = 0
        for trade_no, money, code in rows:
            if ensure_code_in_licenses(code, trade_no=str(trade_no or ""), money=str(money or ""), source="linuxdo_bootstrap"):
                n_ok += 1
        log_line(f"bootstrap_sync_licenses done rows={len(rows)} ok={n_ok}")
    except Exception as e:
        log_line(f"bootstrap_sync_licenses FAILED err={e}")


# ---------------------------
# 页面：订单查询页（你现在的页面风格）
# ---------------------------
ORDER_QUERY_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>领取兑换码 | 订单查询</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
    :root {
        --primary: #2563eb;
        --primary-hover: #1d4ed8;
        --bg-color: #f8fafc;
        --card-bg: #ffffff;
        --text-main: #0f172a;
        --text-sub: #64748b;
        --border: #e2e8f0;
        --radius: 14px;
    }
    * { box-sizing: border-box; }
    body {
        margin: 0;
        font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
        background: var(--bg-color);
        color: var(--text-main);
    }
    .wrap {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 28px 16px;
    }
    .card {
        width: 100%;
        max-width: 520px;
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 22px;
        box-shadow: 0 10px 30px rgba(2, 6, 23, 0.06);
    }
    .title {
        font-size: 20px;
        font-weight: 700;
        margin: 0 0 6px 0;
    }
    .subtitle {
        margin: 0 0 16px 0;
        color: var(--text-sub);
        font-size: 14px;
        line-height: 1.5;
    }
    .tip {
        background: #eff6ff;
        border: 1px solid #dbeafe;
        color: #1d4ed8;
        padding: 10px 12px;
        border-radius: 10px;
        font-size: 13px;
        margin-bottom: 14px;
    }
    label {
        display: block;
        font-size: 13px;
        margin: 10px 0 6px;
        color: var(--text-sub);
        font-weight: 600;
    }
    input {
        width: 100%;
        padding: 12px 12px;
        border: 1px solid var(--border);
        border-radius: 10px;
        outline: none;
        font-size: 14px;
    }
    input:focus {
        border-color: #93c5fd;
        box-shadow: 0 0 0 4px rgba(59,130,246,0.12);
    }
    .btn {
        width: 100%;
        margin-top: 14px;
        padding: 12px 14px;
        border: 0;
        border-radius: 12px;
        background: var(--primary);
        color: #fff;
        font-size: 15px;
        font-weight: 700;
        cursor: pointer;
    }
    .btn:hover { background: var(--primary-hover); }
    .footer {
        margin-top: 14px;
        font-size: 12px;
        color: var(--text-sub);
        line-height: 1.6;
    }
    .err {
        background: #fef2f2;
        border: 1px solid #fecaca;
        color: #b91c1c;
        padding: 10px 12px;
        border-radius: 10px;
        font-size: 13px;
        margin-bottom: 12px;
    }
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <h1 class="title">领取兑换码</h1>
    <p class="subtitle">如果你刚完成支付但页面没显示兑换码，可在这里通过订单号查询。</p>
    {{ERROR_BLOCK}}
    <div class="tip">提示：请粘贴 LinuxDO 订单号 <b>trade_no</b>（数字很长那串）。</div>

    <form method="get" action="/pay/success">
      <label for="trade_no">订单号 trade_no</label>
      <input id="trade_no" name="trade_no" placeholder="例如：12090906417037312" autocomplete="off" />
      <button class="btn" type="submit">查询兑换码</button>
    </form>

    <div class="footer">
      若仍查询不到：请确认 trade_no 是否复制正确，或稍等 10 秒再查一次。<br>
      查询到兑换码后，请到你的网站，在“兑换码 + 邮箱”页面粘贴兑换码进行兑换。
    </div>
  </div>
</div>
</body>
</html>
"""

def render_query_page(error_msg: str = "") -> Response:
    block = ""
    if error_msg:
        block = f'<div class="err">{h(error_msg)}</div>'
    html = ORDER_QUERY_HTML.replace("{{ERROR_BLOCK}}", block)
    return Response(html, status=200, mimetype="text/html; charset=utf-8")


def render_code_page(code: str, trade_no: str = "", money: str = "") -> Response:
    code_esc = h(code or "")
    trade_esc = h(trade_no or "")
    money_esc = h(money or "")
    now_esc = h(beijing_time_str())

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>兑换码已生成</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --primary:#2563eb; --primary-hover:#1d4ed8;
    --bg:#0b1220; --card:#0f172a; --text:#e2e8f0; --sub:#94a3b8; --border:#1e293b;
    --radius:16px;
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:linear-gradient(135deg,#0b1220,#020617);color:var(--text)}}
  .wrap{{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:28px 16px}}
  .card{{width:100%;max-width:560px;background:rgba(15,23,42,.9);border:1px solid var(--border);border-radius:var(--radius);padding:22px;box-shadow:0 18px 50px rgba(0,0,0,.35)}}
  h1{{margin:0 0 6px;font-size:20px}}
  .sub{{margin:0 0 14px;color:var(--sub);font-size:13px;line-height:1.6}}
  .codebox{{display:flex;gap:10px;align-items:stretch;margin-top:10px}}
  .code{{flex:1;padding:12px 14px;border:1px solid var(--border);border-radius:12px;background:#0b1220;font-size:18px;font-weight:800;letter-spacing:1px;text-align:center}}
  .btn{{border:0;border-radius:12px;padding:12px 14px;font-weight:800;cursor:pointer}}
  .btn-copy{{background:#22c55e;color:#052e16}}
  .btn-copy:hover{{filter:brightness(0.95)}}
  .btn-go{{width:100%;margin-top:12px;background:var(--primary);color:#fff}}
  .btn-go:hover{{background:var(--primary-hover)}}
  .meta{{margin-top:12px;color:var(--sub);font-size:12px;line-height:1.7}}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <h1>兑换码已生成 ✅</h1>
    <p class="sub">请先复制兑换码，然后点击“去我的网站兑换”。</p>

    <div class="codebox">
      <div id="code" class="code">{code_esc}</div>
      <button class="btn btn-copy" onclick="copyCode()">一键复制</button>
    </div>

    <button class="btn btn-go" onclick="window.location.href='{h(REDEEM_URL)}'">去我的网站兑换</button>

    <div class="meta">
      订单号：{trade_esc}<br>
      金额：{money_esc}<br>
      生成时间：{now_esc}<br>
      <span style="color:#94a3b8;">提示：到你的网站后，在“兑换码 + 邮箱”页面粘贴兑换码进行兑换。</span>
    </div>
  </div>
</div>

<script>
function copyCode() {{
  const t = document.getElementById('code').innerText || '';
  if (navigator.clipboard && navigator.clipboard.writeText) {{
    navigator.clipboard.writeText(t);
    return;
  }}
  // 兼容老浏览器
  const ta = document.createElement('textarea');
  ta.value = t;
  document.body.appendChild(ta);
  ta.select();
  document.execCommand('copy');
  document.body.removeChild(ta);
}}
</script>
</body>
</html>
"""
    return Response(html, status=200, mimetype="text/html; charset=utf-8")


# ---------------------------
# 路由：LinuxDO notify
# ---------------------------
@app.route("/linuxdo/notify", methods=["GET", "POST"])
def linuxdo_notify():
    secret = os.environ.get("LINUXDO_KEY", "").strip()
    if not secret:
        log_line("LINUXDO_KEY missing")
        return Response("NO_KEY", status=500, mimetype="text/plain")

    # LinuxDO 可能 GET，也可能 POST（form/json），都兼容
    params = {}
    try:
        params.update({k: request.args.get(k) for k in request.args.keys()})
        if request.form:
            params.update({k: request.form.get(k) for k in request.form.keys()})
        if request.is_json:
            j = request.get_json(silent=True) or {}
            if isinstance(j, dict):
                params.update({k: j.get(k) for k in j.keys()})
    except Exception:
        pass

    trade_no = str(params.get("trade_no") or "").strip()
    out_trade_no = str(params.get("out_trade_no") or "").strip()
    money = str(params.get("money") or "").strip()
    trade_status = str(params.get("trade_status") or "").strip()

    ok, payload, a, b = verify_linuxdo_sign(params, secret)
    recv = str(params.get("sign") or "").strip().lower()

    log_line(f"notify recv_sign={recv} A={a} B={b} ok={ok} payload={payload}")

    if not ok:
        return Response("INVALID_SIGN", status=400, mimetype="text/plain")

    # 写库（成功才生成 redeem_code）
    redeem_code = ""
    if trade_status in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        existing = db_get_by_trade_no(trade_no)
        if existing and existing.get("redeem_code"):
            redeem_code = existing["redeem_code"]
        else:
            redeem_code = gen_redeem_code(16)

        db_upsert_order(trade_no, out_trade_no, money, trade_status, redeem_code)

        # ★关键：入库 licenses.json，确保 /api/redeem 可兑换
        ensure_code_in_licenses(redeem_code, trade_no=trade_no, money=money, source="linuxdo_notify")

        log_line(f"notify OK trade_no={trade_no} money={money} status={trade_status} code={redeem_code}")
    else:
        # 非成功也记一下订单（不生成兑换码）
        db_upsert_order(trade_no, out_trade_no, money, trade_status, "")
        log_line(f"notify NONSUCCESS trade_no={trade_no} status={trade_status}")

    return Response("OK", status=200, mimetype="text/plain")


# ---------------------------
# 路由：支付成功/查询页
# ---------------------------
@app.route("/pay/success", methods=["GET"])
def pay_success():
    trade_no = (request.args.get("trade_no") or "").strip()
    out_trade_no = (request.args.get("out_trade_no") or "").strip()

    # 没参数：展示查询页
    if not trade_no and not out_trade_no:
        return render_query_page()

    row = None
    if trade_no:
        row = db_get_by_trade_no(trade_no)
    if (not row) and out_trade_no:
        row = db_get_by_out_trade_no(out_trade_no)

    if not row:
        return render_query_page("未查询到该订单的兑换码。请确认 trade_no 是否复制正确，或稍等 10 秒再查一次。")

    code = (row.get("redeem_code") or "").strip().upper()
    if not code:
        return render_query_page("该订单暂无兑换码（可能还没回调成功）。请稍等 10 秒后再查一次。")

    # ★兜底：用户查到时也确保入库
    ensure_code_in_licenses(code, trade_no=row.get("trade_no") or "", money=row.get("money") or "", source="linuxdo_success")

    return render_code_page(code, trade_no=row.get("trade_no") or "", money=row.get("money") or "")


@app.route("/_health", methods=["GET"])
def health():
    return Response("OK", status=200, mimetype="text/plain")


def main():
    db_init()
    bootstrap_sync_licenses(limit=5000)
    # 只监听本机，由 nginx 反代
    app.run(host="127.0.0.1", port=5010)


if __name__ == "__main__":
    main()
