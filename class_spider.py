import json

import scrapy
from scrapy.http.response.html import HtmlResponse

from anu_spider import ANUSpider
from class_parser import parse_requisites
from models import Course
from nlp_config import TARGET


class ClassSpider(ANUSpider):
    name = 'ClassSpider'
    id_attribute_name = 'CourseCode'
    years = ['2020', '2021', '2022']

    def start_requests(self):
        for year in self.years:
            with open(f'data/cecs_classes_{year}.json') as f:
                data = json.load(f)
                items = data['Items']

                for item in items:
                    url = f"https://{self.DOMAIN}/course/{item[self.id_attribute_name]}"
                    yield scrapy.Request(url, self.parse_class)

    def parse_class(self, response: HtmlResponse) -> Course:
        course = Course()
        course['id'] = response.url.split('/')[-1]
        course['name'] = response.css("span.intro__degree-title__component::text").get().strip()
        course['description'] = self.converter.handle(response.css("div.introduction").get()).strip().replace("\n", " ")
        course['n_units'] = self.parse_unit(response)

        # get requisites
        requisites_txt = response.css("div.requisite").get()
        try:
            requisites_txt = self.converter.handle(requisites_txt)
            requisites_txt = requisites_txt.replace('\n', ' ').replace('\\', '').strip()
        except Exception as e:
            self.logger.warn(f"{response.url}\n{course}\n{response.css('div.requisite').get()}")
            # self.logger.error(e)
            return

        doc = self.nlp(requisites_txt)
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
