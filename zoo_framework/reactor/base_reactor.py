from zoo_framework.core.aop.event import event_map
import gevent


class BaseReactor:
    def __init__(self):
        self.event_timout = 1

    def set_event_timeout(self, timeout):
        self.event_timout = timeout

    def _on_error(self, topic, content, exception: Exception):
        pass

    def _on_success(self, topic, content):
        pass

    def _on_done(self, topic, content):
        pass

    def _serialize_content(self, content):
        return content

    def handle(self, topic, content, handler_name="default"):
        events = event_map.get(handler_name)
        if events is None:
            return

        event = events.get(topic)
        if event is None:
            return

        try:
            _content = self._serialize_content(content)
            event(_content)
            self._on_success(topic, content)
        except Exception as e:
            self._on_error(topic, content, e)
        finally:
            self._on_done(topic, content)
