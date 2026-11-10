"""Explicit transport classification. A custom URL cannot masquerade as local."""
import ipaddress
from urllib.parse import urlsplit, urlunsplit
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

PROVIDERS = {
    'gemini': ('Google Gemini', '', 'gemini'),
    'openai': ('OpenAI', 'https://api.openai.com/v1', 'responses'),
    'anthropic': ('Anthropic Claude', 'https://api.anthropic.com/v1', 'anthropic'),
    'deepseek': ('DeepSeek', 'https://api.deepseek.com', 'chat'),
    'xai': ('xAI Grok', 'https://api.x.ai/v1', 'chat'),
    'groq': ('Groq', 'https://api.groq.com/openai/v1', 'chat'),
    'mistral': ('Mistral', 'https://api.mistral.ai/v1', 'chat'),
    'openrouter': ('OpenRouter', 'https://openrouter.ai/api/v1', 'chat'),
    'custom': ('カスタム（OpenAI互換）', '', 'chat'),
}


def validate_endpoint(url, *, local=False):
    if not isinstance(url, str) or any(ord(c) < 33 for c in url) or any(c in url for c in '\\<>"'):
        raise ValueError('接続URLが不正です。')
    try:
        parsed = urlsplit(url)
        port = parsed.port
        host = parsed.hostname
        if not host or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
            raise ValueError()
        if local:
            if parsed.scheme not in ('http', 'https'):
                raise ValueError()
            # localhost is normalized so DNS/hosts cannot resolve it externally.
            host = '127.0.0.1' if host.lower() == 'localhost' else host
            if not ipaddress.ip_address(host).is_loopback:
                raise ValueError()
        elif parsed.scheme != 'https':
            raise ValueError()
        if '%' in host or parsed.path.startswith('//'):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('ローカル接続は127.0.0.1 / ::1、クラウド接続はHTTPSを指定してください。URL内の認証情報・クエリは使えません。') from None
    authority = ('[' + host + ']') if ':' in host else host
    if port:
        authority += ':' + str(port)
    return urlunsplit((parsed.scheme, authority, parsed.path.rstrip('/'), '', ''))
