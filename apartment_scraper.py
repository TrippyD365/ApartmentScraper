
import requests
import time
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os
import re
import logging
from apartment import Apartment
from immobilienscout24_scraper import Immobilienscout24Scraper
from wg_gesucht_scraper import WgGesuchtScraper
from ebay_kleinanzeigen_scraper import EbayKleinanzeigenScraper
from notification_manager import NotificationManager

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ApartmentScraper:
    def __init__(self, config_file='scraper_config.json'):
        self.config = self.load_config(config_file)
        self.seen_apartments = self.load_seen_apartments()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        })
        self.immoscout_scraper = Immobilienscout24Scraper(self.config, self.session, logger)
        self.wggesucht_scraper = WgGesuchtScraper(self.config, self.session, logger)
        self.ebay_scraper = EbayKleinanzeigenScraper(self.config, self.session, logger)
        self.notifier = NotificationManager(self.config, logger)
        
    def load_config(self, config_file):
        """Konfiguration laden oder Standard-Konfiguration erstellen"""
        default_config = {
            "search_criteria": {
                "max_price": 1200,
                "min_rooms": 3,
                "max_rooms": 4,
                "cities": ["Soest"],
                "keywords": ["haustier", "haustiere", "garten"],
                "excluded_keywords": ["möbliert", "zwischenmiete"]
            },
            "notification": {
                "email": {
                    "enabled": True,
                    "smtp_server": "smtp.example.com",
                    "smtp_port": 587,
                    "sender_email": "your_email@example.com",
                    "sender_password": "your_password_here",
                    "recipient_email": "recipient@example.com"
                },
                "webhook": {
                    "enabled": False,
                    "url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
                }
            },
            "scraping": {
                "interval_minutes": 30,
                "max_results_per_site": 20
            }
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config
            except json.JSONDecodeError as e:
                logger.error(f"Fehlerhafte JSON-Konfiguration gefunden: {e}")
                logger.info("Erstelle neue Standard-Konfiguration...")
                
                # Backup der fehlerhaften Datei erstellen
                backup_name = f"{config_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                if os.path.exists(config_file):
                    os.rename(config_file, backup_name)
                    logger.info(f"Fehlerhafte Konfiguration gesichert als: {backup_name}")
                
                # Neue Konfiguration erstellen
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                logger.info(f"Neue Standard-Konfiguration erstellt: {config_file}")
                return default_config
            except Exception as e:
                logger.error(f"Unerwarteter Fehler beim Laden der Konfiguration: {e}")
                return default_config
                
        else:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            logger.info(f"Standard-Konfiguration erstellt: {config_file}")
            return default_config
    
    def load_seen_apartments(self):
        """Bereits gesehene Wohnungen laden"""
        seen_file = 'seen_apartments.json'
        if os.path.exists(seen_file):
            try:
                with open(seen_file, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            except json.JSONDecodeError as e:
                logger.error(f"Fehlerhafte seen_apartments.json gefunden: {e}")
                logger.info("Starte mit leerem Set...")
                # Backup erstellen
                backup_name = f"seen_apartments.json.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.rename(seen_file, backup_name)
                logger.info(f"Fehlerhafte Datei gesichert als: {backup_name}")
                return set()
            except Exception as e:
                logger.error(f"Unerwarteter Fehler beim Laden der seen_apartments: {e}")
                return set()
        return set()
    
    def save_seen_apartments(self):
        """Bereits gesehene Wohnungen speichern"""
        with open('seen_apartments.json', 'w', encoding='utf-8') as f:
            json.dump(list(self.seen_apartments), f, indent=2)
    
    def scrape_immobilienscout24(self, city):
        return self.immoscout_scraper.scrape(city)
    
    def scrape_wg_gesucht(self, city):
        return self.wggesucht_scraper.scrape(city)
    
    def scrape_ebay_kleinanzeigen(self, city):
        return self.ebay_scraper.scrape(city)
    
    def matches_criteria(self, apartment):
        """Prüfen ob Wohnung den Kriterien entspricht"""
        criteria = self.config["search_criteria"]
        
        # Preis prüfen
        price_match = re.search(r'(\d+(?:\.\d+)?)', apartment.price.replace(',', '.'))
        if price_match:
            price = float(price_match.group(1))
            if price > criteria["max_price"]:
                return False
        
        # Keywords prüfen
        text_to_check = f"{apartment.title} {apartment.description}".lower()
        
        # Ausgeschlossene Keywords prüfen
        for excluded in criteria.get("excluded_keywords", []):
            if excluded.lower() in text_to_check:
                return False
        
        # Gewünschte Keywords prüfen (optional)
        if criteria.get("keywords"):
            has_keyword = any(keyword.lower() in text_to_check for keyword in criteria["keywords"])
            if not has_keyword:
                return False
        
        return True
    
    def send_email_notification(self, apartments):
        self.notifier.send_email_notification(apartments)
    
    def send_webhook_notification(self, apartments):
        """Webhook-Benachrichtigung senden (z.B. Slack)"""
        if not self.config["notification"]["webhook"]["enabled"]:
            return
        
        try:
            webhook_url = self.config["notification"]["webhook"]["url"]
            
            message = f"🏠 *Neue Wohnungsangebote gefunden!*\n\n"
            
            for apartment in apartments:
                message += f"• *{apartment.title}*\n"
                message += f"  💰 {apartment.price} | 📍 {apartment.location}\n"
                message += f"  🔗 <{apartment.url}|Anzeige ansehen>\n\n"
            
            payload = {
                "text": message,
                "username": "Wohnungs-Bot",
                "icon_emoji": ":house:"
            }
            
            response = requests.post(webhook_url, json=payload)
            if response.status_code == 200:
                logger.info(f"Webhook-Benachrichtigung für {len(apartments)} Wohnungen gesendet")
            else:
                logger.error(f"Fehler beim Senden der Webhook-Benachrichtigung: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Fehler beim Senden der Webhook-Benachrichtigung: {e}")
    
    def scrape_all_sites(self):
        """Alle Seiten scrapen"""
        all_apartments = []
        cities = self.config["search_criteria"]["cities"]
        
        for city in cities:
            logger.info(f"Scrape {city}...")
            
            # ImmobilienScout24
            apartments = self.scrape_immobilienscout24(city)
            all_apartments.extend(apartments)
            time.sleep(2)  # Pause zwischen Anfragen
            
            # WG-Gesucht
            apartments = self.scrape_wg_gesucht(city)
            all_apartments.extend(apartments)
            time.sleep(2)
            
            # eBay Kleinanzeigen
            apartments = self.scrape_ebay_kleinanzeigen(city)
            all_apartments.extend(apartments)
            time.sleep(2)
        
        return all_apartments
    
    def filter_new_apartments(self, apartments):
        """Nur neue Wohnungen filtern"""
        new_apartments = []
        
        for apartment in apartments:
            apartment_hash = apartment.get_hash()
            if apartment_hash not in self.seen_apartments:
                new_apartments.append(apartment)
                self.seen_apartments.add(apartment_hash)
        
        return new_apartments
    
    def run_once(self):
        """Einmaligen Scraping-Durchlauf ausführen"""
        logger.info("Starte Scraping-Durchlauf...")
        
        all_apartments = self.scrape_all_sites()
        new_apartments = self.filter_new_apartments(all_apartments)
        
        if new_apartments:
            logger.info(f"{len(new_apartments)} neue Wohnungen gefunden!")
            
            # Benachrichtigungen senden
            self.send_email_notification(new_apartments)
            self.send_webhook_notification(new_apartments)
            
            # Gesehene Wohnungen speichern
            self.save_seen_apartments()
            
            # Neue Wohnungen in JSON speichern
            with open(f'new_apartments_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json', 'w', encoding='utf-8') as f:
                json.dump([apt.to_dict() for apt in new_apartments], f, indent=2, ensure_ascii=False)
        else:
            logger.info("Keine neuen Wohnungen gefunden.")
        
        return new_apartments
    
    def run_continuous(self):
        """Kontinuierliches Scraping"""
        interval = self.config["scraping"]["interval_minutes"]
        logger.info(f"Starte kontinuierliches Scraping (Intervall: {interval} Minuten)")
        
        while True:
            try:
                self.run_once()
                logger.info(f"Warte {interval} Minuten bis zum nächsten Durchlauf...")
                time.sleep(interval * 60)
            except KeyboardInterrupt:
                logger.info("Scraping gestoppt.")
                break
            except Exception as e:
                logger.error(f"Unerwarteter Fehler: {e}")
                time.sleep(60)  # 1 Minute warten bei Fehlern

def main():
    """Hauptfunktion"""
    scraper = ApartmentScraper()
    
    print("🏠 Wohnungs-Scraper")
    print("=" * 40)
    print("1. Einmaligen Durchlauf starten")
    print("2. Kontinuierliches Scraping starten")
    print("3. Konfiguration anzeigen")
    
    choice = input("\nWählen Sie eine Option (1-3): ")
    
    if choice == "1":
        apartments = scraper.run_once()
        print(f"\n✅ {len(apartments)} neue Wohnungen gefunden!")
        
        for i, apt in enumerate(apartments, 1):
            print(f"\n{i}. {apt.title}")
            print(f"   💰 {apt.price} | 📍 {apt.location}")
            print(f"   🔗 {apt.url}")
    
    elif choice == "2":
        scraper.run_continuous()
    
    elif choice == "3":
        print("\nAktuelle Konfiguration:")
        print(json.dumps(scraper.config, indent=2, ensure_ascii=False))
    
    else:
        print("Ungültige Auswahl.")

if __name__ == "__main__":
    main()