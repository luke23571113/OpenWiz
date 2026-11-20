#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
"""The module docstring narrates what the file does."""
import json

URL = "https://example.com/#not-a-comment"

# PRIVACY: never write the token to a log.
TOKEN_ENV = 'SYNTHETIC_TOKEN'


def load(path):
    """Load the file."""
    # Open it and parse it.
    with open(path) as f:
        return json.load(f)  # parse


TEXT = """
# a heading inside a string, not a comment
"""


def skipped():  # noqa: C901 -- the synthetic rule misfires on one-line bodies
    return 1  # type: ignore


# DATA LOSS: deleting this folder deletes every saved run.
RUNS = 'runs'
