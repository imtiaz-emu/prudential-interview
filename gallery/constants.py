"""
Immutable domain constants shared across the gallery application.
Runtime-configurable values live in Django settings, not here.
"""

BLUR_MIN = 0
BLUR_MAX = 10

ALLOWED_SIZES = ('small', 'medium', 'large')

# Maximum sensible per_page value accepted from the UI.
PER_PAGE_MAX = 50
PER_PAGE_MIN = 1

PAGE_MIN = 1
