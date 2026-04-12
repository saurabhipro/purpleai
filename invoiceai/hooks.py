# -*- coding: utf-8 -*-
"""One-time DB cleanup when the addon was renamed purpleai_invoices → invoiceai."""

import logging

_logger = logging.getLogger(__name__)


def migrate_from_purpleai_invoices(cr_or_env):
    """Fix ir.module.module / dependencies / xmlids after folder rename.

    Accepts a cursor or an ``api.Environment`` (Odoo 18+ ``pre_init_hook`` passes ``env``).

    Safe to run repeatedly. If Odoo fails before any module loads, run
    ``tools/fix_purpleai_invoices_module_name.sql`` against the database with Odoo stopped.
    """
    cr = cr_or_env.cr if hasattr(cr_or_env, "cr") else cr_or_env
    if not hasattr(cr, "execute"):
        raise TypeError(
            "migrate_from_purpleai_invoices expected cr or env, got %s" % (type(cr_or_env),)
        )
    cr.execute(
        """
        UPDATE ir_module_module_dependency
        SET name = 'invoiceai'
        WHERE name = 'purpleai_invoices'
        """
    )
    if cr.rowcount:
        _logger.info(
            "invoiceai: repointed %s module dependency row(s) from purpleai_invoices → invoiceai",
            cr.rowcount,
        )

    cr.execute(
        """
        UPDATE ir_model_data
        SET module = 'invoiceai'
        WHERE module = 'purpleai_invoices'
        """
    )
    if cr.rowcount:
        _logger.info(
            "invoiceai: updated %s ir.model_data row(s) to module invoiceai",
            cr.rowcount,
        )

    cr.execute(
        """
        UPDATE ir_act_client
        SET tag = 'invoiceai.dashboard'
        WHERE tag = 'purpleai_invoices.dashboard'
        """
    )
    if cr.rowcount:
        _logger.info(
            "invoiceai: updated %s client action(s) tag purpleai_invoices.dashboard → invoiceai.dashboard",
            cr.rowcount,
        )
    cr.execute(
        """
        UPDATE ir_act_client
        SET tag = 'invoiceai.action_folder_explorer'
        WHERE tag = 'purpleai_invoices.action_folder_explorer'
        """
    )
    if cr.rowcount:
        _logger.info(
            "invoiceai: updated %s client action(s) folder explorer tag to invoiceai.*",
            cr.rowcount,
        )

    cr.execute("SELECT id, state FROM ir_module_module WHERE name = 'purpleai_invoices'")
    old = cr.fetchone()
    if not old:
        return
    old_id, old_state = old
    cr.execute("SELECT id, state FROM ir_module_module WHERE name = 'invoiceai'")
    inv = cr.fetchone()
    if inv:
        inv_id, inv_state = inv
        # Odoo always has a stub row for invoiceai (usually uninstalled). If the old app was
        # active, we must mark invoiceai installed or models (e.g. purple_ai.extraction_result)
        # never load → RPC KeyError on that model.
        if old_state in ('installed', 'to upgrade', 'to remove') and inv_state in (
            'uninstalled',
            'to install',
        ):
            cr.execute(
                "UPDATE ir_module_module SET state = 'installed' WHERE id = %s",
                (inv_id,),
            )
            _logger.info(
                "invoiceai: set module invoiceai (id=%s) to installed "
                "(migrated from purpleai_invoices state=%s)",
                inv_id,
                old_state,
            )
        cr.execute(
            "UPDATE ir_module_module SET state = 'uninstalled' WHERE id = %s",
            (old_id,),
        )
        _logger.info(
            "invoiceai: set legacy module purpleai_invoices (id=%s) to uninstalled; using invoiceai row",
            old_id,
        )
    else:
        cr.execute(
            "UPDATE ir_module_module SET name = 'invoiceai' WHERE id = %s",
            (old_id,),
        )
        _logger.info(
            "invoiceai: renamed ir_module_module row id=%s from purpleai_invoices → invoiceai (state=%s)",
            old_id,
            old_state,
        )


def verify_models_registered(registry):
    """Fail install early if Python models did not register (easier than a silent KeyError later)."""
    if "purple_ai.extraction_result" not in registry:
        raise RuntimeError(
            "invoiceai: model purple_ai.extraction_result is missing from the registry. "
            "See the Odoo server log for import errors, and ensure only one addon folder "
            "named 'invoiceai' is on addons_path (remove legacy copies: purpleai_invoices, invoicesai)."
        )
