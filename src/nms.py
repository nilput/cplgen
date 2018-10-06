import inspect
from types import SimpleNamespace
class nms(SimpleNamespace):
    def __getattr__(self, name):
        err = None
        try:
            return super().__getattr__(name)
        except:
            pass
        err = 'couldn\'t find the member "{}"\n'.format(name)
        err += 'available memebers: \n'
        err += ', '.join(map(lambda x: "\n  '{}':{}".format(x[0],(str(x[1]) if (len(str([x[1]])) < 50) else (str(x[1])[:50] + '...'))), self.__dict__.items()))
        raise AttributeError(err)
