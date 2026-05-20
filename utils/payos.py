import json
import hashlib
import hmac
import requests
from utils.config import PAYOS_CLIENT_ID, PAYOS_API_KEY, PAYOS_CHECKSUM_KEY


def _sort_obj_by_key(obj: dict) -> dict:
    return dict(sorted(obj.items()))


def _convert_obj_to_query_str(obj: dict) -> str:
    parts = []
    for key, value in obj.items():
        if isinstance(value, bool):
            value_str = str(value).lower()
        elif isinstance(value, (int, float)):
            value_str = str(value)
        elif value in [None, "null", "undefined"]:
            value_str = ""
        elif isinstance(value, list):
            value_str = json.dumps(
                [_sort_obj_by_key(i) if isinstance(i, dict) else i for i in value],
                separators=(",", ":"),
                ensure_ascii=False,
            )
        else:
            value_str = str(value)
        parts.append(f"{key}={value_str}")
    return "&".join(parts)


def verify_webhook_signature(data: dict, signature: str) -> bool:
    sorted_data = _sort_obj_by_key(data)
    query_str = _convert_obj_to_query_str(sorted_data)
    expected = hmac.new(
        PAYOS_CHECKSUM_KEY.encode("utf-8"),
        query_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _create_signature(order_code, amount, desc, cancel_url, return_url):
    raw = "&".join([
        f"amount={amount}",
        f"cancelUrl={cancel_url}",
        f"description={desc}",
        f"orderCode={order_code}",
        f"returnUrl={return_url}",
    ])
    return hmac.new(
        PAYOS_CHECKSUM_KEY.encode(),
        raw.encode(),
        hashlib.sha256,
    ).hexdigest()


def create_payos_payment(order_code: int, amount: int, expires_at):
    cancel_url = "http://localhost:3000/cancel"
    return_url = "http://localhost:3000/success"
    desc = f"DH{str(order_code)[-6:]}"

    amount = int(amount)
    order_code = int(order_code)

    signature = _create_signature(order_code, amount, desc, cancel_url, return_url)

    payload = {
        "orderCode": order_code,
        "amount": amount,
        "description": desc,
        "cancelUrl": cancel_url,
        "returnUrl": return_url,
        "expiredAt": int(expires_at.timestamp()),
        "signature": signature,
    }

    res = requests.post(
        "https://api-merchant.payos.vn/v2/payment-requests",
        json=payload,
        headers={
            "x-client-id": PAYOS_CLIENT_ID,
            "x-api-key": PAYOS_API_KEY,
            "Content-Type": "application/json",
        },
        timeout=10,
    )

    data = res.json()

    if data.get("code") != "00":
        raise Exception(f"PayOS error: {data}")

    return {
        "checkoutUrl": data["data"]["checkoutUrl"],
        "paymentLinkId": data["data"]["paymentLinkId"],
        "qr_code": data["data"]["qrCode"],
        "amount": amount,
        "description": desc,
        "bin": data["data"].get("bin", ""),
        "account_name": data["data"].get("accountName", ""),
        "account_number": data["data"].get("accountNumber", ""),
    }