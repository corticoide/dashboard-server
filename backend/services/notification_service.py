import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from backend.models.alert import AlertRule, AlertFire

logger = logging.getLogger(__name__)


def _build_smtp(settings) -> smtplib.SMTP:
    smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
    smtp.starttls()
    if settings.smtp_user:
        smtp.login(settings.smtp_user, settings.smtp_password)
    return smtp


def send_alert_email(rule: AlertRule, fire: AlertFire) -> None:
    """Send alert-fired email via smtplib using settings.smtp_*."""
    from backend.config import settings
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[ServerDash Alert] {rule.name} triggered"
    msg["From"] = settings.smtp_from
    msg["To"] = rule.email_to
    body = (
        f"Alert rule '{rule.name}' has been triggered.\n\n"
        f"Condition: {rule.condition_type}\n"
        f"Detail: {fire.detail or 'n/a'}\n"
        f"Fired at: {fire.fired_at.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
    )
    msg.attach(MIMEText(body, "plain"))
    with _build_smtp(settings) as smtp:
        smtp.sendmail(settings.smtp_from, rule.email_to, msg.as_string())
    logger.info("Alert email sent for rule '%s' (fire id=%s)", rule.name, fire.id)


def send_recovery_email(rule: AlertRule, fire: AlertFire) -> None:
    """Send alert-recovered email via smtplib using settings.smtp_*."""
    from backend.config import settings
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[ServerDash Alert] {rule.name} recovered"
    msg["From"] = settings.smtp_from
    msg["To"] = rule.email_to
    body = (
        f"Alert rule '{rule.name}' has recovered.\n\n"
        f"Condition: {rule.condition_type}\n"
        f"Detail at fire: {fire.detail or 'n/a'}\n"
        f"Fired at: {fire.fired_at.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        f"Recovered at: {fire.recovered_at.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
    )
    msg.attach(MIMEText(body, "plain"))
    with _build_smtp(settings) as smtp:
        smtp.sendmail(settings.smtp_from, rule.email_to, msg.as_string())
    logger.info("Recovery email sent for rule '%s' (fire id=%s)", rule.name, fire.id)
