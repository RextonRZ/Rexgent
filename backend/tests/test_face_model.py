from app.services.face_model import cosine_similarity


def test_cosine_identical_vectors():
    v = [0.1, 0.2, 0.3, 0.4]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-6


def test_cosine_orthogonal_vectors():
    assert abs(cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-6


def test_cosine_handles_empty():
    assert cosine_similarity([], [1.0]) == 0.0


def test_cosine_mismatched_lengths():
    assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0


def test_cosine_zero_vector():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
