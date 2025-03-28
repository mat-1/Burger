# Fork info

This is a maintained fork of Burger that only targets the latest Minecraft
snapshot (but may coincidentally work on other new versions). It was created for
use in [Azalea](https://github.com/mat-1/azalea)'s code generator, so features
that aren't necessary for that purpose will not be maintained and might be
removed in the future.

# Burger

Burger is a "framework" for automatically extracting data from the Minecraft
game for the purpose of writing the protocol specification, interoperability,
and other neat uses.

## The Idea

Burger is made up of _toppings_, which can provide and satisfy simple
dependencies, and which can be run all-together or just a few specifically. Each
topping is then aggregated by `munch.py` into the whole and output as a JSON
dictionary.

## Usage

The simplest way to use Burger is to pass the version as the only argument,
which will download the specified Minecraft client for you. The downloaded jar
will be saved in the working directory, and if it already exists the existing
verison will be used.

    $ python munch.py 1.21.5

To download the latest snapshot, the string "latest" can be passed instead.

    $ python munch.py latest

Alternatively, you can specify the client jar by passing it as an argument.

    $ python munch.py 1.21.5.jar

You can redirect the output from the default `stdout` by passing `-o <path>` or
`--output <path>`. This is useful when combined with verbose output (`-v` or
`--verbose`) so that the output doesn't go into the file.

    $ python munch.py latest --output output.json

You can see what toppings are available by passing `-l` or `--list`.

    $ python munch.py --list

You can also run specific toppings by passing a comma-delimited list to `-t` or
`--toppings`. If a topping cannot be used because it's missing a dependency, it
will output an error telling you what also needs to be included. Toppings will
generally automatically load their dependencies, however.

    $ python munch.py latest --toppings language,stats

The above example would only extract the language information, as well as the
stats and achievements (both part of `stats`).
