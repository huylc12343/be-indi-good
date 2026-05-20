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
    print("DEBUG FULL BODY:", body)  # ← thêm dòng này
    print("DEBUG discount_code field:", repr(body.get("discount_code")))
    print("DEBUG discount_code_amount field:", repr(body.get("discount_code_amount")))
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

    subtotal_calc = 0.0

    for item in order_items:
        merch_id = item.get("merch_id")
        if not merch_id:
            return "Thiếu merch_id"

        try:
            quantity = int(item.get("quantity", 0))
        except (TypeError, ValueError):
            return "quantity phải là số nguyên"

        if quantity <= 0:
            return "Số lượng phải lớn hơn 0"

        try:
            unit_price = float(item.get("unit_price", 0))
        except (TypeError, ValueError):
            return "unit_price phải là số"

        if unit_price < 0:
            return "Giá sản phẩm không hợp lệ"

        try:
            item_subtotal = float(item.get("subtotal", 0))
        except (TypeError, ValueError):
            return "subtotal item phải là số"

        expected_item_subtotal = unit_price * quantity
        if not math.isclose(item_subtotal, expected_item_subtotal, rel_tol=1e-9):
            return f"Subtotal item không hợp lệ, expected {expected_item_subtotal}"

        # ✅ variant fields (optional)
        for field in ["selected_type", "selected_color", "selected_size"]:
            val = item.get(field)
            if val is not None and not isinstance(val, str):
                return f"{field} phải là chuỗi"

        subtotal_calc += expected_item_subtotal

    # ✅ subtotal tổng
    try:
        body_subtotal = float(body.get("subtotal", 0))
    except (TypeError, ValueError):
        return "subtotal phải là số"

    if not math.isclose(body_subtotal, subtotal_calc, rel_tol=1e-9):
        return f"Subtotal không hợp lệ, expected {subtotal_calc}"

    # ✅ shipping fee
    try:
        shipping_fee = float(body.get("shipping_fee", 0))
    except (TypeError, ValueError):
        return "shipping_fee phải là số"

    if shipping_fee < 0:
        return "Phí vận chuyển không hợp lệ"

    # ✅ discount code
    discount_code_amount = 0.0
    discount_code_value = body.get("discount_code") or body.get("discount_code_id")
    print(f"debug body = {body}")
    print(f"DEBUG discount_code_value={repr(discount_code_value)}")
    if discount_code_value:
        discount_code = get_discount_code_by_code(discount_code_value)
        if not discount_code:
            return "Mã giảm giá không tồn tại hoặc đã hết hạn"

        discount_code_amount = float(_calc_code_discount(discount_code, subtotal_calc))

        try:
            body_discount = float(body.get("discount_code_amount", 0))
        except (TypeError, ValueError):
            return "discount_code_amount phải là số"

        if not math.isclose(body_discount, discount_code_amount, rel_tol=1e-9):
            return f"Discount code amount không hợp lệ, expected {discount_code_amount}"

    # ✅ total
    expected_total = math.ceil(max(0.0, subtotal_calc + shipping_fee - discount_code_amount))

    try:
        body_total = int(float(body.get("total", 0)))
    except (TypeError, ValueError):
        return "total phải là số"
    print(f"DEBUG subtotal_calc={subtotal_calc}, shipping={shipping_fee}, discount={discount_code_amount}, expected={expected_total}, got={body_total}")

    if body_total != expected_total:
        return f"Total không hợp lệ, expected {expected_total}"
    return None


def _calc_code_discount(discount_code: dict, subtotal: float) -> int:
    min_order = float(discount_code.get("min_order_value", 0) or 0)
    if subtotal < min_order:
        return 0

    if discount_code.get("type") == "fixed":
        return int(float(discount_code.get("value", 0) or 0))  # ✅ float() trước rồi mới int()
    elif discount_code.get("type") == "percentage":
        return math.ceil(subtotal * float(discount_code.get("value", 0) or 0) / 100)

    return 0


def _calc_combo_discount(ticket_type: dict, quantity: int) -> int:
    tiers = ticket_type.get("discount_tiers", [])
    for tier in tiers:
        min_q = tier.get("min_quantity", 0)
        max_q = tier.get("max_quantity")
        if min_q <= quantity and (max_q is None or quantity <= max_q):
            return tier.get("discount_amount", 0)
    return 0