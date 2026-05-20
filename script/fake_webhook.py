import requests

url = "https://5zs7s6x0-5000.asse.devtunnels.ms/webhook/payos"

payload = {
    "test": "hello"
}

headers = {
    "Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

print("Status:", response.status_code)

# tránh lỗi nếu response không phải JSON
try:
    print("Response:", response.json())
except:
    print("Raw response:", response.text)