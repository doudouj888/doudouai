#!/usr/bin/env python3
import argparse, json, re
from pathlib import Path
from datetime import datetime

def split_ids(v):
    if isinstance(v, list):
        arr = v
    else:
        s = str(v or "").replace("\r", "\n")
        s = re.sub(r"[,\uFF0C;| ]+", "\n", s)
        arr = s.split("\n")
    return [x.strip() for x in arr if x.strip()]

def norm_mpg(v):
    try: n = int(v)
    except: n = 4
    return n if n > 0 else 4

def norm_item(item, idx):
    if not isinstance(item, dict): return None
    ids = split_ids(item.get("ids", ""))
    if not ids: return None
    out = {
        "name": str(item.get("name") or f"母号{idx+1}").strip(),
        "cookies": str(item.get("cookies") or "").strip(),
        "ids": "\n".join(ids),
        "max_per_group": norm_mpg(item.get("max_per_group", 4)),
    }
    for k in ("access_token", "token", "rt"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            out[k] = v.strip()
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="/opt/gpt_pro/state.json")
    ap.add_argument("--file", required=True, help="批量文件（TSV）")
    args = ap.parse_args()

    state_p = Path(args.state)
    raw = {}
    if state_p.exists():
        raw = json.loads(state_p.read_text(encoding="utf-8") or "{}")
        if not isinstance(raw, dict): raw = {}

    # 兼容旧格式 -> accounts
    src = raw.get("accounts") if isinstance(raw.get("accounts"), list) else [raw]
    accounts = []
    for i, it in enumerate(src):
        n = norm_item(it, i)
        if n: accounts.append(n)

    # 读取批量导入
    imp = Path(args.file)
    if not imp.exists():
        raise SystemExit(f"导入文件不存在: {imp}")

    rejected = []
    existed_keys = {a["ids"]: i for i, a in enumerate(accounts)}
    lines = imp.read_text(encoding="utf-8", errors="ignore").splitlines()

    added = updated = skipped = 0
    for ln, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"): 
            continue

        parts = line.split("\t")
        if len(parts) == 2:
            name, sec, ids, mpg = "", parts[0], parts[1], 4
        elif len(parts) >= 3:
            name, sec, ids = parts[0], parts[1], parts[2]
            mpg = parts[3] if len(parts) >= 4 else 4
        else:
            rejected.append(f"[{ln}] 列数不足: {line}")
            continue

        ids_arr = split_ids(ids)
        if not ids_arr:
            rejected.append(f"[{ln}] 缺少团队ID")
            continue

        sec = sec.strip()
        looks_cookie = (
            "__Secure-next-auth.session-token" in sec
            or "cf_clearance=" in sec
            or "oai-did=" in sec
            or sec.startswith("[")
            or sec.startswith("{")
        )
        if not looks_cookie:
            rejected.append(f"[{ln}] 第二列不是Cookie（像AT），当前worker不支持AT直跑")
            continue

        item = {
            "name": name.strip() or f"母号_{ln}",
            "cookies": sec,
            "ids": "\n".join(ids_arr),
            "max_per_group": norm_mpg(mpg),
        }
        key = item["ids"]
        if key in existed_keys:
            i = existed_keys[key]
            old = accounts[i]
            old["name"] = item["name"] or old.get("name", "")
            old["cookies"] = item["cookies"] or old.get("cookies", "")
            old["max_per_group"] = item["max_per_group"] or old.get("max_per_group", 4)
            updated += 1
        else:
            accounts.append(item)
            existed_keys[key] = len(accounts) - 1
            added += 1

    # 写回
    bak = state_p.with_name(f"state.json.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    if state_p.exists():
        bak.write_text(state_p.read_text(encoding="utf-8"), encoding="utf-8")

    raw["accounts"] = accounts
    state_p.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    rej_p = Path("/opt/gpt_pro/mothers_rejected.txt")
    rej_p.write_text("\n".join(rejected), encoding="utf-8")

    print(f"OK added={added} updated={updated} total_accounts={len(accounts)} rejected={len(rejected)}")
    print(f"backup={bak}")
    print(f"rejected_file={rej_p}")

if __name__ == "__main__":
    main()
