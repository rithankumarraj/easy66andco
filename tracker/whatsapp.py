"""
Meta WhatsApp Business Cloud API Integration (Sandbox / Test Environment).
Allows sending loan request links with KYC and income proof checklists directly
via Meta's Graph API and 1-click WhatsApp Web / App links (wa.me).
"""
import os
import urllib.parse
import logging
import requests
from .models import WhatsAppConfig

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"


def get_whatsapp_credentials():
    """Return (phone_number_id, access_token) from DB config with env var fallback."""
    config = WhatsAppConfig.get_solo()
    phone_id = (config.phone_number_id or os.environ.get('WHATSAPP_PHONE_ID', '')).strip()
    token = (config.access_token or os.environ.get('WHATSAPP_TOKEN', '')).strip()
    return phone_id, token


def format_loan_request_message(request=None, applicant_name="", loan_link=None):
    """
    Constructs the borrower message with the 3 mandatory upload document requirements.
    Uses clean characters to prevent diamond encoding artifacts in WhatsApp.
    """
    if not loan_link:
        if request:
            loan_link = request.build_absolute_uri("/loan-request/")
        else:
            loan_link = "http://127.0.0.1:8000/loan-request/"

    greeting = f"Hello {applicant_name}!" if applicant_name else "Hello!"

    message = (
        f"{greeting} Greetings from Easy 66 & Co (Thavanai Finance).\n\n"
        f"You can apply for your loan directly online using this link:\n"
        f"{loan_link}\n\n"
        f"Required Documents (Mandatory for all loans):\n"
        f"• PAN Card\n"
        f"• Aadhaar Card\n"
        f"• Recent Utility Bill (electricity, water, or piped gas bill within the last 2-3 months)\n\n"
        f"Please upload these 3 documents in the link above for fast loan disbursement.\n"
        f"— Easy 66 & Co"
    )
    return message


def format_autopay_mandate_message(loan, request=None):
    """
    Constructs the message for Cashfree AutoPay Mandate Authorization.
    """
    auth_url = loan.cashfree_auth_link
    if not auth_url and request:
        auth_url = request.build_absolute_uri(f"/subscriptions/simulator/{loan.cashfree_subscription_id}/")

    customer_name = loan.customer.name
    freq_label = loan.get_frequency_display()

    message = (
        f"Hello {customer_name}! Greetings from Easy 66 & Co.\n\n"
        f"Your Thavanai loan {loan.loan_id} (₹{loan.gross_principal:,.0f}) has been approved.\n"
        f"• Installment: ₹{loan.installment_amount:,.0f} ({freq_label})\n"
        f"• Total Installments: {loan.installment_count}\n\n"
        f"Please accept and authorize your AutoPay mandate below:\n"
        f"{auth_url}\n\n"
        f"Once authorized, your installments will be collected automatically on schedule.\n"
        f"— Easy 66 & Co · Thavanai Finance"
    )
    return message


def send_meta_whatsapp_cta(to_phone, header_text, body_text, button_text, button_url):
    """
    Sends a WhatsApp Interactive Call-To-Action (CTA URL) button card via Meta's Graph API.
    Renders as a rich message card with a clickable '[ ↗ Button ]' button at the bottom.
    Falls back gracefully to text message with link if interactive mode is rejected by sandbox.
    """
    phone_id, access_token = get_whatsapp_credentials()
    clean_phone = clean_phone_number(to_phone)

    if not phone_id or not access_token:
        return {
            'success': False,
            'mode': 'unconfigured',
            'error': 'Meta Phone Number ID and Access Token are not configured yet.'
        }

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Meta WhatsApp Interactive CTA URL payload
    interactive_payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_phone,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "header": {
                "type": "text",
                "text": header_text[:60]
            },
            "body": {
                "text": body_text[:1024]
            },
            "footer": {
                "text": "Easy 66 & Co · Thavanai Finance"
            },
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": button_text[:20],
                    "url": button_url
                }
            }
        }
    }

    try:
        resp = requests.post(url, json=interactive_payload, headers=headers, timeout=12)
        data = resp.json()

        if resp.status_code in [200, 201]:
            msg_id = data.get('messages', [{}])[0].get('id', '')
            return {
                'success': True,
                'mode': 'meta_interactive_cta',
                'status_code': resp.status_code,
                'message_id': msg_id,
                'data': data
            }
        else:
            # Fallback to standard text with preview_url
            if button_url and button_url not in body_text:
                fallback_text = f"*{header_text}*\n\n{body_text}\n\n{button_text}: {button_url}"
            else:
                fallback_text = f"*{header_text}*\n\n{body_text}"
            text_payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": clean_phone,
                "type": "text",
                "text": {"preview_url": True, "body": fallback_text}
            }
            fb_resp = requests.post(url, json=text_payload, headers=headers, timeout=12)
            fb_data = fb_resp.json()
            if fb_resp.status_code in [200, 201]:
                return {
                    'success': True,
                    'mode': 'meta_cloud_api_text_fallback',
                    'status_code': fb_resp.status_code,
                    'message_id': fb_data.get('messages', [{}])[0].get('id', ''),
                    'data': fb_data
                }
            err_msg = data.get('error', {}).get('message', 'Unknown Meta API error')
            return {
                'success': False,
                'mode': 'meta_cloud_api',
                'status_code': resp.status_code,
                'error': f"Meta Error: {err_msg}",
                'data': data
            }
    except Exception as e:
        logger.exception(f"Error calling Meta WhatsApp API: {e}")
        return {
            'success': False,
            'mode': 'meta_cloud_api',
            'error': f"Connection Error: {str(e)}"
        }


def clean_phone_number(phone):
    """Clean phone number into standard international format without '+' or spaces (e.g. 919871000001)."""
    digits = ''.join(filter(str.isdigit, str(phone or '')))
    if len(digits) == 10:
        digits = '91' + digits  # Default India country code
    return digits


def get_direct_whatsapp_url(phone, text):
    """Generates direct wa.me link that opens in WhatsApp Web or mobile app."""
    clean_phone = clean_phone_number(phone)
    encoded_text = urllib.parse.quote(text)
    return f"https://wa.me/{clean_phone}?text={encoded_text}"


def send_meta_whatsapp_message(to_phone, message_text, preview_url=False):
    """
    Sends text message via Meta's WhatsApp Cloud API Sandbox.
    Matches official Meta docs:
    POST https://graph.facebook.com/v21.0/{phone_number_id}/messages
    """
    phone_id, access_token = get_whatsapp_credentials()
    clean_phone = clean_phone_number(to_phone)

    if not phone_id or not access_token:
        return {
            'success': False,
            'mode': 'unconfigured',
            'error': 'Meta Phone Number ID and Access Token are not configured yet. You can use the Direct WhatsApp (wa.me) button or enter your credentials in WhatsApp Settings.'
        }

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_phone,
        "type": "text",
        "text": {
            "preview_url": preview_url,
            "body": message_text
        }
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=12)
        data = resp.json()

        if resp.status_code in [200, 201]:
            msg_id = data.get('messages', [{}])[0].get('id', '')
            return {
                'success': True,
                'mode': 'meta_cloud_api',
                'status_code': resp.status_code,
                'message_id': msg_id,
                'data': data
            }
        else:
            err_msg = data.get('error', {}).get('message', 'Unknown Meta API error')
            err_type = data.get('error', {}).get('type', '')
            err_code = data.get('error', {}).get('code', resp.status_code)
            return {
                'success': False,
                'mode': 'meta_cloud_api',
                'status_code': resp.status_code,
                'error': f"Meta Error [{err_code}]: {err_msg} ({err_type})",
                'data': data
            }
    except Exception as e:
        logger.exception(f"Error calling Meta WhatsApp API: {e}")
        return {
            'success': False,
            'mode': 'meta_cloud_api',
            'error': f"Connection Error: {str(e)}"
        }


def generate_meta_curl_command(to_phone, message_text):
    """
    Generates the exact cURL command matching Meta's developer documentation:
    https://developers.facebook.com/documentation/business-messaging/whatsapp/about-the-platform#example-sending-a-text-message-using-curl
    """
    raw_phone_id, raw_token = get_whatsapp_credentials()
    phone_id = raw_phone_id or "<WHATSAPP_BUSINESS_PHONE_NUMBER_ID>"
    token = raw_token or "<ACCESS_TOKEN>"
    clean_phone = clean_phone_number(to_phone) if to_phone else "<WHATSAPP_USER_PHONE_NUMBER>"
    escaped_body = message_text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

    return (
        f"curl -i -X POST \\\n"
        f"  'https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_id}/messages' \\\n"
        f"  -H 'Authorization: Bearer {token}' \\\n"
        f"  -H 'Content-Type: application/json' \\\n"
        f"  -d '{{\n"
        f"    \"messaging_product\": \"whatsapp\",\n"
        f"    \"recipient_type\": \"individual\",\n"
        f"    \"to\": \"{clean_phone}\",\n"
        f"    \"type\": \"text\",\n"
        f"    \"text\": {{\n"
        f"      \"preview_url\": false,\n"
        f"      \"body\": \"{escaped_body}\"\n"
        f"    }}\n"
        f"  }}'"
    )
