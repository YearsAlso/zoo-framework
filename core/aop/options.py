from core.container import params


def options(name=""):
    def import_mod(cls):
        _name = name
        if _name is None:
            _name = cls.__name__
        if params.get(_name) is not None:
            _name = _name + "_" + len(params)
        params[_name] = cls
        return cls
    
    return import_mod
