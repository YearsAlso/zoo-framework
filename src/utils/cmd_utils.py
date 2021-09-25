import os


class CmdUtils(object):
    @classmethod
    def cmd_read(cls,cmd):
        with os.popen(cmd) as p:
            response = p.read()
        return str(response).strip()