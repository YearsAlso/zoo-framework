"""The waiter factory: builds a waiter by **scheduling-model name**.

History: this factory used to pick among three near-identical waiter
subclasses by "run policy name" (simple / stable / safe). The only
difference among them was "what to do when the pool is undersized"
(expand / queue / reject), unrelated to the concurrency primitive or the
time semantics - so the difference is now carried by ``ThreadPoolModel``'s
backpressure policy parameter, the factory keys on the model name, and the
legacy policy names MUST be rejected explicitly.
"""

from zoo_framework.constant import WaiterConstant

from .base_waiter import BaseWaiter


class WaiterFactory:
    """The waiter factory: builds the matching waiter by scheduling-model name."""

    @staticmethod
    def get_waiter(name: str | None = None) -> BaseWaiter:
        """Build a waiter by scheduling-model name.

        An unrecognized model name is rejected explicitly with the available
        models listed, MUST NOT silently return the default model - a silent
        downgrade would make the observed behavior of a mis-typed config
        entirely unrelated to the config, without the caller ever noticing.

        Args:
            name: the scheduling-model name (a ``worker:mode`` value); None
                means derived from config

        Returns:
            A waiter instance with the matching model assembled

        Raises:
            ValueError: the model name is unrecognized
        """
        if name is not None and name not in WaiterConstant.IMPLEMENTED_WORKER_MODES:
            raise ValueError(
                f"unknown scheduling model {name!r}; available models are "
                f"{list(WaiterConstant.IMPLEMENTED_WORKER_MODES)}"
            )
        return BaseWaiter(model_name=name)
