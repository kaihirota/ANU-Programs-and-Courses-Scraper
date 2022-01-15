import os
import json

import scrapy
from scrapy.http.response.html import HtmlResponse

from models import SpecialisationPage
from spider_program import SpiderProgram


class SpiderSpecialisation(SpiderProgram):
    name = 'SpiderSpecialisation'
    id_attribute_name = 'SubPlanCode'

    def start_requests(self):
        path = 'data/from_api/specialisations/'
        all_items = {}
        for fn in os.listdir(path):
            s, _ = os.path.splitext(fn)
            specialisation_type, _ = s.split('_')
            with open(os.path.join(path, fn)) as f:
                data = json.load(f)
                for item in data['Items']:
                    all_items[item[self.id_attribute_name]] = specialisation_type
        for key in sorted(all_items.keys()):
            specialisation_type = all_items[key]
            url = f"https://{self.DOMAIN}/{specialisation_type}/{key}"
            yield scrapy.Request(url, self.parse)

    def parse(self, response: HtmlResponse, **kwargs):
        if "Error" in response.url:
            self.logger.info(response.url)
            return

        components = response.url.split('/')
        program_id = components[-1]
        specialisation_type = components[-2]
        program_name = response.css('span.intro__degree-title__component::text').get()
        program_name = self.converter.handle(program_name).replace("\n", "")

        item = SpecialisationPage()
        item['id'] = program_id
        item['name'] = program_name
        item['type'] = specialisation_type
        item['units'] = self.parse_unit(response)
        item['requirements'] = self.parse_requirements(response)
        yield item
