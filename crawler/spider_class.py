import json
import re

from bs4 import BeautifulSoup
from bs4.element import NavigableString
import scrapy
from scrapy.http.response.html import HtmlResponse

from class_parser import parse_requisites
from models import Program, Requirement, Specialization, Course
from nlp_config import TARGET, ALL_SPECIALISATIONS, ALL_PROGRAMS
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

        attrs = self.parse_class_info(response)

        course = Course()
        course['id'] = response.url.split('/')[-1]
        course['subject_code'] = course['id'][:4]
        course['course_number'] = course['id'][4:]
        course['name'] = response.css("span.intro__degree-title__component::text").get().strip()
        course['n_units'] = self.parse_unit(response)
        course['subject'] = attrs['Course subject']
        course['college'] = attrs['ANU College']
        course['offered_by'] = attrs['Offered by']
        course['academic_career'] = attrs['Academic career']
        course['course_convener'] = self.parse_convener(response)
        course['co_taught'] = self.parse_co_taught(response)
        course['description'] = get_intro_text(response)

        course['offered_in'] = []
        for val in attrs.values():
            if type(val) == str and 'semester' in val.lower():
                course['offered_in'] += val,

        requisites_txt = get_requisites_text(response)

        if requisites_txt:
            requisites_txt = requisites_txt.replace('R&D', 'Research and Development')

            # if class code is not followed by a space, insert space
            requisites_txt = re.sub('([A-Z]{4}[0-9]{4})([a-z]+)', '\\1 \\2', requisites_txt)

            # remove everything in a pair of parenthesis if it only contains upper-case characters
            # "Master of Laws (MLLM)" -> "Master of Laws"
            requisites_txt = re.sub('\([A-Z]+\)', '', requisites_txt)

            # apply parenthesis to Advanced / Honours, if it doesn't come after "of"
            requisites_txt = requisites_txt.replace(' Advanced ', ' (Advanced) ').replace(' Honours ', ' (Honours) ')
            requisites_txt = requisites_txt.replace('of (Advanced)', 'of Advanced')

            requisites_txt = requisites_txt.replace('&', 'and')

            # insert space if parenthesis and word are not space-separated
            requisites_txt = re.sub('([A-Za-z])\(', '\\1 (', requisites_txt)

            # strip inner gap between parenthesis and character
            requisites_txt = re.sub('\(\s+', '(', requisites_txt)
            requisites_txt = re.sub('\s+\)', ')', requisites_txt)

            # remove empty parenthesis
            requisites_txt = re.sub('\(\s?\)', '', requisites_txt)

            # remove leading spaces
            requisites_txt = re.sub('\s+', ' ', requisites_txt)

            doc = self.nlp(requisites_txt)
            course['requisites_raw'] = doc.text

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
