# Judged obsolete (cleanup-aop-public-surface / issue #49): this module is
# no longer exported from the `core` / `core.aop` package surface; the module
# path is kept for one minor cycle for migration, and will be deleted in the
# next minor together with `workers.WorkerRegister`. Historical problems:
# the legacy table it writes is never read by the dispatch chain `Master`
# uses (`WorkerRegistry`), so registered instances are never dispatched; the
# key is still the bare class name; instantiation happens at import time.
# The only wired-up path is `Master.register_worker(name, worker_class)`.
import warnings

from zoo_framework.workers import WorkerRegister

worker_register: WorkerRegister = WorkerRegister()

_DEPRECATION_TEXT = (
    "@worker does not hook into dispatch: it registers into the legacy WorkerRegister, "
    "which Master never reads, so registered instances are never dispatched. "
    "Use Master.register_worker(name, worker_class) instead; this module will be removed in the next minor version."
)


def worker(count: int = 1):
    """A decorator registering the given number of worker instances.

    .. deprecated:: judged obsolete (#49); emits a ``DeprecationWarning``
        when used - see the module top note.

    Args:
        count (int): the number of worker instances to register, default 1.

    Returns:
        function: an inner decorator handling the decorated class.
    """

    def inner(cls):
        """The inner decorator performing the actual worker registration.

        Args:
            cls (class): the decorated class, the worker's type.

        Returns:
            class: the original class, keeping the decorator transparent.
        """
        # The deprecation signal is raised at the site where the decorated
        # class is defined (stacklevel pierces past the decorator apply point).
        warnings.warn(_DEPRECATION_TEXT, DeprecationWarning, stacklevel=3)
        # When only one instance is needed, register an instance of the class directly
        if count == 1:
            worker_register.register(cls.__name__, cls())
            return cls

        # When multiple instances are needed, number each one and register
        # them separately
        for i in range(1, count + 1):
            instance = cls()
            instance.num = i
            worker_register.register(f"{cls.__name__}_{i}", instance)
        return cls

    return inner
