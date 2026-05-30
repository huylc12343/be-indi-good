import requests
import hashlib
import hmac
import json

WEBHOOK_URL = "https://5zs7s6x0-5000.asse.devtunnels.ms/webhook/payos"

# ⚠️ thay bằng checksum key của PayOS bạn đang dùng
CHECKSUM_KEY = "94d3efac939e90e22c8d7bb518e6d7f9eeb74ffd4f067a29b2ce40ab4e4ce497"

def generate_signature(data: dict) -> str:
    import hmac
    import hashlib

    sorted_items = sorted(data.items())

    raw = "&".join(
        f"{k}={str(v).strip()}" for k, v in sorted_items if v is not None
    )

    print("RAW STRING:", raw)

    return hmac.new(
        CHECKSUM_KEY.encode(),
        raw.encode(),
        hashlib.sha256
    ).hexdigest()

def fake_webhook():
    data = {
        "accountNumber": "123456789",
        "amount": 28800,
        "description": "TEST ORDER",
        "reference": "test-ref",
        "transactionDateTime": "2026-05-23 10:00:00",
        "virtualAccountNumber": "VIRTUAL123",
        "counterAccountName": "TEST USER",
        "counterAccountNumber": "123456",
        "currency": "VND",
        "orderCode": 58504176,
        "paymentLinkId": "test-payment-link"
    }

    signature = generate_signature(data)

    payload = {
        "code": "00",
        "desc": "success",
        "success": True,
        "data": data,
        "signature": signature
    }

    res = requests.post(WEBHOOK_URL, json=payload)

    print("STATUS:", res.status_code)
    print("RESPONSE:", res.text)


if __name__ == "__main__":
    fake_webhook()