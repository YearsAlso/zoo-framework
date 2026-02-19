# 全局字典，用于存储参数验证规则
params_validate_map = {}


def validation(params_key="") -> object:
    """返回一个装饰器函数，用于将参数插入到指定键的验证列表中。

    参数:
        params_key (str): 用于标识参数验证规则的键，默认为空字符串。

    返回:
        function: 内部函数，接受一个参数并将其插入到对应键的验证列表中。
    """
    def inner(params):
        # 如果指定键在验证映射中不存在，则初始化为空列表
        if params_validate_map.get(params_key) is None:
            params_validate_map[params_key] = []

        # 将参数插入到对应键的验证列表中
        params_validate_map[params_key].insert(params)
        return params

    return inner


def validation_params(params_key, value):
    """验证给定值是否存在于指定键的验证列表中。

    参数:
        params_key (str): 用于查找验证列表的键。
        value (any): 需要验证的值。

    返回:
        bool or None:
            - 如果值存在于验证列表中，返回True；
            - 如果验证列表不存在或类型不正确，返回False；
            - 如果值不在验证列表中，返回None。
    """
    # 获取指定键对应的验证列表
    valid_values = params_validate_map.get(params_key)

    # 如果验证列表不存在，直接返回False
    if valid_values is None:
        return False

    # 如果验证列表不是列表类型，返回False
    if type(valid_values) != list:
        return False

    # 检查值是否在验证列表中
    if value in valid_values:
        return True
    return None
