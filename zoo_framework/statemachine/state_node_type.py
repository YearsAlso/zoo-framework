from enum import Enum


class StateNodeType(Enum):
    """
    状态节点类型
    """
    string = "string"
    number = "number"
    datetime = "datetime"
    boolean = "boolean"
    array = "array"

    # 节点分支，也就是字典类型
    branch = "branch"

    @staticmethod
    def get_type_by_value(value):
        """
        根据值获取类型
        """
        if isinstance(value, str):
            return StateNodeType.string
        elif isinstance(value, int) or isinstance(value, float):
            return StateNodeType.number
        elif isinstance(value, bool):
            return StateNodeType.boolean
        elif isinstance(value, list):
            return StateNodeType.array
        elif isinstance(value, dict):
            return StateNodeType.branch
        else:
            return None
