# -*- coding: utf-8 -*-
"""
auth.py — Module xác thực OTP cho vcode
Giao tiếp với Cloudflare Worker để:
- Gửi OTP đến email @asia-plus.net
- Xác thực OTP và lấy session token
- Kiểm tra session còn hạn không
- Lấy OPENAI_API_KEY sau khi đã auth
"""
import hmac
import hashlib
import time
import os
import json
import requests

# ── Config (hard-coded, OPENAI_API_KEY vẫn bảo mật trong Cloudflare) ────────
_WORKER_URL  = "https://wkr-ai-coding.hung-daotuan-1991.workers.dev"
_APP_TOKEN   = "vcode2025XmP2xL8nQ5wR7jT4"
_HMAC_SECRET = "b7f3c9a4e2d84f1c" + "9a6b7e5d2f0a3c8b1d6e4f9a2c7b5e8d3f1a9c6b2e4d7f0"
ALLOWED_DOMAIN = "asia-plus.net"


def _sign() -> dict:
    """Tạo HMAC headers cho mỗi request"""
    worker_url  = os.environ.get("WORKER_URL",   _WORKER_URL)
    app_token   = os.environ.get("APP_TOKEN",    _APP_TOKEN)
    hmac_secret = os.environ.get("HMAC_SECRET",  _HMAC_SECRET)

    timestamp = str(int(time.time()))
    message   = f"{app_token}:{timestamp}".encode()
    signature = hmac.new(hmac_secret.encode(), message, hashlib.sha256).hexdigest()

    return {
        "worker_url": worker_url,
        "headers": {
            "X-App-Token":  app_token,
            "X-Timestamp":  timestamp,
            "X-Signature":  signature,
            "Content-Type": "application/json",
        }
    }


def _call(endpoint: str, body: dict) -> dict:
    """Gọi Worker endpoint"""
    ctx = _sign()
    try:
        resp = requests.post(
            ctx["worker_url"] + endpoint,
            headers=ctx["headers"],
            json=body,
            timeout=10
        )
        return resp.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Public API ───────────────────────────────────────────────────────────────

def is_valid_email(email: str) -> bool:
    """Kiểm tra email có đúng domain không"""
    return email.lower().strip().endswith(f"@{ALLOWED_DOMAIN}")


def send_otp(email: str) -> tuple[bool, str]:
    """
    Gửi OTP đến email.
    Returns: (success, message)
    """
    if not is_valid_email(email):
        return False, f"Chỉ chấp nhận email @{ALLOWED_DOMAIN}"

    result = _call("/send-otp", {"email": email})
    if result.get("ok"):
        return True, "OTP đã được gửi đến email của bạn"
    return False, result.get("error", "Không gửi được OTP")


def verify_otp(email: str, otp: str) -> tuple[bool, str, str]:
    """
    Xác thực OTP.
    Returns: (success, message, session_token)
    """
    result = _call("/verify-otp", {"email": email, "otp": otp})
    if result.get("ok"):
        return True, "Đăng nhập thành công", result.get("token", "")
    return False, result.get("error", "OTP không đúng"), ""


def check_session(token: str) -> tuple[bool, str]:
    """
    Kiểm tra session token còn hạn không.
    Returns: (valid, email)
    """
    if not token:
        return False, ""
    result = _call("/check-session", {"token": token})
    if result.get("ok"):
        return True, result.get("email", "")
    return False, ""


def get_openai_key(token: str) -> str:
    """
    Lấy OPENAI_API_KEY từ Worker (cần session hợp lệ).
    """
    result = _call("/get-key", {"token": token})
    if result.get("ok"):
        return result.get("key", "")
    return ""


def block_email(email: str) -> tuple[bool, str]:
    """Block email — không cho đăng nhập"""
    result = _call("/block-email", {"email": email})
    return result.get("ok", False), result.get("message", result.get("error", ""))


def unblock_email(email: str) -> tuple[bool, str]:
    """Unblock email"""
    result = _call("/unblock-email", {"email": email})
    return result.get("ok", False), result.get("message", result.get("error", ""))


def list_blocked() -> list[str]:
    """Lấy danh sách email bị block"""
    result = _call("/list-blocked", {})
    return result.get("emails", [])


def is_admin(email: str) -> bool:
    """Kiểm tra email có phải admin không (lưu trong KV)"""
    result = _call("/check-admin", {"email": email})
    return result.get("isAdmin", False)


def get_usage(days: int = 7) -> list[dict]:
    """Lấy thống kê usage theo email trong N ngày gần nhất"""
    result = _call("/get-usage", {"days": days})
    return result.get("usage", [])