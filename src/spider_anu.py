from abc import ABC

import html2text
import spacy
from scrapy.http.response.html import HtmlResponse
from scrapy.spiders import CrawlSpider

from nlp_config import PATTERNS


class SpiderANU(ABC, CrawlSpider):
    DOMAIN = 'programsandcourses.anu.edu.au'
    converter = html2text.HTML2Text()
    converter.ignore_links = True

    nlp = spacy.load("en_core_web_sm")
    ruler = nlp.add_pipe("entity_ruler", config={"validate": True}, before="ner")
    ruler.add_patterns(PATTERNS)

    def parse_unit(self, response: HtmlResponse) -> int:
        """
        Extract units from program or class webpage
        """
        res_txt = response.xpath(
            "//ul[@class='degree-summary__requirements']/li[@class='degree-summary__requirements-units']/text()")
        lines = [elem.replace('\r\n', '').strip() for elem in res_txt.getall()]
        for line in lines:
            if line and line[0].isnumeric():
                tokens = line.split()
                unit = int(tokens[0])
                return unit
