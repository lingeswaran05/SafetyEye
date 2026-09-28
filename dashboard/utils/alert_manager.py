import logging
import os
import smtplib
import threading
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"

LOG = logging.getLogger("SafetyEye.alerts")
logging.basicConfig(level=logging.INFO)

# Global cooldown timestamp across all violation emails (default 60s / 1 min)
_last_email_sent_time = 0.0
_lock = threading.Lock()


def get_smtp_config():
    """Dynamically loads and returns SMTP configuration from environment or .env file."""
    if load_dotenv is not None and ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=True)

    server = os.getenv("SAFETYEYE_SMTP_SERVER", "smtp.gmail.com")
    try:
        port = int(os.getenv("SAFETYEYE_SMTP_PORT", "587"))
    except ValueError:
        port = 587
    sender = os.getenv("SAFETYEYE_SENDER_EMAIL", "").strip()
    password = os.getenv("SAFETYEYE_SENDER_PASSWORD", "").strip()
    receivers_raw = os.getenv("SAFETYEYE_RECEIVER_EMAILS", "").strip()
    receivers = [e.strip() for e in receivers_raw.split(",") if e.strip()]
    try:
        cooldown = int(os.getenv("SAFETYEYE_EMAIL_COOLDOWN", "60"))
    except ValueError:
        cooldown = 60

    return {
        "server": server,
        "port": port,
        "sender": sender,
        "password": password,
        "receivers": receivers,
        "cooldown": cooldown,
    }


def send_email(subject: str, body: str, image_path: str = None, receivers: list = None) -> bool:
    cfg = get_smtp_config()
    target_receivers = receivers or cfg["receivers"]
    sender_email = cfg["sender"]
    sender_password = cfg["password"]
    smtp_server = cfg["server"]
    smtp_port = cfg["port"]

    if not sender_email or not sender_password or not target_receivers:
        LOG.info("Email alert skipped: SMTP credentials not configured in .env file (see .env.example).")
        return False

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = ", ".join(target_receivers)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    if image_path and Path(image_path).exists():
        try:
            with open(image_path, "rb") as f:
                img_data = f.read()
            img_part = MIMEImage(img_data, name=Path(image_path).name)
            msg.attach(img_part)
        except Exception as e:
            LOG.warning("Could not attach image to email: %s", e)

    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=12) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        LOG.info("Consolidated email alert successfully sent to: %s", target_receivers)
        return True
    except Exception as exc:
        LOG.error("Failed to send email alert: %s", exc)
        return False


def trigger_alert(record: dict) -> bool:
    """
    Triggers a single consolidated email alert containing all detected violations.
    Enforces a strict 1-minute (or configured) global cooldown to prevent spam.
    """
    global _last_email_sent_time
    cfg = get_smtp_config()
    now = time.time()
    cooldown = cfg["cooldown"]

    with _lock:
        if (now - _last_email_sent_time) < cooldown:
            remaining = cooldown - (now - _last_email_sent_time)
            LOG.info("Email alert throttled: Cooldown active (%.1fs remaining).", remaining)
            return False
        _last_email_sent_time = now

    violations = record.get("violations")
    if not violations:
        v_type = record.get("violation_type", "Safety Violation")
        violations = [v.strip() for v in v_type.split(",") if v.strip()]

    if len(violations) > 1:
        subject = f"⚠️ SafetyEye Alert: {len(violations)} Violations Detected ({', '.join(violations[:2])})"
    elif violations:
        subject = f"⚠️ SafetyEye Alert: {violations[0]} Detected"
    else:
        subject = "⚠️ SafetyEye Alert: PPE Compliance Violation Detected"

    violations_bullet_list = "\n".join(f"  • ❌ {v}" for v in violations)

    body = (
        f"🚨 PPE SAFETY VIOLATION REPORT — SAFETYEYE MONITORING SYSTEM\n\n"
        f"The following safety violations were detected simultaneously:\n\n"
        f"{violations_bullet_list}\n\n"
        f"📋 INCIDENT DETAILS:\n"
        f"  • Timestamp  : {record.get('timestamp')}\n"
        f"  • Worker ID  : {record.get('worker_id', 'Worker-01')}\n"
        f"  • Confidence : {record.get('confidence', 0.0):.1%}\n"
        f"  • Source     : {record.get('source', '0')}\n\n"
        f"An annotated snapshot has been attached for verification.\n"
        f"Please inspect the SafetyEye Live Monitoring Dashboard for immediate corrective action.\n"
    )

    image_path = record.get("frame_image")
    return send_email(subject, body, image_path=image_path)


def trigger_alert_async(record: dict):
    thread = threading.Thread(target=trigger_alert, args=(record,), daemon=True)
    thread.start()
