from celery import Celery
from playwright.sync_api import sync_playwright
from sqlalchemy import create_engine, text
import os
import json
import time
import redis

DB_URL = "postgresql://user:password@db/gptdb"
REDIS_URL = "redis://redis:6379/0"
engine = create_engine(DB_URL)
r_client = redis.Redis.from_url(REDIS_URL)

# Celery 配置
celery_app = Celery('worker', broker=REDIS_URL)

def get_available_master():
    # 简单的轮询逻辑：找一个人数<4的组
    with engine.connect() as conn:
        # 这里的SQL逻辑简化，实际需更严谨
        res = conn.execute(text("SELECT uuid, cookie FROM masters WHERE count < 4 LIMIT 1"))
        return res.fetchone()

def do_invite(uuid, cookie_str, email):
    print(f"🤖 启动浏览器邀请 {email} -> {uuid}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = browser.new_context()
        
        # 注入 Cookie
        cookies = json.loads(cookie_str)
        pw_cookies = []
        for c in cookies:
            if 'chatgpt.com' in c.get('domain',''):
                pw_cookies.append({'name':c['name'], 'value':c['value'], 'domain':'.chatgpt.com', 'path':'/'})
        ctx.add_cookies(pw_cookies)
        
        page = ctx.new_page()
        page.goto(f"https://chatgpt.com/c/{uuid}")
        page.wait_for_selector("textarea", timeout=30000)
        
        page.goto("https://chatgpt.com/admin/members")
        page.click("button:has-text('Invite')")
        page.fill("input[type='email']", email)
        page.keyboard.press("Enter")
        page.click("button:has-text('Send')")
        time.sleep(5)
        browser.close()
    return True

# 简单的轮询守护进程 (替代 Celery 复杂配置)
if __name__ == "__main__":
    print("🔥 机器人启动...")
    while True:
        # 从 Redis 列表取任务
        task_raw = r_client.rpop("invite_queue")
        if task_raw:
            task = json.loads(task_raw)
            email = task['email']
            
            master = get_available_master()
            if master:
                try:
                    do_invite(master[0], master[1], email)
                    # 成功后计数+1
                    with engine.connect() as conn:
                        conn.execute(text(f"UPDATE masters SET count = count + 1 WHERE uuid = '{master[0]}'"))
                        conn.commit()
                    print(f"✅ {email} 完成")
                except Exception as e:
                    print(f"❌ 失败: {e}")
            else:
                print("⚠️ 没有可用席位！任务放回队列")
                r_client.lpush("invite_queue", task_raw)
                time.sleep(60)
        else:
            time.sleep(2)
