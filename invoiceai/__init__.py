import warnings

# Silence known third-party SWIG deprecation warnings on Python 3.12.
warnings.filterwarnings(
    "ignore",
    message=r"builtin type SwigPyPacked has no __module__ attribute",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"builtin type SwigPyObject has no __module__ attribute",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"builtin type swigvarlink has no __module__ attribute",
    category=DeprecationWarning,
)


from . import models
from . import http_limits
from . import wizard
from . import controllers


def pre_init_hook(env):
    """Odoo 18+ passes Environment (see hooks.migrate_from_purpleai_invoices)."""
    from .hooks import migrate_from_purpleai_invoices

    migrate_from_purpleai_invoices(env)


def post_init_hook(env):
    """Odoo 18+ passes a single Environment (not cr, registry)."""
    from .hooks import verify_models_registered

    verify_models_registered(env.registry)
