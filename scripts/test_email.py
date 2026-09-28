"""
Test script for SafetyEye Email Alert Notifications.
Run using: python scripts/test_email.py
"""
import sys
from datetime import datetime
from pathlib import Path

# Ensure UTF-8 output in Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.utils.alert_manager import get_smtp_config, send_email


def main():
    print("=" * 60)
    print(" SafetyEye Email Alert Diagnostics & Test")
    print("=" * 60)

    cfg = get_smtp_config()
    print(f"* SMTP Server     : {cfg['server']}:{cfg['port']}")
    print(f"* Sender Email    : {cfg['sender'] or '(Not configured)'}")
    print(f"* Receiver Emails : {cfg['receivers'] or '(Not configured)'}")
    print(f"* Has Password    : {'Yes' if cfg['password'] else 'No'}")
    print("-" * 60)

    if not cfg["sender"] or not cfg["password"] or not cfg["receivers"]:
        print("\n[!] Configuration Incomplete!")
        print("Please create a .env file in the root project folder with the following variables:\n")
        print("SAFETYEYE_SMTP_SERVER=smtp.gmail.com")
        print("SAFETYEYE_SMTP_PORT=587")
        print("SAFETYEYE_SENDER_EMAIL=your_email@gmail.com")
        print("SAFETYEYE_SENDER_PASSWORD=your_16_digit_app_password")
        print("SAFETYEYE_RECEIVER_EMAILS=recipient_email@example.com\n")
        print("Note: For Gmail, use an 'App Password' (16 characters) from Google Account Security.")
        return 1

    print("\nAttempting to send a test alert email...")
    test_subject = f"SafetyEye Test Alert - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    test_body = (
        "Hello,\n\n"
        "This is a test notification from SafetyEye PPE Workplace Monitoring System.\n"
        "If you received this email, your email notification alert setup is working properly!\n"
    )

    success = send_email(subject=test_subject, body=test_body)
    if success:
        print("\n[+] Success! Test email sent to:", ", ".join(cfg["receivers"]))
        return 0
    else:
        print("\n[-] Failed to send email. Check your credentials, network connection, or App Password.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
