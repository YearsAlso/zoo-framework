import os


class PathTools:
    @staticmethod
    def path_exit(path: str) -> bool:
        if path.endswith("*"):
            path = path.replace("*","")
        return os.path.exists(path)

    @staticmethod
    def is_file(path: str) -> bool:
        if path.endswith("*"):
            path = path.replace("*","")
        return os.path.isfile(path)

    @staticmethod
    def get_path_file(path: str) -> list:
        """
        获得路径下所有文件
        :param path:
        :return:
        """
        if path.endswith("*"):
            path = path.replace("*","")
        return os.listdir(path)

    @staticmethod
    def parse_path_expression(expression: str) -> list:
        """
        解析路径表达式
        :param expression:
        :return:
        """
        result = []

        if expression.count(".") < 0:
            _is_exit = PathTools.path_exit(expression)
            if not _is_exit:
                return result

            _is_path = PathTools.is_file(expression)
            if not _is_path:
                return result
        else:
            # 替换表达式路径
            expression = expression.replace(".", "/")
            if not expression.startswith("./") and not expression.startswith("/"):
                expression = "./" + expression

            _is_exit = PathTools.path_exit(expression)
            if not _is_exit:
                return result

            if expression.endswith("*"):
                result = PathTools.get_path_file(expression)
            else:
                return [expression]

        return result
