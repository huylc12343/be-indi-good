import os
from datetime import datetime
import requests
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

DIRECTUS_URL = os.getenv("DIRECTUS_URL")
DIRECTUS_TOKEN = os.getenv("DIRECTUS_TOKEN")

if not DIRECTUS_URL or not DIRECTUS_TOKEN:
    raise RuntimeError("DIRECTUS_URL hoặc DIRECTUS_TOKEN chưa được set trong .env")

DIRECTUS_HEADERS = {
    "Authorization": f"Bearer {DIRECTUS_TOKEN}",
    "Content-Type": "application/json",
}


def create_order(payload: dict):
    payload["order_id"] = "DH" + str(datetime.now().timestamp()).split(".")[0][-6:]
    payload["payos_order_code"] = payload["order_id"]
    payload["order_code"] = payload["order_code"]
    
    res = requests.post(
        f"{DIRECTUS_URL}/items/merch_orders",
        headers=DIRECTUS_HEADERS,
        json=payload,
    )
    print("CREATE ORDER STATUS:", res.status_code)
    print("CREATE ORDER RESPONSE:", res.text)
    res.raise_for_status()
    if res.status_code not in [200, 201]:
        raise HTTPException(status_code=500, detail=res.text)
    return res.json()["data"]


def create_order_item(payload: dict):
    res = requests.post(
        f"{DIRECTUS_URL}/items/merch_order_items",
        headers=DIRECTUS_HEADERS,
        json=payload,
    )
    print("CREATE ITEM STATUS:", res.status_code)
    print("CREATE ITEM RESPONSE:", res.text)
    if res.status_code not in [200, 201]:
        raise HTTPException(status_code=res.status_code, detail=res.text)
    return res.json()["data"]

def get_product(merch_id: str):
    res = requests.get(
        f"{DIRECTUS_URL}/items/merch/{merch_id}",
        headers=DIRECTUS_HEADERS,
    )
    res.raise_for_status()
    return res.json()["data"]
def get_products_by_ids(merch_ids: list):
    if not merch_ids:
        return {}

    res = requests.get(
        f"{DIRECTUS_URL}/items/merch",
        headers=DIRECTUS_HEADERS,
        params={
            "filter[id][_in]": ",".join(map(str, merch_ids)),
            "fields": "*",
        }
    )

    res.raise_for_status()
    data = res.json().get("data", [])

    # convert thành dict cho dễ lookup
    return {item["id"]: item for item in data}
def get_order(order_id: str):
    res = requests.get(
        f"{DIRECTUS_URL}/items/merch_orders/{order_id}",
        headers=DIRECTUS_HEADERS,
        params={"fields[]": ["*", "merch_order_items.*"]},
    )
    res.raise_for_status()
    return res.json()["data"]


def get_order_by_code(order_code: str):
    res = requests.get(
        f"{DIRECTUS_URL}/items/merch_orders",
        headers=DIRECTUS_HEADERS,
        params={
            "filter[order_code][_eq]": order_code,
            "fields[]": ["*", "merch_order_items.*"],
            "limit": 1,
        },
    )
    print("GET ORDER BY CODE STATUS:", res.status_code)
    print("GET ORDER BY CODE URL:", res.url)
    print("GET ORDER BY CODE RESPONSE:", res.text)
    res.raise_for_status()
    data = res.json().get("data", [])
    return data[0] if data else None


def update_order_status(order_id: str, status: str):
    res = requests.patch(
        f"{DIRECTUS_URL}/items/merch_orders/{order_id}",
        headers=DIRECTUS_HEADERS,
        json={"status": status},
    )
    res.raise_for_status()


def cancel_order(order_id: str):
    update_order_status(order_id, "cancel")


def get_discount_code_by_code(code: str):
    res = requests.get(
        f"{DIRECTUS_URL}/items/discount_codes",
        headers=DIRECTUS_HEADERS,
        params={
            "filter[code][_eq]": code,
            "filter[status][_eq]": "available",
            "fields": "*",
        },
    )
    print("DISCOUNT STATUS:", res.status_code)
    print("DISCOUNT RESPONSE:", res.text)
    res.raise_for_status()
    data = res.json().get("data", [])
    return data[0] if data else None


def get_order_by_payos_code(order_code: int):
    res = requests.get(
        f"{DIRECTUS_URL}/items/merch_orders",
        headers=DIRECTUS_HEADERS,
        params={
            "filter[payos_order_code][_eq]": order_code,
            "limit": 1,
        },
    )
    res.raise_for_status()
    data = res.json().get("data", [])
    return data[0] if data else None