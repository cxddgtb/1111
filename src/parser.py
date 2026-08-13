import base64
import json
import urllib.parse

def decode_base64(s):
    s = s.strip()
    missing_padding = len(s) % 4
    if missing_padding: s += '=' * (4 - missing_padding)
    try: return base64.b64decode(s).decode('utf-8')
    except: return ""

def parse_v2ray_uri(uri, index):
    try:
        if uri.startswith('vmess://'):
            json_str = decode_base64(uri[8:])
            if not json_str: return None
            node = json.loads(json_str)
            return {
                'name': node.get('ps', f'VMess-{index}'),
                'type': 'vmess', 'server': node.get('add'),
                'port': int(node.get('port')), 'uuid': node.get('id'),
                'alterId': int(node.get('aid', 0)), 'cipher': node.get('scy', 'auto'),
                'network': node.get('net', 'tcp'), 'tls': node.get('tls', '') == 'tls',
                'servername': node.get('sni', node.get('host', '')),
                'ws-opts': {'path': node.get('path', '/'), 'headers': {'Host': node.get('host', '')}} if node.get('net') == 'ws' else None
            }
        elif uri.startswith('vless://'):
            uri = uri[8:]
            name = urllib.parse.unquote(uri.split('#')[1]) if '#' in uri else f'VLESS-{index}'
            uuid, rest = uri.split('#')[0].split('@', 1)
            server_port, params_str = rest.split('?', 1)
            server, port = server_port.rsplit(':', 1)
            params = urllib.parse.parse_qs(params_str)
            return {
                'name': name, 'type': 'vless', 'server': server, 'port': int(port),
                'uuid': uuid, 'network': params.get('type', ['tcp'])[0],
                'tls': params.get('security', ['none'])[0] in ['tls', 'reality'],
                'servername': params.get('sni', [''])[0], 'client-fingerprint': 'chrome',
                'ws-opts': {'path': params.get('path', ['/'])[0], 'headers': {'Host': params.get('host', [''])[0]}} if params.get('type', ['tcp'])[0] == 'ws' else None
            }
        elif uri.startswith('trojan://'):
            uri = uri[9:]
            name = urllib.parse.unquote(uri.split('#')[1]) if '#' in uri else f'Trojan-{index}'
            password, rest = uri.split('#')[0].split('@', 1)
            server_port = rest.split('?')[0]
            server, port = server_port.rsplit(':', 1)
            return {
                'name': name, 'type': 'trojan', 'server': server, 'port': int(port),
                'password': password, 'sni': rest.split('sni=')[1].split('&')[0] if 'sni=' in rest else server,
                'network': 'tcp'
            }
        elif uri.startswith('ss://'):
            uri = uri[5:]
            name = urllib.parse.unquote(uri.split('#')[1]) if '#' in uri else f'SS-{index}'
            userinfo, server_port = uri.split('#')[0].split('@', 1) if '@' in uri else (decode_base64(uri.split('?')[0]), "")
            server, port = server_port.rsplit(':', 1)
            method, password = userinfo.split(':', 1)
            return {'name': name, 'type': 'ss', 'server': server, 'port': int(port), 'cipher': method, 'password': password}
    except Exception: pass
    return None
