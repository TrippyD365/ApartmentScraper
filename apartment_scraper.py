import requests
from bs4 import BeautifulSoup
import time
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import hashlib
import os
from dataclasses import dataclass
from typing import List, Dict, Optional
import re
import logging
import undetected_chromedriver as uc
from selenium import webdriver

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Apartment:
    title: str
    price: str
    location: str
    rooms: str
    size: str
    url: str
    source: str
    description: str = ""
    
    def to_dict(self):
        return {
            'title': self.title,
            'price': self.price,
            'location': self.location,
            'rooms': self.rooms,
            'size': self.size,
            'url': self.url,
            'source': self.source,
            'description': self.description
        }
    
    def get_hash(self):
        """Eindeutige ID für die Wohnung generieren"""
        content = f"{self.title}{self.price}{self.location}{self.url}"
        return hashlib.md5(content.encode()).hexdigest()

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
        logger.info("ImmobilienScout24 scrapen")
        apartments = []
        try:
            base_url = "https://www.immobilienscout24.de/Suche/de/nordrhein-westfalen/soest-kreis/soest/wohnung-mieten"
            params = {
                'price': f'-{self.config["search_criteria"]["max_price"]}',
                'numberofrooms': f'{self.config["search_criteria"]["min_rooms"]}-{self.config["search_criteria"]["max_rooms"]}',
                'petsallowedtypes': 'yes,negotiable'
            }
            
            # Volle URL mit Parametern ausgeben
            temp_req = requests.Request('GET', base_url, params=params).prepare()
            full_url = temp_req.url
            print(f"ImmobilienScout24 URL: {full_url}")

            driver = uc.Chrome()
            if full_url is not None:
                driver.get(full_url)
            else:
                logger.error("Die generierte URL für ImmobilienScout24 ist None.")
                return apartments

            response = self.session.get(base_url, params=params)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Wohnungsangebote finden (Selektoren können sich ändern)
                listings = soup.find_all('div', class_='result-list-entry')

                logger.info(str(listings.__len__()) + " Anzeigen gefunden.")
                
                for listing in listings[:self.config["scraping"]["max_results_per_site"]]:
                    try:
                        title = listing.find('h2', class_='result-list-entry__brand-title-container').text.strip()
                        price = listing.find('dd', class_='grid-item').text.strip()
                        location = listing.find('div', class_='result-list-entry__address').text.strip()
                        
                        # URL extrahieren
                        link_elem = listing.find('a')
                        if link_elem:
                            url = "https://www.immobilienscout24.de" + link_elem.get('href')
                        else:
                            continue
                        
                        apartment = Apartment(
                            title=title,
                            price=price,
                            location=location,
                            rooms="N/A",
                            size="N/A",
                            url=url,
                            source="ImmobilienScout24"
                        )
                        
                        if self.matches_criteria(apartment):
                            apartments.append(apartment)
                    
                    except Exception as e:
                        logger.error(f"Fehler beim Parsen eines Listings: {e}")
                        continue
            else:
                logger.error(f"Fehler beim Abrufen von ImmobilienScout24: Statuscode {response.status_code}")
                '''logger.error(f"Response HTML: {response.text[:2000]}")'''
        
        except Exception as e:
            logger.error(f"Fehler beim Scrapen von ImmobilienScout24: {e}")
        
        return apartments
    
    def scrape_wg_gesucht(self, city):
        logger.info("Wg-Gesucht scrapen")
        apartments = []
        try:
            base_url = f"https://www.wg-gesucht.de/wohnungen-in-{city.lower()}.html"


            # Volle URL mit Parametern ausgeben
            temp_req = requests.Request('GET', base_url, params=params).prepare()
            full_url = temp_req.url
            print(f"Wg-Gesucht URL: {full_url}")

            response = self.session.get(base_url)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Wohnungsangebote finden
                listings = soup.find_all('div', class_='wgg_card')
                logger.info(str(listings.__len__()) + " Anzeigen gefunden.")
                
                for listing in listings[:self.config["scraping"]["max_results_per_site"]]:
                    try:
                        title_elem = listing.find('h3', class_='headline')
                        if not title_elem:
                            continue
                        
                        title = title_elem.text.strip()
                        
                        # Preis extrahieren
                        price_elem = listing.find('div', class_='col-xs-3')
                        price = price_elem.text.strip() if price_elem else "N/A"
                        
                        # Link extrahieren
                        link_elem = listing.find('a')
                        if link_elem:
                            url = "https://www.wg-gesucht.de/" + link_elem.get('href')
                        else:
                            continue
                        
                        apartment = Apartment(
                            title=title,
                            price=price,
                            location=city,
                            rooms="N/A",
                            size="N/A",
                            url=url,
                            source="WG-Gesucht"
                        )
                        
                        if self.matches_criteria(apartment):
                            apartments.append(apartment)
                    
                    except Exception as e:
                        logger.error(f"Fehler beim Parsen eines WG-Gesucht Listings: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"Fehler beim Scrapen von WG-Gesucht: {e}")
        
        return apartments
    
    def scrape_ebay_kleinanzeigen(self, city):
        logger.info("eBay Kleinanzeigen scrapen")
        apartments = []
        try:
            base_url = f"https://www.ebay-kleinanzeigen.de/s-wohnung-mieten/{city}/c203"
            response = self.session.get(base_url)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Wohnungsangebote finden
                listings = soup.find_all('div', class_='aditem')
                logger.info(str(listings.__len__()) + " Anzeigen gefunden.")
                
                for listing in listings[:self.config["scraping"]["max_results_per_site"]]:
                    try:
                        title_elem = listing.find('h2', class_='text-module-begin')
                        if not title_elem:
                            continue
                        
                        title = title_elem.text.strip()
                        
                        # Preis extrahieren
                        price_elem = listing.find('p', class_='aditem-main--middle--price-shipping--price')
                        price = price_elem.text.strip() if price_elem else "VB"
                        
                        # Ort extrahieren
                        location_elem = listing.find('div', class_='aditem-main--top--left')
                        location = location_elem.text.strip() if location_elem else city
                        
                        # Link extrahieren
                        link_elem = listing.find('a', class_='ellipsis')
                        if link_elem:
                            url = "https://www.ebay-kleinanzeigen.de" + link_elem.get('href')
                        else:
                            continue
                        
                        apartment = Apartment(
                            title=title,
                            price=price,
                            location=location,
                            rooms="N/A",
                            size="N/A",
                            url=url,
                            source="eBay Kleinanzeigen"
                        )
                        
                        if self.matches_criteria(apartment):
                            apartments.append(apartment)
                    
                    except Exception as e:
                        logger.error(f"Fehler beim Parsen eines eBay Kleinanzeigen Listings: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"Fehler beim Scrapen von eBay Kleinanzeigen: {e}")
        
        return apartments
    
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
        """E-Mail-Benachrichtigung senden"""
        # Credentials and config are now always read from config file
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
            logger.info(f"E-Mail-Benachrichtigung für {len(apartments)} Wohnungen gesendet")
        except Exception as e:
            logger.error(f"Fehler beim Senden der E-Mail: {e}")
    
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