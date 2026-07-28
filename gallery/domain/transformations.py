"""
Transformation domain: canonical model for image transform options.

``ImageTransform`` is the single source of truth for what visual
modifications apply to an image.  It is:

- Constructed from validated ``GalleryParams`` or ``DetailParams``.
- Provider-agnostic (no picsum-specific logic lives here).
- Stable: identical inputs always produce identical cache-key segments.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from gallery.domain.validation import DetailParams, GalleryParams


@dataclass(frozen=True)
class ImageTransform:
    """Immutable, canonical representation of image transform options.

    Attributes:
        size:       Named size key (``small``, ``medium``, ``large``).
        grayscale:  Whether to render the image in greyscale.
        blur:       Blur intensity in the range 0–10 (0 = no blur).
    """

    size: str
    grayscale: bool = False
    blur: int = 0  # 0 means no blur applied

    # ------------------------------------------------------------------
    # Factory constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_gallery_params(cls, params: GalleryParams) -> ImageTransform:
        """Build a transform from validated gallery parameters."""
        return cls(size=params.size, grayscale=params.grayscale, blur=params.blur)

    @classmethod
    def from_detail_params(cls, params: DetailParams) -> ImageTransform:
        """Build a transform from validated detail parameters."""
        return cls(size=params.size, grayscale=params.grayscale, blur=params.blur)

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    def pixel_size(self) -> int:
        """Return the pixel dimension (width and height) for this named size."""
        image_sizes: dict[str, int] = getattr(settings, 'IMAGE_SIZES', {
            'small': 200,
            'medium': 400,
            'large': 800,
        })
        return image_sizes[self.size]

    def is_normal(self) -> bool:
        """Return True when no transform is applied (plain image)."""
        return not self.grayscale and self.blur == 0

    # ------------------------------------------------------------------
    # Canonical representations
    # ------------------------------------------------------------------

    def cache_key_segment(self) -> str:
        """Stable string segment for inclusion in cache keys.

        Canonical order guarantees that the same logical transform always
        produces the same key regardless of how the object was constructed.

        Examples::

            ImageTransform('medium').cache_key_segment()
            # → 'size:medium'

            ImageTransform('large', grayscale=True, blur=5).cache_key_segment()
            # → 'size:large,grayscale:1,blur:5'
        """
        parts = [f"size:{self.size}"]
        if self.grayscale:
            parts.append("grayscale:1")
        if self.blur > 0:
            parts.append(f"blur:{self.blur}")
        return ",".join(parts)

    def as_provider_params(self) -> dict:
        """Provider-agnostic transform parameters as a plain dict.

        The URL builder (Task 5) translates these into provider-specific
        query strings; this layer stays ignorant of picsum specifics.

        Returns::

            {
                "size": "medium",           # always present
                "grayscale": True,          # only when True
                "blur": 5,                  # only when > 0
            }
        """
        params: dict = {"size": self.size}
        if self.grayscale:
            params["grayscale"] = True
        if self.blur > 0:
            params["blur"] = self.blur
        return params
