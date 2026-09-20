"""Serve EchoHarness for the h3-test battery (CI + local).

The H3 compliance gate is the test battery (``hermes-h3-shim``:
``h3-test --endpoint <url>``, 46 tests across 6 categories, exit 0 =
compliant). This runner serves the canonical 46/46 template
(``h3_harness.examples.echo.EchoHarness``) on the battery port (9191) so CI
and local developers can verify compliance without touching the example.

``echo.py`` itself exposes a module-level ``app`` and serves the same
battery port by default, so ``uvicorn h3_harness.examples.echo:app`` also
works (README Examples section); this wrapper is not required for
compliance. CI keeps it as the pinned battery server: loopback-only bind,
quiet uvicorn logging, and a stable entry point independent of example
changes.
"""

import uvicorn
from fastapi import FastAPI

from h3_harness import add_middleware, create_router
from h3_harness.examples.echo import EchoHarness

app = FastAPI()
app.include_router(create_router(EchoHarness()))
add_middleware(app)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9191, log_level="warning")
