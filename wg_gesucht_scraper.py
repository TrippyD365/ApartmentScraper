import logging
from apartment import Apartment

class WgGesuchtScraper:
    def __init__(self, config, session, logger=None):
        self.config = config
        self.session = session
        self.logger = logger or logging.getLogger(__name__)

    def scrape(self, city):
        self.logger.info("Wg-Gesucht scrapen")
        apartments = []
        try:
            base_url = f"https://www.wg-gesucht.de/wohnungen-in-{city.lower()}.html"
            response = self.session.get(base_url)
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                listings = soup.find_all('div', class_='wgg_card')
                self.logger.info(str(len(listings)) + " Anzeigen gefunden.")
                for listing in listings[:self.config["scraping"]["max_results_per_site"]]:
                    try:
                        title_elem = listing.find('h3', class_='headline')
                        if not title_elem:
                            continue
                        title = title_elem.text.strip()
                        price_elem = listing.find('div', class_='col-xs-3')
                        price = price_elem.text.strip() if price_elem else "N/A"
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
                        apartments.append(apartment)
                    except Exception as e:
                        self.logger.error(f"Fehler beim Parsen eines WG-Gesucht Listings: {e}")
                        continue
        except Exception as e:
            self.logger.error(f"Fehler beim Scrapen von WG-Gesucht: {e}")
        return apartments
