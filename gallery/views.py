from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from gallery.domain.validation import (
    ValidationError,
    validate_detail_params,
    validate_gallery_params,
)
from gallery.errors import NoFallbackError
from gallery.services.gallery_service import GalleryService

# One service instance per process — stateless except for the underlying
# requests.Session which benefits from connection reuse.
_service = GalleryService()

_PER_PAGE_OPTIONS = [5, 10, 20, 50]
_SIZES = ['small', 'medium', 'large']


def gallery(request):
    """Main gallery view: validates params, assembles page, renders grid."""
    raw = request.GET

    try:
        params = validate_gallery_params(
            page_raw=raw.get('page'),
            per_page_raw=raw.get('per_page'),
            size_raw=raw.get('size'),
            grayscale_raw=raw.get('grayscale'),
            blur_raw=raw.get('blur'),
        )
    except ValidationError as exc:
        messages.warning(request, exc.message)
        if exc.field == 'page':
            # Preserve all other active params, reset page to 1.
            q = raw.copy()
            q['page'] = '1'
            return redirect(f"{reverse('gallery:index')}?{q.urlencode()}")
        return redirect(reverse('gallery:index'))

    gallery_page = _service.get_page(params)

    for error in gallery_page.errors:
        messages.warning(request, error)

    context = {
        'gallery_page': gallery_page,
        'params': params,
        'prev_url': _page_url(raw, params.page - 1) if gallery_page.has_previous else None,
        'next_url': _page_url(raw, params.page + 1) if gallery_page.has_next else None,
        'filter_query': _filter_query(params),
        'sizes': _SIZES,
        'per_page_options': _PER_PAGE_OPTIONS,
    }
    return render(request, 'gallery.html', context)


def detail(request, image_id):
    """Detail view: shows a single larger image with its active parameters."""
    raw = request.GET

    try:
        params = validate_detail_params(
            image_id_raw=image_id,
            size_raw=raw.get('size'),
            grayscale_raw=raw.get('grayscale'),
            blur_raw=raw.get('blur'),
        )
    except ValidationError as exc:
        messages.error(request, exc.message)
        return redirect(reverse('gallery:index'))

    try:
        item = _service.get_detail(params)
    except NoFallbackError:
        messages.error(request, f"Image {image_id} is currently unavailable.")
        return redirect(reverse('gallery:index'))

    context = {
        'item': item,
        'params': params,
        'filter_query': _filter_query_detail(params),
        'gallery_url': f"{reverse('gallery:index')}?{_filter_query_detail(params)}",
    }
    return render(request, 'detail.html', context)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _page_url(raw_get, page: int) -> str:
    """Build a query string pointing to *page*, preserving all other params."""
    q = raw_get.copy()
    q['page'] = str(page)
    return f"?{q.urlencode()}"


def _filter_query(params) -> str:
    """URL-encoded active filter params (no page) for detail links."""
    parts = [f"size={params.size}", f"per_page={params.per_page}"]
    if params.grayscale:
        parts.append("grayscale=1")
    if params.blur > 0:
        parts.append(f"blur={params.blur}")
    return "&".join(parts)


def _filter_query_detail(params) -> str:
    """URL-encoded filter params for back-to-gallery links from detail."""
    parts = [f"size={params.size}"]
    if params.grayscale:
        parts.append("grayscale=1")
    if params.blur > 0:
        parts.append(f"blur={params.blur}")
    return "&".join(parts)

