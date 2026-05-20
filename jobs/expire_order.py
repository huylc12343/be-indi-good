# jobs/expire_order.py
from utils.directus import get_order, cancel_order
import logging

logger = logging.getLogger(__name__)


def expire_order(order_id: str):
    order = get_order(order_id)

    if not order:
        logger.warning(f"Order {order_id} not found")
        return

    # ✅ chỉ xử lý nếu vẫn chưa thanh toán
    if order["status"] != "init":
        logger.info(f"Order {order_id} is {order['status']}, skip")
        return

    # ❌ merch không cần release ticket
    cancel_order(order_id)

    logger.info(f"Order {order_id} expired and cancelled")