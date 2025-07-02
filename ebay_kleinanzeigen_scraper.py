import logging
from apartment import Apartment

class EbayKleinanzeigenScraper:
    def __init__(self, config, session, logger=None):
        self.config = config
        self.session = session
        self.logger = logger or logging.getLogger(__name__)

    def scrape(self, city):
        self.logger.info("eBay Kleinanzeigen scrapen")
        apartments = []
        try:
            base_url = f"https://www.ebay-kleinanzeigen.de/s-wohnung-mieten/{city}/c203"
            response = self.session.get(base_url)
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                listings = soup.find_all('div', class_='aditem')
                self.logger.info(str(len(listings)) + " Anzeigen gefunden.")
                for listing in listings[:self.config["scraping"]["max_results_per_site"]]:
                    try:
                        title_elem = listing.find('h2', class_='text-module-begin')
                        if not title_elem:
                            continue
                        title = title_elem.text.strip()
                        price_elem = listing.find('p', class_='aditem-main--middle--price-shipping--price')
                        price = price_elem.text.strip() if price_elem else "VB"
                        location_elem = listing.find('div', class_='aditem-main--top--left')
                        location = location_elem.text.strip() if location_elem else city
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
                        apartments.append(apartment)
                    except Exception as e:
                        self.logger.error(f"Fehler beim Parsen eines eBay Kleinanzeigen Listings: {e}")
                        continue
        except Exception as e:
            self.logger.error(f"Fehler beim Scrapen von eBay Kleinanzeigen: {e}")
        return apartments
