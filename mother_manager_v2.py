#!/usr/bin/env python3
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime
import streamlit as st

BASE_DIR = Path("/opt/gpt_pro")
STATE_FILE = BASE_DIR / "state.json"
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def safe_int(v, default=4, min_v=1, max_v=100):
    try:
        n = int(v)
    except Exception:
        n = default
    if n < min_v:
        n = min_v
    if n > max_v:
        n = max_v
    return n

def dedupe_keep_order(items):
    out, seen = [], set()
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

def normalize_ids(raw):
    if raw is None:
        return []
    if isinstance(raw, list):
        text = "\n".join([str(x) for x in raw if str(x).strip()])
    else:
        text = str(raw)

    text = text.replace("\r", "\n")
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("，", ",").replace("；", ";")
    parts = re.split(r"[\n,;|]+", text)

    ids = [p.strip() for p in parts if p and p.strip()]
    return dedupe_keep_order(ids)

def parse_cookie_array(v):
    arr = None
    if isinstance(v, list):
        arr = v
    elif isinstance(v, str):
        t = v.strip()
        if not t:
            return []
        try:
            obj = json.loads(t)
        except Exception:
            return []
        if isinstance(obj, list):
            arr = obj

    if not isinstance(arr, list):
        return []

    cleaned = []
    for c in arr:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name", "")).strip()
        value = str(c.get("value", "")).strip()
        if not name or value == "":
            continue
        cleaned.append(c)
    return cleaned

def extract_ids(item, cookies):
    vals = []

    if isinstance(item, dict):
        for k in (
            "workspace_id", "workspaceId", "team_id", "teamId",
            "group_id", "groupId", "ids", "ids_str", "group_ids", "groupIds",
            "workspace_ids", "workspaceIds"
        ):
            v = item.get(k)
            if v is not None and str(v).strip():
                vals.extend(normalize_ids(v))

        acc = item.get("account")
        if isinstance(acc, dict):
            for k in ("id", "workspace_id", "workspaceId"):
                v = acc.get(k)
                if v is not None and str(v).strip():
                    vals.extend(normalize_ids(v))

    for ck in cookies:
        if not isinstance(ck, dict):
            continue
        n = str(ck.get("name", "")).strip()
        v = str(ck.get("value", "")).strip()
        if n in ("_account", "workspace_id", "account_id") and v:
            vals.extend(normalize_ids(v))

    return dedupe_keep_order(vals)

def cookie_fingerprint(cookies):
    try:
        mini = [{"name": c.get("name"), "domain": c.get("domain"), "value": c.get("value")} for c in cookies]
        s = json.dumps(mini, ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]
    except Exception:
        return "na"

def to_state_item(rec):
    return {
        "name": rec["name"],
        "cookies": json.dumps(rec["cookies"], ensure_ascii=False),
        "ids": "\n".join(rec["ids"]),
        "max_per_group": safe_int(rec["max_per_group"], default=4, min_v=1, max_v=100),
    }

def load_accounts_from_state():
    if not STATE_FILE.exists():
        return []

    try:
        cfg = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

    if isinstance(cfg, dict) and isinstance(cfg.get("accounts"), list):
        raw_items = cfg["accounts"]
    elif isinstance(cfg, dict) and cfg.get("cookies") and cfg.get("ids"):
        raw_items = [cfg]
    else:
        raw_items = []

    out = []
    for i, it in enumerate(raw_items, 1):
        if not isinstance(it, dict):
            continue
        cookies = parse_cookie_array(it.get("cookies")) or parse_cookie_array(it.get("cookies_json"))
        ids = normalize_ids(it.get("ids") if "ids" in it else it.get("ids_str", ""))
        if not ids:
            ids = extract_ids(it, cookies)

        if cookies and ids:
            out.append({
                "name": str(it.get("name") or f"Node{i}").strip(),
                "cookies": cookies,
                "ids": ids,
                "max_per_group": safe_int(it.get("max_per_group", 4), default=4, min_v=1, max_v=100),
            })
    return out

def save_accounts_to_state(records):
    payload = {"accounts": [to_state_item(r) for r in records]}
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"state_{ts}.json"
    if STATE_FILE.exists():
        backup_file.write_text(STATE_FILE.read_text(encoding="utf-8"), encoding="utf-8")

    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)
    return backup_file

def make_record(name, cookies, ids, mpg):
    ids = dedupe_keep_order(ids)
    if not cookies or not ids:
        return None
    return {
        "name": (name or "").strip() or "Node",
        "cookies": cookies,
        "ids": ids,
        "max_per_group": safe_int(mpg, default=4, min_v=1, max_v=100),
    }

def parse_bulk_payload(text, default_mpg=4):
    raw = (text or "").strip()
    if not raw:
        return [], "empty", []

    errs = []
    try:
        obj = json.loads(raw)
    except Exception:
        obj = None

    # JSON 模式
    if obj is not None:
        # 纯 Cookie 数组
        if isinstance(obj, list) and obj and all(isinstance(x, dict) and "name" in x and "value" in x for x in obj):
            ids = extract_ids({}, obj)
            rec = make_record("Node1", obj, ids, default_mpg)
            if rec:
                return [rec], "json-cookie-array", errs
            return [], "json-cookie-array", ["Cookie数组内没找到团队ID（_account）"]

        if isinstance(obj, dict) and isinstance(obj.get("accounts"), list):
            items = obj.get("accounts", [])
        elif isinstance(obj, list):
            items = obj
        elif isinstance(obj, dict):
            items = [obj]
        else:
            items = []

        parsed = []
        for i, it in enumerate(items, 1):
            if not isinstance(it, dict):
                continue
            cookies = (
                parse_cookie_array(it.get("cookies"))
                or parse_cookie_array(it.get("cookies_json"))
                or parse_cookie_array(it.get("cookie"))
            )

            # 单条 cookie dict
            if not cookies and {"name", "value", "domain"}.issubset(set(it.keys())):
                cookies = [it]

            ids = extract_ids(it, cookies)

            if not cookies:
                errs.append(f"第{i}项：cookies 缺失或不是数组")
                continue
            if not ids:
                errs.append(f"第{i}项：团队ID缺失（workspace_id/account.id/_account）")
                continue

            rec = make_record(
                str(it.get("name") or f"Node{i}"),
                cookies,
                ids,
                it.get("max_per_group", default_mpg),
            )
            if rec:
                parsed.append(rec)

        if parsed:
            return parsed, "json-accounts", errs

    # TSV 模式：名称<TAB>cookies_json<TAB>ids(可空)<TAB>max_per_group(可空)
    parsed = []
    for ln, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        cols = line.split("\t")
        if len(cols) < 2:
            errs.append(f"第{ln}行：至少2列（名称 + cookies_json）")
            continue

        name = cols[0].strip() or f"Node{len(parsed)+1}"
        cookies = parse_cookie_array(cols[1].strip())
        ids = normalize_ids(cols[2].strip()) if len(cols) >= 3 else []
        if not ids:
            ids = extract_ids({}, cookies)
        mpg = cols[3].strip() if len(cols) >= 4 else default_mpg

        if not cookies:
            errs.append(f"第{ln}行：cookies_json 非法")
            continue
        if not ids:
            errs.append(f"第{ln}行：团队ID缺失")
            continue

        rec = make_record(name, cookies, ids, mpg)
        if rec:
            parsed.append(rec)

    return parsed, ("tsv" if parsed else "none"), errs

def merge_records(existing, incoming, mode):
    if mode == "全量替换":
        return incoming

    out = list(existing)
    idx_by_key = {}

    for i, r in enumerate(out):
        key = r["ids"][0] if r["ids"] else f"cookie:{cookie_fingerprint(r['cookies'])}"
        idx_by_key[key] = i

    for r in incoming:
        key = r["ids"][0] if r["ids"] else f"cookie:{cookie_fingerprint(r['cookies'])}"
        if key in idx_by_key:
            if mode == "按团队ID覆盖":
                out[idx_by_key[key]] = r
            else:
                # 追加模式遇到重复就跳过
                pass
        else:
            idx_by_key[key] = len(out)
            out.append(r)
    return out

def parse_index_expr(expr, max_n):
    s = (expr or "").replace("，", ",").strip()
    if not s:
        return []
    out = set()
    for part in s.split(","):
        p = part.strip()
        if not p:
            continue
        if "-" in p:
            a, b = p.split("-", 1)
            try:
                aa, bb = int(a), int(b)
                if aa > bb:
                    aa, bb = bb, aa
                for x in range(aa, bb + 1):
                    if 1 <= x <= max_n:
                        out.add(x)
            except Exception:
                pass
        else:
            try:
                x = int(p)
                if 1 <= x <= max_n:
                    out.add(x)
            except Exception:
                pass
    return sorted(out)

st.set_page_config(page_title="母号管理后台 V2", layout="wide")
st.title("母号管理后台 V2")
st.caption("支持：Cookie数组 / accounts JSON / TSV；支持批量导入、覆盖、删除、导出")

if "preview_records" not in st.session_state:
    st.session_state.preview_records = []
if "preview_mode" not in st.session_state:
    st.session_state.preview_mode = ""
if "preview_errs" not in st.session_state:
    st.session_state.preview_errs = []

accounts = load_accounts_from_state()
total_groups = sum(len(a["ids"]) for a in accounts)

c1, c2, c3 = st.columns(3)
c1.metric("当前母号数", len(accounts))
c2.metric("总团队ID数", total_groups)
c3.metric("state.json", str(STATE_FILE))

st.markdown("---")
left, right = st.columns([1, 1])

with left:
    st.subheader("A. 批量导入")
    payload = st.text_area("粘贴导入内容", height=260, placeholder="支持 JSON/TSV")
    default_mpg = st.number_input("默认每组上限", min_value=1, max_value=100, value=5, step=1)
    mode = st.selectbox("导入模式", ["追加（重复跳过）", "按团队ID覆盖", "全量替换"])

    if st.button("解析预览", type="primary"):
        parsed, p_mode, errs = parse_bulk_payload(payload, default_mpg=default_mpg)
        st.session_state.preview_records = parsed
        st.session_state.preview_mode = p_mode
        st.session_state.preview_errs = errs

    if st.session_state.preview_mode:
        st.info(f"解析模式：{st.session_state.preview_mode}；可导入 {len(st.session_state.preview_records)} 条")
    if st.session_state.preview_errs:
        st.warning("解析告警：\n- " + "\n- ".join(st.session_state.preview_errs[:20]))

    if st.session_state.preview_records:
        rows = []
        for i, r in enumerate(st.session_state.preview_records, 1):
            rows.append({
                "序号": i,
                "名称": r["name"],
                "团队ID首项": r["ids"][0] if r["ids"] else "",
                "团队ID数量": len(r["ids"]),
                "每组上限": r["max_per_group"],
                "Cookie数量": len(r["cookies"]),
                "指纹": cookie_fingerprint(r["cookies"]),
            })
        st.dataframe(rows, use_container_width=True, height=220)

        if st.button("执行导入并保存"):
            merged = merge_records(accounts, st.session_state.preview_records, mode)
            backup = save_accounts_to_state(merged)
            st.success(f"保存成功：{len(merged)} 条；备份：{backup}")
            st.session_state.preview_records = []
            st.session_state.preview_mode = ""
            st.session_state.preview_errs = []
            st.rerun()

with right:
    st.subheader("B. 当前母号列表 / 移除")
    if accounts:
        rows = []
        for i, r in enumerate(accounts, 1):
            rows.append({
                "序号": i,
                "名称": r["name"],
                "团队ID首项": r["ids"][0] if r["ids"] else "",
                "团队ID数量": len(r["ids"]),
                "每组上限": r["max_per_group"],
                "Cookie数量": len(r["cookies"]),
                "指纹": cookie_fingerprint(r["cookies"]),
            })
        st.dataframe(rows, use_container_width=True, height=340)
    else:
        st.caption("当前为空")

    rm_expr = st.text_input("删除序号（示例：2,5,8-12）")
    if st.button("删除选中序号并保存"):
        idxs = parse_index_expr(rm_expr, len(accounts))
        if not idxs:
            st.error("没有有效序号")
        else:
            keep = [r for i, r in enumerate(accounts, 1) if i not in set(idxs)]
            backup = save_accounts_to_state(keep)
            st.success(f"已删除 {len(idxs)} 条；剩余 {len(keep)}；备份：{backup}")
            st.rerun()

st.markdown("---")
st.subheader("C. 导出（便于迁移/回滚）")
export_accounts = []
for r in accounts:
    export_accounts.append({
        "name": r["name"],
        "workspace_id": r["ids"][0] if r["ids"] else "",
        "ids": r["ids"],
        "max_per_group": r["max_per_group"],
        "cookies": r["cookies"],
    })
export_json = json.dumps({"accounts": export_accounts}, ensure_ascii=False, indent=2)

st.download_button(
    "下载当前母号配置 JSON",
    data=export_json,
    file_name=f"mother_accounts_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
    mime="application/json",
)
st.text_area("复制用 JSON", export_json, height=180)
