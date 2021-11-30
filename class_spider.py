import json

import html2text as html2text
import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

from nlp_params import TARGET
from models import Course
from class_parser import parse_requisites, nlp


class ClassSpider(CrawlSpider):
    domain = 'programsandcourses.anu.edu.au'
    converter = html2text.HTML2Text()
    converter.ignore_links = True

    name = 'ClassSpider'
    year = '2022'
    data_file = f'cecs_classes_{year}.json'

    rules = (
        Rule(LinkExtractor(allow=(r'/program/\w+',),
                           allow_domains={domain}), ),
        Rule(LinkExtractor(allow=(r'/specialisation/\w+-SPEC',),
                           allow_domains={domain}), ),
        Rule(LinkExtractor(allow=(r'/([0-9]{4}/)?course/\w+',),
                           allow_domains={domain}),
             callback='parse_class')
    )

    def start_requests(self):
        with open(self.data_file) as f:
            data = json.load(f)
            items = data['Items']

            for item in items:
                url = f"https://{self.domain}/course/{item['CourseCode']}"
                yield scrapy.Request(url, self.parse_class)

    def parse_class(self, response) -> Course:
        course = Course()
        course['id'] = response.url.split('/')[-1]
        course['name'] = response.css("span.intro__degree-title__component::text").get().strip()
        course['description'] = self.converter.handle(response.css("div.introduction").get()).strip().replace("\n", " ")

        # get units
        txt = " ".join([elem.get() for elem in response.css("li.degree-summary__requirements-units::text")])
        doc = nlp(txt)

        unit = 0
        for token in doc:
            if token.is_digit:
                unit = int(token.text)

        course['n_units'] = unit

        # get requisites
        requisites_txt = response.css("div.requisite").get()
        try:
            requisites_txt = self.converter.handle(requisites_txt)
            requisites_txt = requisites_txt.replace('\n', ' ').replace('\\', '').strip()
        except Exception as e:
            self.logger.warn(f"{response.url}\n{course}\n{response.css('div.requisite').get()}")
            # self.logger.error(e)
            return

        doc = nlp(requisites_txt)
        course['requisites_raw'] = doc.text
        course['entities'] = [ent.text for ent in doc.ents if ent.label_ in TARGET]

        requisites = parse_requisites(doc)
        if len(requisites) > 1:
            course['requisites'] = {
                "description": "",
                "operator": {
                    "AND": requisites
                }
            }
        else:
            course['requisites'] = requisites[0]

        self.logger.info(course)
        return course
