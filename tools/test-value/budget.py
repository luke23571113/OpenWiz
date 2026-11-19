#!/usr/bin/env python3
"""TV14 CLI boundary, before the budget enforcement is implemented."""
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--base', required=True)
parser.add_argument('--head', required=True)
parser.add_argument('--event', required=True)
parser.parse_args()
print('test budget: enforcement not implemented')
