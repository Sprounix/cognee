from uuid import UUID, uuid4
from enum import Enum
from typing import List, Dict, Optional

from pydantic import Field, field_validator

from cognee.low_level import DataPoint


class JobLevelEnum(str, Enum):
    internship = "Internship"
    entry_level = "Entry-level"
    junior = "Junior"
    mid_level = "Mid-level"
    senior = "Senior"
    lead = "Lead"
    principal = "Principal"
    staff = "Staff"
    manager = "Manager"
    director = "Director"
    executive = "Executive"
    other = "Other"


class JobTypeEnum(str, Enum):
    internship = "Internship"
    full_time = "Full-time"
    part_time = "Part-time"
    contract = "Contract"
    temporary = "Temporary"
    per_diem = "Per-Diem"
    other = "Other"


class QualificationCategoryEnum(str, Enum):
    education = "Education"
    major = "Major"
    experience = "Experience"
    skill = "Skill"
    language = "Language"
    certificate = "Certificate"
    industry = "Industry"
    other = "Other"


class NameData(DataPoint):
    name: str
    metadata: Dict = {
        "index_fields": ["name"],
    }


class Company(NameData):
    pass


class JobSkill(NameData):
    pass


class JobLocation(NameData):
    pass


class JobEducation(NameData):
    pass

class JobMajor(NameData):
    pass


class JobIndustry(NameData):
    pass


class JobFunction(NameData):
    pass


class JobLanguage(DataPoint):
    name: str
    proficiency: Optional[str] | None = Field(
        default=None
    )
    metadata: Dict = {
        "index_fields": ["name"],
    }


class QualificationItem(DataPoint):
    category: str = Field(
        title="Qualification Category",
        examples=[
            "Education",
            "Major",
            "Experience",
            "Skill",
            "Language",
            "Certificate",
            "Industry",
            "Other",
        ],
    )
    item: str
    metadata: Dict = {
        "index_fields": ["item"],
    }


class Qualification(DataPoint):
    required: List[QualificationItem] = Field(
        default=[],
        title="Required requirements",
    )
    preferred: List[QualificationItem] = Field(
        default=[],
        title="Preferred requirements",
    )


class ResponsibilityItem(DataPoint):
    item: str
    metadata: Dict = {
        "index_fields": ["item"],
    }


class Job(DataPoint):
    """
    Extracted job information with complete required parameters and valid data types.
    """
    id: UUID = Field(
        default_factory=uuid4,
        title="Job ID",
        description="Use the provided `id` as the job `id`.",
    )
    title: str = Field(
        title="Job Title",
        description="Job Title",
    )
    job_level: List[str] = Field(
        title="Job level",
        description="Job level include Internship, Entry-level, Junior, Mid-level, Senior, Lead, Principal, Staff, Manager, Director, Executive, Other",
        examples=["Senior"]
    )
    # compensation: str = Field(
    #     default="",
    #     title="Compensation",
    #     description="Compensation Range",
    #     examples=["$200,000.00/yr - $500,000.00/yr"]
    # )
    job_function: JobFunction = Field(
        title="Job function",
        description="Extract the core job title,  (i.e., the standard name of the position, such as `Python Engineer` or `Product Manager`) from the given job title, ignoring non-job title information such as location, industry direction, experience requirements, and skill attachments contained in the text.",
        examples=[{"name": "Python Engineer"}]
    )
    work_locations: List[JobLocation] = Field(
        title="Work Locations",
        description='All specified work locations. Look for city/area/state names.',
        examples=[{"name": "New York, NY"},]
    )
    skills: List[JobSkill] = Field(
        title="Core Skill Tags",
        description="Core professional skill tags required for the job, with a maximum of 8 tags.",
        examples=[{"name": "Python"}]
    )
    job_type: List[str] = Field(
        title="Job Type",
        description="job types include Internship, Full-time, Part-time, Contract, Temporary, Per Diem, Seasonal, Other.",
        examples=["Full-time"]
    )
    # education: List[JobEducation] = Field(
    #     default=[],
    #     title="Education requirements",
    #     description="List of education requirements",
    #     examples=["Bachelor"]
    # )
    majors: List[JobMajor] = Field(
        title="Major requirements",
        description="Requirements for professional fields or disciplines of the job.",
        examples=[{"name": "Computer Science"}]
    )
    # languages: Optional[List[JobLanguage]] = Field(
    #     default=[],
    #     title="Language requirements",
    #     description="Language refers to human natural languages used for communication (e.g., English, Chinese), excluding programming languages or computer languages.",
    #     examples=["English", "Chinese"]
    # )
    # industries: Optional[List[JobIndustry]] = Field(
    #     default=[],
    #     title="Industry requirements",
    #     description="Requirements for relevant industry experience of the job.",
    #     examples=["Financial"]
    # )
    qualification: Qualification = Field(
        title="Qualification",
        description="Job qualification requirements, including required and preferred requirements, every item returned sentence by sentence.",
    )
    responsibilities: List[ResponsibilityItem] = Field(
        title="Core Responsibilities",
        description="Summarize the core responsibilities of the current position, with a maximum of 5 item, every item returned sentence by sentence.",
    )

    metadata: Dict = {
        "index_fields": ["title"],
    }
