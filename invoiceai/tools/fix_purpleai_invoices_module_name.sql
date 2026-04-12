-- Run with Odoo STOPPED if the server logs:
--   "inconsistent states ... missing: ['purpleai_invoices']"
-- Then start Odoo and install/upgrade the invoiceai addon.
--
-- psql -d YOUR_DB -f fix_purpleai_invoices_module_name.sql

BEGIN;

UPDATE ir_module_module_dependency
SET name = 'invoiceai'
WHERE name = 'purpleai_invoices';

UPDATE ir_model_data
SET module = 'invoiceai'
WHERE module = 'purpleai_invoices';

UPDATE ir_act_client SET tag = 'invoiceai.dashboard' WHERE tag = 'purpleai_invoices.dashboard';
UPDATE ir_act_client SET tag = 'invoiceai.action_folder_explorer' WHERE tag = 'purpleai_invoices.action_folder_explorer';

-- If both module rows exist: mark invoiceai installed if legacy was active, then drop legacy row.
DO $$
DECLARE
    old_id INTEGER;
    old_st VARCHAR;
    new_id INTEGER;
    new_st VARCHAR;
BEGIN
    SELECT id, state INTO old_id, old_st FROM ir_module_module WHERE name = 'purpleai_invoices' LIMIT 1;
    IF old_id IS NULL THEN
        RETURN;
    END IF;
    SELECT id, state INTO new_id, new_st FROM ir_module_module WHERE name = 'invoiceai' LIMIT 1;
    IF new_id IS NOT NULL THEN
        IF old_st IN ('installed', 'to upgrade', 'to remove')
           AND new_st IN ('uninstalled', 'to install') THEN
            UPDATE ir_module_module SET state = 'installed' WHERE id = new_id;
        END IF;
        UPDATE ir_module_module SET state = 'uninstalled' WHERE id = old_id;
    ELSE
        UPDATE ir_module_module SET name = 'invoiceai' WHERE id = old_id;
    END IF;
END $$;

COMMIT;
