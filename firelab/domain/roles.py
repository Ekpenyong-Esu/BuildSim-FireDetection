"""Who is in the building, and how well they get themselves out.

Speed differences are about familiarity, not fitness: knowing where the back
stairs are matters more than how fast you can run.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    """A kind of person on campus, and how well they get themselves out."""

    key: str  # the id used in config, the API and Occupant.role, e.g. "student"
    label: str  # plural, for the UI
    singular: str  # used to name each person, e.g. "Student 3"
    speed: float  # multiplier on the configured walking speed
    note: str  # why they walk at that speed, shown in the Population panel


ROLES = (
    Role("student", "Students", "Student", 1.05, "quick, but only know the main entrance"),
    Role("lecturer", "Lecturers", "Lecturer", 1.0, "know the building"),
    Role("staff", "Staff", "Staff", 1.0, "technical and administrative staff"),
    Role("security", "Security", "Guard", 1.15, "drilled on the escape routes"),
    Role("visitor", "Visitors", "Visitor", 0.85, "have never been here before"),
)
ROLE_BY_KEY = {role.key: role for role in ROLES}

DEFAULT_POPULATION = {"student": 100, "lecturer": 10, "staff": 5, "security": 5, "visitor": 10}
