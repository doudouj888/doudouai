from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base
from pydantic import BaseModel
import os
import redis
import json
import uuid

# --- 配置 ---
DB_URL = "postgresql://user:password@db/gptdb"
REDIS_URL = "redis://redis:6379/0"

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
r_client = redis.Redis.from_url(REDIS_URL)

# --- 数据库模型 ---
class License(Base):
    __tablename__ = "licenses"
    code = Column(String, primary_key=True)
    status = Column(String, default="unused") # unused, used
    email = Column(String)

class Master(Base):
    __tablename__ = "masters"
    uuid = Column(String, primary_key=True)
    cookie = Column(String)
    count = Column(Integer, default=0)

# 初始化表
Base.metadata.create_all(bind=engine)

app = FastAPI()

# --- API ---
class RedeemReq(BaseModel):
    code: str
    email: str

@app.post("/api/redeem")
def redeem(req: RedeemReq):
    db = SessionLocal()
    # 1. 验卡
    lic = db.query(License).filter(License.code == req.code, License.status == "unused").first()
    if not lic:
        db.close()
        raise HTTPException(400, "无效卡密")
    
    # 2. 标记使用
    lic.status = "used"
    lic.email = req.email
    db.commit()
    
    # 3. 放入队列
    task = {"email": req.email}
    r_client.lpush("invite_queue", json.dumps(task))
    db.close()
    return {"success": True}

# --- 简易管理员接口 (初始化数据用) ---
@app.post("/admin/init")
def init_data(cookie: str, uuids: str):
    db = SessionLocal()
    # 清空旧号
    db.query(Master).delete()
    for uid in uuids.split('\n'):
        if uid.strip():
            db.add(Master(uuid=uid.strip(), cookie=cookie))
    
    # 生成测试卡密
    db.query(License).delete()
    db.add(License(code="GPT-TEST-8888"))
    db.commit()
    db.close()
    return {"msg": "初始化完成"}

@app.get("/")
def home():
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>GPT 兑换</title>
    <style>body{background:#111;color:white;display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif} 
    .box{background:#222;padding:40px;border-radius:20px;text-align:center}
    input{display:block;width:100%;margin:10px 0;padding:10px;border-radius:5px;border:none}
    button{background:blue;color:white;padding:10px 20px;border:none;border-radius:5px;cursor:pointer}</style>
    </head>
    <body>
    <div class="box">
        <h1>GPT Team 激活</h1>
        <input id="c" placeholder="卡密"><input id="e" placeholder="邮箱">
        <button onclick="sub()">兑换</button>
    </div>
    <script>
    async function sub(){
        let c=document.getElementById('c').value, e=document.getElementById('e').value;
        let res = await fetch('/api/redeem', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({code:c, email:e})});
        let dat = await res.json();
        alert(dat.success ? '成功！排队中' : dat.detail);
    }
    </script>
    </body></html>
    """
    return HTMLResponse(html)
