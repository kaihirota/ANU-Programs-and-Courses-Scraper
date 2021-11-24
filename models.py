from typing import List

from scrapy import Field, Item


class Course(Item):
    type: 'course'
    id: str = Field()
    name: str = Field()
    n_units: int = Field()
    description: str = Field()
    requisites: str = Field()
    requisites_raw: str = Field()
    entities: List[str] = Field()


class Requirement(Item):
    n_units: int = Field()
    items: List[str] = Field()
    description: str = Field()


class Program(Item):
    type: 'program'
    id: str = Field()
    name: str = Field()
    requirements: List[Requirement] = Field()


class Specialization(Item):
    type: 'specialization'
    id: str = Field()
    name: str = Field()
    requirements: List[Requirement] = Field()