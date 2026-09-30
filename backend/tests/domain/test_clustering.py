from review_radar.domain.clustering import agglomerate


def test_groups_close_vectors_and_drops_small_groups() -> None:
    vectors = [
        [1.0, 0.0, 0.0],
        [0.98, 0.05, 0.0],
        [0.97, 0.0, 0.05],
        [0.0, 1.0, 0.0],
        [0.02, 0.99, 0.0],
        [0.0, 0.97, 0.03],
        [0.0, 0.96, 0.05],
        [0.0, 0.0, 1.0],
    ]
    clusters = agglomerate(vectors, max_distance=0.2, min_size=3, representatives=2)

    assert [c.members for c in clusters] == [(3, 4, 5, 6), (0, 1, 2)]
    assert len(clusters[0].representatives) == 2
    assert set(clusters[0].representatives) <= set(clusters[0].members)
    assert abs(sum(v * v for v in clusters[0].centroid) - 1.0) < 1e-9


def test_is_deterministic_and_handles_zero_vectors() -> None:
    vectors = [[0.0, 0.0], [1.0, 1.0], [1.0, 1.0], [1.0, 1.0]]
    first = agglomerate(vectors, min_size=2)
    assert first == agglomerate(vectors, min_size=2)
    assert first[0].members == (1, 2, 3)


def test_empty_input() -> None:
    assert agglomerate([]) == []
