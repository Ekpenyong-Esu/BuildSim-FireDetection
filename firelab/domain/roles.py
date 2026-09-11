"""Who is in the building, and how well they get themselves out.

Speed differences are about familiarity, not fitness: knowing where the back
stairs are matters more than how fast you can run.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    """A kind of person on campus, and how well they get themselves out."""

    key: str
    label: str  # plural, for the UI
    singular: str
    speed: float  # multiplier on the configured walking speed
    note: str


ROLES = (
    Role("student", "Students", "Student", 1.05, "quick, but only know the main entrance"),
    Role("lecturer", "Lecturers", "Lecturer", 1.0, "know the building"),
    Role("staff", "Staff", "Staff", 1.0, "technical and administrative staff"),
    Role("security", "Security", "Guard", 1.15, "drilled on the escape routes"),
    Role("visitor", "Visitors", "Visitor", 0.85, "have never been here before"),
)
ROLE_BY_KEY = {role.key: role for role in ROLES}

DEFAULT_POPULATION = {"student": 28, "lecturer": 5, "staff": 4, "security": 1, "visitor": 2}
