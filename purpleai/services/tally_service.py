# -*- coding: utf-8 -*-
import requests
import logging
from odoo import _

_logger = logging.getLogger(__name__)

def push_voucher_to_tally(env, invoice_data):
    """
    invoice_data should be a dict containing:
    - voucher_type: 'Purchase' or 'Sales'
    - date: YYYYMMDD
    - number: Invoice Number
    - party_name: Vendor/Customer Name
    - amount: Total Amount
    - ledger_entries: list of dicts with {'name': LedgerName, 'amount': Amount, 'is_debit': True/False}
    """
    params = env['ir.config_parameter'].sudo()
    url = params.get_param('tender_ai.tally_url', 'http://localhost').strip()
    port = params.get_param('tender_ai.tally_port', '9000').strip()
    company = params.get_param('tender_ai.tally_company', '').strip()

    if not url.startswith('http'):
        url = f'http://{url}'
    
    tally_url = f"{url}:{port}"

    # Prepare Ledger Entries XML
    ledger_xml = ""
    for entry in invoice_data.get('ledger_entries', []):
        amount = entry['amount']
        # Tally expects negative for Credit, positive for Debit (simplified)
        # Actually in Tally XML, <ALLLEDGERENTRIES.LIST> has <AMOUNT>
        # A positive amount in <AMOUNT> is usually Credit, negative is Debit. 
        # But it depends on the context.
        tally_amount = -abs(amount) if entry.get('is_debit') else abs(amount)
        
        ledger_xml += f"""
                        <ALLLEDGERENTRIES.LIST>
                            <LEDGERNAME>{entry['name']}</LEDGERNAME>
                            <ISDEEMEDPOSITIVE>{'Yes' if entry.get('is_debit') else 'No'}</ISDEEMEDPOSITIVE>
                            <AMOUNT>{tally_amount}</AMOUNT>
                        </ALLLEDGERENTRIES.LIST>"""

    xml_payload = f"""
    <ENVELOPE>
        <HEADER>
            <TALLYREQUEST>Import Data</TALLYREQUEST>
        </HEADER>
        <BODY>
            <IMPORTDATA>
                <REQUESTDESC>
                    <REPORTNAME>All Masters</REPORTNAME>
                    <STATICVARIABLES>
                        <SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY>
                    </STATICVARIABLES>
                </REQUESTDESC>
                <REQUESTDATA>
                    <TALLYMESSAGE xmlns:UDF="TallyUDF">
                        <VOUCHER VCHTYPE="{invoice_data['voucher_type']}" ACTION="Create" OBJTYPE="Voucher">
                            <DATE>{invoice_data['date']}</DATE>
                            <VOUCHERTYPENAME>{invoice_data['voucher_type']}</VOUCHERTYPENAME>
                            <VOUCHERNUMBER>{invoice_data['number']}</VOUCHERNUMBER>
                            <REFERENCE>{invoice_data.get('reference', invoice_data['number'])}</REFERENCE>
                            <PARTYLEDGERNAME>{invoice_data['party_name']}</PARTYLEDGERNAME>
                            <VCHSTATUS>Created</VCHSTATUS>
                            <NARRATION>{invoice_data.get('narration', '')}</NARRATION>
                            <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
                            {ledger_xml}
                        </VOUCHER>
                    </TALLYMESSAGE>
                </REQUESTDATA>
            </IMPORTDATA>
        </BODY>
    </ENVELOPE>
    """

    try:
        response = requests.post(tally_url, data=xml_payload, timeout=10)
        if response.status_code == 200:
            res_text = response.content.decode('utf-8')
            if '<CREATED>1</CREATED>' in res_text:
                return {'status': 'success', 'message': _('Successfully pushed to Tally.')}
            elif '<ERRORS>1</ERRORS>' in res_text:
                # Extract error message if possible
                import re
                error_match = re.search(r'<LINEERROR>(.*?)</LINEERROR>', res_text)
                error_msg = error_match.group(1) if error_match else _('Unknown Tally Error')
                return {'status': 'error', 'message': error_msg}
            else:
                return {'status': 'error', 'message': _('Unexpected Tally Response: %s') % res_text}
        else:
            return {'status': 'error', 'message': _('HTTP Error %s') % response.status_code}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def get_tally_ledgers(env):
    """Fetches all ledger names from the active Tally company."""
    params = env['ir.config_parameter'].sudo()
    url = params.get_param('tender_ai.tally_url', 'http://localhost').strip()
    port = params.get_param('tender_ai.tally_port', '9000').strip()
    company = params.get_param('tender_ai.tally_company', '').strip()

    if not url.startswith('http'):
        url = f'http://{url}'
    tally_url = f"{url}:{port}"

    xml_request = f"""
    <ENVELOPE>
        <HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
        <BODY>
            <EXPORTDATA>
                <REQUESTDESC>
                    <REPORTNAME>List of Ledgers</REPORTNAME>
                    <STATICVARIABLES><SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY></STATICVARIABLES>
                </REQUESTDESC>
            </EXPORTDATA>
        </BODY>
    </ENVELOPE>
    """

    try:
        response = requests.post(tally_url, data=xml_request, timeout=15)
        if response.status_code == 200:
            import re
            # Extract names from <NAME>...</NAME> tags
            names = re.findall(r'<NAME>(.*?)</NAME>', response.content.decode('utf-8'))
            # Filter out internal/system names and duplicates
            clean_names = sorted(list(set([n for n in names if not n.startswith('$')])))
            return {'status': 'success', 'ledgers': clean_names}
        else:
            return {'status': 'error', 'message': _('Tally HTTP %s') % response.status_code}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
