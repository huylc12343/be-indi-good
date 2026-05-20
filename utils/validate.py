# utils/validate.py
import re
import math
from utils.directus import get_discount_code_by_code

PHONE_NUMBER_REGEX = re.compile(r'^(?:\+84|0084|0)[235789][0-9]{1,2}[0-9]{7}$')
EMAIL_REGEX = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


def validate_email(email: str) -> str | None:
    if not EMAIL_REGEX.match(email):
        return "Email không đúng định dạng"
    return None


def validate_phone(phone: str) -> str | None:
    if not PHONE_NUMBER_REGEX.match(phone):
        return "Số điện thoại không đúng định dạng"
    return None


def validate_order(body: dict) -> str | None:
    """
    Validate đơn hàng merch
    """

    # ✅ Email
    email_err = validate_email(body.get("customer_email", ""))
    if email_err:
        return email_err

    # ✅ Phone
    phone_err = validate_phone(body.get("customer_phone", ""))
    if phone_err:
        return phone_err

    # ✅ Address
    if not body.get("customer_address"):
        return "Địa chỉ không được để trống"

    # ✅ order_items
    order_items = body.get("order_items", [])
    if not order_items:
        return "Cần ít nhất 1 sản phẩm"

    subtotal_calc = 0

    for item in order_items:
        merch_id = item.get("merch_id")
        quantity = item.get("quantity", 0)
        quantity = item.get("quantity", 0)

        try:
            quantity = int(quantity)
        except:
            return "quantity must be a number"

        if quantity <= 0:
            return "quantity must be greater than 0"
        
        unit_price = item.get("unit_price", 0)
        try:
            unit_price = float(unit_price)
        except:
            return "unit_price must be a number"

        if unit_price <= 0:
            return "unit_price must be greater than 0"
        subtotal = item.get("subtotal", 0)

        if not merch_id:
            return "Thiếu merch_id"

        if quantity <= 0:
            return "Số lượng phải lớn hơn 0"

        if unit_price <= 0:
            return "Giá sản phẩm không hợp lệ"

        expected_subtotal = unit_price * quantity

        if subtotal != expected_subtotal:
            return f"Subtotal item không hợp lệ, expected {expected_subtotal}"

        subtotal_calc += expected_subtotal

    # ✅ subtotal tổng
    if body.get("subtotal") != subtotal_calc:
        return f"Subtotal không hợp lệ, expected {subtotal_calc}"

    # ✅ discount code
    discount_code_amount = 0
    discount_code_value = body.get("discount_code")

    if discount_code_value:
        discount_code = get_discount_code_by_code(discount_code_value)
        if not discount_code:
            return "Mã giảm giá không tồn tại hoặc đã hết hạn"

        discount_code_amount = _calc_code_discount(discount_code, subtotal_calc)

        if body.get("discount_code_amount", 0) != discount_code_amount:
            return f"Discount code amount không hợp lệ, expected {discount_code_amount}"

    # ✅ shipping fee
    shipping_fee = body.get("shipping_fee", 0)
    if shipping_fee < 0:
        return "Phí vận chuyển không hợp lệ"

    # ✅ total
    expected_total = max(
        0,
        math.ceil(subtotal_calc + shipping_fee - discount_code_amount)
    )

    if body.get("total") != expected_total:
        return f"Total không hợp lệ, expected {expected_total}"

    return None
def _calc_combo_discount(ticket_type: dict, quantity: int) -> int:
    tiers = ticket_type.get("discount_tiers", [])
    for tier in tiers:
        min_q = tier.get("min_quantity", 0)
        max_q = tier.get("max_quantity")
        if min_q <= quantity and (max_q is None or quantity <= max_q):
            return tier.get("discount_amount", 0)
    return 0


def _calc_code_discount(discount_code: dict, subtotal: int) -> int:
    min_order = discount_code.get("min_order_value", 0)
    if subtotal < min_order:
        return 0

    if discount_code.get("type") == "fixed":
        return discount_code.get("value", 0)
    elif discount_code.get("type") == "percentage":
        return math.ceil(subtotal * discount_code.get("value", 0) / 100)  # ceil

    return 0