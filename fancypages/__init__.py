from __future__ import absolute_import

import os

__version__ = VERSION = "0.3.0"


def get_fancypages_paths(path):
    """ Get absolute paths for *path* relative to the project root """
    return [os.path.join(os.path.dirname(os.path.abspath(__file__)), path)]


def get_oscar_fancypages_paths(path):
    from fancypages.contrib import oscar_fancypages
    return [
        os.path.join(
            os.path.dirname(os.path.abspath(oscar_fancypages.__file__)), path)
    ] + get_fancypages_paths(path)


def get_required_apps():
    return [
        'django_extensions',
        # used for image thumbnailing
        'sorl.thumbnail',
        # framework used for the internal API
        'rest_framework',
        # provides a convenience layer around model inheritance
        # that makes lookup of nested models easier. This is used
        # for the content block hierarchy.
        'model_utils',
        # static file compression and collection
        'compressor',
        # migration handling
        'south',
    ]


def get_fancypages_apps():
    return ['fancypages.assets', 'fancypages']
