import copy
from time import sleep

from zoo_framework.utils import LogUtils
from zoo_framework.statemachine.state_machine_manager import StateMachineManager
from zoo_framework.utils import FileUtils
from .base_worker import BaseWorker
import pickle


class StateMachineWorker(BaseWorker):

    def __init__(self):
        BaseWorker.__init__(self, {
            "is_loop": True,
            "delay_time": 5,
            "name": "StateMachineWorker"
        })
        self.is_loop = True

    def _destroy(self, result):
        pass

    def _execute(self):
        from zoo_framework.params import StateMachineParams
        state_machine_manager = StateMachineManager()

        # TODO: 状态树按照作用域进行划分，每个作用域对应一个文件，文件名为作用域名

        if state_machine_manager.have_loaded() is False:
            if FileUtils.file_exists(StateMachineParams.PICKLE_PATH):
                # 如果文件存在
                with open(StateMachineParams.PICKLE_PATH, 'rb') as f:
                    try:
                        unpickler = pickle.Unpickler(f)
                        state_machines = unpickler.load()
                        LogUtils.info(f"state_machines：{state_machines}")
                        state_machine_manager.load_state_machines(state_machines)
                    except Exception as e:
                        LogUtils.error(e)
                        state_machine_manager.load_state_machines()
                        return

                    # TODO：这里需要对线程加锁

                    # TODO：对文件进行校验

                    # TODO：文件的备份和切片功能

            else:
                # 如果文件不存在
                state_machine_manager.load_state_machines()
        else:
            with open(StateMachineParams.PICKLE_PATH, 'wb') as f:
                state_machines = state_machine_manager.get_state_machines()
                copy_value = copy.deepcopy(state_machines)
                # 加载只加载其中的值，不加载锁文件
                pickle.dump(copy_value, f)
