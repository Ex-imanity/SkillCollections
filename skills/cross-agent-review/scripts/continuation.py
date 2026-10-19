"""Durable identity for explicit continuation of one unfinished review gate.

The shared marker lock must cover every method. This record is separate from
the legacy attempt/success counters, and never contains prompts or credentials.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from .common import MAX_REVIEW_ATTEMPTS, MAX_SUCCESSFUL_REVIEWS, ReviewResult, _atomic_write_text, _load_counts


class ReviewContinuation:
    def __init__(self, *, resume: bool, cwd: str, artifact_paths: list, session_store: str,
                 binding_context: dict | None = None):
        self.resume = resume
        self.cwd = cwd
        self.artifact_paths = artifact_paths
        self.session_store = session_store
        self.binding_context = binding_context or {}
        self.path = ""
        self.data = {}
        self.started = False

    def check(self, *, marker_path: str, gate_id: str, artifact_key: str,
              request_prompt: str, reviewer: str, requested_model: str | None,
              output_path: str | None, cost_log_path: str) -> None:
        key = hashlib.sha256(gate_id.encode()).hexdigest()
        self.path = os.path.abspath(marker_path) + ".sessions/" + key + ".json"
        previous = None
        if os.path.exists(self.path):
            try:
                previous = json.loads(Path(self.path).read_text(encoding="utf-8"))
                if not isinstance(previous, dict) or type(previous.get("version")) is not int or previous["version"] != 1:
                    raise ValueError("invalid schema version")
                if previous.get("state") not in {"running", "timed_out", "completed", "failed"}:
                    raise ValueError("invalid lifecycle state")
                if not isinstance(previous.get("binding"), str) or len(previous["binding"]) != 64:
                    raise ValueError("invalid binding")
                UUID(previous["session_id"])
                for field in ("attempt", "continuation", "successes_before"):
                    if type(previous[field]) is not int or previous[field] < 0:
                        raise ValueError("invalid counter")
                if not 0 < previous["attempt"] <= MAX_REVIEW_ATTEMPTS or previous["successes_before"] >= MAX_SUCCESSFUL_REVIEWS:
                    raise ValueError("invalid attempt/success count")
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                raise ValueError("continuation record is damaged; preserve it for diagnosis") from exc

        if self.resume and (previous is None or previous["state"] != "timed_out"):
            raise ValueError("only a recorded, unfinished timed-out gate can be resumed")
        if not self.resume and previous and previous["state"] in {"running", "timed_out"}:
            raise ValueError("gate is unfinished; observe the original runner, then use --resume after timeout")

        cwd = os.path.realpath(self.cwd)
        files = {}
        for item in self.artifact_paths:
            path = Path(item)
            path = (Path(cwd) / path).resolve() if not path.is_absolute() else path.resolve()
            if not path.is_file():
                raise ValueError("artifact-path must reference an existing file")
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            files[str(path)] = digest.hexdigest()
        identity = dict(gate_id=gate_id, artifact_key=artifact_key, request=request_prompt,
                        reviewer=reviewer, model=requested_model, cwd=cwd, files=files,
                        session_store=os.path.realpath(self.session_store),
                        cost_log=os.path.abspath(cost_log_path),
                        output=os.path.abspath(output_path) if output_path else None)
        if self.binding_context:
            identity["peer_context"] = self.binding_context
        binding = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        counts, valid = _load_counts(marker_path)
        current = counts.get(artifact_key, {"attempts": 0, "successes": 0})
        if not valid:
            raise ValueError("invalid attempt marker")
        if self.resume:
            if (previous["binding"] != binding or current["attempts"] != previous["attempt"]
                    or current["successes"] != previous["successes_before"]):
                raise ValueError("original request/artifact/scope/model/output or attempt marker changed; start a counted gate")
            self.data = {**previous, "continuation": previous["continuation"] + 1}
        else:
            self.data = dict(version=1, binding=binding, session_id=str(uuid4()), state="running",
                             continuation=0, successes_before=current["successes"])

    @property
    def session_id(self) -> str:
        return self.data["session_id"]

    @property
    def runtime_dir(self) -> str:
        return self.path + ".runtime/" + self.session_id

    def start(self, attempt: int) -> None:
        self.data.update(attempt=attempt, state="running", parent_pid=os.getpid())
        _atomic_write_text(self.path, json.dumps(self.data, indent=2, sort_keys=True) + "\n")
        self.started = True

    def decorate(self, result: ReviewResult) -> ReviewResult:
        if self.resume and result.status == "success" and result.envelope.get("session_id") != self.session_id:
            result = ReviewResult("provenance_failure", None,
                                  {**result.envelope, "detail": "resumed reviewer returned a different session ID"}, 1)
        if result.status == "timeout":
            result.envelope["session_id"] = self.session_id
        result.envelope.update(continuation_state_path=self.path, attempt=self.data["attempt"],
                               continuation=self.data["continuation"], resumable=result.status == "timeout")
        return result

    def finish(self, result: ReviewResult) -> ReviewResult:
        if not self.started:
            return result
        result = self.decorate(result)
        self.data["state"] = ("timed_out" if result.status == "timeout" else
                              "completed" if result.status == "success" else "failed")
        _atomic_write_text(self.path, json.dumps(self.data, indent=2, sort_keys=True) + "\n")
        return result
