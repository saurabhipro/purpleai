# -*- coding: utf-8 -*-

"""
Increase Odoo's global request size limit early (before controllers parse JSON).

Why:
- Odoo applies `web.max_file_upload_size` (ICP) during `ir.http._pre_dispatch`.
- Some routes (notably `/web/dataset/call_kw`) need to parse JSON *before*
  `_pre_dispatch` runs, e.g. to compute `readonly`. Large payloads then fail
  with 413 at Werkzeug level.

Solution:
- Allow configuring the global limit from `odoo.conf` so the server accepts the
  request body in the first place.

Config (odoo.conf):
[options]
tender_ai_max_content_length = 536870912   ; 512 MiB in bytes
"""

import logging

from odoo.tools import config

_logger = logging.getLogger(__name__)

try:
    from odoo import http as odoo_http
except Exception:  # pragma: no cover
    odoo_http = None


def _apply_max_content_length_patch():
    if not odoo_http:
        return

    key = "tender_ai_max_content_length"
    raw = None
    try:
        raw = config.get(key)
    except Exception:
        raw = None

    if not raw:
        return

    try:
        value = int(str(raw).strip())
    except Exception:
        _logger.warning("Tender AI: invalid %s=%r (must be integer bytes). Ignored.", key, raw)
        return

    if value <= 0:
        _logger.warning("Tender AI: %s must be > 0. Ignored.", key)
        return

    current = getattr(odoo_http, "DEFAULT_MAX_CONTENT_LENGTH", None)
    if isinstance(current, int) and value <= current:
        _logger.info("Tender AI: %s=%s <= current (%s). No change.", key, value, current)
        return

    try:
        odoo_http.DEFAULT_MAX_CONTENT_LENGTH = value
        _logger.info("Tender AI: set Odoo DEFAULT_MAX_CONTENT_LENGTH to %s bytes via %s", value, key)
    except Exception as e:
        _logger.warning("Tender AI: failed to set DEFAULT_MAX_CONTENT_LENGTH: %s", str(e))


_apply_max_content_length_patch()


