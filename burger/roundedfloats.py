import six


def transform_floats(o):
    if isinstance(o, float):
        return round(o, 5)
    elif isinstance(o, dict):
        return {k: transform_floats(v) for k, v in six.iteritems(o)}
    elif isinstance(o, (list, tuple)):
        return [transform_floats(v) for v in o]
    return o
