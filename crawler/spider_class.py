import json

from bs4 import BeautifulSoup
from bs4.element import NavigableString
import scrapy
from scrapy.http.response.html import HtmlResponse

from class_parser import parse_requisites
from models import Program, Requirement, Specialization, Course
from nlp_config import TARGET
from spider_anu import SpiderANU


class SpiderClass(SpiderANU):
    """This class is for scraping ANU classes"""

    name = 'SpiderClass'
    id_attribute_name = 'CourseCode'

    def start_requests(self):
        classes = {}
        with open(f'data/from_api/classes.json') as f:
            data = json.load(f)
            items = data['Items']

            for item in items:
                if item[self.id_attribute_name] not in classes:
                    url = f"https://{self.DOMAIN}/course/{item[self.id_attribute_name]}"
                    yield scrapy.Request(url, self.parse_class)
                    classes[item[self.id_attribute_name]] = item

    def parse(self, response: HtmlResponse, **kwargs) -> Course:
        return self.parse_class(response)

    def parse_class(self, response: HtmlResponse) -> Course:
        if "Error" in response.url:
            self.logger.info(response.url)
            return

        course = Course()
        course['id'] = response.url.split('/')[-1]
        course['name'] = response.css("span.intro__degree-title__component::text").get().strip()
        course['n_units'] = self.parse_unit(response)

        def get_intro_text(response: HtmlResponse):
            soup = BeautifulSoup(response.css("div.introduction").get(), 'html.parser')

            arr = []
            for child in soup.children:
                arr += child,
                break

            elements = [elem.text for elem in arr[0].contents]
            return "\n".join(elements)

        def get_requisites_text(response: HtmlResponse):
            html = response.css("div.requisite").get()
            if not html:
                return

            soup = BeautifulSoup(html, 'html.parser')

            arr = []
            for child in soup.children:
                arr += child,
                break

            txt = ''
            for item in arr[0].contents:
                if type(item) == str:
                    txt += f' {item}'
                else:
                    txt += f' {item.text}'
            return txt.replace('\n', ' ').replace('\\', '').strip()

        course['description'] = get_intro_text(response)

        requisites_txt = get_requisites_text(response)
        if requisites_txt:
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

        return course
