"""
Shared data-transfer types consumed by services, views, and templates.

These are plain dataclasses — no Django ORM, no provider logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gallery.domain.transformations import ImageTransform
from gallery.domain.validation import GalleryParams


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


@dataclass
class GalleryPage:
    """Complete payload for rendering a gallery page.

    Attributes:
        items:        Ordered list of ``ImageItem`` objects for this page.
        page:         Current page number (1-based).
        per_page:     Number of images per page.
        has_previous: True when a previous page exists.
        has_next:     True when a next page exists.
        params:       Original validated params — used to preserve active
                      filters in pagination links.
        errors:       Human-readable messages for any images that could not
                      be loaded (partial-failure case).
    """

    items: list[ImageItem]
    page: int
    per_page: int
    has_previous: bool
    has_next: bool
    params: GalleryParams
    errors: list[str] = field(default_factory=list)

