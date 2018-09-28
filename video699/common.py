# -*- coding: utf-8 -*-

"""This module implements commonly useful constants, and functions.

"""

from math import floor, ceil

import numpy as np


COLOR_RGBA_TRANSPARENT = (0, 0, 0, 0)


def change_aspect_ratio_by_upscaling(original_width, original_height, new_aspect_ratio):
    """Returns new dimensions that upscale an image to a new aspect ratio.

    Parameters
    ----------
    original_width : int
        The original width of an image.
    original_height : int
        The original height of an image.
    new_aspect_ratio : Fraction
        A new aspect ratio. The ratio must be non-zero.

    Returns
    -------
    rescaled_width : int
        The width of the image after rescaling.
    rescaled_height : int
        The height of the image after rescaling.

    Raises
    ------
    ValueError
        When some of the original dimensions or the new aspect ratio is zero.
    """

    if original_width == 0:
        raise ValueError('The original width be non-zero')
    if original_width == 0 or original_height == 0:
        raise ValueError('The original height must be non-zero')
    if new_aspect_ratio == 0:
        raise ValueError('The new aspect ratio must be non-zero')

    new_aspect_width = new_aspect_ratio.numerator
    new_aspect_height = new_aspect_ratio.denominator
    ratio_of_ratios = (new_aspect_width * original_height) / (new_aspect_height * original_width)

    if ratio_of_ratios >= 1:
        rescaled_width = int(round(original_width * ratio_of_ratios))
        rescaled_height = original_height
    else:
        rescaled_width = original_width
        rescaled_height = int(round(original_height / ratio_of_ratios))

    return (rescaled_width, rescaled_height)


def rescale_and_keep_aspect_ratio(original_width, original_height, new_width=None, new_height=None):
    """Returns new dimensions, and margins that rescale an image and keep its aspect ratio.

    Notes
    -----
    The rescaled image is vertically and horizontally centered and its dimensions do not exceed
    the new dimensions of the image either vertically or horizontally.

    Parameters
    ----------
    original_width : int
        The original width of an image.
    original_height : int
        The original height of an image.
    new_width : int
        The new width of the image including the margins. When unspecified or ``None`` and the new
        height is specified, the new height minimizes the margins. When both the new width and the
        new height are unspecified or ``None``, the new height equals the original height.
    new_height : int
        The new height of the image including the margins. When unspecified or ``None`` and the new
        width is specified, the new height minimizes the margins. When both the new width and the
        new height are unspecified or ``None``, the new width equals the original width.

    Returns
    -------
    rescaled_width : int
        The width of the image after rescaling.
    rescaled_height : int
        The height of the image after rescaling.
    top_margin : int
        The width of the top margin of the rescaled image.
    bottom_margin : int
        The width of the bottom margin of the rescaled image.
    left_margin : int
        The width of the left margin of the rescaled image.
    right_margin : int
        The width of the right margin of the rescaled image.

    Raises
    ------
    ValueError
        When some of the original or new dimensions is zero.
    """

    if original_width == 0:
        raise ValueError('The original width be non-zero')
    if original_width == 0 or original_height == 0:
        raise ValueError('The original height must be non-zero')
    if new_width == 0:
        raise ValueError('The new width be non-zero')
    if new_width == 0 or new_height == 0:
        raise ValueError('The new height must be non-zero')

    if new_width is None or new_height is None:
        top_margin = 0
        bottom_margin = 0
        left_margin = 0
        right_margin = 0
        if new_width is None and new_height is None:
            rescaled_width = original_width
            rescaled_height = original_height
        elif new_width is not None:
            rescaled_width = new_width
            rescaled_height = new_width / original_width * original_height
        else:
            rescaled_width = new_height / original_height * original_width
            rescaled_height = new_height
    else:
        aspect_ratio = min(new_width / original_width, new_height / original_height)
        rescaled_width = int(round(original_width * aspect_ratio))
        rescaled_height = int(round(original_height * aspect_ratio))
        margin_width = (new_width - rescaled_width) / 2
        margin_height = (new_height - rescaled_height) / 2
        top_margin = floor(margin_height)
        bottom_margin = ceil(margin_height)
        left_margin = floor(margin_width)
        right_margin = ceil(margin_width)
    return (
        rescaled_width,
        rescaled_height,
        top_margin,
        bottom_margin,
        left_margin,
        right_margin,
    )


def timedelta_as_xsd_duration(timedelta):
    """Serializes a timedelta object as a string that satisfies the XML Schema duration datatype.

    Parameters
    ----------
    timedelta : timedelta
        A timedelta object.

    Returns
    -------
    duration : duration
        A string that satisfies the XML Schema duration datatype.
    """

    duration = 'P{days}DT{seconds}.{microseconds}S'.format(
        days=timedelta.days,
        seconds=timedelta.seconds,
        microseconds=timedelta.microseconds,
    )
    return duration


def benjamini_hochberg(p_values):
    """Adjusts p-values from independent hypothesis tests to q-values.

    The q-values are determined using the false discovery rate (FDR) controlling procedure of
    Benjamini and Hochberg [BenjaminiHochberg1995]_.

    .. [BenjaminiHochberg1995] Benjamini, Yoav; Hochberg, Yosef (1995). "Controlling the false
       discovery rate: a practical and powerful approach to multiple testing". Journal of the
       Royal Statistical Society, Series B. 57 (1): 289–300. MR 1325392.

    Notes
    -----
    This method was adapted from `code posted to Stack Overflow by Eric Talevich`_.

    .. _code posted to Stack Overflow by Eric Talevich: https://stackoverflow.com/a/33532498/657401

    Parameters
    ----------
    p_values : iterable of scalar
        p-values from independent hypothesis tests.

    Returns
    -------
    q_values : iterable of scalar
        The p-values adjusted using the FDR controlling procedure.
    """

    p_value_array = np.asfarray(p_values)
    num_pvalues = len(p_value_array)
    descending_order = p_value_array.argsort()[::-1]
    original_order = descending_order.argsort()
    steps = num_pvalues / np.arange(num_pvalues, 0, -1)
    descending_q_values = np.minimum.accumulate(steps * p_value_array[descending_order]).clip(0, 1)
    q_values = descending_q_values[original_order]
    return q_values
