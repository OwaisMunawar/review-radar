"""Theme discovery over summary embeddings.

Average-linkage agglomerative clustering with a cosine distance cut-off. We use
it instead of k-means because the number of themes is the unknown we are trying
to find, and a distance threshold is something a person can reason about
("summaries this close say the same thing"). At a few thousand reviews per run
the O(n^2) memory is fine; beyond that the roadmap moves to HDBSCAN.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

Matrix = npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class Cluster:
    members: tuple[int, ...]
    centroid: tuple[float, ...]
    representatives: tuple[int, ...]


def _normalize(vectors: Matrix) -> Matrix:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return vectors / norms


def agglomerate(
    vectors: Sequence[Sequence[float]],
    *,
    max_distance: float = 0.35,
    min_size: int = 3,
    representatives: int = 3,
) -> list[Cluster]:
    """Group vectors whose average pairwise cosine distance stays under `max_distance`.

    Deterministic: ties resolve to the lowest index, so the same input always
    yields the same themes, which keeps demo mode and tests reproducible.
    """
    if len(vectors) == 0:
        return []
    x = _normalize(np.asarray(vectors, dtype=np.float64))
    n = x.shape[0]
    distance: Matrix = 1.0 - x @ x.T
    np.fill_diagonal(distance, np.inf)

    members: list[list[int]] = [[i] for i in range(n)]
    active = np.ones(n, dtype=bool)

    for _ in range(n - 1):
        flat = int(np.argmin(distance))
        i, j = divmod(flat, n)
        if distance[i, j] > max_distance:
            break
        if j < i:
            i, j = j, i
        size_i, size_j = len(members[i]), len(members[j])
        # Lance-Williams update for average linkage.
        merged = (size_i * distance[i] + size_j * distance[j]) / (size_i + size_j)
        distance[i, :] = merged
        distance[:, i] = merged
        distance[i, i] = np.inf
        distance[j, :] = np.inf
        distance[:, j] = np.inf
        members[i].extend(members[j])
        members[j] = []
        active[j] = False

    clusters: list[Cluster] = []
    for index in np.flatnonzero(active):
        group = sorted(members[int(index)])
        if len(group) < min_size:
            continue
        points = x[group]
        centroid = _normalize(points.mean(axis=0, keepdims=True))[0]
        closeness = points @ centroid
        ranked = [group[k] for k in np.argsort(-closeness, kind="stable")[:representatives]]
        clusters.append(
            Cluster(
                members=tuple(group),
                centroid=tuple(float(v) for v in centroid),
                representatives=tuple(ranked),
            )
        )
    clusters.sort(key=lambda c: (-len(c.members), c.members[0]))
    return clusters
