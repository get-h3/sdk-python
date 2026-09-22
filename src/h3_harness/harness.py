"""H3 Harness — BaseHarness ABC + FastAPI router for one-line integration.

Usage:
    from h3_harness import BaseHarness, Decision, DecisionType, create_router
    from fastapi import FastAPI

    class MyHarness(BaseHarness):
        async def on_process(self, req):
            return Decision(decision=DecisionType.TEXT, text=TextResponse(...))

        async def on_result(self, req):
            return Decision(decision=DecisionType.END, end=End(reason="task_complete"))

    app = FastAPI()
    app.include_router(create_router(MyHarness()))
    # Optional: add request logging with add_middleware(app)

"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from ._version import __version__
from .protocol import (
    CancelRequest,
    CancelResponse,
    Capability,
    Decision,
    DecisionType,
    End,
    EndReason,
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    HealthStatus,
    ProcessRequest,
    ResultRequest,
    SessionResponse,
    SessionStatus,
)

logger = logging.getLogger(__name__)


class BaseHarness(ABC):
    """Abstract base class for H3-compliant agent harnesses.

    Subclasses MUST implement ``on_process`` and ``on_result``.
    Optional overrides: ``on_cancel``, ``on_session_terminate``, ``health``.
    """

    _started_at: float = 0.0

    # Router-side session liveness (session_id -> "active" | "completed"),
    # populated by create_router on the session lifecycle endpoints.
    #
    # The class default MUST be None, never a `{}` literal: a dict on the class
    # is shared by every instance (cross-instance state leak). The dict is
    # lazily created inside _track_session, mirroring the _started_at lazy-init
    # in health() so subclasses that never call super().__init__() (GAP-025)
    # still work.
    #
    # Deliberately NOT named `_sessions`: the shipped examples (README
    # quickstart, examples/echo.py, examples/minimal.py) and most adopter
    # harnesses already use `_sessions` for their own get_session_info
    # metadata dicts. Writing status strings into that name clobbers the
    # metadata and makes GET /v1/sessions/{id} fail on `info.get(...)`.
    #
    # LIVE sessions only (SDKPY-GAP-063b): a session is in here from the
    # POST /v1/process that opens the turn until it ends — the END decision
    # of POST /v1/result or DELETE /v1/sessions/{id} PURGES the entry. The
    # dict therefore cannot accumulate one entry per finished conversation.
    _live_sessions: dict[str, str] | None = None

    # Bounded closing window of ended sessions (session_id -> terminal
    # status), also lazily created. The END purge removes the live entry, but
    # ``GET /v1/sessions/{id}`` and ``session_status()`` must keep reporting a
    # truthful ``completed`` for it (GAP-058 parity), so the terminal status
    # is remembered here — bounded by ``_ended_session_cap``, oldest evicted
    # first, exactly like the shim scaffold's H3_SESSION_MAX (get-h3/shim
    # d62dc7f). Same class-default-None rule as ``_live_sessions``.
    _ended_sessions: dict[str, str] | None = None

    #: How many recently-ended sessions keep answering for their status.
    #: One entry per finished conversation either way — this is what stops
    #: the ended window from becoming the unbounded leak the live map was.
    #: 0 (or less) disables the window: the purge then keeps no memory.
    #: Subclasses may override; the class default is shared, never mutated.
    _ended_session_cap: int = 1024

    def __init__(self) -> None:
        self._started_at = time.time()

    @abstractmethod
    async def on_process(self, req: ProcessRequest) -> Decision:
        """Called when a new user message arrives.

        Return the first Decision in the agent loop.
        """
        ...

    @abstractmethod
    async def on_result(self, req: ResultRequest) -> Decision:
        """Called after Hermes executes a Decision.

        Return the next Decision. Return Decision(decision=DecisionType.END, ...)
        to finish the session.
        """
        ...

    async def on_cancel(self, req: CancelRequest) -> bool:
        """Called when the user interrupts. Return True to confirm cancellation."""
        return True

    async def on_session_terminate(self, session_id: str) -> None:
        """Called on DELETE /v1/sessions/{session_id}.

        Override to perform cleanup when a session is terminated.
        The base implementation is a no-op.
        """
        return None

    def _track_session(self, session_id: str, status: str = "active") -> None:
        """Record/update session liveness. Never raises.

        Called by ``create_router`` on POST /v1/process, POST /v1/result and
        DELETE /v1/sessions/{session_id}. Safe when ``__init__`` was never
        called: the tracking dicts are lazily created here, exactly like
        ``_started_at`` is lazily initialised in :meth:`health`.

        ``"active"`` is the only live state: the session is stored in
        ``_live_sessions`` and any ended status the router filed for it is
        dropped, so a fresh ``POST /v1/process`` re-activates a session that
        had gone quiet.

        EVERY other status is terminal — the END decision of ``POST
        /v1/result`` (``task_complete`` and ``error`` alike) and ``DELETE
        /v1/sessions/{id}`` — and PURGES the live entry rather than
        overwriting it in place, filing the status in the bounded
        :meth:`_remember_ended` window instead (SDKPY-GAP-063b). That is the
        difference from DF4-H3-SHIM-2, which left the ended entry sitting in
        the live map until something happened to read health: one-shot and
        error-path conversations now leave the live map at the END write, so
        they cannot accumulate. The status reads are unchanged (GAP-058) —
        ``session_status()`` and ``GET /v1/sessions/{id}`` still resolve a
        truthful ``completed`` for the ended session, from the window.
        """
        try:
            if not session_id:
                return
            if status == SessionStatus.ACTIVE.value:
                tracked = self._live_sessions
                if not isinstance(tracked, dict):
                    tracked = {}
                    self._live_sessions = tracked
                tracked[session_id] = status
                ended = self._ended_sessions
                if isinstance(ended, dict):
                    ended.pop(session_id, None)
                return
            tracked = self._live_sessions
            if isinstance(tracked, dict):
                tracked.pop(session_id, None)
            self._remember_ended(session_id, status)
        except Exception:  # pragma: no cover - defensive: never fail a request
            logger.exception("_track_session failed for %s", session_id)

    def _remember_ended(self, session_id: str, status: str) -> None:
        """File a terminal status in the bounded closing window. Never raises.

        The window is the memory behind ``session_status()`` and
        ``GET /v1/sessions/{id}`` for a session whose live entry the END
        purge already removed: the ended status stays resolvable while it is
        in the window, and the window keeps at most ``_ended_session_cap``
        entries — oldest evicted first, mirroring the shim scaffold's
        ``H3_SESSION_MAX`` (get-h3/shim d62dc7f). Without that cap the window
        would just be the unbounded live map under a new name.
        """
        try:
            ended = self._ended_sessions
            if not isinstance(ended, dict):
                ended = {}
                self._ended_sessions = ended
            ended.pop(session_id, None)  # re-insert as the most recent
            ended[session_id] = status
            cap = self._ended_session_cap
            if cap <= 0:
                ended.clear()
                return
            while len(ended) > cap:
                ended.pop(next(iter(ended)), None)
        except Exception:  # pragma: no cover - defensive: never fail a request
            logger.exception("_remember_ended failed for %s", session_id)

    def _tracked_session_status(self, session_id: str) -> str | None:
        """Raw router-tracked status string for ``session_id``, else ``None``.

        The single read of the router's tracking: the live map first, then
        the bounded ended window (SDKPY-GAP-063b). ``session_status()`` and
        ``active_session_count()`` both go through here, so the two surfaces
        that answer "is this session live?" (GET /v1/sessions/{id} and
        GET /v1/health) can never read the router's tracking differently.
        """
        for tracked in (self._live_sessions, self._ended_sessions):
            if not isinstance(tracked, dict):
                continue
            value = tracked.get(session_id)
            if isinstance(value, str):
                return value
        return None

    def session_status(self, session_id: str) -> SessionStatus | None:
        """Router-tracked status for ``session_id``, or ``None``.

        ``None`` means the router has no tracked status for this session id:
        no ``POST /v1/process``, ``POST /v1/result`` or
        ``DELETE /v1/sessions/{id}`` ever carried it, OR it ended so long ago
        that the bounded ended window (``_ended_session_cap``) has since
        evicted it. It is NOT a statement about the harness's own session
        store — ``get_session_info`` remains the authority for session
        metadata and for 404s.

        When the router has tracked the id, the status is the one written on
        the lifecycle endpoint: ``ACTIVE`` from ``POST /v1/process``,
        ``COMPLETED`` once ``POST /v1/result`` returns an ``end`` decision or
        ``DELETE /v1/sessions/{id}`` runs, else ``ACTIVE`` again. The END
        purge (SDKPY-GAP-063b) removes the session from the live map at that
        write but keeps the status here, so the ended session keeps resolving
        while it is in the window.

        A tracked value the router itself would not have written (a harness
        writing its own strings into ``_live_sessions``) is reported as
        ``None`` — the "never tracked anything usable" answer, so callers
        keep their historical default instead of echoing junk.
        """
        raw = self._tracked_session_status(session_id)
        if raw is None:
            return None
        try:
            return SessionStatus(raw)
        except ValueError:
            return None

    def _resolve_status(self, session_id: str, info: object) -> SessionStatus | None:
        """THE shared liveness resolution behind both surfaces (GAP-058).

        Order: an explicit, valid status stated by the harness's
        ``get_session_info`` dict wins (GAP-035) → else the router's own
        tracking via :meth:`session_status` → else ``None``, meaning "nothing
        usable anywhere" and each caller applies its own historical default
        (``GET /v1/sessions/{id}`` uses ACTIVE; health counts the session as
        not live).

        ``GET /v1/sessions/{id}`` and ``active_session_count()`` both call
        this, so the two answers to "is this session live?" cannot drift.
        """
        status = _harness_status(info.get("status")) if isinstance(info, dict) else None
        if status is None:
            status = self.session_status(session_id)
        return status

    def _session_is_active(self, session_id: str) -> bool:
        """Cross-check a tracked session against ``get_session_info``.

        A harness that reports the session as missing or ``"completed"``
        disagrees with the router's own tracking (the examples flip to
        ``"completed"`` in ``on_result``), so it must not be counted. A
        harness that raises from ``get_session_info`` keeps its tracked value.
        A harness that still states ``"active"`` for a session the router has
        already ended keeps it counted too — the harness's own word wins
        (GAP-058), and the ended window is read for the status it overrides.

        GAP-058: the status decision is :meth:`_resolve_status` — the SAME
        resolution ``GET /v1/sessions/{id}`` reports — so the count and the
        reported status cannot disagree. Two rules outrank it: a harness that
        reports the session as MISSING (``None``) is never counted, and one
        that raises keeps its tracked value.
        """
        get_info = getattr(self, "get_session_info", None)
        if get_info is None:
            return self._resolve_status(session_id, None) is SessionStatus.ACTIVE
        try:
            info = get_info(session_id)
        except Exception:
            logger.exception("get_session_info failed for %s", session_id)
            return True
        if info is None:
            return False
        return self._resolve_status(session_id, info) is SessionStatus.ACTIVE

    def active_session_count(self) -> int | None:
        """Number of live (tracked, not ended) sessions.

        Returns ``None`` ONLY when the harness tracks nothing at all: no
        session has ever been seen — neither live nor in the ended window —
        AND ``get_session_info`` is not implemented. Untracked harnesses
        therefore keep the historical ``active_sessions: null`` health
        payload. Every other harness reports an integer — ``0`` when it
        tracks sessions but none are live.

        Session GC (DF4-H3-SHIM-2 + SDKPY-GAP-063b). The live map is bounded
        by construction: the END purge removes a session at the END write, so
        ended conversations never sit in it waiting for a read. This scan is
        the cross-check that remains — a live entry that resolves not-live
        here (a harness whose ``get_session_info`` disagrees with the
        router's tracking) is not counted and is pruned. The ended window is
        NOT emptied by a read — that memory is what keeps
        ``GET /v1/sessions/{id}`` answering ``completed`` after health has
        already counted the session as not live; a read must never split that
        pair (GAP-058). The cap bounds it instead. A session the harness
        still states ``"active"`` is counted from either map: its own word is
        the answer.
        """
        live = self._live_sessions if isinstance(self._live_sessions, dict) else {}
        ended = self._ended_sessions if isinstance(self._ended_sessions, dict) else {}
        if not live and not ended:
            return 0 if hasattr(self, "get_session_info") else None
        count = 0
        for session_id in list(live):
            # GAP-058: liveness comes from the SAME resolution
            # GET /v1/sessions/{id} reports (_session_is_active ->
            # _resolve_status), so the count and the reported status cannot
            # disagree. A tracked-but-not-active session is simply not live.
            if self._session_is_active(session_id):
                count += 1
            else:
                live.pop(session_id, None)
        for session_id in list(ended):
            if self._session_is_active(session_id):
                count += 1
        return count

    def health(self) -> HealthResponse:
        """Return harness health status. Override for custom health logic."""
        # GAP-025: quickstart subclasses may never call super().__init__(), so
        # _started_at stays at the class default (0.0) and uptime would be a
        # Unix epoch. Lazy-init on first health() call keeps uptime sane.
        if self._started_at <= 0:
            self._started_at = time.time()
        return HealthResponse(
            status=HealthStatus.OK,
            version=__version__,
            active_sessions=self.active_session_count(),
            transport="rest",
            protocol_version="1.0",
            uptime_seconds=int(time.time() - self._started_at),
            capabilities=list(Capability),
        )


def _error_response(status_code: int, code: ErrorCode, message: str) -> JSONResponse:
    """Build a standard H3 error JSON response."""
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=ErrorDetail(code=code, message=message)).model_dump(
            mode="json"
        ),
    )


def _iso_timestamp(value: object) -> str:
    """Coerce a session timestamp to the protocol's ISO-8601 string form.

    SessionResponse.started_at / last_active are protocol strings. Harnesses
    may store epoch seconds (``time.time()`` — the canonical echo example
    did) or ISO strings; coercing here keeps the wire format valid instead
    of 500ing on pydantic validation.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    return str(value)


def _session_status(value: object) -> SessionStatus:
    """Resolve a harness-provided status value to a SessionStatus.

    GAP-035: ``get_session_info`` may carry a ``status`` key (values matching
    SessionStatus, e.g. "active"/"completed"). Unknown or invalid values fall
    back to ACTIVE — the pre-GAP-035 contract and the safe default for
    harnesses that don't track status at all.
    """
    resolved = _harness_status(value)
    return resolved if resolved is not None else SessionStatus.ACTIVE


def _harness_status(value: object) -> SessionStatus | None:
    """Resolve a harness-provided status value, or ``None`` when unusable.

    GAP-058 splits the GAP-035 behaviour in two: ``None`` means the harness
    stated nothing usable — the key is absent, not a string, or not a
    recognised :class:`SessionStatus` — and the caller decides the fallback
    (``GET /v1/sessions/{id}`` consults the router's own tracking, then
    ACTIVE). An explicit valid value is passed through unchanged.
    """
    if isinstance(value, str):
        try:
            return SessionStatus(value)
        except ValueError:
            return None
    return None


def _track(harness: BaseHarness, session_id: str, status: str) -> None:
    """Best-effort session-liveness update from the router.

    Guarded with ``hasattr``: a harness that overrides these routes or never
    calls ``super().__init__()`` must not turn a request into a 500 because of
    tracking, so this is a silent no-op for harnesses without the hook.
    """
    tracker = getattr(harness, "_track_session", None)
    if tracker is None:
        return
    try:
        tracker(session_id, status)
    except Exception:  # pragma: no cover - defensive: never fail a request
        logger.exception("session tracking failed for %s", session_id)


def create_router(harness: BaseHarness, *, prefix: str = "") -> APIRouter:
    """Create a FastAPI router wired to the given harness.

    Registers all H3 endpoints:
        GET  /v1/health
        POST /v1/process
        POST /v1/result
        POST /v1/cancel
        GET  /v1/sessions/{session_id}
        DELETE /v1/sessions/{session_id}

    Usage:
        app = FastAPI()
        app.include_router(create_router(MyHarness()))
        # or with a prefix:
        app.include_router(create_router(MyHarness(), prefix="/api"))
    """
    router = APIRouter(prefix=prefix)

    # ── GET /v1/health ───────────────────────────────────────────
    @router.get("/v1/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return harness.health()

    # ── POST /v1/process ─────────────────────────────────────────
    @router.post(
        "/v1/process", response_model=Decision, response_model_exclude_none=True
    )  # noqa: E501
    async def process(req: ProcessRequest) -> Decision:
        try:
            decision = await harness.on_process(req)
        except Exception as exc:
            logger.exception("on_process failed")
            decision = Decision(
                decision=DecisionType.END,
                end=End(reason=EndReason.ERROR, summary=str(exc)),
            )
        # DF-H3-SDK-PYTHON-FOREMAN-5: a message makes the session live. The
        # response is returned unchanged (the error decision above included).
        _track(harness, req.session_id, "active")
        return decision

    # ── POST /v1/result ──────────────────────────────────────────
    @router.post(
        "/v1/result", response_model=Decision, response_model_exclude_none=True
    )  # noqa: E501
    async def result(req: ResultRequest) -> Decision:
        try:
            decision = await harness.on_result(req)
        except Exception as exc:
            logger.exception("on_result failed")
            decision = Decision(
                decision=DecisionType.END,
                end=End(reason=EndReason.ERROR, summary=str(exc)),
            )
        # An END decision closes the exchange — the session is PURGED from the
        # live tracking (filed in the bounded ended window) so one-shot and
        # error-path conversations cannot accumulate there; a harness crash in
        # on_result lands on the END/error decision above and purges the same
        # way (SDKPY-GAP-063b). Any other decision — text, tool_call, llm_call:
        # the conversation continues — keeps the session live.
        status = "completed" if decision.decision == DecisionType.END else "active"
        _track(harness, req.session_id, status)
        return decision

    # ── POST /v1/cancel ──────────────────────────────────────────
    # GAP-060: the body is typed by cancel-response.json, whose required set
    # is exactly {cancelled, cancelled_decision_id}. session_id is NOT part of
    # that contract, so it is not returned here; a consumer that validates the
    # body against the schema must not receive extra prose.
    @router.post("/v1/cancel", response_model=CancelResponse)
    async def cancel(req: CancelRequest) -> CancelResponse:
        try:
            # Battery (test_5_9b cancel_unknown_session): cancelling a
            # nonexistent session must 404 when the harness tracks sessions.
            if hasattr(harness, "get_session_info"):
                info = harness.get_session_info(req.session_id)  # type: ignore[union-attr]
                if info is None:
                    raise HTTPException(status_code=404, detail="Session not found")
            confirmed = await harness.on_cancel(req)
            # The contract requires cancelled_decision_id but sanctions null
            # (schema type ["string", "null"]): the base harness keeps no
            # in-flight decision registry, so nothing was in flight to name.
            return CancelResponse(cancelled=confirmed, cancelled_decision_id=None)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("on_cancel failed")
            raise HTTPException(status_code=500, detail=str(exc))

    # ── GET /v1/sessions/{session_id} ────────────────────────────
    @router.get("/v1/sessions/{session_id}", response_model=SessionResponse)
    async def get_session(session_id: str, request: Request):
        # If the harness provides session tracking, use it.
        if hasattr(harness, "get_session_info"):
            info = harness.get_session_info(session_id)  # type: ignore[union-attr]
            if info is None:
                raise HTTPException(status_code=404, detail="Session not found")
            # GAP-058: ONE source of truth for liveness. An explicit, valid
            # status in the harness dict still wins (GAP-035); when the dict
            # states nothing usable — key absent, or an unrecognised value —
            # fall back to the router's own tracking (the same value
            # GET /v1/health counts), and only then to the historical ACTIVE.
            # Without this a no-status harness (the AGENTS.md quickstart)
            # reported "active" forever while /v1/health counted it as not
            # live.
            status = harness._resolve_status(  # type: ignore[union-attr]
                session_id, info
            )
            if status is None:
                status = SessionStatus.ACTIVE
            return SessionResponse(
                session_id=session_id,
                started_at=_iso_timestamp(info.get("started_at")),
                last_active=_iso_timestamp(info.get("last_active")),
                turn_count=info.get("turn_count", 0),
                status=status,
            )
        # Default: no session tracking — the router's own tracking when it
        # has any, else ACTIVE (the historical answer for an endpoint that
        # cannot see sessions at all). Same resolution as the branch above.
        status = harness._resolve_status(session_id, None)
        if status is None:
            status = SessionStatus.ACTIVE
        return SessionResponse(
            session_id=session_id,
            started_at="",
            last_active="",
            turn_count=0,
            status=status,
        )

    # ── DELETE /v1/sessions/{session_id} ─────────────────────────
    @router.delete("/v1/sessions/{session_id}")
    async def terminate_session(session_id: str):
        try:
            # GAP-019: session-existence validation matching cancel
            # (battery test_5_9b) and GET (test_5_10) — deleting a
            # nonexistent session must 404 when the harness tracks
            # sessions, not silently return 200 terminated.
            if hasattr(harness, "get_session_info"):
                info = harness.get_session_info(session_id)  # type: ignore[union-attr]
                if info is None:
                    raise HTTPException(status_code=404, detail="Session not found")
            await harness.on_session_terminate(session_id)
            # DF-H3-SDK-PYTHON-FOREMAN-5: a terminated session is no longer live.
            _track(harness, session_id, "completed")
            return {"session_id": session_id, "terminated": True}
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("on_session_terminate failed")
            raise HTTPException(status_code=500, detail=str(exc))

    return router
