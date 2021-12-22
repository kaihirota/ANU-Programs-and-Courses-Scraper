from scrapy import Field, Item
from typing import List, Union, Dict, Any


class Node(Item):
    id: str = Field()
    name: str = Field()


class Course(Node):
    n_units: int = Field()
    description: str = Field()
    requisites: Dict[str, Any] = Field()
    requisites_raw: str = Field()
    entities: List[str] = Field()


class Specialization(Node):
    type: str = Field()

class Requirement(Item):
    n_units: int = Field()
    items: List[Union[Course, Specialization]] = Field()
    description: str = Field()


class Program(Node):
    n_units: int = Field()
    requirements: List[Requirement] = Field()
    specialisations: List[Specialization] = Field()

class SpecializationPage(Specialization):
    n_units: int = Field()
    requirements: List[Requirement] = Field()
