import base64
import yaml
from collections import defaultdict

def select_top_500(alive_nodes):
    # 按照国家+类型进行分组，实现平均轮流加入
    groups = defaultdict(list)
    for item in alive_nodes:
        country = item.get('country', 'Unknown')
        p_type = item['node'].get('type', 'Unknown')
        groups[f"{country}_{p_type}"].append(item)
        
    for k in groups: groups[k].sort(key=lambda x: x['delay'])
        
    selected = []
    iterators = {k: 0 for k in groups}
    
    while len(selected) < 500:
        added = False
        for k in groups:
            if len(selected) >= 500: break
            idx = iterators[k]
            if idx < len(groups[k]):
                selected.append(groups[k][idx]['node'])
                iterators[k] += 1
                added = True
        if not added: break
    return selected

def node_to_uri(node):
    # 将节点转换为通用订阅 URI
    t = node.get('type')
    if t == 'vmess':
        import json
        vmess = {"v": "2", "ps": node['name'], "add": node['server'], "port": str(node['port']),
                 "id": node.get('uuid', ''), "aid": str(node.get('alterId', 0)), "net": node.get('network', 'tcp'),
                 "tls": "tls" if node.get('tls') else "", "sni": node.get('servername', '')}
        return "vmess://" + base64.b64encode(json.dumps(vmess).encode()).decode()
    elif t == 'vless':
        params = f"type={node.get('network', 'tcp')}&security={'tls' if node.get('tls') else 'none'}&sni={node.get('servername', '')}"
        return f"vless://{node.get('uuid', '')}@{node['server']}:{node['port']}?{params}#{node['name']}"
    elif t == 'trojan':
        return f"trojan://{node.get('password', '')}@{node['server']}:{node['port']}#{node['name']}"
    elif t == 'ss':
        userinfo = base64.b64encode(f"{node.get('cipher', '')}:{node.get('password', '')}".encode()).decode()
        return f"ss://{userinfo}@{node['server']}:{node['port']}#{node['name']}"
    return None

def generate_base64_sub(nodes, filename):
    uris = [uri for n in nodes if (uri := node_to_uri(n))]
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(base64.b64encode("\n".join(uris).encode()).decode())

def generate_clash_config(nodes, filename):
    # 兜底去重：确保写入配置时节点名称绝对唯一，防止 Mihomo/Clash 报错
    safe_nodes = []
    used = set()
    for n in nodes:
        new_node = n.copy()
        base = new_node['name']
        i = 2
        while new_node['name'] in used:
            new_node['name'] = f"{base}_{i}"
            i += 1
        used.add(new_node['name'])
        safe_nodes.append(new_node)

    config = {
        'port': 7890, 'socks-port': 7891, 'allow-lan': False, 'mode': 'Rule',
        'log-level': 'info', 'external-controller': '127.0.0.1:9090',
        'proxies': safe_nodes, 'proxy-groups': [],
        'rules': ['GEOIP,CN,DIRECT', 'MATCH,🚀 Node Select']
    }
    countries = list(set([n.get('country', 'Unknown') for n in safe_nodes]))
    country_groups = {f'🌍 {c}': [n['name'] for n in safe_nodes if n.get('country') == c] for c in countries}
    
    for name, proxies in country_groups.items():
        config['proxy-groups'].append({'name': name, 'type': 'url-test', 'proxies': proxies, 'url': 'http://www.gstatic.com/generate_204', 'interval': 300})
        
    config['proxy-groups'].insert(0, {'name': '🚀 Node Select', 'type': 'select', 'proxies': list(country_groups.keys()) + ['DIRECT']})
    
    with open(filename, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)
