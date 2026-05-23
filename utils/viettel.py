# utils/viettel.py
import httpx

LOGIN_URL = "https://partner.viettelpost.vn/v2/user/Login"
PRICE_URL = "https://partner.viettelpost.vn/v2/order/getPriceAllNlp"

USERNAME = "0787097309"
PASSWORD = "Linh123!@#"

SENDER_ADDRESS = "207 Giải Phóng, phường Đồng Tâm, quận Hai Bà Trưng, thành phố Hà Nội"


async def get_access_token() -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            LOGIN_URL,
            json={"USERNAME": USERNAME, "PASSWORD": PASSWORD},
            headers={"Cookie": "SERVERID=E"},
        )
        response.raise_for_status()

        data = response.json().get("data")
        if not data or not data.get("token"):
            raise ValueError("Không lấy được token ViettelPost")

        return data["token"]

import httpx

def calculate_shipping_fee(address: str, total_price: float) -> dict:
    with httpx.Client() as client:
        login = client.post(
            LOGIN_URL,
            json={"USERNAME": USERNAME, "PASSWORD": PASSWORD},
            headers={"Cookie": "SERVERID=E"},
        )
        login.raise_for_status()

        token = login.json()["data"]["token"]

        response = client.post(
            PRICE_URL,
            json={
                "SENDER_ADDRESS": SENDER_ADDRESS,
                "RECEIVER_ADDRESS": address,
                "PRODUCT_TYPE": "HH",
                "PRODUCT_WEIGHT": 1000,
                "PRODUCT_LENGTH": 30,
                "PRODUCT_WIDTH": 21,
                "PRODUCT_HEIGHT": 10,
                "PRODUCT_PRICE": total_price,
                "MONEY_COLLECTION": "0",
                "TYPE": 1,
            },
            headers={
                "Token": token,
                "Cookie": "SERVERID=E",
            },
        )

        response.raise_for_status()

        body = response.json()
        result = body.get("RESULT", [])

        if not result:
            raise ValueError("No shipping result")

        stk = next(
            (item for item in result if item.get("MA_DV_CHINH") == "STK"),
            result[0],
        )

        fee = stk.get("GIA_CUOC")

        return {"shipping_fee": fee}