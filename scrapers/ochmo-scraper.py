import requests
from bs4 import BeautifulSoup
import re
import io
from PyPDF2 import PdfReader  # pip install PyPDF2
from urllib.parse import urljoin


class PdfReport:
    """
    Represents a single PDF report from NASA.
    It handles the parsing of the PDF content to extract metadata.
    """
    def __init__(self, url: str):
        """
        Initializes the PdfReport instance.

        Args:
            url: The direct URL to the PDF file.
        """
        self.url = url
        self.ochmo_id = None
        self.title = None
        self.technical_requirements_docs = []
        self.technical_requirements = []
        self._pdf_bytes = None

    def _fetch_pdf_content(self):
        """Downloads the PDF content from the URL if not already fetched."""
        if self._pdf_bytes is None:
            try:
                response = requests.get(self.url)
                response.raise_for_status()
                self._pdf_bytes = response.content
            except requests.exceptions.RequestException as e:
                print(f"Error fetching PDF from {self.url}: {e}")
                self._pdf_bytes = None

    def parse(self):
        """
        Fetches the PDF and parses its first page to extract metadata.
        This method populates the instance's attributes.
        """
        self._parse_ochmo_id()
        self._parse_title()
        self._fetch_pdf_content()
        if not self._pdf_bytes:
            return

        try:
            reader = PdfReader(io.BytesIO(self._pdf_bytes))
            if not reader.pages:
                return

            page_text = reader.pages[0].extract_text()
            self._parse_technical_requirements(page_text)
        except Exception as e:
            print(f"Error parsing PDF from {self.url}: {e}")

    def _parse_ochmo_id(self):
        """Extracts the OCHMO ID from the URL."""
        id_match = re.search(r"(OCHMO-M?TB-\d+)", self.url, re.IGNORECASE)
        if id_match:
            self.ochmo_id = id_match.group(1).upper()
        else:
            self.ochmo_id = None


    def _parse_title(self):
        """Extracts the title from the page url."""
        if not self.ochmo_id:
            return
        
        title_match = re.search(r"ochmo-m?tb-\d+-(.*?)\.pdf", self.url, re.IGNORECASE)
        if title_match:
            # Replace hyphens with spaces and capitalize each word
            self.title = title_match.group(1).replace("-", " ").title()
        else:
            self.title = None

    def _parse_technical_requirements(self, page_text: str):
        """Extracts related document codes from the 'Relevant Technical Requirements' section."""
        
        trd_matches = re.finditer(r"(NASA\s?-\s?STD\s?-\s?\d+\sVolume\s\d,\s?Rev\s\w)", page_text, re.IGNORECASE)
        for match in trd_matches:
            self.technical_requirements_docs.append(match.group(1).replace(" -", "-"))

        tr_matches = re.finditer(r"\[(V\d\s*\d+)\]", page_text, re.IGNORECASE)
        for match in tr_matches:
            self.technical_requirements.append(match.group(1))

    def to_dict(self):
        """Returns a dictionary representation of the report."""
        return {
            "url": self.url,
            "ochmo_id": self.ochmo_id,
            "title": self.title,
            "techincal_requirements_docs": self.technical_requirements_docs,
            "technical_requirements": self.technical_requirements,
        }
    
    def to_string_pretty(self):
        """Returns a nicely formatted string representation of the report."""
        report_str = f"URL: {self.url}\n"
        report_str += f"OCHMO ID: {self.ochmo_id}\n"
        report_str += f"Title: {self.title}\n"
        report_str += "Technical Requirements Docs:\n\t"
        report_str += "\n\t".join(self.technical_requirements_docs) + "\n"
        report_str += "Technical Requirements:\n\t"
        report_str += "\n\t".join(self.technical_requirements)
        return report_str

    def __repr__(self):
        """Provides a developer-friendly string representation of the object."""
        return f"PdfReport(ochmo_id='{self.ochmo_id}', title='{self.title}')"


class NasaScraper:
    """
    A scraper for fetching and parsing NASA OCHMO technical briefs.
    """
    def __init__(self, base_url: str):
        """
        Initializes the NasaScraper.

        Args:
            base_url: The URL of the page containing the list of PDF links.
        """
        self.base_url = base_url

    def _list_pdf_links(self) -> list[str]:
        """Fetches the page and returns absolute URLs of all OCHMO-MTB PDFs."""
        try:
            resp = requests.get(self.base_url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")
            links = []
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if re.search(r"ochmo-m?tb-\d+.*\.pdf\?", href, re.IGNORECASE):
                    absolute_url = urljoin(self.base_url, href)
                    links.append(absolute_url)
            return links
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch the base URL: {e}")
            return []

    def scrape_reports(self, limit: {int|None} = None) -> list[PdfReport]:
        """
        Scrapes all PDF reports from the base URL.

        Returns:
            A list of PdfReport objects, each containing parsed data.
        """
        pdf_urls = self._list_pdf_links()[:limit]
        reports = []
        for url in pdf_urls:
            print(f"Processing: {url}")
            report = PdfReport(url=url)
            report.parse()
            if report.ochmo_id: # Only add reports that were successfully parsed
                reports.append(report)
        return reports


if __name__ == "__main__":
    BASE_URL = "https://www.nasa.gov/ochmo/hsa-standards/ochmo-technical-briefs/"
    
    scraper = NasaScraper(base_url=BASE_URL)
    all_reports = scraper.scrape_reports(3)
    
    print("\n--- Scraping Complete ---\n")
    for rpt in all_reports:
        print(rpt.to_string_pretty())
