from app.workers.export_worker import assign_episodes


def test_single_episode_everything_resolves_to_one():
    entries = [{"scene_number": 1}, {"scene_number": 2}, {"scene_number": 3}]
    assert assign_episodes(entries, {1: 1, 2: 1, 3: 1}) == [1, 1, 1]


def test_missing_mapping_defaults_to_episode_one():
    entries = [{"scene_number": 4}, {"scene_number": 5}]
    assert assign_episodes(entries, {}) == [1, 1]


def test_two_episodes_split_on_scene_boundary():
    entries = [{"scene_number": n} for n in (1, 2, 3, 4)]
    eps = assign_episodes(entries, {1: 1, 2: 1, 3: 2, 4: 2})
    assert eps == [1, 1, 2, 2]


def test_imported_media_rides_the_current_episode():
    # a scene-less chunk (imported media) between scene 2 (ep 1) and scene 3
    # (ep 2) belongs to the episode that is playing when it appears
    entries = [{"scene_number": 1}, {"scene_number": None},
               {"scene_number": 3}, {"scene_number": None}]
    eps = assign_episodes(entries, {1: 1, 3: 2})
    assert eps == [1, 1, 2, 2]


def test_leading_import_defaults_to_episode_one():
    entries = [{"scene_number": None}, {"scene_number": 1}]
    assert assign_episodes(entries, {1: 1}) == [1, 1]
