import warnings
import logging

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

# Hide known account model warnings when account module is intentionally not installed.
class _AccountComodelWarningFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        return "unknown comodel_name 'account." not in msg

logging.getLogger('odoo.fields').addFilter(_AccountComodelWarningFilter())

from . import models
from . import http_limits
from . import wizard
from . import controllers
