import logging
from apartment import Apartment

class Immobilienscout24Scraper:
    def __init__(self, config, session, logger=None):
        self.config = config
        self.session = session
        self.logger = logger or logging.getLogger(__name__)

    def scrape(self, city):
        self.logger.info("ImmobilienScout24 scrapen")
        apartments = []
        try:
            base_url = "https://www.immobilienscout24.de/Suche/de/nordrhein-westfalen/soest-kreis/soest/wohnung-mieten"
            params = {
                'price': f'-{self.config["search_criteria"]["max_price"]}',
                'numberofrooms': f'{self.config["search_criteria"]["min_rooms"]}-{self.config["search_criteria"]["max_rooms"]}',
                'petsallowedtypes': 'yes,negotiable'
            }
            temp_req = self.session.prepare_request(self.session.request('GET', base_url, params=params))
            full_url = temp_req.url
            print(f"ImmobilienScout24 URL: {full_url}")

            # Optional: Selenium/undetected_chromedriver logic can be added here if needed

            response = self.session.get(base_url, params=params)
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                listings = soup.find_all('div', class_='result-list-entry')
                self.logger.info(str(len(listings)) + " Anzeigen gefunden.")
                for listing in listings[:self.config["scraping"]["max_results_per_site"]]:
                    try:
                        title = listing.find('h2', class_='result-list-entry__brand-title-container').text.strip()
                        price = listing.find('dd', class_='grid-item').text.strip()
                        location = listing.find('div', class_='result-list-entry__address').text.strip()
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
                        apartments.append(apartment)
                    except Exception as e:
                        self.logger.error(f"Fehler beim Parsen eines Listings: {e}")
                        continue
            else:
                self.logger.error(f"Fehler beim Abrufen von ImmobilienScout24: Statuscode {response.status_code}")
        except Exception as e:
            self.logger.error(f"Fehler beim Scrapen von ImmobilienScout24: {e}")
        return apartments
