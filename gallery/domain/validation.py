"""
Validation domain: parse, validate, and normalise query parameters.

All public entry points return either a ``ValidationResult`` (success) or
raise ``ValidationError`` (failure). Views should catch ``ValidationError``
and redirect / display the embedded message rather than propagating it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

from gallery.constants import (
    ALLOWED_SIZES,
    BLUR_MAX,
    BLUR_MIN,
    PAGE_MIN,
    PER_PAGE_MAX,
    PER_PAGE_MIN,
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GalleryParams:
    """Normalised, validated parameters for a gallery page request."""

    page: int
    per_page: int
    size: str
    grayscale: bool
    blur: int  # 0 means no blur


@dataclass(frozen=True)
class DetailParams:
    """Normalised, validated parameters for an image detail request."""

    image_id: int
    size: str
    grayscale: bool
    blur: int


# ---------------------------------------------------------------------------
# Validation error
# ---------------------------------------------------------------------------


class ValidationError(Exception):
    """Raised when one or more query parameters fail validation.

    Attributes:
        message: User-facing description of what went wrong.
        field:   Which parameter caused the failure (for logging).
    """

    def __init__(self, message: str, field: str = '') -> None:
        super().__init__(message)
        self.message = message
        self.field = field


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_int(raw: Any, name: str, *, default: int | None = None) -> int:
    """Convert *raw* to a positive integer or raise ``ValidationError``."""
    if raw is None or str(raw).strip() == '':
        if default is not None:
            return default
        raise ValidationError(f"'{name}' is required.", field=name)
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        raise ValidationError(
            f"'{name}' must be a whole number.", field=name
        )
    return value


def _parse_bool(raw: Any, *, default: bool = False) -> bool:
    """Interpret a query-param value as a boolean flag."""
    if raw is None:
        return default
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


# ---------------------------------------------------------------------------
# Public validators
# ---------------------------------------------------------------------------


def validate_gallery_params(
    page_raw: Any = None,
    per_page_raw: Any = None,
    size_raw: Any = None,
    grayscale_raw: Any = None,
    blur_raw: Any = None,
) -> GalleryParams:
    """Validate and normalise gallery query parameters.

    Args:
        page_raw:      Raw ``page`` query value (string or None).
        per_page_raw:  Raw ``per_page`` query value (string or None).
        size_raw:      Raw ``size`` query value (string or None).
        grayscale_raw: Raw ``grayscale`` query value (string or None).
        blur_raw:      Raw ``blur`` query value (string or None).

    Returns:
        ``GalleryParams`` with validated, typed values.

    Raises:
        ``ValidationError`` on any invalid input.
    """
    # --- page ---
    page = _parse_int(page_raw, 'page', default=PAGE_MIN)
    if page < PAGE_MIN:
        raise ValidationError(
            'Page number must be 1 or greater.', field='page'
        )

    # --- per_page ---
    default_per_page: int = getattr(settings, 'IMAGES_PER_PAGE', 10)
    per_page = _parse_int(per_page_raw, 'per_page', default=default_per_page)
    if not (PER_PAGE_MIN <= per_page <= PER_PAGE_MAX):
        raise ValidationError(
            f'Images per page must be between {PER_PAGE_MIN} and {PER_PAGE_MAX}.',
            field='per_page',
        )

    # --- size ---
    default_size: str = getattr(settings, 'IMAGE_DEFAULT_SIZE', 'medium')
    size = str(size_raw).strip().lower() if size_raw else default_size
    if size not in ALLOWED_SIZES:
        raise ValidationError(
            f"Size must be one of: {', '.join(ALLOWED_SIZES)}.", field='size'
        )

    # --- grayscale ---
    grayscale = _parse_bool(grayscale_raw)

    # --- blur ---
    blur = _parse_int(blur_raw, 'blur', default=0)
    if not (BLUR_MIN <= blur <= BLUR_MAX):
        raise ValidationError(
            f'Blur intensity must be between {BLUR_MIN} and {BLUR_MAX}.',
            field='blur',
        )

    return GalleryParams(
        page=page,
        per_page=per_page,
        size=size,
        grayscale=grayscale,
        blur=blur,
    )


def validate_detail_params(
    image_id_raw: Any,
    size_raw: Any = None,
    grayscale_raw: Any = None,
    blur_raw: Any = None,
) -> DetailParams:
    """Validate and normalise image detail query parameters.

    Args:
        image_id_raw:  Raw image identifier (URL capture or query param).
        size_raw:      Raw ``size`` query value.
        grayscale_raw: Raw ``grayscale`` query value.
        blur_raw:      Raw ``blur`` query value.

    Returns:
        ``DetailParams`` with validated, typed values.

    Raises:
        ``ValidationError`` on any invalid input.
    """
    # --- image_id ---
    image_id = _parse_int(image_id_raw, 'image_id')
    if image_id < 1:
        raise ValidationError('Image ID must be a positive integer.', field='image_id')

    # --- size ---
    default_size: str = getattr(settings, 'IMAGE_DEFAULT_SIZE', 'medium')
    size = str(size_raw).strip().lower() if size_raw else default_size
    if size not in ALLOWED_SIZES:
        raise ValidationError(
            f"Size must be one of: {', '.join(ALLOWED_SIZES)}.", field='size'
        )

    # --- grayscale ---
    grayscale = _parse_bool(grayscale_raw)

    # --- blur ---
    blur = _parse_int(blur_raw, 'blur', default=0)
    if not (BLUR_MIN <= blur <= BLUR_MAX):
        raise ValidationError(
            f'Blur intensity must be between {BLUR_MIN} and {BLUR_MAX}.',
            field='blur',
        )

    return DetailParams(
        image_id=image_id,
        size=size,
        grayscale=grayscale,
        blur=blur,
    )
