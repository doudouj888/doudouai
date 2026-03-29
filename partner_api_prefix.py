import os, json
from flask import Flask, request, jsonify

BASE_DIR = "/opt/gpt_pro"
LICENSE_FILE = os.getenv("LICENSES_PATH", f"{BASE_DIR}/licenses.json")
QUEUE_FILE   = os.getenv("QUEUE_FILE",   f"{BASE_DIR}/queue.txt")
HISTORY_FILE = os.getenv("HISTORY_FILE", f"{BASE_DIR}/history.txt")
REDEEM_LOG   = os.getenv("REDEEM_LOG",   f"{BASE_DIR}/redeem_log.txt")
INVITE_LOG   = os.getenv("INVITE_LOG",   f"{BASE_DIR}/invite_log.txt")

ALLOWED_PREFIX = os.getenv("ALLOWED_PREFIX", "CUSTA").strip().upper()
ALLOWED_PREFIX2 = ALLOWED_PREFIX if ALLOWED_PREFIX.endswith("-") else (ALLOWED_PREFIX + "-")

API_KEY = os.getenv("PARTNER_QUERY_KEY", "").strip()
MAX_BATCH = 200

app = Flask(__name__)

def require_key():
    k = (request.headers.get("X-API-Key") or "").strip()
    return bool(API_KEY) and k == API_KEY

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}

def normalize_license(entry):
    if entry is None:
        return {"exists": False, "status": "invalid", "email": "", "time": ""}
    if isinstance(entry, str):
        s = entry.strip().lower()
        if s not in ("unused", "used"):
            s = "used"
        return {"exists": True, "status": s, "email": "", "time": ""}
    if isinstance(entry, dict):
        s = str(entry.get("status", "used")).strip().lower()
        if s not in ("unused", "used"):
            s = "used"
        return {
            "exists": True,
            "status": s,
            "email": str(entry.get("email","") or ""),
            "time":  str(entry.get("time","") or ""),
        }
    return {"exists": True, "status": "used", "email": "", "time": ""}

def read_lines_set(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set([x.strip().lower() for x in f if x.strip()])
    except Exception:
        return set()

def find_latest_line_contains(path, needle_lower: str, max_tail_lines: int = 5000):
    """从文件尾部找最后一条包含 needle 的行（避免全文件扫太慢）"""
    try:
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-max_tail_lines:]
        for line in reversed(lines):
            if needle_lower in line.lower():
                return line.strip("\n")
        return ""
    except Exception:
        return ""

def parse_redeem_log_line(line: str):
    """
    redeem_log.txt: 北京时间+0800 \t code \t email
    例：2026-01-03 23:11:22 +0800\tCUSTA-XXX\tuser@xx.com
    """
    if not line:
        return {"found": False}
    parts = line.split("\t")
    if len(parts) < 3:
        return {"found": False}
    return {"found": True, "redeemed_at": parts[0].strip(), "code": parts[1].strip(), "email": parts[2].strip()}

def parse_invite_log_line(line: str):
    """
    invite_log.txt: YYYY-mm-dd HH:MM:SS \t 母号X-组Y \t email
    """
    if not line:
        return {"found": False}
    parts = line.split("\t")
    if len(parts) < 3:
        return {"found": False}
    return {"found": True, "invited_at": parts[0].strip(), "slot": parts[1].strip(), "email": parts[2].strip()}

def email_state(email: str):
    e = email.strip().lower()
    if not e:
        return "bad_request"
    q = read_lines_set(QUEUE_FILE)
    h = read_lines_set(HISTORY_FILE)
    if e in q:
        return "queued"
    if e in h:
        return "invited"
    return "unknown"

@app.route("/api/partner/ping", methods=["GET"])
def ping():
    return jsonify(success=True, message="ok"), 200

@app.route("/api/partner/code_status", methods=["POST"])
def code_status():
    if not require_key():
        return jsonify(success=False, error="UNAUTHORIZED"), 401

    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip().upper()
    if not code:
        return jsonify(success=False, error="BAD_REQUEST", message="CODE_REQUIRED"), 400
    if not code.startswith(ALLOWED_PREFIX2):
        return jsonify(success=False, error="FORBIDDEN", message="PREFIX_NOT_ALLOWED"), 403

    db = load_json(LICENSE_FILE)
    info = normalize_license(db.get(code))
    return jsonify(success=True, data={"code": code, **info}), 200

@app.route("/api/partner/code_status_batch", methods=["POST"])
def code_status_batch():
    if not require_key():
        return jsonify(success=False, error="UNAUTHORIZED"), 401

    data = request.get_json(silent=True) or {}
    codes = data.get("codes") or []
    if not isinstance(codes, list):
        return jsonify(success=False, error="BAD_REQUEST", message="CODES_MUST_BE_LIST"), 400

    codes = [str(x).strip().upper() for x in codes if str(x).strip()]
    if not codes:
        return jsonify(success=False, error="BAD_REQUEST", message="CODES_REQUIRED"), 400
    if len(codes) > MAX_BATCH:
        return jsonify(success=False, error="BAD_REQUEST", message=f"TOO_MANY_CODES_MAX_{MAX_BATCH}"), 400

    seen, uniq = set(), []
    for c in codes:
        if c not in seen:
            seen.add(c); uniq.append(c)

    db = load_json(LICENSE_FILE)
    out = []
    for c in uniq:
        if not c.startswith(ALLOWED_PREFIX2):
            out.append({"code": c, "exists": False, "status": "not_allowed", "email": "", "time": ""})
            continue
        info = normalize_license(db.get(c))
        out.append({"code": c, **info})

    return jsonify(success=True, data=out, meta={"count": len(out)}), 200

@app.route("/api/partner/order_status", methods=["POST"])
def order_status():
    """
    客户最想要的“全状态”接口：
    输入：code + email
    输出：
      - code 状态（unused/used/invalid）
      - email 状态（queued/redeemed/invited/unknown）
      - redeem_log 最新记录（如果有）
      - invite_log 最新记录（如果有：时间+母号/组号）
    """
    if not require_key():
        return jsonify(success=False, error="UNAUTHORIZED"), 401

    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip().upper()
    email = (data.get("email") or "").strip()

    if not code or not email:
        return jsonify(success=False, error="BAD_REQUEST", message="CODE_AND_EMAIL_REQUIRED"), 400
    if not code.startswith(ALLOWED_PREFIX2):
        return jsonify(success=False, error="FORBIDDEN", message="PREFIX_NOT_ALLOWED"), 403

    # code 状态（来自 licenses.json）
    db = load_json(LICENSE_FILE)
    cinfo = normalize_license(db.get(code))

    # redeem_log / invite_log（从文件尾部找最后一条）
    redeem_line = find_latest_line_contains(REDEEM_LOG, f"\t{code}\t".lower(), max_tail_lines=8000)
    rinfo = parse_redeem_log_line(redeem_line)

    invite_line = find_latest_line_contains(INVITE_LOG, f"\t{email}".lower(), max_tail_lines=15000)
    iinfo = parse_invite_log_line(invite_line)

    # email 状态：优先以 invite_log 为准（最接近“邀请成功”）
    if iinfo.get("found"):
        estate = "invited"
    else:
        estate = email_state(email)
        # 如果 licenses.json 已用 + redeem_log 找到，但还没 invite_log，就标 redeemed（已兑换待邀请）
        if estate == "unknown" and cinfo.get("exists") and cinfo.get("status") == "used" and rinfo.get("found"):
            estate = "redeemed"

    return jsonify(success=True, data={
        "code": {"code": code, **cinfo},
        "email": {"email": email, "state": estate},
        "redeem_log": rinfo,
        "invite_log": iinfo
    }), 200

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=13002)
