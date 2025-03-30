from jawa.classloader import ClassLoader


class Topping(object):
    PROVIDES = None
    DEPENDS = None

    @staticmethod
    def act(aggregate, classloader: ClassLoader):
        raise NotImplementedError()
