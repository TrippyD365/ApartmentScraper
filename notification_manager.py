import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

class NotificationManager:
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

    def send_email_notification(self, apartments):
        if not self.config["notification"]["email"]["enabled"]:
            return
        try:
            smtp_config = self.config["notification"]["email"]
            msg = MIMEMultipart()
            msg['From'] = smtp_config["sender_email"]
            msg['To'] = smtp_config["recipient_email"]
            msg['Subject'] = f"Neue Wohnungsangebote gefunden! ({len(apartments)} Angebote)"
            body = f"""
            Hallo!

            Ich habe {len(apartments)} neue Wohnungsangebote gefunden, die Ihren Kriterien entsprechen:

            """
            for i, apartment in enumerate(apartments, 1):
                body += f"""
                {i}. {apartment.title}
                Preis: {apartment.price}
                Ort: {apartment.location}
                Zimmer: {apartment.rooms}
                Größe: {apartment.size}
                Quelle: {apartment.source}
                Link: {apartment.url}
                
            """
            body += f"""
            Viel Erfolg bei der Wohnungssuche!

            Gesendet am: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
            """
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            server = smtplib.SMTP(smtp_config["smtp_server"], smtp_config["smtp_port"])
            server.starttls()
            server.login(smtp_config["sender_email"], smtp_config["sender_password"])
            server.send_message(msg)
            server.quit()
            self.logger.info(f"E-Mail-Benachrichtigung für {len(apartments)} Wohnungen gesendet")
        except Exception as e:
            self.logger.error(f"Fehler beim Senden der E-Mail: {e}")
