import yaml
import httpx
import subprocess
import time
import os
import urllib.parse
import concurrent.futures

def generate_test_config(nodes):
    config = {
        'mixed-port': 7890, 'allow-lan': False, 'mode': 'rule', 'log-level': 'silent',
        'external-controller': '127.0.0.1:9090', 'proxies': nodes,
        'proxy-groups': [], 'rules': ['MATCH,DIRECT']
    }
    with open('src/test_config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(config, f)

def run_mihomo_test(nodes):
    if not nodes: return []
    for i, node in enumerate(nodes): node['name'] = f"node_{i}" # 防止特殊字符导致 API 报错
    generate_test_config(nodes)
    
    proc = subprocess.Popen(
        ['./src/mihomo', '-d', './src', '-f', './src/test_config.yaml'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    
    for _ in range(15):
        try:
            r = httpx.get("http://127.0.0.1:9090/proxies", timeout=2)
            if r.status_code == 200: break
        except: pass
        time.sleep(1)
    else:
        proc.terminate()
        return []
        
    alive_nodes = []
    def test_one(node):
        encoded_name = urllib.parse.quote(node['name'], safe='')
        url = f"http://127.0.0.1:9090/proxies/{encoded_name}/delay?timeout=3000&url=http://www.gstatic.com/generate_204"
        try:
            r = httpx.get(url, timeout=5)
            data = r.json()
            if 'delay' in data: return {'node': node, 'delay': data['delay']}
        except: pass
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(test_one, n) for n in nodes]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res: alive_nodes.append(res)
                
    proc.terminate()
    proc.wait()
    if os.path.exists('src/test_config.yaml'): os.remove('src/test_config.yaml')
    return alive_nodes
