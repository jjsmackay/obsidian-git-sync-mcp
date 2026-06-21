"""A thin ``git`` CLI wrapper for the worker -- one subprocess call per method.

The worker is the single thread that touches git; this module is its only door
to the ``git`` binary. Every method runs ``git -C <vault> ...`` via
``subprocess.run`` with a timeout and captured output, returning a small
``GitResult`` (rc/stdout/stderr) rather than raising on an expected non-zero --
a failed push or a rebase conflict is normal control flow for the worker, not an
exception. The ONE thing that raises is a subprocess timeout (a wedged git
command): the caller swallows it, logs, and moves on.

We drive the ``git`` CLI (not libgit2/pygit2) deliberately: it is the same tool
the bobsidian origin used, behaves identically against the real vault, and is
trivially testable against a tmp ``git init`` + a bare remote.

Logging never echoes remote URLs or other secrets -- only the host's git
exit code and, for a timeout, the exception type. Remote URLs can embed tokens.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# A wedged git command must never block the single worker thread forever. The
# worker swallows the resulting TimeoutExpired and retries on the next cycle.
DEFAULT_TIMEOUT = 120.0


@dataclass(frozen=True)
class GitResult:
    """The outcome of one git invocation. ``ok`` is the zero-exit convenience."""

    rc: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.rc == 0


class GitOps:
    """Run git commands against one working tree.

    Holds the vault path and the optional commit identity; methods map one-to-one
    to the git operations the worker needs. A non-zero exit returns a ``GitResult``
    (callers branch on ``.ok``); a timeout propagates ``subprocess.TimeoutExpired``
    for the caller to swallow.
    """

    def __init__(
        self,
        vault: Path | str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        author_name: str | None = None,
        author_email: str | None = None,
    ) -> None:
        self.vault = Path(vault)
        self.timeout = timeout
        self.author_name = author_name
        self.author_email = author_email

    def _run(self, *args: str) -> GitResult:
        """Run ``git -C <vault> <args>`` and capture its result.

        Never raises on a non-zero exit (``check=False``); the caller inspects
        ``GitResult.ok``. Lets ``subprocess.TimeoutExpired`` propagate -- a hung
        git command is the one case the worker must handle specially.
        """
        try:
            proc = subprocess.run(
                ["git", "-C", str(self.vault), *args],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            # Log type only -- args could carry a remote URL with an embedded token.
            logger.warning("git command timed out after %ss", self.timeout)
            raise
        return GitResult(proc.returncode, proc.stdout, proc.stderr)

    def _identity_args(self) -> list[str]:
        """``-c user.name=… -c user.email=…`` when an identity is configured.

        Passed per-invocation (not via env or global config) so the worker's
        commits carry a stable author without mutating the host's git config.
        """
        args: list[str] = []
        if self.author_name:
            args += ["-c", f"user.name={self.author_name}"]
        if self.author_email:
            args += ["-c", f"user.email={self.author_email}"]
        return args

    # --- Staging -----------------------------------------------------------

    def add(self, paths) -> GitResult:
        """Stage the named paths. ``-A`` pathspec semantics record deletions too.

        ``git add -A -- <paths>`` stages adds, modifications AND removals of the
        given paths, so a deleted/moved file is recorded correctly even though it
        no longer exists on disk.
        """
        return self._run("add", "-A", "--", *paths)

    def add_all(self) -> GitResult:
        """Stage the whole working tree (the sweep's blunt instrument)."""
        return self._run("add", "-A")

    # --- Inspection --------------------------------------------------------

    def has_staged(self) -> bool:
        """True when the index holds changes to commit.

        ``git diff --cached --quiet`` exits 1 when there ARE staged changes, 0
        when there are none -- so a non-zero (non-ok) result means "something
        staged".
        """
        return not self._run("diff", "--cached", "--quiet").ok

    def is_dirty(self) -> bool:
        """True when the working tree has any uncommitted change (staged or not)."""
        return bool(self._run("status", "--porcelain").stdout.strip())

    # --- Committing --------------------------------------------------------

    def commit(self, message: str) -> GitResult:
        """Commit the staged index with ``message``; a no-op when nothing is staged.

        Checks ``has_staged()`` first so an empty commit is never attempted (git
        would exit non-zero and we would log a spurious failure). Returns an
        ``ok`` no-op result when there is nothing to commit.
        """
        if not self.has_staged():
            return GitResult(0, "", "nothing staged")
        return self._run(*self._identity_args(), "commit", "-m", message)

    # --- Remote sync -------------------------------------------------------

    def fetch(self, remote: str) -> GitResult:
        """Fetch from ``remote``. A non-ok result (offline) is the caller's signal
        to skip the rebase but still try the push."""
        return self._run("fetch", remote)

    def rebase_theirs(self, remote: str, branch: str) -> GitResult:
        """Rebase local commits onto ``<remote>/<branch>`` with local-wins conflict
        policy.

        ``-X theirs`` during a rebase favours the commits being replayed (our
        just-made local commits), so local content wins on conflict. A non-ok
        result means the rebase could not complete and the caller must
        ``rebase_abort()`` -- we NEVER leave conflict markers in the tree.
        """
        return self._run("rebase", "-X", "theirs", f"{remote}/{branch}")

    def rebase_abort(self) -> GitResult:
        """Abort an in-progress rebase, restoring the pre-rebase tree."""
        return self._run("rebase", "--abort")

    def push(self, remote: str, branch: str) -> GitResult:
        """Push ``branch`` to ``remote``. A non-ok result (rejected/offline) is
        logged and swallowed by the caller; the commits retry next cycle."""
        return self._run("push", remote, branch)

    # --- Topology ----------------------------------------------------------

    def current_branch(self) -> str | None:
        """The current branch name, or None on a detached HEAD / failure."""
        result = self._run("rev-parse", "--abbrev-ref", "HEAD")
        if not result.ok:
            return None
        name = result.stdout.strip()
        return name or None

    def remote_exists(self, remote: str) -> bool:
        """True when ``remote`` is configured (``git remote get-url`` succeeds)."""
        return self._run("remote", "get-url", remote).ok
