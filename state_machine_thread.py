from constant import StateMachineConstant
from core import worker
from statemachine.state_machine_manager import StateMachineManager
from utils import FileUtils
from .base_thread import BaseThread
import pickle


@worker()
class StateMachineThread(BaseThread):
    
    def __init__(self):
        BaseThread.__init__(self, {
            "is_loop": True,
            "delay_time": 5,
            "name": "StateMachineThread"
        })
        self.is_loop = True
    
    def _destroy(self, result):
        pass
    
    def _execute(self):
        state_machine_manager = StateMachineManager()
        
        if state_machine_manager.have_loaded() is False:
            if FileUtils.file_exists(StateMachineConstant.PICKLE_FILE):
                # 如果文件存在
                with open(StateMachineConstant.PICKLE_FILE, 'rb') as f:
                    state_machines = pickle.load(f)
                    state_machine_manager.load_state_machines(state_machines)
            else:
                # 如果文件不存在
                state_machine_manager.load_state_machines()
        
        with open(StateMachineConstant.PICKLE_FILE, 'wb') as f:
            state_machines = state_machine_manager.get_state_machines()
            pickle.dump(state_machines, f)
