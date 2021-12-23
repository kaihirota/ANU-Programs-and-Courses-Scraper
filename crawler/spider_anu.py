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

    def parse_class_info(self, response: HtmlResponse) -> str:
        elems = response.xpath(
            "//div[@class='degree-summary__codes']/ul[@class='degree-summary__codes-column']/li[@class='degree-summary__code']/span[@class='degree-summary__code-text']/text()")

        elems = [elem.get().strip() for elem in elems]
        attrs = [elem for elem in elems if elem]

        elems = response.xpath(
            "//div[@class='degree-summary__codes']/ul[@class='degree-summary__codes-column']/li[@class='degree-summary__code']/span[@class='degree-summary__code-heading']/text()")
        elems = [elem.get().strip() for elem in elems]
        attrs_headings = [elem for elem in elems if elem]

        attr_dict = {key: val for key, val in zip(attrs_headings, attrs)}
        return attr_dict

    def parse_convener(self, response: HtmlResponse) -> str:
        elems = response.xpath(
            "//div[@class='degree-summary__codes']/ul[@class='degree-summary__codes-column']/li[@class='degree-summary__code']/ul/li/span/text()")
        elems = [elem.get().strip() for elem in elems]
        elems = [elem for elem in elems if elem]
        return elems[0] if elems else ''

    def parse_co_taught(self, response: HtmlResponse) -> str:
        elems = response.xpath(
            "//div[@class='degree-summary__codes']/ul[@class='degree-summary__codes-column']/li[@class='degree-summary__code']/ul/li/span/a/text()")
        elems = [elem.get().strip() for elem in elems]
        elems = [elem for elem in elems if elem]
        return elems[0] if elems else []