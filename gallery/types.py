"""
Shared data-transfer types consumed by services, views, and templates.

These are plain dataclasses — no Django ORM, no provider logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from gallery.domain.transformations import ImageTransform


@dataclass(frozen=True)
class ImageItem:
    """All data a view or template needs to render a single gallery image.

    Attributes:
        image_id:  Numeric identifier used by the upstream provider.
        url:       Backend-generated image URL (ready for use in ``<img src>``).
        width:     Rendered pixel width.
        height:    Rendered pixel height.
        transform: The ``ImageTransform`` that produced this item.
    """

    image_id: int
    url: str
    width: int
    height: int
    transform: ImageTransform
