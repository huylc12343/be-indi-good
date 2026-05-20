# jobs/send_order_email.py — full code với PDF đính kèm

import logging
import smtplib
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.utils import formatdate
from string import Template
from utils.config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    EMAIL_SENDER,
    EMAIL_SENDER_NAME,
    IMG_EMAIL_URL,
    EMAIL_DOMAIN,
)
from email.header import Header
from email.utils import formataddr

logger = logging.getLogger(__name__)


def _format_currency(amount: int) -> str:
    return f"{amount:,.0f}".replace(",", ".") + " đ"


def _build_email_html(order: dict) -> str:
    from utils.directus import get_ticket_type

    customer_name = order.get("customer_name", "")
    order_code = order.get("order_code", "")
    total = _format_currency(order.get("total", 0))

    order_items = order.get("order_items", [])
    ticket_type_name = ""
    quantity = 0
    if order_items:
        item = order_items[0]
        quantity = item.get("quantity", 0)

        # Fetch ticket type để lấy tên
        ticket_type_id = item.get("ticket_type_id")
        if ticket_type_id:
            ticket_type = get_ticket_type(ticket_type_id)
            if ticket_type:
                ticket_type_name = ticket_type.get("name", "")

    discount_code_amount = order.get("discount_code_amount", 0)
    if discount_code_amount:
        discount_label = f"- {_format_currency(discount_code_amount)}"
    else:
        discount_label = "Không có"

    with open("templates/order_email.html", "r", encoding="utf-8") as f:
        template = Template(f.read())

    return template.safe_substitute(
        BASE_URL=IMG_EMAIL_URL,
        customer_name=customer_name,
        order_code=order_code,
        ticket_type_name=ticket_type_name,
        quantity=quantity,
        discount_label=discount_label,
        total=total,
    )


def send_order_email(order_id: str):
    from utils.directus import get_order, get_tickets_by_order, update_order_status
    from utils.ticket_pdf import generate_ticket_pdf

    order = get_order(order_id)
    if not order:
        logger.error(f"send_order_email: order {order_id} not found")
        return

    tickets = get_tickets_by_order(order_id)
    if not tickets:
        logger.warning(f"send_order_email: no tickets found for order {order_id}")
        return

    customer_email = order.get("customer_email")
    if not customer_email:
        logger.error(f"send_order_email: no email for order {order_id}")
        return

    # Build email HTML
    html = _build_email_html(order)

    # Build email
    msg = MIMEMultipart("mixed")
    msg["Subject"] = "[In-đỉ In-đi] XÁC NHẬN ĐẶT VÉ THÀNH CÔNG"
    msg["From"] = formataddr((str(Header(EMAIL_SENDER_NAME, "utf-8")), EMAIL_SENDER))
    msg["To"] = customer_email
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = f"<{uuid.uuid4()}@{EMAIL_DOMAIN}>"
    msg["Content-Language"] = "vi"

    # alternative: mail client chỉ hiển thị 1 part, ưu tiên html
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText("Vui lòng dùng email client hỗ trợ HTML để xem email này.", "plain", "utf-8"))
    alt.attach(MIMEText(html, "html", "utf-8"))
    msg.attach(alt)

    # Gen và attach PDF cho từng ticket
    for ticket in tickets:
        try:
            filename, pdf_bytes = generate_ticket_pdf(ticket, order)
            attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
            attachment.add_header(
                "Content-Disposition",
                "attachment",
                filename=filename,
            )
            msg.attach(attachment)
            logger.info(f"send_order_email: attached {filename}")
        except Exception as e:
            logger.error(f"send_order_email: failed to gen PDF for ticket {ticket.get('id')}: {e}")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_SENDER, customer_email, msg.as_string())
        logger.info(f"send_order_email: sent to {customer_email} for order {order_id}")

        # Update order status → done
        update_order_status(order_id, "done")
        logger.info(f"send_order_email: order {order_id} → done")

    except Exception as e:
        logger.error(f"send_order_email: failed: {e}")
        raise e