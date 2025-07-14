from enum import Enum
from typing import List, Dict, Optional

from pydantic import Field

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
    The `id` must be returned in UUIDv4 format; otherwise, processing errors will occur.
    """
    title: str = Field(
        title="Job Title",
        description="Work location requirements",
    )
    job_level: List[JobLevelEnum] = Field(
        title="Job level",
        description="Job level",
        examples=["Senior"]
    )
    # job_functions: List[JobFunction] = Field(
    #     default=[],
    #     title="Job functions",
    #     description="Core functional tags of the job",
    # )
    work_locations: List[JobLocation] = Field(
        default=[],
        title="Work Locations",
        description='All specified work locations. Look for city/state names. Also, explicitly identify if the role is "Remote", "Hybrid", or "On-site".',
        examples=["United States", "Remote", "Hybrid", "On-site"]
    )
    # work_years: List[str] = Field(
    #     default=[],
    #     title="Work Years",
    #     description="The overall requirement for years of work experience for this job",
    #     examples=["5+ years of experience"]
    # )
    skills: List[JobSkill] = Field(
        default=[],
        title="Skill Tags",
        description="Core professional skill tags required for the job",
        examples=[{"name": "Python"}]
    )
    job_type: List[JobTypeEnum] = Field(
        default=[],
        title="Job Type",
        description="job types include Internship, Full-time, Part-time, Contract, Temporary, Per Diem, Other.",
        examples=["Full-time"]
    )
    # education: List[JobEducation] = Field(
    #     default=[],
    #     title="Education requirements",
    #     description="List of education requirements",
    #     examples=["Bachelor"]
    # )
    majors: List[JobMajor] = Field(
        default=[],
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
        default=[],
        title="Responsibility requirements",
        description="Descriptions of responsibilities and tasks of the job, every item returned sentence by sentence.",
    )

    metadata: Dict = {
        "index_fields": ["title"],
    }
