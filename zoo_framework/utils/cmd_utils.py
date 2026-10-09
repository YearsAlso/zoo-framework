import os


class CmdUtils:
    """A utility for running shell commands.

    [Security note - this is **deliberately retained**, not an oversight] The
    contract of this class is exactly "hand the caller's command string to
    the shell" (see the ``cmd`` argument of each method), so the **B605
    (start_process_with_a_shell, the shell-injection surface) raised by
    `os.popen` / `os.system` is inherent to that contract**, not a removable
    implementation detail: an alternative that preserved the contract (e.g.
    `shlex.split` + `subprocess.run(shell=False)`) would drop pipes,
    redirections, `&&` and the rest of the shell semantics - a **semantic
    change** we do not decide for the author here; besides, `os.system`'s
    return semantics (exit code) differ from `popen().read()`'s (stdout).
    So, following the repo's established pattern (see
    `persistence_scheduler.py` on pickle), this is closed with a **targeted
    `# nosec`**, and the risk is written here rather than erased.

    **Risk boundary**: this class has **zero call sites in the repo** (only
    exported via `utils/__init__`'s `__all__`, i.e. public API). The real
    risk depends on whether the **caller** splices untrusted input into
    ``cmd`` - that judgment belongs to the caller, not this class.
    """

    @classmethod
    def cmd_read(cls, cmd: str) -> str:
        """Run the cmd command."""
        with os.popen(cmd) as p:  # nosec B605
            response = p.read()
        return response.strip()

    @classmethod
    def cmd_write(cls, cmd: str) -> None:
        """Run the cmd command."""
        os.system(cmd)  # nosec B605

    @classmethod
    def cmd_write_with_result(cls, cmd: str) -> int:
        """Run the cmd command."""
        return os.system(cmd)  # nosec B605
