import os
import json
import time
import requests
from dotenv import load_dotenv
from mine.email_mine import email

# ================= 敏感配置：.env =================
# 项目根目录：本文件在 mine/ 子目录，.env 与 main.py 都在根目录这一层
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 从项目根目录的 .env 加载 B站 Cookie / CSRF / 房间号 等配置（模板见 .env.example）
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _env(name):
    """读取环境变量，缺失时给出明确的报错提示，方便排查配置问题"""
    try:
        return os.environ[name]
    except KeyError:
        raise SystemExit(f"[配置缺失] .env 中没有 {name}，请参照 .env.example 补齐") from None


# B站登录 Cookie（整段，含 SESSDATA 等；过期需重新复制到根目录的 .env）
cookie = _env("BILIBILI_COOKIE")
# CSRF Token（即 Cookie 里的 bili_jct），用于弹幕发送校验
csrf = _env("BILIBILI_CSRF")
# 目标直播间房间号（在 .env 里修改即可，无需改代码）
room_id = int(_env("BILIBILI_ROOM_ID"))


def send(msg):
    """
    返回码约定:
      0 = 需要人工处理的错误(如 csrf 失效/未登录)，终止脚本
      1 = 发送成功
      2 = 被禁言
      3 = 频率限制/系统升级中，稍后重试本条
      4 = 瞬时错误(网络/超时/响应解析失败)，稍后重试本条
    """
    url = "https://api.live.bilibili.com/msg/send"

    data = {
        "bubble": "0",
        "msg": msg,
        "color": "16777215",
        "mode": "1",
        "room_type": "0",
        "jumpfrom": "84002",
        "reply_mid": "0",
        "fontsize": "25",
        "rnd": str(int(time.time())),  # ← 动态时间戳
        "roomid": str(room_id),  # ← 统一变量，不要写死
        "csrf": csrf,
        "csrf_token": csrf,
    }

    headers = {
        "cookie": cookie,
        "origin": "https://live.bilibili.com",  # ← 必须加
        "referer": f"https://live.bilibili.com/{room_id}",  # ← 必须加
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.55",
        "content-type": "application/x-www-form-urlencoded",  # ← 建议加
    }

    try:
        response = requests.post(url=url, data=data, headers=headers, timeout=10)
        tmp = response.text
        message = json.loads(tmp)
    except Exception as e:
        # 网络异常/超时/返回非JSON：属于瞬时错误，返回 4 让主循环重试本条
        print(f"发送请求异常: {e}")
        return 4

    code = message.get("code")
    msg_text = message.get("message", "")

    # 只有发送失败（code<0 或 message 非空）时才打印 B站原始返回，便于排查；
    # 发送成功时静默，避免控制台被超长 JSON 刷屏
    if code < 0 or msg_text:
        print(tmp)

    if code < 0:
        email(
            text="说书人脚本异常终止: \n" + str(message),
            subject="说书人脚本",
        )
        return 0
    elif msg_text == "你被禁言啦":
        email(
            text=f"说书人脚本异常: {msg_text},脚本暂停一天",
            subject="说书人脚本",
        )
        return 2
    elif msg_text == "系统升级中":
        email(text=f"说书人脚本异常: {msg_text}", subject="说书人脚本")
        return 3
    else:
        return 1


def isStart():
    url = f"https://api.live.bilibili.com/room/v1/Room/get_info?room_id={room_id}"
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.55",
    }
    response = requests.get(url=url, headers=headers, timeout=10)
    ans = json.loads(response.text)
    flag = ans["data"]["live_status"]
    return flag
