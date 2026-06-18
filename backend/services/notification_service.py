"""
Notification Service — email alerts + digest summaries.

Config:
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, NOTIFY_EMAIL
"""
import json, os, smtplib, threading, time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", SMTP_USER)
ALERT_ENABLED = bool(SMTP_USER and SMTP_PASS)

THRESHOLDS = {
    "daily_cost_yuan": 10.0,
    "hourly_error_rate": 0.1,
    "agent_down_minutes": 5,
}

class NotificationService:
    def __init__(self):
        self._sent_alerts: Dict[str, float] = {}
        self._alert_cooldown = 3600  # 1 hour between same-type alerts

    @property
    def available(self) -> bool:
        return ALERT_ENABLED

    def send(self, subject: str, body: str, to: str = ""):
        if not self.available: return
        t = threading.Thread(target=self._send_sync, args=(subject, body, to or NOTIFY_EMAIL), daemon=True)
        t.start()

    def _send_sync(self, subject: str, body: str, to: str):
        try:
            msg = MIMEMultipart()
            msg["Subject"] = f"[AI OS] {subject}"
            msg["From"] = SMTP_USER
            msg["To"] = to
            msg.attach(MIMEText(body, "html", "utf-8"))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
                s.starttls()
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
        except Exception as e:
            print(f"[Notify] Send failed: {e}")

    def alert_if_needed(self, alert_type: str, context: dict):
        if not self.available: return
        now = time.time()
        last = self._sent_alerts.get(alert_type, 0)
        if now - last < self._alert_cooldown: return
        self._sent_alerts[alert_type] = now

        subject_map = {
            "cost_spike": f"费用告警: {context.get('cost_yuan', 0)}元",
            "error_spike": f"错误率告警: {context.get('error_rate', 0)}%",
            "agent_down": f"Agent 异常: {context.get('agent', '?')}",
        }
        body = f"""<h3>AI Company OS 告警</h3>
        <table>
        <tr><td>类型</td><td>{alert_type}</td></tr>
        <tr><td>时间</td><td>{datetime.now().isoformat()[:19]}</td></tr>
        <tr><td>详情</td><td>{json.dumps(context, ensure_ascii=False)}</td></tr>
        </table>"""
        self.send(subject_map.get(alert_type, alert_type), body)

    def daily_digest(self, stats: dict):
        body = f"""<h3>AI Company OS 每日摘要</h3>
        <table style='border-collapse:collapse'>
        <tr><td>日期</td><td>{datetime.now().strftime('%Y-%m-%d')}</td></tr>
        <tr><td>总调用</td><td>{stats.get('all_calls', 0)}</td></tr>
        <tr><td>总Tokens</td><td>{stats.get('all_tokens', 0):,}</td></tr>
        <tr><td>费用</td><td>¥{stats.get('cost_yuan', 0)}</td></tr>
        <tr><td>会话数</td><td>{stats.get('sessions', 0)}</td></tr>
        </table>"""
        self.send(f"每日摘要 {datetime.now().strftime('%Y-%m-%d')}", body)


_notify: Optional[NotificationService] = None
def get_notification() -> NotificationService:
    global _notify
    if _notify is None: _notify = NotificationService()
    return _notify
