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
    # 替换特定字符并清理
    name = name.replace('🇨🇳TW', '🇹🇼TW')
    name = re.sub(r'[_\s]*@wangcai_8[_\s]*', ' ', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def extract_region(name: str):
    # 尝试匹配两字符 flag emoji + 地区
    match = re.match(r'^([\U0001F1E6-\U0001F1FF]{2})([A-Z]{2,})', name)
    if match:
        return match.group(1), match.group(2)
    # 尝试匹配任意 emoji + 地区
    for e in emoji.EMOJI_DATA.keys():
        if name.startswith(e):
            remain = name[len(e):]
            match_region = re.match(r'^([A-Z]{2,})', remain)
            if match_region:
                return e, match_region.group(1)
    # 默认
    return '🏳️', 'ZZ'

def is_flag_emoji(e):
    return re.match(r'^[🇦-🇿]{2}$', e)

def load_available_emojis():
    return [e for e in emoji.EMOJI_DATA.keys() if not is_flag_emoji(e)]

def generate_unique_emoji(used_emojis, available_emojis):
    choice = random.choice([e for e in available_emojis if e not in used_emojis])
    used_emojis.add(choice)
    return choice

def check_ip_sequence(proxies):
    ips = []
    for p in proxies:
        ip = p.get('server')
        try:
            ip_obj = ipaddress.ip_address(ip)
            ips.append(int(ip_obj))
        except:
            return False
    ips.sort()
    if len(ips) == 256 and ips[-1] - ips[0] == 255:
        return True
    return False

# ------------------ URL 节点解析 ------------------
def parse_vmess(url):
    try:
        data_b64 = url[8:]
        decoded = base64.b64decode(data_b64 + "=" * (-len(data_b64) % 4)).decode()
        info = yaml.safe_load(decoded)
        return {
            "name": info.get("ps", ""),
            "type": "vmess",
            "server": info.get("add", ""),
            "port": int(info.get("port", 0)),
            "uuid": info.get("id", ""),
            "alterId": info.get("aid", 0),
            "cipher": info.get("scy", "auto"),
            "tls": info.get("tls", False)
        }
    except Exception as e:
        print(f"⚠️ VMess 解析失败: {url} -> {e}")
        return None

def parse_vless(url):
    try:
        parsed = urlparse(url)
        name = unquote(parsed.fragment)
        return {
            "name": name,
            "type": "vless",
            "server": parsed.hostname,
            "port": parsed.port,
            "uuid": parsed.username,
            "encryption": parse_qs(parsed.query).get("encryption", ["none"])[0],
            "tls": "tls" in parsed.scheme.lower() or "tls" in parsed.query
        }
    except Exception as e:
        print(f"⚠️ VLESS 解析失败: {url} -> {e}")
        return None

def parse_trojan(url):
    try:
        parsed = urlparse(url)
        name = unquote(parsed.fragment)
        return {
            "name": name,
            "type": "trojan",
            "server": parsed.hostname,
            "port": parsed.port,
            "password": parsed.username,
            "sni": parse_qs(parsed.query).get("sni", [""])[0],
            "udp": True
        }
    except Exception as e:
        print(f"⚠️ Trojan 解析失败: {url} -> {e}")
        return None

def parse_ss(url):
    # 只处理常规 ss://method:pass@host:port#name
    try:
        if url.startswith("ss://"):
            ss_body = url[5:]
            if "#" in ss_body:
                ss_body, name = ss_body.split("#", 1)
                name = unquote(name)
            else:
                name = ""
            if "@" in ss_body:
                method_pass, host_port = ss_body.split("@")
                method, password = method_pass.split(":")
                host, port = host_port.split(":")
                return {
                    "name": name,
                    "type": "ss",
                    "server": host,
                    "port": int(port),
                    "cipher": method,
                    "password": password
                }
        return None
    except Exception as e:
        print(f"⚠️ SS 解析失败: {url} -> {e}")
        return None

def parse_hy2(url):
    try:
        parsed = urlparse(url)
        password = parsed.username
        host = parsed.hostname
        port = parsed.port
        params = parse_qs(parsed.query)
        name = unquote(parsed.fragment)
        return {
            "name": name,
            "type": "hysteria2",
            "server": host,
            "port": port,
            "password": password,
            "sni": params.get("sni", [""])[0],
            "alpn": [params.get("alpn", ["h3"])[0]],
            "obfs": params.get("obfs", [""])[0],
            "obfs-password": params.get("obfs-password", [""])[0],
            "udp": True
        }
    except Exception as e:
        print(f"⚠️ Hysteria2 解析失败: {url} -> {e}")
        return None

def parse_tuic(url):
    try:
        parsed = urlparse(url)
        uuid, password = parsed.username.split(":") if parsed.username else ("", "")
        host = parsed.hostname
        port = parsed.port
        params = parse_qs(parsed.query)
        name = unquote(parsed.fragment)
        return {
            "name": name,
            "type": "tuic",
            "server": host,
            "port": port,
            "uuid": uuid,
            "password": password,
            "sni": params.get("sni", [""])[0],
            "alpn": [params.get("alpn", ["h3"])[0]],
            "congestion_control": params.get("congestion_control", ["bbr"])[0],
            "udp_relay_mode": "nat",
            "fast_open": True
        }
    except Exception as e:
        print(f"⚠️ TUIC 解析失败: {url} -> {e}")
        return None

def parse_node(url):
    url = url.strip()
    if url.startswith("vmess://"):
        return parse_vmess(url)
    elif url.startswith("vless://"):
        return parse_vless(url)
    elif url.startswith("trojan://"):
        return parse_trojan(url)
    elif url.startswith("ss://") or url.startswith("ssr://"):
        return parse_ss(url)
    elif url.startswith("hy2://"):
        return parse_hy2(url)
    elif url.startswith("tuic://"):
        return parse_tuic(url)
    else:
        return None

# ------------------ 文件处理 ------------------
def extract_proxies_block(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    proxies_lines = []
    in_proxies = False
    proxies_indent = None
    for line in lines:
        if not in_proxies:
            if re.match(r'^\s*proxies\s*:\s*$', line):
                in_proxies = True
                proxies_indent = len(line) - len(line.lstrip())
                proxies_lines.append(line)
        else:
            indent = len(line) - len(line.lstrip())
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
    proxies = data.get('proxies', [])
    if not proxies:
        print(f"⚠️ proxies 节点为空: {filepath}")
        return
    node_count = len(proxies)
    types = set(p.get('type', 'unknown') for p in proxies)
    node_type = types.pop() if len(types) == 1 else 'Mix'
    emoji_prefix = generate_unique_emoji(used_emojis, available_emojis)
    ip_regular = check_ip_sequence(proxies)
    # 分地区分组
    region_groups = {}
    for p in proxies:
        p['name'] = clean_name(p['name'])
        flag, region = extract_region(p['name'])
        key = (flag, region)
        region_groups.setdefault(key, []).append(p)
    for (flag, region), group in region_groups.items():
        group_size = len(group)
        num_len = 2 if node_count <= 100 else 3
        if ip_regular and group_size == 256:
            def ip_last_octet(proxy):
                try:
                    ip = ipaddress.ip_address(proxy.get('server'))
                    return int(str(ip).split('.')[-1])
                except:
                    return 999
            group_sorted = sorted(group, key=ip_last_octet)
            start_num = 0
        else:
            group_sorted = group
            start_num = 1
        for idx, p in enumerate(group_sorted):
            seq = str(start_num + idx).zfill(num_len)
            new_name = f"{emoji_prefix}{node_count}{node_type}{flag}{region}_{seq}"
            p['name'] = new_name
    out = {'proxies': proxies}
    with open(output_filename, 'w', encoding='utf-8') as f:
        yaml.dump(out, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    print(f"✅ 生成 YAML 文件: {output_filename}, 节点数: {node_count}, 类型: {node_type}")

def process_url_file(filepath, output_filename, used_emojis, available_emojis):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = [line.strip() for line in f if line.strip()]
    nodes = []
    for line in lines:
        node = parse_node(line)
        if node:
            nodes.append(node)
    if not nodes:
        print(f"⚠️ 文件 {filepath} 无有效节点，跳过")
        return
    node_count = len(nodes)
    emoji_prefix = generate_unique_emoji(used_emojis, available_emojis)
    for n in nodes:
        n['name'] = clean_name(n['name'])
        flag, region = extract_region(n['name'])
        n['name'] = f"{emoji_prefix}{node_count}Mix{flag}{region}_001"  # 序号简单处理
    # 转 Base64 输出
    urls = lines
    base64_content = base64.b64encode("\n".join(urls).encode()).decode()
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(base64_content)
    print(f"✅ 生成 URL Base64 文件: {output_filename}, 节点数: {node_count}")

def process_file(filepath, output_filename, used_emojis, available_emojis):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read().strip()
    if not content:
        print(f"⚠️ 空文件，跳过: {filepath}")
        return
    if any(k in content for k in ["proxies:", "type:", "server:"]):
        process_yaml_file(filepath, output_filename, used_emojis, available_emojis)
    elif re.search(r'^(vmess|vless|trojan|ss|ssr|hy2|tuic)://', content, re.M):
        process_url_file(filepath, output_filename, used_emojis, available_emojis)
    else:
        print(f"⚠️ 忽略非节点文件: {filepath}")

# ------------------ 主程序 ------------------
def main():
    upstream_dir = 'upstream_repo'
    files = sorted([f for f in os.listdir(upstream_dir) if os.path.isfile(os.path.join(upstream_dir, f))])
    available_emojis = load_available_emojis()
    used_emojis = set()
    file_idx = 1
    for file in files:
        filepath = os.path.join(upstream_dir, file)
        output_filename = f"suiyuan8_{file_idx:03}.yaml"
        process_file(filepath, output_filename, used_emojis, available_emojis)
        file_idx += 1

if __name__ == '__main__':
    main()
