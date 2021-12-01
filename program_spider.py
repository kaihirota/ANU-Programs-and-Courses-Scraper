import json
from collections import deque
from typing import List

import scrapy
from scrapy import Selector

from anu_spider import ANUSpider
from models import Course, Requirement, Program, Specialization


class ProgramSpider(ANUSpider):
    name = 'ProgramSpider'
    id_attribute_name = 'AcademicPlanCode'
    data_files = ['data/programs_undergrad.json', 'data/programs_postgrad.json']

    def start_requests(self):
        for file_path in self.data_files:
            with open(file_path) as f:
                data = json.load(f)
                items = data['Items']

                for item in items[:5]:
                    url = f"https://{self.DOMAIN}/program/{item[self.id_attribute_name]}"
                    yield scrapy.Request(url, self.parse_program)

    def parse_program(self, response):
        program_id = response.url.split('/')[-1]
        program_name = response.css('span.intro__degree-title__component::text').get()
        if program_name:
            self.logger.info(response.url)
            program_name = self.converter.handle(program_name).replace("\n", "")

            p = Program()
            p['id'] = program_id
            p['name'] = program_name
            p['n_units'] = self.parse_unit(response)
            p['requirements'] = self.parse_requirements(response)
            yield p

    def parse_requirements(self, response) -> List[Requirement]:
        queue = deque(response.xpath("//div[contains(@id, 'study')]/div/p"))
        requirements = []
        while queue:
            popped_item: Selector = queue.popleft()
            popped_item_tokens = self.converter.handle(popped_item.get()).split()

            if 'specialisation' not in response.url and 'Specialisations:' in popped_item_tokens:
                # parse specialization section of a program (not specialization page)
                units = 0
                for t in popped_item_tokens:
                    try:
                        units = int(t)
                    except Exception:
                        pass
                r = Requirement()
                r['n_units'] = units
                r['items'] = self.parse_specializations(response)
                r['description'] = self.converter.handle(popped_item.get()).replace("\n", "")
                requirements += r,
            elif 'units' in popped_item_tokens \
                    and 'following' in popped_item_tokens \
                    and queue and not queue[0].get()[0].isnumeric():
                units = 0
                for t in popped_item_tokens:
                    try:
                        units = int(t)
                    except Exception:
                        pass

                req = []
                while queue:
                    popped_item_tokens = self.converter.handle(queue[0].get()).split()
                    if len(popped_item_tokens) > 1 and not popped_item_tokens[0].isnumeric():
                        c = Course()
                        c['n_units'] = 6
                        c['id'] = popped_item_tokens[0]
                        c['name'] = " ".join(popped_item_tokens[1:])
                        req += c,
                        queue.popleft()
                    else:
                        break

                r = Requirement()
                r['n_units'] = units
                r['items'] = req
                r['description'] = self.converter.handle(popped_item.get()).replace("\n", "")
                requirements += r,

        return requirements

    def parse_specializations(self, response) -> List:
        self.logger.info(response.url)
        specialisations = []
        for item in response.xpath("//div[@class='body__inner__columns']/div/ul/li/a"):
            specialisations += {"name": item.css('a::text').extract_first(), 'path': item.attrib['href']},
        return specialisations

    def parse_specialization_requirements(self, response) -> List[Requirement]:
        if len(response.xpath("//div[contains(@id, 'study')]/div/table")) > 0:
            reqs = []
            req = []

            for course_selector in response.xpath("//div[contains(@id, 'study')]/div/table/tbody/tr"):
                c = Course()
                c['n_units'] = 6
                c['id'] = course_selector.xpath('td/a/text()').get()
                c['name'] = self.converter.handle(course_selector.xpath('td')[1].get()).strip()
                req += c,

            s = self.converter.handle(response.xpath("//div[contains(@id, 'study')]/div/p").get())
            tokens = s.split()
            units = 0
            for t in tokens:
                try:
                    units = int(t)
                except Exception:
                    pass
            r = Requirement()
            r['items'] = req
            r['n_units'] = units
            r['description'] = s.replace("\n", "")
            reqs += r,
            return reqs
        else:
            queue = deque(response.xpath("//div[contains(@id, 'study')]/div/p"))
            requirements = []
            while queue:
                popped_item: Selector = queue.popleft()
                popped_item_tokens = self.converter.handle(popped_item.get()).split()

                if 'units' in popped_item_tokens \
                        and 'following' in popped_item_tokens \
                        and queue \
                        and not queue[0].get()[0].isnumeric():
                    units = 0
                    for t in popped_item_tokens:
                        try:
                            units = int(t)
                        except Exception:
                            pass

                    req = []
                    while queue:
                        popped_item_tokens = self.converter.handle(queue[0].get()).split()
                        if len(popped_item_tokens) > 1 and not popped_item_tokens[0].isnumeric():
                            c = Course()
                            c['n_units'] = 6
                            c['id'] = popped_item_tokens[0]
                            c['name'] = " ".join(popped_item_tokens[1:])
                            req += c,
                            queue.popleft()
                        else:
                            break

                    r = Requirement()
                    r['n_units'] = units
                    r['items'] = req
                    r['description'] = self.converter.handle(popped_item.get()).replace("\n", "")
                    requirements += r,

            return requirements
