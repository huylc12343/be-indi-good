import requests
import json

BASE_URL = "https://5zs7s6x0-5000.asse.devtunnels.ms/"  # đổi nếu bạn deploy

def test_send_email(order_code, amount):
    url = f"{BASE_URL}/webhook/payos"

    payload = {
        "code": "00",  # bắt buộc để vào flow success
        "data": {
            "orderCode": order_code,  # 🔥 phải đúng order_code DB
            "amount": amount          # 🔥 phải đúng total DB
        },
        "signature": "test_signature"  # sẽ fail nếu verify thật
    }

    print("🚀 Sending request...")
    print(json.dumps(payload, indent=2))

    res = requests.post(url, json=payload)

    print("\n📥 RESPONSE")
    print("Status:", res.status_code)
    print("Body:", res.text)


if __name__ == "__main__":
    # 🔥 thay bằng order thật của bạn
    ORDER_CODE = "12345678"
    AMOUNT = 2500

    test_send_email(ORDER_CODE, AMOUNT)