import json
import re
from collections import Counter, OrderedDict
from typing import List, Tuple, Union

from bs4 import BeautifulSoup
import scrapy
from scrapy.http.response.html import HtmlResponse

from models import Program, Requirement, Specialization, Course
from spider_anu import SpiderANU


class SpiderProgram(SpiderANU):
    """This class is for scraping ANU programs - Master, Bachelor, Diploma, etc"""

    name = 'ProgramSpider'
    id_attribute_name = 'AcademicPlanCode'
    data_files = ['data/from_api/programs_undergrad.json', 'data/from_api/programs_postgrad.json']

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

        arr = []
        for child in soup.children:
            arr += child,

        elements = arr[0].contents
        elements_with_padding = []
        for elem in elements:
            if elem.name == 'h2' and elem.text != 'Program Requirements':
                break
            if elem.text in {"Minors", "Study Options", "Specialisations", "Honours grade calculation"}:
                break

            try:
                attributes = dict([prop.split(':') for prop in elem.attrs['style'].split(';') if prop])
                if 'padding-left' in attributes:
                    padding = int(float(attributes['padding-left'].replace('px', '').replace('pt', '').strip()))
                elif 'margin-left' in attributes:
                    padding = int(float(attributes['margin-left'].replace('px', '').replace('pt', '').strip()))
                else:
                    padding = 0
            except Exception:
                padding = 0

            if elem.name and elem.name == 'ul':
                padding = elements_with_padding[-1][1] + 1
                for c in elem.children:
                    elements_with_padding += (c.text, padding),
            else:
                txt = elem.text
                p = re.compile(r"([A-Z]{4}[0-9]{4})")
                txt = p.sub(r' \1', txt)
                txt = txt.replace('\n', '').replace('\xa0', '').strip()
                if txt:
                    elements_with_padding += (txt, padding),

        def convert_padding_to_rank(elements: List[Tuple[str, int]]) -> List[Tuple[str, int]]:
            # use OrderedDict to preserve order
            counter = Counter([padding for line, padding in elements])
            val_to_freq = OrderedDict(sorted([list(item) for item in counter.items()]))
            rank = 0
            val_to_rank = {}
            for val, freq in val_to_freq.items():
                val_to_rank[val] = rank

                # correct indentation if indent size difference is less than 10 but greater than 0
                for other_val, _ in val_to_freq.items():
                    if 0 < abs(val - other_val) < 10:
                        if other_val in val_to_rank:
                            val_to_rank[val] = val_to_rank[other_val]

                rank += 1

            # convert padding / margin to rank and store in list
            ret = []
            for line, padding in elements:
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

        return convert_padding_to_rank(elements_with_padding)

    def group_requirements(
            self,
            data: List[Tuple[Union[str, List[str]], int]],
            current_indent_level: int=0,
            is_specialisation: bool=False,
            specialisation_type: str=None
    ) -> List[Union[Course, Requirement, Specialization]]:
        requirements = []
        while data:
            line, indent = data.pop()
            doc = self.nlp(line)
            classes = [ent.text for ent in doc.ents if ent.label_ == 'CLASS']

            # check if line is a description like "xx units from completion of classes from the following list"
            m = re.search(r"\d+ unit[s]", line)
            if m and m.group(0) and len(classes) == 0:
                # collect classes for the requirement into a list and recurse
                children = []
                while data and data[-1][1] > indent:
                    children += data.pop(),

                req = Requirement()
                req['description'] = line
                req['n_units'] = int(m.group(0).split()[0])
                req['items'] = self.group_requirements(children[::-1], current_indent_level + 1)

                if 'major' in line and 'minor' not in line:
                    req['items'] = self.group_requirements(children[::-1], current_indent_level + 1, True, 'Major')
                elif 'minor' in line:
                    req['items'] = self.group_requirements(children[::-1], current_indent_level + 1, True, 'Minor')
                elif 'specialisation' in line:
                    req['items'] = self.group_requirements(children[::-1], current_indent_level + 1, True, 'Specialization')
                else:
                    # sometimes there will be lines like "6 units from completion of COMPxxxx"
                    if classes and not req['items']:
                        req['items'] = classes
                    if 'items' in req and not req['items']:
                        del req['items']

                requirements += req,
            elif classes:
                if len(classes) == 1:
                    # assume a single line only contains one class
                    if 'units' in line.lower():
                        line = re.sub(r"\(\d+ unit[s]\)", "", line)
                    line = line.replace(classes[0], "").lstrip('- ').strip()

                    course = Course()
                    course['id'] = classes[0]
                    course['name'] = line
                    requirements += course,
                else:
                    class_id = ''
                    class_name = ''
                    classes_group = set()
                    for token in doc:
                        if token.ent_type_ == 'CLASS':
                            if class_id and class_name:
                                course = Course()
                                course['id'] = class_id
                                course['name'] = class_name.strip()
                                requirements += course,
                                classes_group.add(class_id)

                            class_id = token.text
                            class_name = ''
                        else:
                            class_name += token.text + " "

                    if class_id not in classes_group:
                        course = Course()
                        course['id'] = class_id
                        course['name'] = class_name.strip()
                        requirements += course,

            elif current_indent_level > 0:
                if 'major' in line.lower() or 'minor' in line.lower():
                    item = Specialization()

                    if 'major' in line.lower():
                        line = line.replace('major', '')
                        item['type'] = 'major'
                    else:
                        line = line.replace('minor', '')
                        item['type'] = 'minor'

                    item['name'] = line.strip()
                    requirements += item,
                else:
                    if 'Either' in doc.vocab and any([line.replace(":", "") == 'Or' for line, padding in data]):
                        item = Requirement()
                        item['description'] = line
                        item['items'] = []

                        children = []
                        while data and data[-1][0].replace(":", "") != 'Or':
                            children += data.pop(),

                        item['items'] += self.group_requirements(children[::-1], current_indent_level+1),

                        if not data:
                            break

                        data.pop() # throw away "Or"

                        children2 = []
                        children2 += data.pop(),
                        while data and data[-1][1] > children2[0][1]:
                            children2 += data.pop(),

                        item['items'] += self.group_requirements(children2[::-1], current_indent_level+1),
                        # item['n_units']
                        requirements += item,
                    elif is_specialisation:
                        item = Specialization()
                        item['name'] = line
                        item['type'] = specialisation_type
                        requirements += item,
                    # else:
                    #     item = Requirement()
                    #     item['description'] = line
                    #     requirements += item,

        return requirements

    def parse_requirements(self, response: HtmlResponse) -> List[Requirement]:
        data = self.convert_response_for_requirements_to_str(response)
        return self.group_requirements(data[::-1], 0)
