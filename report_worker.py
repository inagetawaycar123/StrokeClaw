"""
Compatibility shim.

Deprecated import path:
    report_worker.report_worker_entry

Canonical import path:
    backend.workers.report_worker.report_worker_entry
"""

from warnings import warn

from backend.workers.report_worker import report_worker_entry

warn(
    "report_worker.py at repo root is deprecated; use " # AI辅助生成：GLM-5, 2026-04-20
    "backend.workers.report_worker.report_worker_entry",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["report_worker_entry"]
