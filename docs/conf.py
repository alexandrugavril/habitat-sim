# Copyright (c) Facebook, Inc. and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import os
import re
import sys


# TODO make this less brittle
sys.path = [
    os.path.join(os.path.dirname(__file__), "../"),
    # os.path.join(os.path.dirname(__file__), '../build-bundledmagnum/src/deps/magnum-bindings/src/python/')
] + sys.path


import habitat_sim  # NOQA

# TODO: remove once m.css handles class hierarchies better
habitat_sim.logging.GlogFormatter.formatStack.__doc__ = ""
# Monkey patch the registry to be the _Registry class instead of the singleton for docs
habitat_sim.registry = type(habitat_sim.registry)

PROJECT_TITLE = "Habitat"
PROJECT_SUBTITLE = "Sim Python Docs"
PROJECT_LOGO = "habitat.svg"
FAVICON = "habitat-blue.png"
MAIN_PROJECT_URL = "/"
INPUT_MODULES = [habitat_sim]
INPUT_DOCS = ["docs.rst", "gfx.rst"]
INPUT_PAGES = [
    "pages/index.rst",
    "pages/new-actions.rst",
    "pages/stereo-agent.rst",
    "pages/notebooks.rst",
]

PLUGINS = [
    "m.abbr",
    "m.code",
    "m.components",
    "m.dox",
    "m.gh",
    "m.htmlsanity",
    "m.images",
    "m.link",
    "m.math",
    "m.sphinx",
]

CLASS_INDEX_EXPAND_LEVELS = 2

NAME_MAPPING = {
    # I have no idea what is going on with this thing -- it reports itself as
    # being from the builtins module?
    "quaternion": "quaternion.quaternion",
    # TODO: remove once the inventory file contains this info
    "_magnum": "magnum",
}
PYBIND11_COMPATIBILITY = True
ATTRS_COMPATIBILITY = True

OUTPUT = "../build/docs/habitat-sim/"

LINKS_NAVBAR1 = [
    (
        "Pages",
        "pages",
        [
            ("Add new actions", "new-actions"),
            ("Stereo agent", "stereo-agent"),
            ("Notebooks", "notebooks"),
        ],
    ),
    ("Classes", "classes", []),
]
LINKS_NAVBAR2 = [
    ("C++ Docs", "../habitat-cpp/index.html", []),
    ("Habitat API Docs", "../habitat-api/index.html", []),
]

FINE_PRINT = f"""
| {PROJECT_TITLE} {PROJECT_SUBTITLE}. Copyright © 2019 Facebook AI Research.
| Created with `m.css Python doc generator <https://mcss.mosra.cz/documentation/python/>`_."""
THEME_COLOR = "#478cc3"
STYLESHEETS = [
    "https://fonts.googleapis.com/css?family=Source+Sans+Pro:400,400i,600,600i%7CSource+Code+Pro:400,400i,600",
    "theme.compiled.css",
]

M_SPHINX_INVENTORIES = [
    ("python.inv", "https://docs.python.org/3/", [], ["m-doc-external"]),
    ("numpy.inv", "https://docs.scipy.org/doc/numpy/", [], ["m-doc-external"]),
    (
        "quaternion.inv",
        "https://quaternion.readthedocs.io/en/latest/",
        [],
        ["m-doc-external"],
    ),
    (
        "magnum-bindings.inv",
        "https://doc.magnum.graphics/python/",
        [],
        ["m-doc-external"],
    ),
]
M_SPHINX_INVENTORY_OUTPUT = "objects.inv"
M_SPHINX_PARSE_DOCSTRINGS = True

M_HTMLSANITY_SMART_QUOTES = True
# Will people hate me if I enable this?
# M_HTMLSANITY_HYPHENATION = True

_hex_colors_src = re.compile(
    r"""<span class="s2">&quot;0x(?P<hex>[0-9a-f]{6})&quot;</span>"""
)
_hex_colors_dst = r"""<span class="s2">&quot;0x\g<hex>&quot;</span><span class="m-code-color" style="background-color: #\g<hex>;"></span>"""

M_CODE_FILTERS_POST = {
    ("Python", "string_hex_colors"): lambda code: _hex_colors_src.sub(
        _hex_colors_dst, code
    )
}

M_DOX_TAGFILES = [
    (
        "corrade.tag",
        "https://doc.magnum.graphics/corrade/",
        ["Corrade::"],
        ["m-doc-external"],
    ),
    (
        "magnum.tag",
        "https://doc.magnum.graphics/magnum/",
        ["Magnum::"],
        ["m-doc-external"],
    ),
    ("../build/docs/habitat-cpp.tag", "../habitat-cpp/", [], ["m-doc-external"]),
]
