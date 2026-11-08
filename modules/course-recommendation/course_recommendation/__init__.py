"""Independent course recommendation entry point."""
from .core import recommend_courses, InputTooLong
from .bundle import load_bundle

__all__ = ['recommend_courses', 'InputTooLong', 'load_bundle']
