import httpx
import re
import base64
import yaml

TARGET_README = "https://raw.githubusercontent.com/Helpsoftware/fanqiang/master/README.md"

def get_subscription_urls():
    try:
        resp = httpx.get(TARGET_README, timeout=10)
        # 提取常见的订阅链接格式
        urls = re.findall(r'https?://[^\s<>"]+?(?:\.yaml|\.yml|\.txt|sub[/?]|ACCESS_TOKEN=[a-zA-Z0-9]+)', resp.text)
        urls = list(set(u for u in urls if 'Helpsoftware/fanqiang' not in u))
        return urls
    except Exception as e:
        print(f"Error fetching README: {e}")
        return []

def fetch_nodes(urls):
    uris = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    for url in urls:
        try:
            resp = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
            if resp.status_code == 200:
                content = resp.text.strip()
                # 尝试解析 Base64 标准订阅
                if len(content) > 100 and not content.startswith('proxies:'):
                    try:
                        decoded = base64.b64decode(content).decode('utf-8')
                        uris.extend([line.strip() for line in decoded.split('\n') if line.strip().startswith(('vmess://', 'vless://', 'trojan://', 'ss://'))])
                        continue
                    except Exception: pass
                        
                # 尝试解析 Clash YAML 配置
                if 'proxies:' in content:
                    try:
                        data = yaml.safe_load(content)
                        if 'proxies' in data:
                            for p in data['proxies']:
                                uris.append({'clash_dict': p})
                        continue
                    except Exception: pass
                        
                # 尝试解析纯文本 URI
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith(('vmess://', 'vless://', 'trojan://', 'ss://')):
                        uris.append(line)
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
    return uris
