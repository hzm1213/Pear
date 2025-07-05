import os
import re
import yaml
import random
import emoji
import ipaddress

def clean_name(name: str) -> str:
    # 只替换 🇨🇳TW 为 🇹🇼TW
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

    # 若未匹配，尝试匹配任何 emoji + region
    all_emojis = emoji.EMOJI_DATA.keys()
    for e in all_emojis:
        if name.startswith(e):
            remain = name[len(e):]
            match_region = re.match(r'^([A-Z]{2,})', remain)
            if match_region:
                return e, match_region.group(1)

    # 无法匹配返回默认
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

def process_file(filepath, output_filename, used_emojis, available_emojis):
    print(f"🔍 正在处理文件: {filepath}")

    proxies_text = extract_proxies_block(filepath)
    if not proxies_text:
        print(f"⚠️ 未找到 proxies 块: {filepath}")
        return

    data = yaml.safe_load(proxies_text)
    proxies = data.get('proxies', [])
    node_count = len(proxies)
    if node_count == 0:
        print(f"⚠️ proxies 节点为空: {filepath}")
        return

    types = set(p.get('type', 'unknown') for p in proxies)
    node_type = types.pop() if len(types) == 1 else 'Mix'

    emoji_prefix = generate_unique_emoji(used_emojis, available_emojis)
    print(f"✨ 选用emoji: {emoji_prefix}")

    ip_regular = check_ip_sequence(proxies)

    # 分地区分组
    region_groups = {}
    for p in proxies:
        # 先 clean_name
        p['name'] = clean_name(p['name'])

        # 再 extract_region
        flag, region = extract_region(p['name'])
        key = (flag, region)
        region_groups.setdefault(key, []).append(p)

    for (flag, region), group in region_groups.items():
        group_size = len(group)

        # 补位长度判断，总节点数小于等于100用2位，否则3位
        num_len = 2 if node_count <= 100 else 3

        # IP连续且节点数为256，按IP最后一段排序，编号从000开始
        if ip_regular and group_size == 256:
            def ip_last_octet(proxy):
                try:
                    ip = ipaddress.ip_address(proxy.get('server'))
                    return int(str(ip).split('.')[-1])
                except:
                    return 999  # 非IP放后面
            group_sorted = sorted(group, key=ip_last_octet)
            start_num = 0
        else:
            # 其它情况保持文件顺序
            group_sorted = group
            start_num = 1

        for idx, p in enumerate(group_sorted):
            seq = str(start_num + idx).zfill(num_len)
            new_name = f"{emoji_prefix}{node_count}{node_type}{flag}{region}_{seq}"
            p['name'] = new_name

    out = {'proxies': proxies}

    with open(output_filename, 'w', encoding='utf-8') as f:
        yaml.dump(out, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    print(f"✅ 生成文件: {output_filename}, 节点数: {node_count}, 类型: {node_type}")

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
