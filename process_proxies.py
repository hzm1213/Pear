import os
import re
import yaml
import random
import emoji
import ipaddress
import base64
from urllib.parse import urlparse, parse_qs, unquote

# ------------------ 工具函数 ------------------
def clean_name(name: str) -> str:
    name = name.replace('🇨🇳TW', '🇹🇼TW')
    name = re.sub(r'[_\s]*@wangcai_8[_\s]*', ' ', name, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', name).strip()

def extract_region(name: str):
    match = re.match(r'^([\U0001F1E6-\U0001F1FF]{2})([A-Z]{2,})', name)
    if match:
        return match.group(1), match.group(2)
    for e in emoji.EMOJI_DATA.keys():
        if name.startswith(e):
            remain = name[len(e):]
            match_region = re.match(r'^([A-Z]{2,})', remain)
            if match_region:
                return e, match_region.group(1)
    return '🏳️', 'ZZ'

def is_flag_emoji(e):
    return re.match(r'^[🇦-🇿]{2}$', e)

def load_available_emojis():
    return [e for e in emoji.EMOJI_DATA.keys() if not is_flag_emoji(e)]

def generate_unique_emoji(used_emojis, available_emojis):
    choice = random.choice([e for e in available_emojis if e not in used_emojis])
    used_emojis.add(choice)
    return choice

# ------------------ URL 节点解析 ------------------
def parse_ss(url):
    try:
        if not url.startswith("ss://"):
            return None
        ss_body = url[5:]
        # fragment
        if "#" in ss_body:
            ss_body, frag = ss_body.split("#",1)
            name = unquote(frag)
        else:
            name = ""
        # query/plugin
        if "?" in ss_body:
            ss_body, query = ss_body.split("?",1)
            query_params = parse_qs(query)
        else:
            query_params = {}
        if "@" in ss_body:
            method_pass, host_port = ss_body.split("@",1)
            if ":" in method_pass:
                method, password = method_pass.split(":",1)
            else:
                method = method_pass
                password = ""
            host, port = host_port.split(":")
            return {
                "name": name,
                "type": "ss",
                "server": host,
                "port": int(port),
                "method": method,
                "password": password,
                "plugin": query_params.get("plugin", [""])[0],
                "plugin_opts": {k:v[0] for k,v in query_params.items() if k != "plugin"}
            }
        return None
    except:
        return None

def parse_vmess(url):
    try:
        b64 = url[8:]
        decoded = base64.b64decode(b64 + "=" * (-len(b64)%4)).decode()
        info = yaml.safe_load(decoded)
        return {"name": info.get("ps",""), "type":"vmess", "server": info.get("add",""), "port": int(info.get("port",0))}
    except:
        return None

def parse_vless(url):
    try:
        parsed = urlparse(url)
        name = unquote(parsed.fragment)
        return {"name": name, "type":"vless", "server": parsed.hostname, "port": parsed.port}
    except:
        return None

def parse_trojan(url):
    try:
        parsed = urlparse(url)
        name = unquote(parsed.fragment)
        return {"name": name, "type":"trojan", "server": parsed.hostname, "port": parsed.port}
    except:
        return None

def parse_node(url):
    url = url.strip()
    if url.startswith("vmess://"):
        return parse_vmess(url)
    elif url.startswith("vless://"):
        return parse_vless(url)
    elif url.startswith("trojan://"):
        return parse_trojan(url)
    elif url.startswith(("ss://","ssr://","hy2://","tuic://")):
        return parse_ss(url)
    else:
        return None

# ------------------ 文件处理 ------------------
def extract_proxies_block(filepath):
    with open(filepath,'r',encoding='utf-8',errors='ignore') as f:
        lines = f.readlines()
    proxies_lines=[]
    in_proxies=False
    proxies_indent=None
    for line in lines:
        if not in_proxies:
            if re.match(r'^\s*proxies\s*:\s*$', line):
                in_proxies=True
                proxies_indent = len(line)-len(line.lstrip())
                proxies_lines.append(line)
        else:
            indent = len(line)-len(line.lstrip())
            if indent <= proxies_indent and line.strip() != '':
                break
            proxies_lines.append(line)
    return ''.join(proxies_lines) if proxies_lines else None

def process_yaml_file(filepath, output_filename, used_emojis, available_emojis):
    proxies_text = extract_proxies_block(filepath)
    if not proxies_text:
        print(f"⚠️ 未找到 proxies 块: {filepath}")
        return
    data = yaml.safe_load(proxies_text)
    proxies = data.get('proxies',[])
    valid_nodes = [p for p in proxies if p.get('type') not in ['direct','reject']]
    if not valid_nodes:
        print(f"⚠️ Clash 文件 {filepath} 内无有效节点，跳过")
        return
    node_count = len(valid_nodes)
    types = set(p.get('type','unknown') for p in valid_nodes)
    node_type = types.pop() if len(types)==1 else 'Mix'
    emoji_prefix = generate_unique_emoji(used_emojis, available_emojis)
    region_groups = {}
    for p in valid_nodes:
        p['name'] = clean_name(p['name'])
        flag, region = extract_region(p['name'])
        key=(flag,region)
        region_groups.setdefault(key,[]).append(p)
    for (flag,region),group in region_groups.items():
        num_len = 2 if node_count <=100 else 3
        for idx,p in enumerate(group,1):
            seq = str(idx).zfill(num_len)
            p['name'] = f"{emoji_prefix}{node_count}{node_type}{flag}{region}_{seq}"
    out = {'proxies': valid_nodes}
    with open(output_filename,'w',encoding='utf-8') as f:
        yaml.dump(out,f,allow_unicode=True,sort_keys=False,default_flow_style=False)
    print(f"✅ 生成 YAML 文件: {output_filename}, 节点数: {node_count}, 类型: {node_type}")

def process_url_file(filepath, output_filename, used_emojis, available_emojis):
    with open(filepath,'r',encoding='utf-8',errors='ignore') as f:
        lines=[line.strip() for line in f if line.strip()]
    nodes=[]
    for line in lines:
        node = parse_node(line)
        if node:
            nodes.append(node)
    if not nodes:
        print(f"⚠️ 文件 {filepath} 无有效节点，跳过")
        return
    node_count = len(nodes)
    emoji_prefix = generate_unique_emoji(used_emojis, available_emojis)
    for idx,n in enumerate(nodes):
        n['name'] = clean_name(n['name'])
        flag, region = extract_region(n['name'])
        seq = str(idx+1).zfill(3 if node_count>100 else 2)
        n['name'] = f"{emoji_prefix}{node_count}Mix{flag}{region}_{seq}"
    # 输出 Base64，保留原始 URL 内容
    base64_content = base64.b64encode("\n".join(lines).encode()).decode()
    with open(output_filename,'w',encoding='utf-8') as f:
        f.write(base64_content)
    print(f"✅ 生成 URL Base64 文件: {output_filename}, 节点数: {node_count}")

def process_file(filepath, output_filename, used_emojis, available_emojis):
    with open(filepath,'r',encoding='utf-8',errors='ignore') as f:
        lines=[line.strip() for line in f if line.strip()]
    if not lines:
        print(f"⚠️ 空文件，跳过: {filepath}")
        return
    if any(re.match(r'^(ss|ssr|vmess|vless|trojan|hy2|tuic)://', line) for line in lines):
        process_url_file(filepath, output_filename, used_emojis, available_emojis)
    elif any(line.startswith('proxies:') for line in lines):
        process_yaml_file(filepath, output_filename, used_emojis, available_emojis)
    else:
        print(f"⚠️ 忽略非节点文件: {filepath}")

# ------------------ 主程序 ------------------
def main():
    upstream_dir = 'upstream_repo'
    files = sorted([f for f in os.listdir(upstream_dir) if os.path.isfile(os.path.join(upstream_dir,f))])
    available_emojis = load_available_emojis()
    used_emojis = set()
    file_idx = 1
    for file in files:
        filepath = os.path.join(upstream_dir,file)
        output_filename = f"suiyuan8_{file_idx:03}.yaml"
        process_file(filepath, output_filename, used_emojis, available_emojis)
        file_idx += 1

if __name__ == '__main__':
    main()
