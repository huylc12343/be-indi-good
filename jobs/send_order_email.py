# jobs/send_order_email.py

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate
from string import Template
from email.header import Header
from email.utils import formataddr
from utils.config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    EMAIL_SENDER, EMAIL_SENDER_NAME, IMG_EMAIL_URL,
)

logger = logging.getLogger(__name__)


def _format_currency(amount) -> str:
    try:
        return f"{int(float(amount)):,}".replace(",", ".") + "đ"
    except:
        return "0đ"

def _build_order_items_html(order_items: list, products_map: dict) -> str:
    rows = ""

    for item in order_items:
        merch_id = item.get("merch") or item.get("merch_id")
        qty = int(item.get("quantity") or 0)

        product = products_map.get(merch_id, {})
        product_name = product.get("name") or product.get("title") or "Sản phẩm"

        # Build variant suffix: tên_type_color_size nếu có
        variants = []
        if item.get("selected_type"):
            variants.append(item["selected_type"])
        if item.get("selected_color"):
            variants.append(item["selected_color"])
        if item.get("selected_size"):
            variants.append(item["selected_size"])

        display_name = "-".join([product_name] + variants) if variants else product_name

        rows += f"""
        <div style="
            font-size: 14px;
            color: #333;
            line-height: 20px;
            margin-bottom: 4px;
        ">
            <span style="display:inline-block; width: 40px;">
                {qty:02d} x
            </span>
            <span>{display_name}</span>
        </div>
        """

    return rows or "<div>Không có sản phẩm</div>"

def _build_email_html(order: dict) -> str:
    from utils.directus import get_products_by_ids

    customer_name = order.get("customer_name", "")
    customer_email = order.get("customer_email", "")
    customer_phone = order.get("customer_phone", "")
    # ✅ FIX: khai báo shipping_method_raw TRƯỚC khi dùng
    shipping_method_raw = order.get("shipping_method") or _detect_shipping_method(order)
    shipping_method = _format_shipping_method(shipping_method_raw)

    # ✅ luôn lấy address (áp dụng cho cả shipping + pickup)
    customer_address = order.get("customer_address") or order.get("shipping_address", "")

    subtotal = _format_currency(order.get("subtotal", 0))
    discount_combo = float(order.get("discount_combo") or 0)
    discount_code = float(order.get("discount_code_amount") or 0)

    discount_total = discount_combo + discount_code
    discount = _format_currency(discount_total)
    shipping_fee = _format_currency(order.get("shipping_fee", 0))
    total = _format_currency(order.get("total", 0))

    order_items = order.get("order_items", [])  # ← đổi merch_order_items → order_items
    # print("ORDER ITEMS:", order_items)  # ← xem structure thực tế
    print("CUSTOMER ADDRESS:", customer_address)  # ← xem field nào có address
    merch_ids = [
        item.get("merch") or item.get("merch_id")
        for item in order_items
        if item.get("merch") or item.get("merch_id")
    ]
    # print("MERCH IDS:", merch_ids)  # ← xem ids lấy được

    products_map = get_products_by_ids(merch_ids)
    # print("PRODUCTS MAP:", products_map)  # ← xem fetch được gì

    order_items_html = _build_order_items_html(order_items, products_map)

    with open("templates/order_email.html", "r", encoding="utf-8") as f:
        template = Template(f.read())

    return template.safe_substitute(
        BASE_URL=IMG_EMAIL_URL,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        customer_address=customer_address,
        shipping_method=shipping_method,
        subtotal=subtotal,
        discount=discount,
        shipping_fee=shipping_fee,
        total=total,
        order_items=order_items_html,
    )
def _detect_shipping_method(order: dict) -> str:
    if float(order.get("shipping_fee", 0)) > 0:
        return "shipping"
    return "pickup"
def _format_shipping_method(method: str) -> str:
    if method == "shipping":
        return "Giao hàng tận nơi"
    elif method == "pickup":
        return "Nhận tại sự kiện/ nhận tại bụi rock"
    return "Không xác định"
def send_order_email(order_id: str):
    import requests
    from utils.config import DIRECTUS_URL, DIRECTUS_TOKEN

    headers = {
        "Authorization": f"Bearer {DIRECTUS_TOKEN}",
        "Content-Type": "application/json",
    }

    res = requests.get(
        f"{DIRECTUS_URL}/items/merch_orders/{order_id}",
        headers=headers,
        params={"fields": "*, order_items.*"},  # ← đổi merch_order_items → order_items
    )
    res.raise_for_status()
    order = res.json().get("data")
    # print("ALL ORDER KEYS:", list(order.keys()))
    # print("RAW ORDER:", order)  # xem full data
    print("FETCHED ORDER:", order)
    print("FETCHED customer_address:", order.get("customer_address"))
    if not order:
        logger.error(f"send_order_email: order {order_id} not found")
        return

    customer_email = order.get("customer_email")
    if not customer_email:
        logger.error(f"send_order_email: no email for order {order_id}")
        return

    customer_name = order.get("customer_name", "")
    html_content = _build_email_html(order)
    text_content = f"Xin chào {customer_name}, đơn hàng của bạn đã thanh toán thành công. Mã đơn: {order.get('order_code', '')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "[In-đỉ In-đi] Thanh toán thành công"
    msg["From"] = formataddr((str(Header(EMAIL_SENDER_NAME, "utf-8")), EMAIL_SENDER))
    msg["To"] = customer_email
    msg["Date"] = formatdate(localtime=True)

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_SENDER, customer_email, msg.as_string())
        logger.info(f"send_order_email: sent to {customer_email}")
    except Exception as e:
        logger.error(f"send_order_email: failed: {e}")
        raise