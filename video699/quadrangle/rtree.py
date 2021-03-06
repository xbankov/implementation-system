# -*- coding: utf-8 -*-

"""This module implements a convex quadrangle index that uses the R-tree data structure to
efficiently retrieve convex quadrangles. The implementation uses the libspatialindex library exposed
through the Rtree Python package. A convex quadrangle tracker that uses the convex quadrangle index
is also implemented.

"""

import rtree

from ..interface import ConvexQuadrangleIndexABC, ConvexQuadrangleTrackerABC
from .deque import DequeMovingConvexQuadrangle


class RTreeConvexQuadrangleIndex(ConvexQuadrangleIndexABC):
    """A convex quadrangle index that uses the R-tree structure to efficiently retrieve quadrangles.

    Parameters
    ----------
    quadrangles : iterable of ConvexQuadrangleABC
        The initial convex quadrangles in the index.

    Attributes
    ----------
    quadrangles : read-only set-like object of ConvexQuadrangleABC
        The convex quadrangles in the index.
    """

    def __init__(self, quadrangles=()):
        self._quadrangles = {id(quadrangle): quadrangle for quadrangle in quadrangles}
        self._quadrangle_ids = {
            quadrangle: quadrangle_id
            for quadrangle_id, quadrangle in self._quadrangles.items()
        }
        self._index = rtree.index.Index([
            (
                quadrangle_id,
                (
                    quadrangle.top_left_bound[0],
                    quadrangle.top_left_bound[1],
                    quadrangle.bottom_right_bound[0],
                    quadrangle.bottom_right_bound[1],
                ),
                None,
            )
            for quadrangle_id, quadrangle in self._quadrangles.items()
        ])

    @property
    def quadrangles(self):
        return self._quadrangles.values()

    def add(self, quadrangle):
        if quadrangle not in self.quadrangles:
            self._quadrangles[id(quadrangle)] = quadrangle
            self._quadrangle_ids[quadrangle] = id(quadrangle)
            quadrangle_id = id(quadrangle)
            coordinates = (
                quadrangle.top_left_bound[0],
                quadrangle.top_left_bound[1],
                quadrangle.bottom_right_bound[0],
                quadrangle.bottom_right_bound[1],
            )
            self._index.insert(quadrangle_id, coordinates)

    def discard(self, quadrangle):
        if quadrangle in self.quadrangles:
            quadrangle_id = self._quadrangle_ids[quadrangle]
            coordinates = (
                quadrangle.top_left_bound[0],
                quadrangle.top_left_bound[1],
                quadrangle.bottom_right_bound[0],
                quadrangle.bottom_right_bound[1],
            )
            del self._quadrangles[quadrangle_id]
            del self._quadrangle_ids[quadrangle]
            self._index.delete(quadrangle_id, coordinates)

    def clear(self):
        self._quadrangles.clear()
        self._quadrangle_ids.clear()
        self._index = rtree.index.Index()

    def jaccard_indexes(self, input_quadrangle):
        coordinates = (
            input_quadrangle.top_left_bound[0],
            input_quadrangle.top_left_bound[1],
            input_quadrangle.bottom_right_bound[0],
            input_quadrangle.bottom_right_bound[1],
        )
        intersection = self._index.intersection(coordinates)
        jaccard_indexes = {}
        for indexed_quadrangle_id in intersection:
            indexed_quadrangle = self._quadrangles[indexed_quadrangle_id]
            intersection_area = input_quadrangle.intersection_area(indexed_quadrangle)
            if intersection_area > 0:
                union_area = input_quadrangle.union_area(indexed_quadrangle)
                jaccard_indexes[indexed_quadrangle] = intersection_area / union_area
        return jaccard_indexes


class RTreeDequeConvexQuadrangleTracker(ConvexQuadrangleTrackerABC):
    """Quadrangle tracker using :class:`RTreeConvexQuadrangleIndex`, :class:`DequeMovingQuadrangle`.

    Parameters
    ----------
    window_size : int or None, optional
        The maximum number of previous time frames for which the quadrangle movements are stored. If
        ``None`` or unspecified, then the number of time frames is unbounded.

    Raises
    ------
    ValueError
        If the window size is less than two.
    """

    def __init__(self, window_size=None):
        if window_size is not None and window_size < 2:
            raise ValueError(
                'The window size must not be less than two due to the contract of method Moving'
                'QuadrangleTrackerABC.update()'
            )
        self._window_size = window_size
        self.clear()

    def clear(self):
        self._moving_quadrangles = {}
        self._previous_quadrangles = set()
        self._quadrangle_index = RTreeConvexQuadrangleIndex()

    def update(self, current_quadrangles):
        """Records convex quadrangles that exist in the current time frame.

        The convex quadrangles in the *current* time frame in the order of iteration are compared
        with the convex quadrangles in the *previous* time frame. The current quadrangles that
        intersect no previous quadrangles are added to the tracker. The current quadrangles that
        intersect at least one previous quadrangle are considered to be the current position of the
        previous quadrangle with the largest Jaccard index. The previous quadrangles that cross no
        current quadrangles are removed from the tracker.

        Parameters
        ----------
        current_quadrangles : iterable of ConvexQuadrangleABC
            The convex quadrangles in the current time frame.

        Returns
        -------
        appeared_quadrangles : set of MovingConvexQuadrangleABC
            The current quadrangles that intersect no previous quadrangles.
        existing_quadrangles : set of MovingConvexQuadrangleABC
            The current quadrangles that intersect at least one previous quadrangle.
        disappeared_quadrangles : set of MovingConvexQuadrangleABC
            The previous quadrangles that cross no current quadrangles.
        """

        stationary_quadrangles = set()
        moved_quadrangles = set()
        appeared_quadrangles = set()
        disappeared_quadrangles = set()
        window_size = self._window_size
        moving_quadrangles = self._moving_quadrangles
        previous_quadrangles = self._previous_quadrangles
        quadrangle_index = self._quadrangle_index

        current_quadrangle_list = list(current_quadrangles)
        for quadrangle in current_quadrangle_list:
            if quadrangle in previous_quadrangles:
                moving_quadrangle = moving_quadrangles[quadrangle]
                moving_quadrangle.add(quadrangle)
                stationary_quadrangles.add(moving_quadrangle)
            else:
                jaccard_indexes = quadrangle_index.jaccard_indexes(quadrangle)
                if jaccard_indexes:
                    (previous_quadrangle, _), *__ = sorted(
                        jaccard_indexes.items(),
                        key=lambda x: x[1],
                        reverse=True
                    )
                    moving_quadrangle = moving_quadrangles[previous_quadrangle]
                    moving_quadrangle.add(quadrangle)
                    quadrangle_index.remove(previous_quadrangle)
                    del moving_quadrangles[previous_quadrangle]
                    moved_quadrangles.add(moving_quadrangle)
                else:
                    moving_quadrangle = DequeMovingConvexQuadrangle(
                        quadrangle,
                        window_size,
                    )
                    appeared_quadrangles.add(moving_quadrangle)
        self._previous_quadrangles = set(current_quadrangle_list)

        reindexed_quadrangles = moved_quadrangles | appeared_quadrangles
        for moving_quadrangle in reindexed_quadrangles:
            quadrangle = next(reversed(moving_quadrangle))
            moving_quadrangles[quadrangle] = moving_quadrangle
            quadrangle_index.add(quadrangle)

        for previous_quadrangle, moving_quadrangle in list(moving_quadrangles.items()):
            if moving_quadrangle not in reindexed_quadrangles | stationary_quadrangles:
                quadrangle_index.remove(previous_quadrangle)
                del moving_quadrangles[previous_quadrangle]
                disappeared_quadrangles.add(moving_quadrangle)

        return (
            appeared_quadrangles,
            moved_quadrangles | stationary_quadrangles,
            disappeared_quadrangles,
        )

    def __iter__(self):
        return iter(self._moving_quadrangles)

    def __len__(self):
        return len(self._moving_quadrangles)
