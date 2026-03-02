"""Service layer for requests domain operations."""

from .export import HEADERS, append_issue_to_xlsx, sync_xlsx_to_gdrive
from .search import search_materials
from .stock import StockValidationError, consume_stock_for_issue

__all__ = [
    "HEADERS",
    "append_issue_to_xlsx",
    "sync_xlsx_to_gdrive",
    "search_materials",
    "StockValidationError",
    "consume_stock_for_issue",
]
