class StateRegister:
    def __init__(self):
        self._state = None

    def set_state(self, state, effect=None):
        self._state = state

    def get_state(self):
        return self._state
