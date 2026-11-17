#!/usr/bin/env python3
"""WM1 (#1056): the war room's split checker. Stub: reports nothing yet."""
import argparse
import sys

sys.dont_write_bytecode = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.parse_args(argv)
    return 0


if __name__ == '__main__':
    sys.exit(main())
