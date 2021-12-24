from scrapy import Field, Item
from typing import List, Union, Dict, Any


class Node(Item):
    id: str = Field()
    name: str = Field()


class Course(Node):
    subject_code: str = Field()
    course_number: int = Field()
    units: int = Field()
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


class Specialisation(Node):
    type: str = Field()


class Requirement(Item):
    units: int = Field()
    items: List[Union[Course, Specialisation]] = Field()
    description: str = Field()


class Program(Node):
    units: int = Field()
    requirements: List[Requirement] = Field()
    specialisations: List[Specialisation] = Field()


class SpecialisationPage(Specialisation):
    units: int = Field()
    requirements: List[Requirement] = Field()
