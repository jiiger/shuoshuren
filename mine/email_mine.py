import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

# ================= 邮件配置：.env =================
# 与 requests_mine.py 共用项目根目录的 .env（本文件在 mine/ 子目录，.env 在其上一级）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _env(name):
    """读取环境变量，缺失时给出明确报错提示，方便排查配置问题"""
    try:
        return os.environ[name]
    except KeyError:
        raise SystemExit(f"[配置缺失] .env 中没有 {name}，请参照 .env.example 补齐") from None


# 发件邮箱 SMTP 配置（账号信息统一放在项目根目录的 .env，代码里不再写死）
mail_host = os.environ.get("QQ_MAIL_HOST", "smtp.qq.com")  # SMTP 服务器（QQ 邮箱固定值）
mail_port = int(os.environ.get("QQ_MAIL_PORT", "465"))     # SSL 加密端口（QQ 邮箱固定值）
mail_user = _env("QQ_MAIL_USER")                           # 发件 QQ 号（不含 @qq.com）
# 注意：QQ 邮箱 SMTP 登录必须使用"授权码"，不是 QQ 登录密码！
mail_pass = _env("QQ_MAIL_AUTH_CODE")                      # SMTP 授权码
sender = _env("QQ_MAIL_SENDER")                            # 发件邮箱完整地址


def email(
    text,
    subject,
    receivers=None,
):
    if receivers is None:
        # 通知接收邮箱：.env 的 QQ_MAIL_RECEIVERS，多个用英文逗号分隔
        receivers = [
            r.strip()
            for r in _env("QQ_MAIL_RECEIVERS").split(",")
            if r.strip()
        ]
        if not receivers:
            raise SystemExit("[配置缺失] .env 的 QQ_MAIL_RECEIVERS 为空，请填写接收邮箱")

    message = MIMEText(text, "plain", "utf-8")
    # 邮件主题
    message["Subject"] = subject
    # 发送方信息
    message["From"] = sender
    # 接受方信息
    message["To"] = receivers[0]

    try:
        # 直接以 SSL 连接 mail_port 端口（SMTP_SSL(host) 已自动完成连接，无需再 connect 一次）
        smtpObj = smtplib.SMTP_SSL(mail_host, mail_port, timeout=10)
        # 登录到服务器
        smtpObj.login(mail_user, mail_pass)
        # 发送
        smtpObj.sendmail(sender, receivers, message.as_string())
        # 退出
        smtpObj.quit()
        print(text + "  ||  邮件通知发送成功")
    except Exception as e:
        print(f"邮件发送失败: {e}（QQ 邮箱需在设置中开启 SMTP 并填写授权码，不是登录密码）")
