import os
import re
import socket
import geoip2.database
from scraper import get_subscription_urls, fetch_nodes
from parser import parse_v2ray_uri
from tester import run_mihomo_test
from generator import generate_clash_config, generate_base64_sub, select_top_500

def dedup_nodes(nodes):
    seen = set()
    deduped = []
    for node in nodes:
        key = f"{node.get('server')}:{node.get('port')}:{node.get('type')}"
        if key not in seen:
            seen.add(key)
            deduped.append(node)
    return deduped

def main():
    print("1. Fetching subscription URLs...")
    urls = get_subscription_urls()
    
    print(f"2. Fetching nodes from {len(urls)} subscriptions...")
    raw_items = fetch_nodes(urls)
    
    print(f"3. Parsing {len(raw_items)} items...")
    nodes = []
    for i, item in enumerate(raw_items):
        if isinstance(item, dict) and 'clash_dict' in item:
            node = item['clash_dict']
            if 'name' not in node or not node.get('server'): continue
            nodes.append(node)
        elif isinstance(item, str):
            parsed = parse_v2ray_uri(item, i)
            if parsed: nodes.append(parsed)
            
    print(f"4. Deduplicating nodes...")
    nodes = dedup_nodes(nodes)
    print(f"   -> {len(nodes)} unique nodes found.")
    
    print("5. Testing nodes with Mihomo (this may take a few minutes)...")
    alive_nodes_with_delay = run_mihomo_test(nodes)
    print(f"   -> {len(alive_nodes_with_delay)} nodes alive.")
    
    print("6. GeoIP Lookup...")
    try:
        reader = geoip2.database.Reader('src/GeoLite2-Country.mmdb')
        ip_pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
        
        final_nodes = []
        used_names = set()  # 新增：记录已使用的节点名称，防止重名导致配置报错
        
        for item in alive_nodes_with_delay:
            node = item['node']
            server = node['server']
            if not ip_pattern.match(server):
                try: server = socket.gethostbyname(server)
                except: server = "8.8.8.8"
                
            try:
                resp = reader.country(server)
                country = resp.country.iso_code or "Unknown"
            except: country = "Unknown"
                
            item['country'] = country
            node['country'] = country
            
            # 重命名节点以包含国家和延迟信息（新增去重后缀逻辑）
            base_name = f"{country}_{node['type'].upper()}_{node['port']}_{item['delay']}"
            name, suffix = base_name, 2
            while name in used_names:
                name = f"{base_name}_{suffix}"
                suffix += 1
            used_names.add(name)
            node['name'] = name
            
            final_nodes.append(item)
            
        print("7. Generating outputs...")
        os.makedirs("output/clash", exist_ok=True)
        os.makedirs("output/base64", exist_ok=True)
        
        # 按国家生成单独的 Clash 配置
        countries = list(set(n['country'] for n in final_nodes))
        for country in countries:
            country_nodes = [n['node'] for n in final_nodes if n['country'] == country]
            generate_clash_config(country_nodes, f"output/clash/clash_{country}.yaml")
            
        # 生成全局 Top 500 配置 (按国家类型延迟最低平均加入)
        top_500_nodes = select_top_500(final_nodes)
        generate_clash_config(top_500_nodes, "output/clash/clash_global_top500.yaml")
        
        # 生成 Base64 订阅
        all_nodes_list = [n['node'] for n in final_nodes]
        generate_base64_sub(all_nodes_list, "output/base64/all_nodes.txt")
        generate_base64_sub(top_500_nodes, "output/base64/top500.txt")
        
        print("Done! Files saved to output/")
    except Exception as e:
        print(f"Fatal Error: {e}")

if __name__ == "__main__":
    main()
