#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, json, time, logging
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
import fcntl, requests

QUEUE_FILE="queue.txt"
HISTORY_FILE="history.txt"
STATE_FILE="state.json"
LOG_FILE="worker_api.log"
LOCK_FILE="worker_api.lock"
BJ_TZ=timezone(timedelta(hours=8))
ROLE_DEFAULT=(os.getenv("INVITE_ROLE","standard-user") or "standard-user").strip()
MAX_PER_CALL=max(1,min(4,int(os.getenv("MAX_PER_CALL","4"))))

logging.basicConfig(level=logging.INFO,format="%(asctime)s - %(levelname)s - %(message)s",handlers=[logging.FileHandler(LOG_FILE,mode="a",encoding="utf-8"),logging.StreamHandler(sys.stdout)])
def log(msg,level="INFO"): logging.log(getattr(logging,level,logging.INFO),msg)

@contextmanager
def locked_open(path,mode):
    f=open(path,mode,encoding="utf-8")
    try:
        fcntl.flock(f,fcntl.LOCK_EX); yield f
    finally:
        fcntl.flock(f,fcntl.LOCK_UN); f.close()

def load_json(path,default):
    if not os.path.exists(path): return default
    try:
        with open(path,"r",encoding="utf-8") as f: return json.load(f)
    except Exception: return default

def load_state(): return load_json(STATE_FILE,{})
def parse_accounts():
    cfg=load_state(); arr=[]
    if not cfg: return arr
    raw=cfg.get("accounts",[]) if isinstance(cfg,dict) and "accounts" in cfg else [cfg]
    for item in raw:
        if not isinstance(item,dict): continue
        cookies=(item.get("cookies") or "").strip()
        ids=[x.strip() for x in (item.get("ids") or "").replace("\r","\n").split("\n") if x.strip()]
        try: mpg=int(item.get("max_per_group",4) or 4)
        except Exception: mpg=4
        if mpg<=0: mpg=4
        if cookies and ids: arr.append({"cookies":cookies,"ids":ids,"max_per_group":mpg})
    return arr

def load_queue():
    if not os.path.exists(QUEUE_FILE): return []
    with locked_open(QUEUE_FILE,"r") as f: return [l.strip() for l in f if l.strip()]

def remove_from_queue(emails):
    if not emails or not os.path.exists(QUEUE_FILE): return
    rm={x.strip().lower() for x in emails if x and x.strip()}
    with locked_open(QUEUE_FILE,"r+") as f:
        lines=[l.strip() for l in f if l.strip()]
        left=[x for x in lines if x.strip().lower() not in rm]
        f.seek(0); f.truncate()
        if left: f.write("\n".join(left)+"\n")

def load_history_entries():
    out=[]
    if not os.path.exists(HISTORY_FILE): return out
    with locked_open(HISTORY_FILE,"r") as f:
        for line in f:
            p=line.strip().split("\t")
            if not p or not p[0]: continue
            try: ai=int(p[1]) if len(p)>=2 else 0
            except Exception: ai=0
            try: gi=int(p[2]) if len(p)>=3 else 0
            except Exception: gi=0
            out.append({"email":p[0],"account_index":ai,"group_index":gi})
    return out

def append_history(email,ai,gi):
    with locked_open(HISTORY_FILE,"a") as f: f.write(f"{email}\t{ai}\t{gi}\n")
    try:
        now=datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S")
        with open("invite_log.txt","a",encoding="utf-8") as f2:
            f2.write(f"{now}\t母号{ai+1}-组{gi+1}\t{email}\n")
    except Exception: pass

def build_session(cookie_data):
    s=requests.Session()
    s.headers.update({
        "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept":"application/json, text/plain, */*",
        "Origin":"https://chatgpt.com",
        "Referer":"https://chatgpt.com/",
    })
    c=(cookie_data or "").strip()
    if not c: return s
    if c.startswith("["):
        try:
            cl=json.loads(c)
            if isinstance(cl,list):
                for it in cl:
                    if not isinstance(it,dict): continue
                    n=it.get("name"); v=it.get("value")
                    if not n: continue
                    d=it.get("domain") or ".chatgpt.com"; p=it.get("path") or "/"
                    try: s.cookies.set(n,v,domain=d,path=p)
                    except Exception:
                        try: s.cookies.set(n,v)
                        except Exception: pass
                return s
        except Exception: pass
    for kv in [x.strip() for x in c.split(";") if "=" in x]:
        try:
            k,v=kv.split("=",1); s.cookies.set(k.strip(),v.strip())
        except Exception: pass
    return s

def get_token(ses):
    try: r=ses.get("https://chatgpt.com/api/auth/session",timeout=20)
    except Exception as e: return None,f"session异常:{e}"
    if r.status_code!=200: return None,f"session状态:{r.status_code}"
    try: d=r.json()
    except Exception: return None,"session非JSON"
    tk=d.get("accessToken") or d.get("access_token")
    return (tk,None) if tk else (None,"session无accessToken")

def get_ws_candidates(ses,token):
    h={"Authorization":f"Bearer {token}"}
    try: r=ses.get("https://chatgpt.com/backend-api/accounts",headers=h,timeout=20)
    except Exception: return []
    if r.status_code!=200: return []
    try: d=r.json()
    except Exception: return []
    items=d.get("items") or d.get("accounts") or []
    out=[]
    for it in items:
        if not isinstance(it,dict): continue
        st=(it.get("structure") or "").lower(); personal=bool(it.get("personal",False))
        if st=="personal" or personal: continue
        for k in ("id","account_id","organization_id"):
            v=it.get(k)
            if v and v not in out: out.append(v)
    return out

def invite_batch(cookie_data,target_hint,emails,role):
    ses=build_session(cookie_data)
    token,err=get_token(ses)
    if not token: return [],f"token失败:{err}"
    cands=[]
    if target_hint: cands.append(target_hint)
    for cid in get_ws_candidates(ses,token):
        if cid not in cands: cands.append(cid)
    if not cands: return [],"无workspace ID"

    hdr={
        "Authorization":f"Bearer {token}",
        "Content-Type":"application/json",
        "Accept":"application/json, text/plain, */*",
        "Origin":"https://chatgpt.com",
        "Referer":"https://chatgpt.com/admin/members",
    }
    payload={"email_addresses":emails,"role":role,"resend_emails":False}
    last_err=""
    for cid in cands:
        url=f"https://chatgpt.com/backend-api/accounts/{cid}/invites"
        try: r=ses.post(url,headers=hdr,json=payload,timeout=25)
        except Exception as e:
            last_err=f"{cid}:请求异常 {e}"; continue
        txt=r.text[:500]
        try: d=r.json()
        except Exception: d={}

        if r.status_code in (200,201):
            succ=[]
            for inv in d.get("account_invites",[]) or []:
                em=(inv.get("email_address") or inv.get("email") or "").strip()
                if em: succ.append(em)
            if succ: return succ,None
            ers=d.get("errored_emails") or []
            last_err=f"{cid}: errored_emails={ers}" if ers else f"{cid}:成功但无account_invites"
            continue

        msg=(d.get("detail") or d.get("message") or d.get("error") or txt) if isinstance(d,dict) else txt
        m=str(msg)
        if r.status_code in (401,403,404) and ("workspace" in m.lower() or "must use workspace account" in m.lower() or r.status_code==404):
            last_err=f"{cid}: HTTP {r.status_code} {m}"; continue
        return [],f"{cid}: HTTP {r.status_code} {m}"
    return [],last_err or "所有候选workspace失败"

def main_loop():
    if not os.path.exists(QUEUE_FILE): open(QUEUE_FILE,"w",encoding="utf-8").close()
    if not os.path.exists(HISTORY_FILE): open(HISTORY_FILE,"w",encoding="utf-8").close()
    oneshot=os.getenv("ONESHOT","0")=="1"

    while True:
        try:
            accs=parse_accounts()
            if not accs:
                log("⚠️ 未配置母号(state.json)")
                if oneshot: break
                time.sleep(10); continue

            queue=load_queue()
            if not queue:
                if oneshot: break
                time.sleep(5); continue

            hist=load_history_entries(); used=[0]*len(accs)
            for h in hist:
                idx=h["account_index"]
                if 0<=idx<len(used): used[idx]+=1

            cai=cgi=None; cap=0
            for ai,acc in enumerate(accs):
                u=used[ai]; mpg=acc.get("max_per_group",4) or 4
                if mpg<=0: mpg=4
                gi=u//mpg; fg=u%mpg
                if gi>=len(acc["ids"]): continue
                left=mpg-fg
                if left<=0: continue
                cai,cgi,cap=ai,gi,left; break

            if cai is None:
                log("✅ 所有母号组已满，暂停60秒")
                if oneshot: break
                time.sleep(60); continue

            acc=accs[cai]; target_id=acc["ids"][cgi]
            batch=queue[:min(cap,MAX_PER_CALL)]
            if not batch:
                if oneshot: break
                time.sleep(5); continue

            log(f"🚀 API邀请：母号{cai+1}-组{cgi+1}，本轮{len(batch)}，role={ROLE_DEFAULT}")
            succ,err=invite_batch(acc["cookies"],target_id,batch,ROLE_DEFAULT)

            if succ:
                for e in succ: append_history(e,cai,cgi)
                remove_from_queue(succ)
                log(f"✅ API本轮成功 {len(succ)}")
            else:
                log(f"⚠️ API本轮失败: {err}",level="ERROR")

            if oneshot: break
            time.sleep(5 if succ else 30)

        except Exception as e:
            log(f"❌ 调度错误: {e}",level="ERROR")
            if oneshot: break
            time.sleep(10)

if __name__=="__main__":
    lk=None
    try:
        lk=open(LOCK_FILE,"w",encoding="utf-8")
        fcntl.flock(lk,fcntl.LOCK_EX|fcntl.LOCK_NB)
        lk.write(str(os.getpid())); lk.flush()
    except OSError:
        log("❌ 已有 worker_api.py 在运行",level="ERROR"); sys.exit(1)
    log("🔥 API邀请 worker 启动...")
    try: main_loop()
    finally:
        try:
            if lk: fcntl.flock(lk,fcntl.LOCK_UN); lk.close()
        except Exception: pass
