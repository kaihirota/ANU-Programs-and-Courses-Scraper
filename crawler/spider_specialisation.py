import os
import json

import scrapy
from scrapy.http.response.html import HtmlResponse

from models import SpecializationPage
from spider_program import SpiderProgram


class SpiderSpecialisation(SpiderProgram):
    id_attribute_name = 'SubPlanCode'

    def start_requests(self):
        path = 'data/from_api/specialisations'
        for fn in os.listdir(path):
            specialisation_type, _ = os.path.splitext(fn)
            with open(os.path.join(path, fn)) as f:
                data = json.load(f)
                for item in data['Items']:
                    url = f"https://{self.DOMAIN}/{specialisation_type}/{item[self.id_attribute_name]}"
                    yield scrapy.Request(url, self.parse)

    def parse(self, response: HtmlResponse, **kwargs):
        if "Error" in response.url:
            return

        components = response.url.split('/')
        program_id = components[-1]
        specialisation_type = components[-2]
        program_name = response.css('span.intro__degree-title__component::text').get()
        program_name = self.converter.handle(program_name).replace("\n", "")

        item = SpecializationPage()
        item['id'] = program_id
        item['name'] = program_name
        item['type'] = specialisation_type
        item['n_units'] = self.parse_unit(response)
        item['requirements'] = self.parse_requirements(response)
        yield item
