"""Single source of truth for the SDK version.

Imported by :mod:`h3_harness` (as ``h3_harness.__version__``) and by
:mod:`h3_harness.harness` for the ``GET /v1/health`` version field.
Deliberately imports nothing, so either importer can use it without an
import cycle.
"""

__version__ = "0.1.5"
