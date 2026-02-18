"""
worker_result - zoo_framework/workers/worker_result.py

模块功能描述。

作者: XiangMeng
版本: 0.5.2-beta
"""


class WorkerResult:
    """工作器结果类

    封装工作器的执行结果，包含主题、内容和类名信息。

    属性：
        topic: 结果主题
        content: 结果内容
        cls_name: 工作器类名

    示例：
        >>> result = WorkerResult('test', 'data', 'TestWorker')
        >>> print(result.topic)
        'test'
    """

    def __init__(self, topic, content, cls_name):
        self.topic = topic
        self.content = content
        self.cls_name = cls_name

    def to_dict(self):
        """转换为字典"""
        return {
            'topic': self.topic,
            'content': self.content,
            'cls_name': self.cls_name
        }

    @classmethod
    def from_dict(cls, data):
        """从字典创建实例"""
        return cls(
            topic=data.get('topic', ''),
            content=data.get('content', ''),
            cls_name=data.get('cls_name', '')
        )

    def __str__(self):
        return f"WorkerResult(topic={self.topic}, cls_name={self.cls_name})"

    def __repr__(self):
        return self.__str__()
