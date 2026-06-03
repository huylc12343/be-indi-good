from gevent import monkey
monkey.patch_all()
import json
import os
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, join_room
from redis import Redis
from rq import Queue
from nanoid import generate
from utils.viettel import calculate_shipping_fee
from utils.config import FLASK_DEBUG, REDIS_URL, ORDER_EXPIRE_SECONDS, CORS_ORIGINS
from utils.directus import (
    create_order, create_order_item, get_order, get_order_by_code,
    update_order_status, cancel_order, get_discount_code_by_code,increate_discount_code_usage
)
from utils.payos import verify_webhook_signature, create_payos_payment
from utils.validate import validate_order
from jobs.expire_order import expire_order
# from flask_limiter import Limiter, RequestLimit

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_order_code():
    first = generate('123456789', 1)
    rest = generate('0123456789', 7)
    return first + rest


app = Flask(__name__)
if CORS_ORIGINS:
    CORS(app, origins=CORS_ORIGINS.split(","))
else:
    CORS(app)


def get_real_ip():
    return request.headers.get("X-Real-IP") or request.remote_addr


# limiter = Limiter(
#     app=app,
#     key_func=get_real_ip,
#     storage_uri=REDIS_URL,
#     default_limits=[],
# )

redis_conn = Redis.from_url(REDIS_URL)
q = Queue(connection=redis_conn)


def handle_order_breach(request_limit: RequestLimit):
    ip = get_real_ip()
    try:
        if not redis_conn.exists(f"blocked:{ip}"):
            redis_conn.setex(f"blocked:{ip}", 12 * 3600, 1)
            logger.warning(f"IP {ip} blocked for 12 hours due to repeated order attempts")
    except Exception as e:
        logger.error(f"Failed to block IP {ip}: {e}")


socketio = SocketIO(
    app,
    cors_allowed_origins=CORS_ORIGINS.split(",") if CORS_ORIGINS else "*",
    message_queue=REDIS_URL,
    async_mode="gevent",
)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/orders", methods=["POST"])
# @limiter.limit("5 per minute", on_breach=handle_order_breach)
def create_order_route():
    # if redis_conn.get(f"blocked:{get_real_ip()}"):
    #     return jsonify({"error": "Too many requests"}), 429

    body = request.get_json()
    print(json.dumps(body, indent=2, ensure_ascii=False))
    discount_code_value = body.get("discount_code")
    discount_code_id = body.get("discount_code_id")
    if not body:
        return jsonify({"error": "Missing request body"}), 400

    order_items = body.pop("order_items", [])
    if not order_items:
        return jsonify({"error": "order_items is required"}), 400

    shipping_fee = float(body.get("shipping_fee", 0))

    try:
        error = validate_order({**body, "order_items": order_items})
        if error:
            return jsonify({"errors": {"message": error}}), 422

        subtotal = sum(
            float(item["unit_price"]) * int(item["quantity"])
            for item in order_items
        )

        from utils.validate import _calc_code_discount

        discount = 0
        discount_code_value = body.get("discount_code")

        if discount_code_value:
            discount_code = get_discount_code_by_code(discount_code_value)
            if discount_code:
                discount = float(_calc_code_discount(discount_code, subtotal))

        total = max(0, subtotal + shipping_fee - discount)

        order_code = generate_order_code()
        expires_at = (
            datetime.now(timezone.utc).replace(microsecond=0)
            + timedelta(seconds=ORDER_EXPIRE_SECONDS)
        )

        body.update({
            "order_code": order_code,
            "status": "init",
            "subtotal": subtotal,
            "discount": discount,
            "total": total,
            # "expires_at": expires_at.isoformat(),
            "discount_code_id": discount_code_id,  # ✅ lưu vào Directus
            "discount_code": discount_code_value,  # ✅ lưu vào Directus
        })

        order = create_order(body)  
        order_id = order["id"]
        order["expires_at"] = expires_at.isoformat()

        created_items = []

        for item in order_items:
            item["merch_order_id"] = order_id
            print("=== ITEM BEFORE CREATE ===")
            print(item)
            print("==========================")
            created_items.append(create_order_item(item))
        order["order_items"] = created_items

        payment_info = create_payos_payment(
            order_code=order_code,
            amount=total,
            expires_at=expires_at,
        )
        order["payment_info"] = payment_info

        job = q.enqueue_in(
            timedelta(seconds=ORDER_EXPIRE_SECONDS),
            expire_order,
            order_id,
        )
        redis_conn.setex(
            f"expire_job:{order_id}",
            ORDER_EXPIRE_SECONDS + 60,
            job.id,
        )

        return jsonify(order), 201

    except Exception as e:
        if "order_id" in locals():
            cancel_order(order_id)
        raise e


@app.route("/orders/<order_id>", methods=["GET"])
def get_order_route(order_id: str):
    order = get_order(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify(order)


@app.route("/shipping/fee", methods=["POST"])
def get_shipping_fee():
    body = request.get_json()
    address = body.get("address")
    subtotal = body.get("subtotal", 0)

    if not address:
        return jsonify({"error": "address is required"}), 400

    try:
        shipping_data = calculate_shipping_fee(address, subtotal)
        return jsonify(shipping_data)
    except Exception as e:
        logger.error(f"Shipping error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/webhook/payos", methods=["POST"])
def payos_webhook():
    try:
        body = request.get_json()

        if not body:
            return jsonify({"error": "Missing body"}), 400

        print("==== WEBHOOK PAYOS ====")
        print("BODY:", body)

        data = body.get("data", {})
        signature = body.get("signature", "")

        # =========================
        # 1. VERIFY SIGNATURE
        # =========================
        if not verify_webhook_signature(data, signature):
            print("❌ Invalid signature")
            return jsonify({"error": "Invalid signature"}), 401

        # =========================
        # 2. CHECK SUCCESS CODE
        # =========================
        # 🔥 FIX: KHÔNG check success nữa
        if body.get("code") != "00":
            print("⚠️ Webhook ignored (code != 00)")
            return jsonify({"status": "ignored"}), 200

        # =========================
        # 3. LẤY ORDER CODE
        # =========================
        order_code = str(data.get("orderCode", ""))
        print("ORDER CODE FROM PAYOS:", order_code)

        if not order_code:
            return jsonify({"error": "Missing orderCode"}), 400

        # =========================
        # 4. TÌM ORDER
        # =========================
        order = get_order_by_code(order_code)

 # 🔥 fallback nếu không tìm thấy

        if not order:
            print("❌ Order not found")
            return jsonify({"error": "Order not found"}), 200

        print("✅ FOUND ORDER:", order["id"])

        # =========================
        # 5. IDEMPOTENT CHECK
        # =========================
        if order["status"] != "init":
            print("⚠️ Order already processed:", order["status"])
            return jsonify({"status": "ignored"}), 200

        # =========================
        # 6. CHECK AMOUNT
        # =========================
        paid_amount = int(data.get("amount", 0))
        order_total = int(float(order["total"]))

        print("COMPARE AMOUNT:", paid_amount, order_total)

        if paid_amount != order_total:
            print("❌ Amount mismatch")
            return jsonify({"status": "ignored"}), 200

        # =========================
        # 7. UPDATE STATUS
        # =========================
        order_id = order["id"]

        # cancel expire job
        _cancel_expire_job(order_id)

        # update DB
        update_order_status(order_id, "done")
        order["status"] = "done"
        print("discount_code_id:",order.get("discount_code_id"))
        increate_discount_code_usage(order.get("discount_code_id"))
        print(f"🎉 ORDER {order_id} UPDATED TO PAID")

        # =========================
        # 7.1 SEND EMAIL (🔥 ADD THIS)
        # =========================
        try:
            from jobs.send_order_email import send_order_email
            print(f"📧 Enqueuing email job for order {order_id}")
            # dùng queue để tránh block webhook
            try:
                from jobs.send_order_email import send_order_email
                # send_order_email(order_id)
                q.enqueue(send_order_email, order_id)
                
                print(f"📧 Email sent for order {order_id}")
            except Exception as e:
                import traceback
                print(f"❌ Failed to send email: {e}")
                traceback.print_exc()  # ← thêm dòng này để thấy full lỗi

            
        except Exception as e:
            print(f"❌ Failed to enqueue email job: {e}")

        # =========================
        # 8. REALTIME SOCKET
        # =========================
        socketio.emit(
            "payment_success",
            {
                "order_id": order_id,
                "order": order
            },
            to=order_id,
        )

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        import traceback
        print("❌ WEBHOOK ERROR:", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def _cancel_expire_job(order_id: str):
    job_id_key = f"expire_job:{order_id}"
    job_id = redis_conn.get(job_id_key)
    if job_id:
        from rq.job import Job
        try:
            job = Job.fetch(job_id.decode(), connection=redis_conn)
            job.cancel()
        except Exception:
            pass
        redis_conn.delete(job_id_key)
from flask import send_from_directory

import requests
from flask import Response
@app.route("/assets/<asset_id>")
def proxy_asset(asset_id):
    url = f"{os.getenv('DIRECTUS_URL')}"
    token = os.getenv("DIRECTUS_TOKEN")

    directus_url = f"{url}/assets/{asset_id}"  # internal Docker network
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(directus_url,headers=headers, stream=True)
    
    return Response(
        resp.iter_content(chunk_size=8192),
        status=resp.status_code,
        content_type=resp.headers.get("Content-Type", "application/octet-stream"),
    )

@app.route('/img/<path:filename>')
def serve_images(filename):
    return send_from_directory('static/img', filename)

@socketio.on("join_order")
def on_join_order(data):
    order_id = data.get("order_id")
    if order_id:
        join_room(order_id)


if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=FLASK_DEBUG,
    )