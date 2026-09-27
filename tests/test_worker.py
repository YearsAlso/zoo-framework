"""Worker 测试模块

测试 BaseWorker 和相关的 Worker 功能
"""


from zoo_framework.constant import WaiterConstant
from zoo_framework.workers import BaseWorker, WorkerProps, WorkerResult


class TestBaseWorker:
    """BaseWorker 测试类"""

    def test_worker_init_with_props(self):
        """测试使用 props 初始化 Worker"""
        props = {
            "is_loop": True,
            "delay_time": 1.5,
            "name": "TestWorker"
        }
        worker = BaseWorker(props)
        assert worker._props == props
        # is_loop 是以 _props 为唯一真源的属性，读取不需要调用语法
        assert worker.is_loop is True
        assert "TestWorker" in worker.name

    def test_worker_init_defaults(self):
        """测试 Worker 默认属性"""
        props = {"name": "TestWorker"}
        worker = BaseWorker(props)
        assert worker.is_loop is False
        assert "TestWorker" in worker.name

    def test_worker_name_property(self):
        """测试 name 属性包含自动编号"""
        worker = BaseWorker({"name": "CustomName"})
        # name 会附加 _num 后缀
        assert "CustomName" in worker.name

    def test_worker_execute(self):
        """测试 Worker _execute 方法可以调用"""
        worker = BaseWorker({"name": "TestWorker"})
        # _execute 默认是空方法，可以正常调用
        result = worker._execute()
        assert result is None

    def test_worker_run(self):
        """测试 Worker run 方法"""
        worker = BaseWorker({"name": "TestWorker"})
        # run 方法应该返回 WorkerResult
        result = worker.run()
        assert isinstance(result, WorkerResult)
        # 结果统一投递到结果主题，并携带产生它的 Worker 名
        assert result.topic == WaiterConstant.WORKER_RESULT_TOPIC
        assert result.worker_name == worker.name


class TestWorkerProps:
    """WorkerProps 测试类"""

    def test_worker_props_init(self):
        """测试 WorkerProps 初始化"""
        props = WorkerProps("TestWorker", True, 2.0)
        assert props.name == "TestWorker"
        assert props.is_loop is True
        assert props.delay_time == 2.0

    def test_worker_props_default_values(self):
        """测试 WorkerProps 默认值"""
        props = WorkerProps("TestWorker")
        assert props.name == "TestWorker"
        assert props.is_loop is True  # 默认 True
        assert props.delay_time == 1  # 默认 1


class TestWorkerResult:
    """WorkerResult 测试类"""

    def test_worker_result_init(self):
        """测试 WorkerResult 初始化"""
        result = WorkerResult("test_topic", "test_content", "TestClass")
        assert result.topic == "test_topic"
        assert result.content == "test_content"
        assert result.cls_name == "TestClass"
