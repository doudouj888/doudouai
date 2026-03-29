#!/usr/bin/env python3
import re, sys, os, sqlite3, datetime

DB='/opt/gpt_pro/invite_queue.db'
QUEUE='/opt/gpt_pro/queue.txt'
HISTORY='/opt/gpt_pro/history.txt'
EMAIL_RE=re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')

def read_lines(path):
    out=[]
    with open(path,'r',encoding='utf-8',errors='ignore') as f:
        for line in f:
            for x in line.replace(',', '\n').split('\n'):
                x=x.strip().lower()
                if x: out.append(x)
    return out

def load_set(path, first_col=False):
    s=set()
    if not os.path.exists(path): return s
    with open(path,'r',encoding='utf-8',errors='ignore') as f:
        for line in f:
            line=line.strip()
            if not line: continue
            if first_col:
                line=line.split('\t')[0].strip()
            if line: s.add(line.lower())
    return s

if len(sys.argv)<2:
    print("用法: python3 /opt/gpt_pro/queue_add.py /path/to/emails.txt [--allow-history]")
    sys.exit(1)

src=sys.argv[1]
allow_history='--allow-history' in sys.argv
if not os.path.exists(src):
    print(f"文件不存在: {src}")
    sys.exit(1)

batch_tag=datetime.datetime.utcnow().strftime('bulk_%Y%m%d_%H%M%S')
now=datetime.datetime.utcnow().isoformat(timespec='seconds')+'Z'
raw=read_lines(src)

queue_set=load_set(QUEUE)
history_set=load_set(HISTORY, first_col=True)

conn=sqlite3.connect(DB)
c=conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS invite_jobs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL,
  status TEXT NOT NULL,
  source TEXT DEFAULT 'manual',
  batch_tag TEXT,
  retries INTEGER DEFAULT 0,
  last_error TEXT,
  account_index INTEGER,
  group_index INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  done_at TEXT
)""")
c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_email
             ON invite_jobs(email) WHERE status IN ('pending','processing')""")

pending_set=set(x[0] for x in c.execute("SELECT email FROM invite_jobs WHERE status IN ('pending','processing')"))

seen=set()
to_add=[]
bad=dup=hist=0

for e in raw:
    if e in seen: 
        dup+=1; continue
    seen.add(e)
    if not EMAIL_RE.match(e):
        bad+=1; continue
    if e in queue_set or e in pending_set:
        dup+=1; continue
    if (not allow_history) and e in history_set:
        hist+=1; continue
    to_add.append(e)

if to_add:
    with open(QUEUE,'a',encoding='utf-8') as f:
        for e in to_add:
            f.write(e+'\n')
    for e in to_add:
        c.execute("""INSERT OR IGNORE INTO invite_jobs(email,status,source,batch_tag,created_at,updated_at)
                     VALUES(?,?,?,?,?,?)""",(e,'pending','bulk',batch_tag,now,now))
    conn.commit()

pending=c.execute("SELECT COUNT(*) FROM invite_jobs WHERE status='pending'").fetchone()[0]
conn.close()

print(f"BATCH={batch_tag}")
print(f"输入={len(raw)} 去重后={len(seen)}")
print(f"新增={len(to_add)} 重复={dup} 历史跳过={hist} 无效邮箱={bad}")
print(f"当前待处理(PENDING)={pending}")
