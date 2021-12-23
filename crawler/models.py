from scrapy import Field, Item
from typing import List, Union, Dict, Any


class Node(Item):
    id: str = Field()
    name: str = Field()


class Course(Node):
    subject_code: str = Field()
    course_number: int = Field()
    n_units: int = Field()
    description: str = Field()
    requisites: Dict[str, Any] = Field()
    requisites_raw: str = Field()
    subject: str = Field()
    college: str = Field()
    offered_by: str = Field()
    academic_career: str = Field()
    course_convener: str = Field()
    co_taught: str = Field()
    offered_in: List[str] = Field()


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
