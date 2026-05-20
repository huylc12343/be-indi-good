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

        rows += f"""
        <tr>
          <td style="padding: 10px 0; font-size: 13px; color: #333;">
            <b>{qty:02d} x</b> {product_name}
          </td>
        </tr>
        """

    return rows or """
        <tr><td style="color:#999;">Không có sản phẩm</td></tr>
    """
    
def _build_email_html(order: dict) -> str:
    from utils.directus import get_products_by_ids

    customer_name = order.get("customer_name", "")
    customer_email = order.get("customer_email", "")
    customer_phone = order.get("customer_phone", "")
    customer_address = order.get("customer_address", "") or order.get("shipping_address", "")
    shipping_method = order.get("shipping_method", "")

    subtotal = _format_currency(order.get("subtotal", 0))
    discount = _format_currency(order.get("discount", 0))
    shipping_fee = _format_currency(order.get("shipping_fee", 0))
    total = _format_currency(order.get("total", 0))

    order_items = order.get("order_items", [])  # ← đổi merch_order_items → order_items
    # print("ORDER ITEMS:", order_items)  # ← xem structure thực tế

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
        discount=subtotal,
        shipping_fee=shipping_fee,
        total=total,
        order_items=order_items_html,
    )

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