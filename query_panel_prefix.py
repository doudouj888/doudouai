import os, json, time, hashlib
import streamlit as st

BASE_DIR = "/opt/gpt_pro"
LICENSES_PATH = os.getenv("LICENSES_PATH", f"{BASE_DIR}/licenses.json")

# 只允许查询这个前缀（你以后换客户，就复制一份文件并改这里）
ALLOWED_PREFIX = os.getenv("ALLOWED_PREFIX", "CUSTA").strip().upper()
ALLOWED_PREFIX2 = ALLOWED_PREFIX if ALLOWED_PREFIX.endswith("-") else (ALLOWED_PREFIX + "-")

def load_licenses(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}

def normalize_entry(entry):
    # 兼容老/新格式：老格式可能是 "unused"/"used"，新格式是 dict
    if entry is None:
        return {"exists": False, "status": "invalid", "revoked": False}
    if isinstance(entry, str):
        status = entry.strip().lower()
        if status not in ("unused", "used"):
            status = "used"
        return {"exists": True, "status": status, "revoked": False}
    if isinstance(entry, dict):
        status = (entry.get("status") or "used").strip().lower()
        if status not in ("unused", "used"):
            status = "used"
        revoked = bool(entry.get("revoked", False))
        return {"exists": True, "status": status, "revoked": revoked}
    return {"exists": True, "status": "used", "revoked": False}

st.set_page_config(page_title="卡密状态批量查询", layout="wide")
st.title(f"卡密状态批量查询（仅允许前缀：{ALLOWED_PREFIX2}）")
st.caption("提示：不符合前缀的卡密会显示 not_allowed（防止扫你全库）。")

txt = st.text_area("批量粘贴卡密（每行一个）", height=220, placeholder=f"{ALLOWED_PREFIX2}XXXXXXX\n{ALLOWED_PREFIX2}YYYYYYY")

c1, c2 = st.columns([1, 1])
with c1:
    max_n = st.number_input("单次最多查询数量", min_value=10, max_value=500, value=200, step=10)
with c2:
    st.write("")

if st.button("🔍 开始查询", use_container_width=True):
    lines = [x.strip().upper() for x in (txt or "").splitlines() if x.strip()]
    # 去重
    seen, codes = set(), []
    for c in lines:
        if c not in seen:
            seen.add(c)
            codes.append(c)

    if not codes:
        st.warning("请先粘贴卡密")
        st.stop()

    if len(codes) > int(max_n):
        st.warning(f"本次 {len(codes)} 个，超过限制 {int(max_n)}，已截断。")
        codes = codes[:int(max_n)]

    db = load_licenses(LICENSES_PATH)

    results = []
    cnt_not_allowed = cnt_invalid = cnt_unused = cnt_used = cnt_revoked = 0

    for code in codes:
        if not code.startswith(ALLOWED_PREFIX2):
            cnt_not_allowed += 1
            results.append({"code": code, "status": "not_allowed", "revoked": False})
            continue

        info = normalize_entry(db.get(code))
        if not info["exists"]:
            cnt_invalid += 1
            results.append({"code": code, "status": "invalid", "revoked": False})
            continue

        status = info["status"]
        revoked = bool(info["revoked"])
        if revoked: cnt_revoked += 1
        if status == "unused": cnt_unused += 1
        else: cnt_used += 1

        results.append({"code": code, "status": status, "revoked": revoked})

    st.subheader("统计")
    st.write({
        "total": len(codes),
        "unused": cnt_unused,
        "used": cnt_used,
        "revoked": cnt_revoked,
        "invalid": cnt_invalid,
        "not_allowed": cnt_not_allowed
    })

    st.subheader("结果明细")
    st.dataframe(results, use_container_width=True, hide_index=True)

    # 审计日志：不记录明文卡密，只记录 hash 前 12 位
    try:
        os.makedirs(f"{BASE_DIR}/logs", exist_ok=True)
        log_path = f"{BASE_DIR}/logs/query_prefix_{ALLOWED_PREFIX}.log"
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        sample = [hashlib.sha256(c.encode()).hexdigest()[:12] for c in codes[:20]]
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{ts} prefix={ALLOWED_PREFIX2} total={len(codes)} unused={cnt_unused} used={cnt_used} revoked={cnt_revoked} invalid={cnt_invalid} not_allowed={cnt_not_allowed} sample_sha12={','.join(sample)}\n")
    except Exception:
        pass
