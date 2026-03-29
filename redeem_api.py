#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
兑换接口服务 redeem_api.py

功能：
1. 接收前端 /api/redeem 请求（POST，JSON：{code, email}）
2. 检查卡密是否存在、是否未使用
3. 先把邮箱写入 queue.txt
4. 写队列成功后，再把该卡密标记为 used，并记录：
   - 使用邮箱 email
   - 使用时间（北京时间）
5. 所有返回格式：{"success": True/False, "message": "xxx"}
"""

import os
import json
from datetime import datetime, timedelta, timezone

from flask import Flask, request, jsonify

import fcntl
from contextlib import contextmanager

# 文件路径配置（和 app.py / worker.py 保持一致）
QUEUE_FILE = "queue.txt"
LICENSE_FILE = "licenses.json"
LICENSE_LOCK_FILE = LICENSE_FILE + ".lock"
REDEEM_LOG_FILE = "redeem_log.txt"

app = Flask(__name__)


@contextmanager
def locked_open(path, mode):
    """
    给 queue.txt 用的简单文件锁，和 worker.py 保持一致。
    """
    f = open(path, mode, encoding="utf-8")
    try:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield f
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


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
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


# ---------- 工具函数 ----------

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
    1）老格式： "GPT-XXXX": "unused" / "used"
    2）新格式： "GPT-XXXX": {"status": "used", "email": "...", "time": "..."}
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


def get_beijing_time_str() -> str:
    """返回当前北京时间字符串，例如：2025-11-23 21:10:00 +0800"""
    tz_bj = timezone(timedelta(hours=8))
    now_bj = datetime.now(tz_bj)
    return now_bj.strftime("%Y-%m-%d %H:%M:%S %z")


def append_redeem_log(code: str, email: str):
    """把成功兑换记录写入 redeem_log.txt：北京时间 | 卡密 | 邮箱"""
    try:
        ts = get_beijing_time_str()
        line = f"{ts}\t{code}\t{email}\n"
        with open(REDEEM_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        # 日志失败不影响业务
        pass


# ---------- 核心接口：/api/redeem ----------

@app.route("/api/redeem", methods=["POST"])
def api_redeem():
    # 1. 取参数
    data = request.get_json(force=True, silent=True) or {}
    code = (data.get("code") or "").strip().upper()
    email = (data.get("email") or "").strip()

    # 基础校验
    if not code or not email:
        return jsonify({"success": False, "message": "卡密和邮箱不能为空"}), 400

    if "@" not in email or "." not in email:
        return jsonify({"success": False, "message": "邮箱格式不正确，请检查后再试。"}), 400

    # 下面所有对 licenses.json 的操作都放在锁里，避免并发覆盖
    with locked_license():
        # 2. 读 licenses.json，检查卡密状态
        db = load_licenses()
        entry = db.get(code)

        if entry is None:
            return jsonify({"success": False, "message": "卡密不存在或填写错误，请核对后再试。"}), 400

        status = get_status_from_entry(entry)
        if status != "unused":
            # 已使用：如果是新格式，尽量把使用邮箱/时间也提示出来
            used_email = ""
            used_time = ""
            if isinstance(entry, dict):
                used_email = entry.get("email", "")
                used_time = entry.get("time", "")

            msg = "该卡密已被使用"
            if used_email:
                msg += f"，使用邮箱：{used_email}"
            if used_time:
                msg += f"，时间：{used_time}"
            msg += "。如有疑问请联系商家。"

            return jsonify({"success": False, "message": msg}), 400

        # 3. 先写队列 queue.txt（非常关键，避免“卡密已用但没排队”的情况）
        try:
            # 用锁，避免和 worker.py 同时改队列导致丢数据
            with locked_open(QUEUE_FILE, "a+") as f:
                f.write(email + "\n")
                f.flush()
        except Exception:
            # 写队列失败，坚决不能把卡密标记为 used
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "服务器写入队列失败，请稍后重试（卡密尚未消耗，可以再次尝试兑换）。",
                    }
                ),
                500,
            )

        # 4. 队列写成功之后，标记卡密为 used，并记录邮箱 + 北京时间
        used_info = {
            "status": "used",
            "email": email,
            "time": get_beijing_time_str(),  # 北京时间
        }
        db[code] = used_info

        try:
            save_licenses(db)
        except Exception:
            # 极端情况：队列已经写进去了，但保存 licenses 失败
            # 这种情况下，用户其实已经排队成功，所以我们仍然返回成功
            append_redeem_log(code, email)
            return jsonify(
                {
                    "success": True,
                    "message": "兑换成功（已进入排队），但记录文件保存异常，如有问题请联系管理员。",
                }
            )

        # 到这里表示队列 + licenses 都处理成功，记一条兑换日志
        append_redeem_log(code, email)

    # 5. 正常返回
    return jsonify(
        {
            "success": True,
            "message": "兑换成功，已进入排队，请等待邮箱邀请（通常 1–15 分钟）。",
        }
    )


# ---------- 启动服务 ----------

if __name__ == "__main__":
    # 监听 0.0.0.0:5000，nginx 会反向代理到这里
    app.run(host="0.0.0.0", port=5000)
