# -*- coding: utf-8 -*-
import requests
import re
import logging
from odoo import _

_logger = logging.getLogger(__name__)


def _get_tally_url(env):
    """Returns (tally_url, default_company) from system config."""
    params = env['ir.config_parameter'].sudo()
    url = params.get_param('tender_ai.tally_url', 'http://localhost').strip()
    port = params.get_param('tender_ai.tally_port', '9000').strip()
    company = params.get_param('tender_ai.tally_company', '').strip()
    if not url.startswith('http'):
        url = f'http://{url}'
    return f"{url}:{port}", company


def get_open_companies(env):
    """
    Fetches all companies currently OPEN in TallyPrime.
    Tally must be running with at least one company open.
    Returns: {'status': 'success', 'companies': ['Company A', 'Company B']}
    """
    tally_url, _ = _get_tally_url(env)

    xml_request = """
    <ENVELOPE>
        <HEADER>
            <TALLYREQUEST>Export Data</TALLYREQUEST>
        </HEADER>
        <BODY>
            <EXPORTDATA>
                <REQUESTDESC>
                    <REPORTNAME>List of Companies</REPORTNAME>
                    <STATICVARIABLES>
                        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                    </STATICVARIABLES>
                </REQUESTDESC>
            </EXPORTDATA>
        </BODY>
    </ENVELOPE>
    """

    try:
        response = requests.post(tally_url, data=xml_request.encode('utf-8'), timeout=10)
        if response.status_code == 200:
            text = response.content.decode('utf-8', errors='replace')
            # Extract company names from <NAME> or <REMOTECMPNAME> tags
            names = re.findall(r'<NAME>\s*(.*?)\s*</NAME>', text, re.IGNORECASE)
            # Also try COMPANY tag attributes
            attr_names = re.findall(r'<COMPANY\b[^>]*NAME="([^"]+)"', text, re.IGNORECASE)
            all_names = list(dict.fromkeys(names + attr_names))  # deduplicate, preserve order
            # Filter out system/empty entries
            clean = [n for n in all_names if n and not n.startswith('$')]
            if not clean:
                return {'status': 'error', 'message': _('No companies found. Ensure at least one company is open in Tally.')}
            return {'status': 'success', 'companies': clean}
        else:
            return {'status': 'error', 'message': _('Tally HTTP %s') % response.status_code}
    except requests.exceptions.ConnectionError:
        return {'status': 'error', 'message': _('Cannot connect to Tally. Ensure Tally is running and port 9000 is accessible.')}
    except Exception as e:
        _logger.exception("Error fetching Tally companies")
        return {'status': 'error', 'message': str(e)}


def push_voucher_to_tally(env, invoice_data, company_name=None):
    """
    invoice_data should be a dict containing:
    - voucher_type: 'Purchase' or 'Sales'
    - date: YYYYMMDD
    - number: Invoice Number
    - party_name: Vendor/Customer Name
    - amount: Total Amount
    - ledger_entries: list of dicts with {'name': LedgerName, 'amount': Amount, 'is_debit': True/False}
    """
    tally_url, default_company = _get_tally_url(env)
    company = company_name or default_company

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
                error_match = re.search(r'<LINEERROR>(.*?)</LINEERROR>', res_text)
                error_msg = error_match.group(1) if error_match else _('Unknown Tally Error')
                return {'status': 'error', 'message': error_msg}
            else:
                return {'status': 'error', 'message': _('Unexpected Tally Response: %s') % res_text}
        else:
            return {'status': 'error', 'message': _('HTTP Error %s') % response.status_code}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def get_tally_ledgers(env, company_name=None):
    """Fetches all ledger names from the specified (or default) Tally company."""
    tally_url, default_company = _get_tally_url(env)
    company = company_name or default_company

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
        response = requests.post(tally_url, data=xml_request.encode('utf-8'), timeout=15)
        if response.status_code == 200:
            names = re.findall(r'<NAME>(.*?)</NAME>', response.content.decode('utf-8'))
            clean_names = sorted(list(set([n for n in names if not n.startswith('$')])))
            return {'status': 'success', 'ledgers': clean_names}
        else:
            return {'status': 'error', 'message': _('Tally HTTP %s') % response.status_code}
    except Exception as e:
        _logger.exception("Error fetching Tally ledgers")
        return {'status': 'error', 'message': str(e)}
