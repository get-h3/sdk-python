"""Serve EchoHarness for the h3-test battery (CI + local).

The H3 compliance gate is the test battery (``hermes-h3-shim``:
``h3-test --endpoint <url>``, 44 tests across 6 categories, exit 0 =
compliant). This runner serves the canonical 44/44 template
(``h3_harness.examples.echo.EchoHarness``) on the battery port so CI and
local developers can verify compliance without touching the example:
``echo.py`` builds its app only inside ``if __name__ == "__main__":`` and
binds 0.0.0.0:8000, which ``uvicorn h3_harness.examples.echo:...`` cannot
serve directly (EchoHarness is a harness class, not a FastAPI app).
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
