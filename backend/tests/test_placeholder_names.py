"""A generic placeholder must never be cast as a character. is_placeholder_
character_name catches unknown markers, bare common nouns, article/adjective +
generic noun, numbered extras, and relational/role labels — while keeping real
names, including ones that are also common words (Rose, Hunter, Grace).
drop_placeholder_characters is the ONE shared gate every Character-row door
uses — the agent pipeline and the manual extract endpoint alike."""
import pytest
from app.services.guardrails import (
    is_placeholder_character_name as ph,
    drop_placeholder_characters,
)


@pytest.mark.parametrize("name", [
    "UNKNOWN FIGURE", "Unknown", "Unnamed", "N/A", "TBD", "Anonymous",
    "Man", "MAN", "Woman", "Boy", "Girl", "Child", "Person", "Figure",
    "Someone", "Crowd", "People", "a mysterious figure", "The Stranger",
    "the old man", "A young woman", "the hooded man", "shadowy figure",
    "their brother", "The Mother", "her son", "his father", "the neighbour",
    "Guard", "Guard 2", "Guard #1", "Villager", "Nurse", "the doctor",
    "Detective", "Officer", "Voice", "Narrator", "Bystander", "Waiter",
    # occupation-only figures
    "Reporter", "Journalist", "Chef", "Lawyer", "Thief", "Dancer", "Singer",
    "Photographer", "Pilot", "Sheriff", "the reporter", "Reporter 2",
    # descriptor stacks ending in a generic noun — the concrete-figure rule
    # taught the writer to say 'a broad-shouldered figure', and it got cast
    "BROAD-SHOULDERED FIGURE", "the rain-soaked figure", "burly man",
    "one-armed stranger", "tattooed woman",
    "", "   ", "???",
])
def test_placeholders_are_flagged(name):
    assert ph(name) is True, name


@pytest.mark.parametrize("name", [
    "Anna", "Deok-hyun", "Myung-joon", "Detective Halloran", "Doctor Kim",
    "Captain Reyes", "King Aeryn", "Father Moon", "Jae-won", "Marco Reyes",
    "Reporter Kim",   # a role with a real name attached survives
    # legitimately common-word first names / surnames must survive
    "Rose", "Hunter", "Grace", "Faith", "Hope", "Joy", "Angel", "Dawn",
    "Sky", "May", "June", "Mercy", "Sunny", "Baker", "Mason", "Cooper",
    "Carter", "Fisher", "Archer",
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


class TestDropPlaceholderCharacters:
    """The 'Shattered Tides' leak: the manual extract endpoint created a
    SHADOWY FIGURE row because only the agent pipeline filtered. Both doors
    now share this one gate."""

    def test_splits_kept_and_dropped(self):
        data = [{"name": "Anna", "role": "PROTAGONIST"},
                {"name": "SHADOWY FIGURE", "role": "ANTAGONIST"},
                {"name": "Deok-hyun", "role": "SUPPORTING"}]
        kept, dropped = drop_placeholder_characters(data)
        assert [c["name"] for c in kept] == ["Anna", "Deok-hyun"]
        assert dropped == ["SHADOWY FIGURE"]

    def test_all_real_names_drop_nothing(self):
        data = [{"name": "Rose"}, {"name": "Hunter"}]
        kept, dropped = drop_placeholder_characters(data)
        assert kept == data
        assert dropped == []

    def test_empty_and_none_input(self):
        assert drop_placeholder_characters([]) == ([], [])
        assert drop_placeholder_characters(None) == ([], [])
