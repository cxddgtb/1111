import base64
import yaml
from collections import defaultdict

TEST_URL = 'http://www.gstatic.com/generate_204'
TEST_INTERVAL = 300

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

def generate_clash_config(nodes, filename, delay_map=None):
    delay_map = delay_map or {}

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

    all_names = [n['name'] for n in safe_nodes]
    # 按延迟从低到高排序，作为故障转移的优先级顺序
    sorted_names = [n['name'] for n in sorted(safe_nodes, key=lambda x: delay_map.get(x['name'], 99999))]

    config = {
        'port': 7890, 'socks-port': 7891, 'allow-lan': False, 'mode': 'Rule',
        'log-level': 'info', 'external-controller': '127.0.0.1:9090',
        'proxies': safe_nodes, 'proxy-groups': [],
        'rules': ['GEOIP,CN,DIRECT', 'MATCH,🚀 节点选择']
    }

    # 手动选择组（默认选中"全球最低延迟"）
    config['proxy-groups'].append({
        'name': '🚀 节点选择', 'type': 'select',
        'proxies': ['⚡ 全球最低延迟', '♻️ 自动故障转移', '⚖️ 负载均衡'] +
                   [f'🌍 {c}' for c in sorted(set(n.get('country', 'Unknown') for n in safe_nodes))] + ['DIRECT']
    })

    # 全局自动选择：延迟最低
    config['proxy-groups'].append({
        'name': '⚡ 全球最低延迟', 'type': 'url-test',
        'proxies': all_names, 'url': TEST_URL, 'interval': TEST_INTERVAL, 'tolerance': 100
    })

    # 保证可用：故障自动切换（按延迟优先级）
    config['proxy-groups'].append({
        'name': '♻️ 自动故障转移', 'type': 'fallback',
        'proxies': sorted_names, 'url': TEST_URL, 'interval': TEST_INTERVAL
    })

    # 负载均衡：分散连接
    config['proxy-groups'].append({
        'name': '⚖️ 负载均衡', 'type': 'load-balance',
        'strategy': 'consistent-hashing',
        'proxies': all_names, 'url': TEST_URL, 'interval': TEST_INTERVAL
    })

    # 按国家分组的自动优选
    countries = sorted(set(n.get('country', 'Unknown') for n in safe_nodes))
    for c in countries:
        config['proxy-groups'].append({
            'name': f'🌍 {c}', 'type': 'url-test',
            'proxies': [n['name'] for n in safe_nodes if n.get('country') == c],
            'url': TEST_URL, 'interval': TEST_INTERVAL, 'tolerance': 100
        })

    with open(filename, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)
