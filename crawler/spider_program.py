from collections import Counter, OrderedDict
import json
import os
import re
from typing import List, Tuple, Union, Dict

from bs4 import BeautifulSoup
from bs4.element import NavigableString
import scrapy
from scrapy.http.response.html import HtmlResponse

from nlp_config import SPEC_MAPPER, ALL_SPECIALISATIONS
from models import Program, Requirement, Specialisation, Course
from spider_anu import SpiderANU


class SpiderProgram(SpiderANU):
    """This class is for scraping ANU programs - Master, Bachelor, Diploma, etc"""
    name = 'SpiderProgram'
    id_attribute_name = 'AcademicPlanCode'
    data_files = ['data/from_api/programs_undergrad.json', 'data/from_api/programs_postgrad.json']
    html_path = '//div[has-class("body", "transition")]' \
                '/div[@id="study"]' \
                '/div[has-class("body__inner", "w-doublewide", "copy")]'

    def start_requests(self):
        for file_path in self.data_files:
            with open(file_path) as f:
                data = json.load(f)
                for item in data['Items']:
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
            p['units'] = self.parse_unit(response)
            p['specialisations'] = self.extract_specialisations(response)
            p['requirements'] = self.parse_requirements(response)
            for i in range(len(p['requirements'])):
                p['requirements'][i] = self.fix_requirement(p['requirements'][i], p['specialisations'])
            yield p

    def fix_requirement(self, req: Union[Requirement, Specialisation], records: List[Specialisation]) -> Union[Requirement, Specialisation]:
        if 'items' in req and req['items']:
            for i in range(len(req['items'])):
                req['items'][i] = self.fix_requirement(req['items'][i], records)
        if type(req) == Specialisation:
            if 'name' in req:
                req['name'] = self.fix_specialisation_name(req['name'])
            if 'id' not in req:
                for item in records:
                    if item['name'] == req['name'] and item['type'] == req['type']:
                        req['id'] = item['id']
                        return req
            if 'id' not in req:
                for item in records:
                    if item['name'] == req['name']:
                        req['id'] = item['id']
                        return req
        if type(req) == list:
            return [self.fix_requirement(item, records) for item in req]
        return req

    def fix_specialisation_name(self, s: str):
        # clean up name
        for keyword in ['Minor', 'minor', 'Major', 'major', 'Specialisation', 'specialisation']:
            if s.endswith(keyword):
                s = s.rstrip(keyword).strip()

        s = re.sub('[A-Z]{3,5}-[A-Z]{3,4}', '', s).strip()
        # s = re.sub('[A-Z]+-[A-Z]+', '', s).strip()

        # remove everything in a pair of parenthesis if it only contains upper-case characters
        # "Master of Laws (MLLM)" -> "Master of Laws"
        s = re.sub('\([A-Z]+\)', '', s).strip()
        return s

    def fix_specialisation_req(self, spec: Specialisation, records: Dict[str, Specialisation]) -> Specialisation:
        spec['name'] = self.fix_specialisation_name(spec['name'])

        # remap specialisation type
        if 'type' in spec and spec['type'] not in {'MAJ', 'MIN', 'SPC'}:
            if spec['type'].lower() in SPEC_MAPPER:
                spec['type'] = SPEC_MAPPER[spec['type'].lower()]

        # find matching specialisation
        for item in records.values():
            if spec['name'].lower().replace(' ', '') == item['Name'].lower().replace(' ', '') and spec['type'] == item['SubplanType']:
                spec['id'] = item['SubPlanCode']
                return spec
        for item in records.values():
            if spec['name'].lower().replace(' ', '') == item['Name'].lower().replace(' ', ''):
                spec['id'] = item['SubPlanCode']
                return spec
        return spec

    def extract_specialisations(self, response: HtmlResponse) -> List[Specialisation]:
        html = response.xpath(self.html_path).get()
        soup = BeautifulSoup(html, 'html.parser')
        spec_headings = {'Majors', 'Minors', 'Specialisations'}

        arr = []
        for child in soup.children:
            arr += child,

        elements = arr[0].contents[::-1]
        elements = [elem for elem in elements if type(elem) != NavigableString]
        specialisations = []

        while elements:
            elem = elements.pop()
            if elem.name == 'h2' and elem.text in spec_headings:
                next_elem = elements.pop()
                if next_elem.name == 'div' and 'body__inner__columns' in next_elem.attrs['class']:
                    children = next_elem.find_all('a')
                    for child in children:
                        spec_name = child.text
                        if spec_name.endswith('Minor'):
                            spec_name = spec_name.replace('Minor', '').strip()

                        _, spec_type, spec_id = child.attrs['href'].split('/')
                        spec_type = spec_type

                        spec = Specialisation()
                        spec['id'] = spec_id
                        spec['name'] = spec_name
                        spec['type'] = spec_type
                        specialisations += self.fix_specialisation_req(spec, ALL_SPECIALISATIONS),
        return specialisations

    def convert_response_for_requirements_to_str(self, response: HtmlResponse) -> List[Tuple[str, int]]:
        """
        parse the response and extract requirements as a list of string and indentation level
        """
        html = response.xpath(self.html_path).get()
        soup = BeautifulSoup(html, 'html.parser')
        req_headings = {'Program Requirements', 'Requirements', "Major Requirements", "Specialisation Requirements",
                        "Honours"}

        arr = []
        for child in soup.children:
            arr += child,

        elements = arr[0].contents
        elements_with_padding = []
        for elem in elements:
            if elem.name == 'h2' and elem.text not in req_headings:
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
            elif elem.name and elem.name == 'table':
                classes = self.parse_table(elem)
                for c in classes:
                    class_name = " ".join([s for s in c if len(s) > 2])
                    elements_with_padding += (class_name, padding + 20),
            else:
                txt = elem.text
                p = re.compile(r"([A-Z]{4}[0-9]{4})")
                txt = p.sub(r' \1 ', txt)
                txt = txt.replace('\n', '').replace('\xa0', '').replace('  ', ' ').strip()
                if txt:
                    doc = self.nlp(txt)
                    classes = [ent.text for ent in doc.ents if ent.label_ == 'CLASS']
                    if len(classes) > 1:
                        s = ''
                        for token in doc:
                            if token.ent_type_ == 'CLASS':
                                if s != '':
                                    elements_with_padding += (s, padding),
                                s = token.text
                            else:
                                s += ' ' + token.text
                        if s != '':
                            elements_with_padding += (s, padding),
                            s = ''
                    else:
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

    def parse_table(self, elem: NavigableString) -> List[List[str]]:
        soup_table = BeautifulSoup(str(elem))

        data = []
        table_body = soup_table.find('tbody')
        rows = table_body.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            cols = [ele.text.strip() for ele in cols]
            data += [ele for ele in cols if ele],  # Get rid of empty values
        return data

    def group_requirements(
            self,
            data: List[Tuple[Union[str, List[str]], int]],
            current_indent_level: int = 0,
            is_specialisation: bool = False,
            specialisation_type: str = None
    ) -> List[Union[Course, Specialisation, Requirement]]:
        requirements = []
        while data:
            line, indent = data.pop()
            lowercase_line = line.lower()
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
                req['units'] = int(m.group(0).split()[0])
                req['items'] = self.group_requirements(children[::-1], current_indent_level + 1)

                if 'major' in lowercase_line and 'minor' not in lowercase_line:
                    req['items'] = self.group_requirements(children[::-1], current_indent_level + 1, True, 'MAJ')
                elif 'minor' in lowercase_line:
                    req['items'] = self.group_requirements(children[::-1], current_indent_level + 1, True, 'MIN')
                elif 'specialisation' in line:
                    req['items'] = self.group_requirements(children[::-1], current_indent_level + 1, True, 'SPC')
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

                    # clean up class name
                    if 'units' in lowercase_line:
                        line = re.sub(r"\(\d+ unit[s]\)", "", line)

                    line = line.replace(classes[0], "").lstrip('- ').strip()
                    line = line.replace('Advanced', '(Advanced)')\
                                .replace('( ', '')\
                                .replace(' )', '').strip()
                    line = line.replace('OR', '').strip()

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
                if 'major' in lowercase_line or 'minor' in lowercase_line or 'specialisation' in lowercase_line:
                    item = Specialisation()

                    pattern = '[A-Z]{3,5}-[A-Z]{3,4}'
                    m = re.match(pattern, line)
                    if m:
                        matched_record = ALL_SPECIALISATIONS[m.group(0)]
                        item['id'] = matched_record['SubPlanCode']
                        item['name'] = matched_record['Name']
                        item['type'] = matched_record['SubplanType']
                        requirements += self.fix_specialisation_req(item, ALL_SPECIALISATIONS),
                    else:
                        if 'major' in lowercase_line:
                            item['type'] = 'MAJ'
                        elif 'minor' in lowercase_line:
                            item['type'] = 'MIN'
                        else:
                            item['type'] = 'SPC'

                        item['name'] = line.strip()
                        requirements += self.fix_specialisation_req(item, ALL_SPECIALISATIONS),
                else:
                    if 'Either' in doc.vocab and any([line.replace(":", "") == 'Or' for line, padding in data]):
                        item = Requirement()
                        item['description'] = line
                        item['items'] = []

                        children = []
                        while data and data[-1][0].replace(":", "") != 'Or':
                            children += data.pop(),

                        item['items'] += self.group_requirements(children[::-1], current_indent_level + 1),

                        if not data:
                            break

                        data.pop()  # throw away "Or"

                        children2 = []
                        children2 += data.pop(),
                        while data and data[-1][1] > children2[0][1]:
                            children2 += data.pop(),

                        item['items'] += self.group_requirements(children2[::-1], current_indent_level + 1),
                        # item['units']
                        requirements += item,
                    elif is_specialisation:
                        item = Specialisation()
                        item['name'] = line.strip()
                        item['type'] = specialisation_type
                        requirements += self.fix_specialisation_req(item, ALL_SPECIALISATIONS),
                    # else:
                    #     item = Requirement()
                    #     item['description'] = line
                    #     requirements += item,

        return requirements

    def parse_requirements(self, response: HtmlResponse) -> List[Requirement]:
        data = self.convert_response_for_requirements_to_str(response)
        return self.group_requirements(data[::-1], 0)
