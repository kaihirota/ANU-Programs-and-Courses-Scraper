import json
import re
from collections import Counter, OrderedDict
from typing import List, Tuple, Union

import scrapy
from bs4 import BeautifulSoup
from scrapy.http.response.html import HtmlResponse

from anu_spider import ANUSpider
from models import Requirement, Program, Course


class ProgramSpider(ANUSpider):
    """This class is for scraping ANU programs - Master, Bachelor, Diploma, etc"""

    name = 'ProgramSpider'
    id_attribute_name = 'AcademicPlanCode'
    data_files = ['data/programs_undergrad.json', 'data/programs_postgrad.json']

    def start_requests(self):
        for file_path in self.data_files:
            with open(file_path) as f:
                data = json.load(f)
                items = data['Items']

                for item in items[:50]:
                    url = f"https://{self.DOMAIN}/program/{item[self.id_attribute_name]}"
                    yield scrapy.Request(url, self.parse)

    def parse(self, response: HtmlResponse, **kwargs):
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

    def convert_response_for_requirements_to_str(self, response: HtmlResponse) -> List[Tuple[str, int]]:
        """
        parse the response and extract requirements as a list of string and indentation level
        """
        html_path = '//div[has-class("body", "transition")]' \
                    '/div[@id="study"]' \
                    '/div[has-class("body__inner", "w-doublewide", "copy")]'

        html = response.xpath(html_path).get()
        soup = BeautifulSoup(html, 'html.parser')

        elements = []
        for child in soup.children:
            elements += child,

        elems = elements[0].contents
        bs_elems = []
        for elem in elems:
            if elem.text in {"Minors", "Study Options", "Specialisations", "Honours grade calculation"}:
                break

            try:
                attributes = dict([prop.split(':') for prop in elem.attrs['style'].split(';')])
                if 'padding-left' in attributes:
                    padding = int(attributes['padding-left'].replace('px', '').replace('pt', '').strip())
                else:
                    padding = int(attributes['margin-left'].replace('px', '').replace('pt', '').strip())
            except Exception:
                padding = 0

            if elem.name and elem.name == 'ul':
                padding = bs_elems[-1][1] + 1
                for c in elem.children:
                    bs_elems += (c.text, padding),
            elif elem.text.replace('\n', '').strip() != '':
                bs_elems += (elem.text.replace('\n', ''), padding),

        counter = Counter([padding for line, padding in bs_elems])
        val_to_freq = OrderedDict(sorted([list(item) for item in counter.items()]))
        rank = 0
        val_to_rank = {}
        for val, _ in val_to_freq.items():
            val_to_rank[val] = rank
            rank += 1

        # convert padding / margin to rank and store in list
        ret = []
        for line, padding in bs_elems:
            if line != 'Program Requirements':
                line = line.replace('\u00a0', ' ').strip()
                ret += [line, val_to_rank[padding]],

        # fix inconsistent indentations
        is_class = [0] * len(ret)
        for i in range(len(ret)):
            doc = self.nlp(ret[i][0])
            is_class[i] = any([ent for ent in doc.ents if ent.label_ == 'CLASS'])

        for i in range(len(ret) - 1):
            if is_class[i] and is_class[i + 1] and ret[i][1] != ret[i + 1][1]:
                ret[i + 1][1] = ret[i][1]

        return ret

    def group_requirements(
            self,
            data: List[Tuple[Union[str, List[str]], int]],
            current_indent_level=0
    ) -> List[Union[Course, Requirement]]:
        requirements = []
        while data:
            line, indent = data.pop()
            doc = self.nlp(line)
            classes = [ent.text for ent in doc.ents if ent.label_ == 'CLASS']

            # check if line is a description like "xx units from completion of classes from the following list"
            m = re.search(r"\d+ unit[s]", line)
            if m and m.group(0):  # TODO: and len(classes) == 0?
                # collect classes for the requirement into a list and recurse
                children = []
                while data and data[-1][1] > indent:
                    children += data.pop(),

                req = Requirement()
                req['description'] = line
                req['n_units'] = int(m.group(0).split()[0])
                req['items'] = self.group_requirements(children[::-1], current_indent_level + 1)

                # sometimes there will be lines like "6 units from completion of COMPxxxx"
                if req['n_units'] and classes and not req['items']:
                    req['items'] = classes
                elif not req['items']:
                    del req['items']

                requirements += req,
            elif classes and len(classes) == 1:
                # assume a single line only contains one class
                course = Course()
                course['id'] = classes[0]
                course['name'] = line.replace(classes[0], "").lstrip('- ').strip()
                requirements += course,

        return requirements

    def parse_requirements(self, response: HtmlResponse) -> List[Requirement]:
        data = self.convert_response_for_requirements_to_str(response)
        return self.group_requirements(data[::-1], 0)
