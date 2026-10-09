from enum import Enum


class StateNodeType(Enum):
    """The state node type."""

    string = "string"
    number = "number"
    datetime = "datetime"
    boolean = "boolean"
    array = "array"

    # Node branch, i.e. the dict type
    branch = "branch"

    @staticmethod
    def get_type_by_value(value):
        """Get the type by value."""
        if isinstance(value, str):
            return StateNodeType.string
        if isinstance(value, (int, float)):
            return StateNodeType.number
        if isinstance(value, bool):
            return StateNodeType.boolean
        if isinstance(value, list):
            return StateNodeType.array
        if isinstance(value, dict):
            return StateNodeType.branch
        return None
