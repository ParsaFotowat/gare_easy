"""Scrapers package initialization"""
from .base_scraper import BaseScraper
from .mef_scraper import MEFScraper
from .toscana_scraper import ToscanaScraper
from .emilia_scraper import EmiliaScraper
from .aria_scraper import AriaScraper

__all__ = ['BaseScraper', 'MEFScraper', 'ToscanaScraper', 'EmiliaScraper', 'AriaScraper']
