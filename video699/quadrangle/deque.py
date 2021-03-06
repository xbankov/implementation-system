# -*- coding: utf-8 -*-

"""This module implements a moving convex quadrangle using the deque data structure.

"""

from collections import deque

from ..interface import MovingConvexQuadrangleABC


class DequeMovingConvexQuadrangle(MovingConvexQuadrangleABC):
    """A convex quadrangle that moves in time represented by a deque.

    Parameters
    ----------
    current_quadrangle : ConvexQuadrangleABC
        The latest coordinates of the moving convex quadrangle.
    window_size : int or None, optional
        The maximum number of previous time frames for which the quadrangle movements are stored. If
        ``None`` or unspecified, then the number of time frames is unbounded.

    Attributes
    ----------
    current_quadrangle : ConvexQuadrangleABC
        The latest coordinates of the moving convex quadrangle.

    Raises
    ------
    ValueError
        If the window size is less than two.
    """

    def __init__(self, current_quadrangle, window_size=None):
        if window_size is not None and window_size < 2:
            raise ValueError(
                'The window size must not be less than two due to the contract of method Moving'
                'QuadrangleTrackerABC.update()'
            )
        self._quadrangles = deque((current_quadrangle,), maxlen=window_size)

    def add(self, quadrangle):
        self._quadrangles.append(quadrangle)

    def __iter__(self):
        return iter(self._quadrangles)

    def __reversed__(self):
        return reversed(self._quadrangles)
