from ccguard import ccguard


print("%load_ext autoreload")
print("%autoreload 2")


def new_parse_args(args=None):
    """
    https://stackoverflow.com/a/4575792/1328968
    >>> parser = argparse.ArgumentParser()
    >>> parser.add_argument('-g', '--global')
    >>> subparsers = parser.add_subparsers(dest="subparser_name") # this line changed
    >>> foo_parser = subparsers.add_parser('foo')
    >>> foo_parser.add_argument('-c', '--count')
    >>> bar_parser = subparsers.add_parser('bar')
    >>> args = parser.parse_args(['-g', 'xyz', 'foo', '--count', '42'])
    >>> args
    Namespace(count='42', global='xyz', subparser_name='foo')
    """

# to implement the circleci check, we need to
# obtain the list of possible comparison term commits (locally to the build environmenr)
# send it to the server, that will find the best reference for those commits
