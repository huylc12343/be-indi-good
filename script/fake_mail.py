import smtplib
from email.mime.text import MIMEText

# 🔧 CONFIG
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "huylc12343@gmail.com"
SMTP_PASSWORD = "gpwy nbel lver oaji"  # 🔥 phải là App Password

FROM_EMAIL = SMTP_USER
TO_EMAIL = "huylc12343@gmail.com"

# 📨 Nội dung mail
subject = "Test gửi mail Python"
body = "Thanh toán thành công 🎉"

msg = MIMEText(body, "plain", "utf-8")
msg["Subject"] = subject
msg["From"] = FROM_EMAIL
msg["To"] = TO_EMAIL

# 🚀 Gửi mail
try:
    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
    server.starttls()
    server.login(SMTP_USER, SMTP_PASSWORD)
    server.sendmail(FROM_EMAIL, TO_EMAIL, msg.as_string())
    server.quit()

    print("✅ Gửi mail thành công!")

except Exception as e:
    print("❌ Lỗi:", e)