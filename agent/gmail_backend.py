"""OAuth Gmail adapter for a dedicated, explicitly allowlisted test mailbox."""
from __future__ import annotations

import base64
import json
import os
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path
from hashlib import sha256

from agent.schemas import ErrorCode, ToolResult

STATE_FILE = Path('.gmail_state/aliases.json')
SCOPES = ['https://www.googleapis.com/auth/gmail.modify',
          'https://www.googleapis.com/auth/gmail.compose']


def _save(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, indent=2), encoding='utf-8')
    tmp.replace(STATE_FILE)


def _load():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    return {'emails': {}, 'drafts': {}, 'sent': {}}


def _service():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError('Gmail dependencies missing: run uv sync --extra gmail') from exc

    account = os.getenv('OPERATOR_GMAIL_TEST_ACCOUNT', '').strip().lower()
    if not account or '@' not in account:
        raise RuntimeError('Set OPERATOR_GMAIL_TEST_ACCOUNT to a dedicated test account')
    token_file = Path(os.getenv('OPERATOR_GMAIL_TOKEN_FILE', '.gmail_state/token.json'))
    secret_file = Path(os.getenv('OPERATOR_GMAIL_CLIENT_SECRETS', 'client_secret.json'))
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not secret_file.exists():
                raise RuntimeError('Gmail OAuth client credentials file not found')
            creds = InstalledAppFlow.from_client_secrets_file(str(secret_file), SCOPES).run_local_server(port=0)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json(), encoding='utf-8')
    service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
    actual = service.users().getProfile(userId='me').execute()['emailAddress'].lower()
    if actual != account:
        raise RuntimeError('OAuth account does not match OPERATOR_GMAIL_TEST_ACCOUNT')
    return service, account


def _email_alias(state, real_id):
    for alias, val in state['emails'].items():
        if val == real_id:
            return alias
    alias = f'em_{len(state["emails"])+1:03d}'
    state['emails'][alias] = real_id
    _save(state)
    return alias


def _header(message, name):
    return next((x.get('value', '') for x in message.get('payload', {}).get('headers', [])
                 if x.get('name', '').lower() == name.lower()), '')


def _body(payload):
    if payload.get('mimeType') == 'text/plain' and payload.get('body', {}).get('data'):
        return base64.urlsafe_b64decode(payload['body']['data'] + '===').decode('utf-8', errors='replace')
    for part in payload.get('parts', []):
        content = _body(part)
        if content:
            return content
    return ''


def _message(service, message_id):
    return service.users().messages().get(userId='me', id=message_id, format='full').execute()


def _allowed_sender(sender):
    allowed = {x.strip().lower() for x in os.getenv('OPERATOR_GMAIL_ALLOWED_RECIPIENTS', '').split(',') if x.strip()}
    return sender.lower() in allowed


def _execute(service, account, name, a, state):
    messages = service.users().messages()
    drafts = service.users().drafts()
    if name == 'finish':
        return ToolResult.success('Run finished.', {'summary': a['summary']})
    if name == 'list_emails':
        query = 'in:inbox' if a['folder'] == 'inbox' else 'in:anywhere -in:inbox -in:trash -in:spam -in:sent -in:drafts'
        if a['unread_only']:
            query += ' is:unread'
        response = messages.list(userId='me', q=query, maxResults=a['limit']).execute()
        items = []
        for msg in response.get('messages', []):
            full = _message(service, msg['id'])
            items.append({'id': _email_alias(state, msg['id']), 'sender': _header(full, 'From'),
                          'subject': _header(full, 'Subject')})
        return ToolResult.success(f'{len(items)} emails found.', {'emails': items}) if items else ToolResult.failure(
            ErrorCode.EMPTY_RESULT, 'No matching messages.', 'Try a different folder or filter.')
    if name in ('read_email', 'apply_label', 'archive_email', 'draft_reply'):
        real = state['emails'].get(a['email_id'])
        if not real:
            return ToolResult.failure(ErrorCode.NOT_FOUND, 'Email id is not mapped.', 'Call list_emails first.')
        msg = _message(service, real)
        if name == 'read_email':
            return ToolResult.success('Untrusted email content.', {'email': {
                'id': a['email_id'], 'sender': _header(msg, 'From'), 'subject': _header(msg, 'Subject'),
                'body': _body(msg.get('payload', {}))[:12000],
            }})
        if name == 'apply_label':
            labels = service.users().labels()
            existing = labels.list(userId='me').execute().get('labels', [])
            target = next((label['id'] for label in existing if label['name'] == a['label']), None)
            if not target:
                target = labels.create(userId='me', body={'name': a['label'], 'labelListVisibility': 'labelShow',
                                                          'messageListVisibility': 'show'}).execute()['id']
            already = target in msg.get('labelIds', [])
            if not already:
                messages.modify(userId='me', id=real, body={'addLabelIds': [target]}).execute()
            return ToolResult.success('Label applied.', {'email_id': a['email_id'], 'label': a['label']}, replay=already)
        if name == 'archive_email':
            already = 'INBOX' not in msg.get('labelIds', [])
            if not already:
                messages.modify(userId='me', id=real, body={'removeLabelIds': ['INBOX']}).execute()
            return ToolResult.success('Email archived.', {'email_id': a['email_id']}, replay=already)
        for alias, info in state['drafts'].items():
            if info['email_id'] == a['email_id'] and info.get('body_hash') == sha256(a['body'].encode()).hexdigest():
                return ToolResult.success('Existing draft reused.', {'draft_id': alias}, replay=True)
        sender = parseaddr(_header(msg, 'From'))[1]
        if not sender:
            return ToolResult.failure(ErrorCode.INVALID_ARGUMENT, 'Cannot identify original sender.')
        reply = EmailMessage()
        reply['From'] = account
        reply['To'] = sender
        reply['Subject'] = 'Re: ' + _header(msg, 'Subject')[:150]
        message_id = _header(msg, 'Message-ID')
        if message_id:
            reply['In-Reply-To'] = message_id
            reply['References'] = message_id
        reply.set_content(a['body'])
        raw = base64.urlsafe_b64encode(reply.as_bytes()).decode('ascii')
        created = drafts.create(userId='me', body={'message': {'raw': raw, 'threadId': msg['threadId']}}).execute()
        alias = f'dr_{len(state["drafts"])+1:03d}'
        state['drafts'][alias] = {'id': created['id'], 'email_id': a['email_id'], 'body_hash': sha256(a['body'].encode()).hexdigest(), 'recipient': sender}
        _save(state)
        return ToolResult.success('Gmail draft created, not sent.', {'draft_id': alias, 'email_id': a['email_id']})
    if name == 'send_reply':
        info = state['drafts'].get(a['draft_id'])
        if not info:
            return ToolResult.failure(ErrorCode.NOT_FOUND, 'Draft not mapped.', 'Create a draft first.')
        if a['draft_id'] in state['sent']:
            return ToolResult.success('Already sent.', {'sent_id': state['sent'][a['draft_id']]}, replay=True)
        if os.getenv('OPERATOR_ENABLE_GMAIL_SEND', '').lower() != 'yes':
            return ToolResult.failure(ErrorCode.NOT_ALLOWED, 'Gmail send disabled.', 'Explicitly enable OPERATOR_ENABLE_GMAIL_SEND=yes for test-only sending.')
        if not _allowed_sender(info['recipient']):
            return ToolResult.failure(ErrorCode.NOT_ALLOWED, 'Recipient not allowlisted.', 'Add a controlled test recipient to the allowlist.')
        sent = drafts.send(userId='me', body={'id': info['id']}).execute()
        state['sent'][a['draft_id']] = sent['id']
        _save(state)
        return ToolResult.success('Gmail test reply sent.', {'sent_id': sent['id'], 'to': info['recipient']})
    return ToolResult.failure(ErrorCode.INVALID_ARGUMENT, 'Unsupported tool.')


def execute_gmail(name, args):
    try:
        service, account = _service()
        return _execute(service, account, name, args, _load())
    except RuntimeError as exc:
        return ToolResult.failure(ErrorCode.NOT_ALLOWED, str(exc), 'Check Gmail OAuth setup and test-account restrictions.')
    except Exception as exc:
        return ToolResult.failure(ErrorCode.TOOL_UNAVAILABLE, 'Gmail operation failed.',
                                  f'{type(exc).__name__}: Check API access, OAuth permissions and network.')
