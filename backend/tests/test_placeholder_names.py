"""A generic placeholder must never be cast as a character. is_placeholder_
character_name catches unknown markers, bare common nouns, article/adjective +
generic noun, numbered extras, and relational/role labels — while keeping real
names, including ones that are also common words (Rose, Hunter, Grace)."""
import pytest
from app.services.guardrails import is_placeholder_character_name as ph


@pytest.mark.parametrize("name", [
    "UNKNOWN FIGURE", "Unknown", "Unnamed", "N/A", "TBD", "Anonymous",
    "Man", "MAN", "Woman", "Boy", "Girl", "Child", "Person", "Figure",
    "Someone", "Crowd", "People", "a mysterious figure", "The Stranger",
    "the old man", "A young woman", "the hooded man", "shadowy figure",
    "their brother", "The Mother", "her son", "his father", "the neighbour",
    "Guard", "Guard 2", "Guard #1", "Villager", "Nurse", "the doctor",
    "Detective", "Officer", "Voice", "Narrator", "Bystander", "Waiter",
    "", "   ", "???",
])
def test_placeholders_are_flagged(name):
    assert ph(name) is True, name


@pytest.mark.parametrize("name", [
    "Anna", "Deok-hyun", "Myung-joon", "Detective Halloran", "Doctor Kim",
    "Captain Reyes", "King Aeryn", "Father Moon", "Jae-won", "Marco Reyes",
    # legitimately common-word first names must survive
    "Rose", "Hunter", "Grace", "Faith", "Hope", "Joy", "Angel", "Dawn",
    "Sky", "May", "June", "Mercy", "Sunny",
])
def test_real_names_survive(name):
    assert ph(name) is False, name


def test_two_token_name_with_a_role_survives():
    # a role/title is fine as long as a proper name rides with it
    assert ph("Sergeant Park") is False
    assert ph("Nurse Aria") is False
    # but the role alone is a placeholder
    assert ph("Sergeant") is True
    assert ph("Nurse") is True
