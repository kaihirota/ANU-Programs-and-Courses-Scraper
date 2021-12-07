from typing import List

from scrapy import Field, Item


class Course(Item):
    id: str = Field()
    name: str = Field()
    n_units: int = Field()
    description: str = Field()
    requisites: str = Field()
    requisites_raw: str = Field()
    entities: List[str] = Field()


class Requirement(Item):
    n_units: int = Field()
    items: List[Course] = Field()
    description: str = Field()


class Program(Item):
    id: str = Field()
    name: str = Field()
    n_units: int = Field()
    requirements: List[Requirement] = Field()
    specialisations: List[str] = Field()


class Specialization(Item):
    id: str = Field()
    name: str = Field()
    n_units: int = Field()
    requirements: List[Requirement] = Field()
