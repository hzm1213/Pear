import os
import re
import yaml
import random
import emoji
import ipaddress
import base64
import urllib.parse

def clean_name(name: str) -> str:
    # 替换 🇨🇳TW 为 🇹🇼TW
    name = name.replace('🇨🇳TW', '🇹🇼TW')
    name = re.sub(r'[_\s]*@wangcai_8[_\s]*', ' ', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

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

def extract_region(name):
    # 尝试匹配两字符 flag emoji + region
    match = re.match(r'^([\U0001F1E6-\U0001F1FF]{2})([A-Z]{2,})', name)
    if match:
        return match.group(1), match.group(2)

    # 尝试匹配 URL 里编码的 emoji
    decoded_name = urllib.parse.unquote(name)
    match_url = re.match(r'^([\U0001F1E6-\U0001F1FF]{2})([A-Z]{2,})', decoded_name)
    if match_url:
        return match_url.group(1), match_url.group(2)

    # 若未匹配，返回默认
    return '🏳️', 'ZZ'

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

def is_flag_emoji(e):
    return re.match(r'^[🇦-🇿]{2}$', e)

def load_available_emojis():
    all_emojis = emoji.EMOJI_DATA.keys()
    filtered_emojis = [e for e in all_emojis if not is_flag_emoji(e)]
    return filtered_emojis

def generate_unique_emoji(used_emojis, available_emojis):
    choice = random.choice([e for e in available_emojis if e not in used_emojis])
    used_emojis.add(choice)
    return choice

def parse_url_nodes(lines):
    nodes = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith(('ss://', 'vmess://', 'vless://', 'trojan://')):
            nodes.append(line)
    return nodes

def process_file(filepath, output_filename, used_emojis, available_emojis):
    print(f"🔍 正在处理文件: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检测 URL 类型节点
    url_nodes = parse_url_nodes(content.splitlines())
    if url_nodes:
        # URL 节点文件直接处理为 Base64 输出
        processed_nodes = []
        node_count = len(url_nodes)
        emoji_prefix = generate_unique_emoji(used_emojis, available_emojis)
        print(f"✨ 选用 emoji: {emoji_prefix}")

        for idx, node_url in enumerate(url_nodes, 1):
            # 尝试提取原节点名 remark
            remark = 'Mix'
            parsed = urllib.parse.urlparse(node_url)
            if '#' in node_url:
                remark_encoded = node_url.split('#', 1)[1]
                remark_decoded = urllib.parse.unquote(remark_encoded)
                _, region = extract_region(remark_decoded)
                remark = f"{emoji_prefix}{node_count}{region}_{str(idx).zfill(3)}"
            # 拼回 URL 并写入 Base64
            processed_nodes.append(node_url.split('#')[0] + '#' + remark)

        # 写入输出文件
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(processed_nodes) + '\n')

        print(f"✅ 生成 URL 文件: {output_filename}, 节点数: {node_count}")
        return

    # 否则尝试解析 Clash 配置文件
    proxies_text = extract_proxies_block(filepath)
    if not proxies_text:
        print(f"⚠️ 未找到 proxies 块或没有节点: {filepath}, 跳过")
        return

    data = yaml.safe_load(proxies_text)
    proxies = data.get('proxies', [])

    # 过滤掉 direct/dns/reject 节点
    real_nodes = [p for p in proxies if p.get('type') not in ('direct', 'dns', 'reject')]
    if not real_nodes:
        print(f"⚠️ 文件 {filepath} 没有可用代理节点，跳过生成")
        return

    node_count = len(real_nodes)
    types = set(p.get('type', 'unknown') for p in real_nodes)
    node_type = types.pop() if len(types) == 1 else 'Mix'

    emoji_prefix = generate_unique_emoji(used_emojis, available_emojis)
    print(f"✨ 选用 emoji: {emoji_prefix}")

    ip_regular = check_ip_sequence(real_nodes)

    # 分地区分组
    region_groups = {}
    for p in real_nodes:
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
            p['name'] = f"{emoji_prefix}{node_count}{node_type}{flag}{region}_{seq}"

    out = {'proxies': real_nodes}

    with open(output_filename, 'w', encoding='utf-8') as f:
        yaml.dump(out, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    print(f"✅ 生成 Clash 文件: {output_filename}, 节点数: {node_count}, 类型: {node_type}")

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
