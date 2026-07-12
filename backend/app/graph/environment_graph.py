"""Environment-reaction graph: an EVENT's state overrides a LOCATION's default.

Video models apply a location's default crowd behavior even when the shot's
event should change it — a concert hall renders applause in the very shot
where the performer collapses. This module keeps a small, composable Neo4j
graph of that world knowledge:

    (Location)-[:DEFAULT_BEHAVIOR {priority:0}]->(EnvironmentBehavior)
    (Event)-[:OVERRIDES {priority:N}]->(EnvironmentBehavior)

At prompt-craft time the shot's location + detected events resolve to the
HIGHEST-priority applicable behavior. The winner is injected into the
positive prompt; the suppressed default goes into the negative prompt. New
locations and events are pure data — extend the graph, not the code.

Everything here is best-effort: no Neo4j (or no match) resolves to None and
the pipeline runs exactly as before.
"""
import logging
import re

logger = logging.getLogger(__name__)

# ── seed data: the value is the override MECHANISM, not exhaustive coverage ──

BEHAVIORS: dict[str, str] = {
    "crowd_cheering": "the crowd stands, applauding, cheering, waving",
    "crowd_shock": ("the crowd is frozen in shock, hands over mouths, murmuring, "
                    "some rising in alarm"),
    "crowd_panic": "the crowd scatters, people running, screaming, ducking for cover",
    "ward_calm": "nurses walk unhurried, monitors beep steadily, visitors talk quietly",
    "ward_emergency": ("staff rush to the bedside, a crash cart is wheeled in, "
                       "urgent voices, a monitor alarm sounding"),
    "street_indifferent": "pedestrians pass by, traffic flows, no one pays attention",
    "street_alarmed": ("passers-by stop and turn, some backing away, one reaching "
                       "for a phone, traffic slowing"),
    "diners_murmur": "diners chat over their tables, cutlery clinks, staff weave between tables",
    "diners_stare": "diners fall silent and stare, forks frozen midair, a waiter stopping mid-step",
    "office_routine": "colleagues type at their desks, phones ring quietly, someone carries coffee",
    "office_alarmed": "colleagues rise from their desks, heads turning, someone hurrying over",
    "room_still": "the room is quiet and still, nothing moves but curtains and dust in the light",
}

LOCATION_DEFAULTS: dict[str, str] = {
    "concert_hall": "crowd_cheering",
    "hospital_room": "ward_calm",
    "street": "street_indifferent",
    "restaurant": "diners_murmur",
    "office": "office_routine",
    "police_station": "office_routine",
    "home": "room_still",
    "school": "office_routine",
    "warehouse": "room_still",
    "rooftop": "room_still",
}

# event -> (behavior, priority). Higher priority wins over the location default
# (priority 0) and over lower-priority concurrent events.
EVENT_OVERRIDES: dict[str, tuple[str, int]] = {
    "performer_collapse": ("crowd_shock", 10),
    "medical_emergency": ("ward_emergency", 10),
    "public_collapse": ("street_alarmed", 10),
    "gunshot": ("crowd_panic", 20),
    "explosion": ("crowd_panic", 20),
    "fight": ("crowd_shock", 10),
    "arrest": ("crowd_shock", 5),
    "public_confrontation": ("diners_stare", 5),
    "death_discovered": ("crowd_shock", 10),
}

# which locations an event's override plausibly applies to; empty = any
EVENT_LOCATIONS: dict[str, set[str]] = {
    "performer_collapse": {"concert_hall"},
    "medical_emergency": {"hospital_room"},
    "public_collapse": {"street", "restaurant", "office", "school"},
}

_LOCATION_PATTERNS: list[tuple[str, str]] = [
    (r"concert|stage|arena|theater|theatre|performance", "concert_hall"),
    (r"hospital|ward|clinic|icu|emergency room", "hospital_room"),
    (r"street|alley|sidewalk|road|crosswalk", "street"),
    (r"restaurant|cafe|diner|bar\b|club", "restaurant"),
    (r"office|precinct|station house", "office"),
    (r"police", "police_station"),
    (r"school|classroom|campus", "school"),
    (r"warehouse|factory", "warehouse"),
    (r"rooftop|roof\b", "rooftop"),
    (r"home|house|apartment|bedroom|living room|kitchen", "home"),
]

_EVENT_PATTERNS: list[tuple[str, str]] = [
    (r"collaps|faint|passes out|clutch(es|ing) (his|her|their) chest|goes still|unconscious",
     "performer_collapse"),
    (r"flatlin|cardiac|resuscitat|code blue", "medical_emergency"),
    (r"gun|shot|shoot|pistol|firearm", "gunshot"),
    (r"explo|blast|bomb", "explosion"),
    (r"fight|punch|attack|assault|struggle", "fight"),
    (r"arrest|handcuff|apprehend", "arrest"),
    (r"confront|accus|shout(s|ing) at|slams the table", "public_confrontation"),
    (r"dead body|corpse|lifeless|finds? (him|her|them) dead", "death_discovered"),
]


def location_key(text: str | None) -> str | None:
    """Map a scene heading / location string onto a seeded location."""
    low = (text or "").lower()
    for pattern, key in _LOCATION_PATTERNS:
        if re.search(pattern, low):
            return key
    return None


def detect_events(text: str | None) -> list[str]:
    """Keyword-detect active events in a shot's action/beat text — zero LLM
    tokens; the vocabulary is small and the graph tolerates misses."""
    low = (text or "").lower()
    found = []
    for pattern, key in _EVENT_PATTERNS:
        if re.search(pattern, low) and key not in found:
            found.append(key)
    return found


_seeded = False


def seed_environment_graph(graph) -> None:
    """Idempotent MERGE of the whole seed. Runs once per process."""
    global _seeded
    if _seeded:
        return
    for key, desc in BEHAVIORS.items():
        graph.write("MERGE (b:EnvironmentBehavior {key:$k}) SET b.desc=$d",
                    {"k": key, "d": desc})
    for loc, beh in LOCATION_DEFAULTS.items():
        graph.write(
            "MERGE (l:Location {key:$l}) "
            "WITH l MATCH (b:EnvironmentBehavior {key:$b}) "
            "MERGE (l)-[:DEFAULT_BEHAVIOR {priority:0}]->(b)",
            {"l": loc, "b": beh})
    for event, (beh, pri) in EVENT_OVERRIDES.items():
        graph.write(
            "MERGE (e:Event {key:$e}) "
            "WITH e MATCH (b:EnvironmentBehavior {key:$b}) "
            "MERGE (e)-[o:OVERRIDES]->(b) SET o.priority=$p",
            {"e": event, "b": beh, "p": pri})
    _seeded = True


RESOLVE_CYPHER = (
    "MATCH (l:Location {key:$location})-[d:DEFAULT_BEHAVIOR]->(bd:EnvironmentBehavior) "
    "OPTIONAL MATCH (e:Event)-[o:OVERRIDES]->(bo:EnvironmentBehavior) "
    "WHERE e.key IN $events "
    "WITH bd, d.priority AS dp, e, bo, o.priority AS op "
    "ORDER BY coalesce(op, -1) DESC LIMIT 1 "
    "RETURN CASE WHEN bo IS NOT NULL AND op > dp THEN bo.desc ELSE bd.desc END AS behavior, "
    "CASE WHEN bo IS NOT NULL AND op > dp THEN bd.desc ELSE null END AS suppressed, "
    "CASE WHEN bo IS NOT NULL AND op > dp THEN e.key ELSE 'location default' END AS source, "
    "CASE WHEN bo IS NOT NULL AND op > dp THEN op ELSE dp END AS priority"
)


def resolve_environment(location_text: str | None, shot_text: str | None) -> dict | None:
    """The full pipeline step: heading + action text in, resolved behavior out.

    Returns {behavior, suppressed, source, priority, location, events} or None
    when there is no seeded location, no Neo4j, or nothing to say."""
    loc = location_key(location_text)
    if not loc:
        return None
    events = [e for e in detect_events(shot_text)
              if (EVENT_LOCATIONS.get(e) is None or loc in EVENT_LOCATIONS[e])]
    try:
        from app.graph.neo4j_client import Neo4jClient
        graph = Neo4jClient()
        try:
            seed_environment_graph(graph)
            rows = graph.run(RESOLVE_CYPHER, {"location": loc, "events": events})
        finally:
            graph.close()
        if not rows:
            return None
        row = rows[0]
        return {"behavior": row["behavior"], "suppressed": row["suppressed"],
                "source": row["source"], "priority": row["priority"],
                "location": loc, "events": events}
    except Exception as e:  # noqa: BLE001 — the graph is an enhancement, never a gate
        logger.warning("environment graph unavailable (%s) — skipping override", e)
        return None
