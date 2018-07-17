import os

try:
    from ymp._version import version as __version__
except ModuleNotFoundError:
    from pkg_resources import get_distribution, DistributionNotFound
    try:
        __version__ = get_distribution(__name__).version
    except DistributionNotFound:
        from setuptools_scm import get_version
        __version__ = get_version(root="..", relative_to=__file__)


# Importing pkg_resources takes rather long (~200ms), for CLI snappiness,
# we manually gather the paths for our distributed files.
_rsc_dir = __path__[0]
_rule_dir = os.path.join(_rsc_dir, "rules")
_etc_dir = os.path.join(_rsc_dir, "etc")
_snakefile = os.path.join(_rule_dir, "Snakefile")
_defaults_file = os.path.join(_etc_dir, "defaults.yml")
_env_dir = os.path.join(_rsc_dir, "conda_envs")

import sys
if 'sphinx' in sys.modules:
    import ymp.config  # required for type hints below

#: Set to 1 to show the YMP expansion process as it is applied to the next
#: Snakemake rule definition.
#:
#: >>> ymp.print_rule = 1
#: >>> rule broken:
#: >>>   ...
#:
#: >>> ymp make broken -vvv
print_rule = 0


def get_config() -> 'config.ConfigMgr':
    """Access the current YMP configuration object.

    This object might change once during normal execution: it is
    deleted before passing control to Snakemake. During unit test
    execution the object is deleted between all tests.
    """
    from ymp.config import ConfigMgr
    return ConfigMgr.instance()
