import argparse
import json
import logging
import os
import sys
import traceback
import urllib

from jawa.classloader import ClassLoader
from jawa.transforms import expand_constants, simple_swap

from burger import website
from burger.mappings import Mappings, set_global_mappings
from burger.roundedfloats import transform_floats


def import_toppings():
    """
    Attempts to imports either a list of toppings or, if none were
    given, attempts to load all available toppings.
    """
    this_dir = os.path.dirname(__file__)
    toppings_dir = os.path.join(this_dir, 'burger', 'toppings')
    from_list = []

    # Traverse the toppings directory and import everything.
    for root, dirs, files in os.walk(toppings_dir):
        for file_ in files:
            if not file_.endswith('.py'):
                continue
            elif file_.startswith('__'):
                continue
            elif file_ == 'topping.py':
                continue

            from_list.append(file_[:-3])

    from burger.toppings.topping import Topping

    toppings = {}
    last = Topping.__subclasses__()

    for topping in from_list:
        __import__('burger.toppings.%s' % topping)
        current = Topping.__subclasses__()
        subclasses = list([o for o in current if o not in last])
        last = Topping.__subclasses__()
        if len(subclasses) == 0:
            logging.error(f"Topping '{topping}' contains no topping")
        elif len(subclasses) >= 2:
            logging.error(f"Topping '{topping}' contains more than one topping")
        else:
            toppings[topping] = subclasses[0]

    return toppings


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog='Burger',
        description='A simple tool for picking out information from Minecraft jar files, primarily useful for developers.',
    )

    parser.add_argument(
        'version',
        help='Either a file name that ends with .jar, a version string like 1.21.5, a URL that directly downloads a jar file, or the word "latest"',
    )
    parser.add_argument('-t', '--toppings')
    parser.add_argument('-o', '--output')
    parser.add_argument(
        '-L',
        '--log',
        help="The log level, may be 'error', 'warn', 'info', or 'debug'. Defaults to 'info'.",
        default='info',
    )
    parser.add_argument('-c', '--compact', action='store_true')
    parser.add_argument('-l', '--list', action='store_true')
    parser.add_argument('-m', '--mappings')
    parser.add_argument('-s', '--url')
    try:
        args = parser.parse_args()
    except argparse.ArgumentError as e:
        sys.stderr.write(str(e))
        sys.exit(1)

    toppings = args.toppings.split(',') if args.toppings else None
    output = open(args.output, 'w') if args.output else sys.stdout
    list_toppings = args.list
    compact = args.compact
    url = args.url
    mappings_path = args.mappings

    version_name = None
    url_path = None

    # logging should be initialized before we do anything that requires it
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=args.log.upper())

    if '://' in args.version:
        # Download a JAR from the given URL
        url_path = args.version
        client_path = urllib.urlretrieve(url_path)[0]
    if args.version.endswith('.jar'):
        client_path = args.version
    if args.version == 'latest':
        # Download a copy of the latest snapshot jar
        client_path = website.latest_client_jar()
    else:
        # version name
        version_name = args.version
        client_path = website.client_jar(version_name)

    if version_name and not mappings_path:
        # download mappings
        mappings_path = website.mappings_txt(args.version)

    if not mappings_path:
        sys.stderr.write(
            'Version name was not passed explicitly, please provide mappings file using --mappings'
        )
        sys.exit(1)

    set_global_mappings(Mappings.parse(open(mappings_path, 'r').read()))

    # Load all toppings
    all_toppings = import_toppings()

    # List all of the available toppings,
    # as well as their docstring if available.
    if list_toppings:
        for topping in all_toppings:
            print(topping)
            topping_doc = all_toppings[topping].__doc__
            if topping_doc:
                print(f' -- {topping_doc}\n')
        sys.exit(0)

    # Get the toppings we want
    if toppings is None:
        loaded_toppings = all_toppings.values()
    else:
        loaded_toppings = []
        for topping in toppings:
            if topping not in all_toppings:
                logging.error(f"Topping '{topping}' doesn't exist")
            else:
                loaded_toppings.append(all_toppings[topping])

    class DependencyNode:
        def __init__(self, topping):
            self.topping = topping
            self.provides = topping.PROVIDES
            self.depends = topping.DEPENDS
            self.childs = []

        def __repr__(self):
            return str(self.topping)

    # Order topping execution by building dependency tree
    topping_nodes = []
    topping_provides = {}
    for topping in loaded_toppings:
        topping_node = DependencyNode(topping)
        topping_nodes.append(topping_node)
        for provides in topping_node.provides:
            topping_provides[provides] = topping_node

    # Include missing dependencies
    for topping in topping_nodes:
        for dependency in topping.depends:
            if dependency not in topping_provides:
                for other_topping in all_toppings.values():
                    if dependency in other_topping.PROVIDES:
                        topping_node = DependencyNode(other_topping)
                        topping_nodes.append(topping_node)
                        for provides in topping_node.provides:
                            topping_provides[provides] = topping_node

    # Find dependency childs
    for topping in topping_nodes:
        for dependency in topping.depends:
            if dependency not in topping_provides:
                sys.stderr.write(f'({topping}) requires ({dependency})')
                sys.exit(1)
            if topping_provides[dependency] not in topping.childs:
                topping.childs.append(topping_provides[dependency])

    # Run leaves first
    to_be_run = []
    while len(topping_nodes) > 0:
        stuck = True
        for topping in topping_nodes:
            if len(topping.childs) == 0:
                stuck = False
                for parent in topping_nodes:
                    if topping in parent.childs:
                        parent.childs.remove(topping)
                to_be_run.append(topping.topping)
                topping_nodes.remove(topping)
        if stuck:
            sys.stderr.write("Can't resolve dependencies")
            sys.exit(1)

    summary = []

    classloader = ClassLoader(
        client_path, max_cache=0, bytecode_transforms=[simple_swap, expand_constants]
    )
    names = classloader.path_map.keys()
    num_classes = sum(1 for name in names if name.endswith('.class'))

    aggregate = {
        'source': {
            'file': client_path,
            'classes': num_classes,
            'other': len(names),
            'size': os.path.getsize(client_path),
        }
    }

    available = []
    for topping in to_be_run:
        missing = [dep for dep in topping.DEPENDS if dep not in available]
        if len(missing) != 0:
            logging.debug(f'Dependencies failed for {topping}: Missing {missing}')
            continue

        orig_aggregate = aggregate.copy()
        try:
            topping.act(aggregate, classloader)
            available.extend(topping.PROVIDES)
        except Exception:
            aggregate = orig_aggregate  # If the topping failed, don't leave things in an incomplete state
            logger.debug(f'Failed to run {topping}')
            if logging.root.isEnabledFor(logging.DEBUG):
                traceback.print_exc()

    summary.append(aggregate)

    if not compact:
        json.dump(transform_floats(summary), output, sort_keys=True, indent=4)
    else:
        json.dump(transform_floats(summary), output)

    # Cleanup temporary downloads (the URL download is temporary)
    if url_path:
        os.remove(url_path)
    # Cleanup file output (if used)
    if output is not sys.stdout:
        output.close()
