import os
import time
import json
from mine.email_mine import email
from mine.requests_mine import send, isStart

# ================= 配置区 =================
# 所有数据文件统一以 main.py 所在目录（项目根目录）为基准，不再依赖"启动时的工作目录"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
BOOK_FILE = os.path.join(BASE_DIR, "book.txt")
DEFAULT_CONFIG = {
    "chunk_size": 20,  # 每次发送的弹幕长度
    "send_interval": 5,  # 发送间隔(秒)
    "poll_interval": 600,  # 开播/下播轮询间隔(秒)
    "ban_sleep": 3600 * 24,  # 被禁言后暂停时间(秒)
    "rate_limit_sleep": 600,  # 触发频率限制后暂停时间(秒)
    "max_consecutive_failures": 10,  # 连续发送失败多少次后终止
    "wait_for_live": True,  # 是否等主播开播后才开始发送（调试时可设 False）
}


def load_config():
    """加载配置，如果不存在则创建默认配置"""
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
        return DEFAULT_CONFIG
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_book():
    """读取并清洗小说文本"""
    if not os.path.exists(BOOK_FILE):
        raise FileNotFoundError(f"找不到小说文件: {BOOK_FILE}")
    with open(BOOK_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    # 去除所有空白字符
    return "".join(content.split())


def save_progress(remaining_text):
    """安全地保存进度到文件"""
    temp_file = BOOK_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(remaining_text)
    # 原子替换，防止写入一半时程序崩溃导致数据丢失
    os.replace(temp_file, BOOK_FILE)


def wait_for_stream():
    """阻塞等待主播开播"""
    print("等待主播开播...")
    while True:
        try:
            if isStart() == 1:
                email(text="检测到主播开播，说书人脚本启动", subject="说书人脚本")
                print("主播已开播，准备发送弹幕")
                return True
        except Exception as e:
            print(f"开播检测异常: {e}")
        time.sleep(CONFIG["poll_interval"])


def main():
    global CONFIG
    CONFIG = load_config()

    # 1. 加载文本并切分
    content = load_book()
    chunk_size = CONFIG["chunk_size"]
    chunks = [content[i : i + chunk_size] for i in range(0, len(content), chunk_size)]
    total = len(chunks)

    if total == 0:
        print("book.txt 已读完，请放入新小说后重新运行")
        return

    # 2. 等主播开播（原代码定义了 wait_for_stream 但从未调用，属于死代码）
    if CONFIG.get("wait_for_live", True):
        wait_for_stream()
    else:
        print("配置 wait_for_live=False，跳过开播等待，直接发送")

    i = 0  # 当前要发送的 chunk 下标，i 之前(不含 i)的都算已发送
    fail_streak = 0

    try:
        # 3. 核心发送循环：只有发送成功才推进 i，失败/限流一律重试本条，不丢段
        while i < total:
            chunk = chunks[i]

            # 每100条检查一次下播状态
            if i > 0 and i % 100 == 0:
                try:
                    if isStart() == 0:
                        email(
                            text=f"检测到炫神下播，说书人脚本暂停，共发送弹幕{i}条",
                            subject="说书人脚本",
                        )
                        print(f"主播下播，已发送 {i} 条")
                        save_progress("".join(chunks[i:]))
                        return
                    else:
                        print(f"[进度] {i}/{total} 条弹幕已发送，在播检测通过")
                except Exception as e:
                    print(f"在播检测异常: {e}")

            # 发送弹幕
            try:
                flag_api = send(chunk)
            except Exception as e:
                print(f"发送异常: {e}")
                flag_api = 4

            # 处理API返回状态
            if flag_api == 4:
                # 瞬时错误（网络/超时/解析失败）：重试本条，连续失败过多则终止
                fail_streak += 1
                if fail_streak >= CONFIG.get("max_consecutive_failures", 10):
                    email(
                        text=f"说书人脚本连续 {fail_streak} 次发送失败，已终止，请检查 cookie/csrf 是否过期",
                        subject="说书人脚本",
                    )
                    print(f"连续 {fail_streak} 次发送失败，终止运行")
                    save_progress("".join(chunks[i:]))
                    return
                print(f"第 {fail_streak} 次发送失败，{CONFIG['send_interval']} 秒后重试本条")
                time.sleep(CONFIG["send_interval"])
                continue
            elif flag_api == 0:
                print("API返回停止信号，脚本终止")
                break
            elif flag_api == 2:
                email(text="说书人脚本被禁言: 脚本暂停一天", subject="说书人脚本")
                save_progress("".join(chunks[i:]))
                print(f"触发禁言，休眠 {CONFIG['ban_sleep']} 秒后退出（下次运行从断点继续）")
                time.sleep(CONFIG["ban_sleep"])
                return
            elif flag_api == 3:
                print(f"触发频率限制，休眠 {CONFIG['rate_limit_sleep']} 秒后重试本条")
                time.sleep(CONFIG["rate_limit_sleep"])
                continue
            else:
                # 发送成功
                fail_streak = 0
                i += 1
                time.sleep(CONFIG["send_interval"])
    except KeyboardInterrupt:
        print("\n用户手动中断，保存进度...")
        save_progress("".join(chunks[i:]))
        return

    # 4. 循环结束（自然发完 或 API 停止信号），保存剩余进度
    save_progress("".join(chunks[i:]))
    email(text=f"说书人脚本本轮终止，共发送 {i} 条，剩余进度已保存", subject="说书人脚本")
    print(f"本轮发送完毕，共 {i} 条")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户手动中断")
    except Exception as e:
        print(f"脚本发生致命错误: {e}")
