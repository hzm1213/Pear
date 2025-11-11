import os
import re
import yaml
import base64
import json
import random
import emoji
import ipaddress
from urllib.parse import unquote, urlparse, parse_qs

# -------------------------------
# 🔧 清洗节点名
# -------------------------------
def clean_name(name: str) -> str:
    name = name.replace('🇨🇳TW', '🇹🇼TW')
    name = re.sub(r'[_\s]*@wangcai_8[_\s]*', ' ', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

# -------------------------------
# 🧩 Base64 自动解码
# -------------------------------
def try_base64_decode(content: str) -> str:
    try:
        if not re.match(r'^[A-Za-z0-9+/=\r\n]+$', content.strip()):
            return content
        decoded = base64.b64decode(content.strip()).decode('utf-8', errors='ignore')
        if any(proto in decoded for proto in ['ss://', 'vmess://', 'trojan://', 'vless://']):
            print("✅ 自动识别并解码 Base64 文件")
            return decoded
        return content
    except Exception:
        return content

# -------------------------------
# 🔍 URL 类型节点判断
# -------------------------------
def is_url_node_file(content: str) -> bool:
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    if not lines:
        return False
    return all(l.startswith(('ss://','vmess://','vless://','trojan://')) for l in lines)

# -------------------------------
# 📦 提取 Clash proxies 块
# -------------------------------
def extract_proxies_block(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"⚠️ 无法读取文件: {filepath} ({e})")
        return None

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

# -------------------------------
# 🧭 提取旗帜与地区
# -------------------------------
def extract_region(name):
    match = re.match(r'^([\U0001F1E6-\U0001F1FF]{2})([A-Z]{2,})', name)
    if match:
        return match.group(1), match.group(2)

    all_emojis = emoji.EMOJI_DATA.keys()
    for e in all_emojis:
        if name.startswith(e):
            remain = name[len(e):]
            match_region = re.match(r'^([A-Z]{2,})', remain)
            if match_region:
                return e, match_region.group(1)
    return '🏳️', 'ZZ'

# -------------------------------
# 🔢 检查 IP 是否连续
# -------------------------------
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
    return len(ips) == 256 and ips[-1] - ips[0] == 255

# -------------------------------
# 😎 Emoji 工具
# -------------------------------
def is_flag_emoji(e):
    return re.match(r'^[🇦-🇿]{2}$', e)

def load_available_emojis():
    all_emojis = emoji.EMOJI_DATA.keys()
    return [e for e in all_emojis if not is_flag_emoji(e)]

def generate_unique_emoji(used_emojis, available_emojis):
    choice = random.choice([e for e in available_emojis if e not in used_emojis])
    used_emojis.add(choice)
    return choice

# -------------------------------
# 🔍 判断 Clash 文件是否包含可用节点
# -------------------------------
def detect_node_file(content: str) -> bool:
    node_keywords = ['ss://', 'vmess://', 'trojan://', 'vless://']
    if any(k in content for k in node_keywords):
        return True
    if 'proxies:' in content:
        try:
            data = yaml.safe_load(content)
            proxies = data.get('proxies', [])
            for p in proxies:
                p_type = str(p.get('type','')).lower()
                if p_type not in ['direct','reject','blackhole']:
                    return True
        except Exception:
            return False
    return False

# -------------------------------
# ⚡ URL 类型节点文件处理（机场订阅）
# -------------------------------
def process_url_file(filepath, output_filename, used_emojis, available_emojis):
    print(f"🔹 处理 URL 类型节点文件: {filepath}")
    with open(filepath,'r',encoding='utf-8') as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]

    node_count = len(lines)
    emoji_prefix = generate_unique_emoji(used_emojis, available_emojis)
    print(f"✨ 选用 emoji: {emoji_prefix}")

    # 分地区分组
    region_groups = {}
    parsed_nodes = []
    for idx, url in enumerate(lines):
        if '#' in url:
            base, remark = url.split('#',1)
            remark = unquote(remark)
        else:
            base, remark = url, 'Unnamed'
        flag, region = extract_region(remark)
        region_groups.setdefault((flag, region), []).append((idx, base, remark))

    # 按地区 + emoji + 编号生成新 remark
    new_lines = []
    for (flag, region), group in region_groups.items():
        num_len = 2 if node_count <= 100 else 3
        for seq_idx, (orig_idx, base, remark) in enumerate(group, start=1):
            seq = str(seq_idx).zfill(num_len)
            new_remark = f"{emoji_prefix}{node_count}{flag}{region}_{seq}"
            new_url = f"{base}#{new_remark}"
            new_lines.append(new_url)

    # 输出 Base64
    content_str = '\n'.join(new_lines)
    b64_content = base64.b64encode(content_str.encode()).decode()
    with open(output_filename,'w',encoding='utf-8') as f:
        f.write(b64_content)

    print(f"✅ 生成机场订阅文件: {output_filename}, 节点数: {node_count}")

# -------------------------------
# 🔨 Clash 文件处理（保持原逻辑）
# -------------------------------
def process_clash_file(filepath, output_filename, used_emojis, available_emojis):
    print(f"🔹 处理 Clash 文件: {filepath}")

    proxies_text = extract_proxies_block(filepath)
    if not proxies_text:
        print(f"⚠️ 未找到 proxies 块: {filepath}")
        return

    data = yaml.safe_load(proxies_text)
    proxies = [p for p in data.get('proxies', []) if str(p.get('type','')).lower() not in ['direct','reject','blackhole']]
    if not proxies:
        print(f"⚠️ proxies 节点为空或全部为非代理节点: {filepath}")
        return

    node_count = len(proxies)
    types = set(p.get('type', 'unknown') for p in proxies)
    node_type = types.pop() if len(types) == 1 else 'Mix'
    emoji_prefix = generate_unique_emoji(used_emojis, available_emojis)
    ip_regular = check_ip_sequence(proxies)

    region_groups = {}
    for p in proxies:
        p['name'] = clean_name(p.get('name','Unnamed'))
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
    with open(output_filename,'w',encoding='utf-8') as f:
        yaml.dump(out,f,allow_unicode=True,sort_keys=False,default_flow_style=False)
    print(f"✅ 生成 Clash 文件: {output_filename}, 节点数: {node_count}, 类型: {node_type}")

# -------------------------------
# 🔨 主处理逻辑
# -------------------------------
def process_file(filepath, output_filename, used_emojis, available_emojis):
    with open(filepath,'r',encoding='utf-8') as f:
        raw_content = f.read()
    content = try_base64_decode(raw_content)

    if is_url_node_file(content):
        process_url_file(filepath, output_filename, used_emojis, available_emojis)
        return
    elif detect_node_file(content):
        process_clash_file(filepath, output_filename, used_emojis, available_emojis)
        return
    else:
        print(f"⚠️ 跳过非节点文件: {os.path.basename(filepath)}")

# -------------------------------
# 🚀 主函数入口
# -------------------------------
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

    print("\n🎉 所有文件处理完成！")

if __name__ == '__main__':
    main()
