import os
import re
import yaml
import random
import base64
import emoji
from urllib.parse import unquote, urlparse
import ipaddress

# =============================
# 配置
# =============================
UPSTREAM_DIR = "upstream_repo"
OUTPUT_PREFIX = "suiyuan8_"

# =============================
# 工具函数
# =============================

def clean_name(name: str) -> str:
    # 替换 🇨🇳TW 为 🇹🇼TW
    name = name.replace('🇨🇳TW', '🇹🇼TW')
    # 去掉 @wangcai_8
    name = re.sub(r'[_\s]*@wangcai_8[_\s]*', ' ', name, flags=re.IGNORECASE)
    # 合并空格
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def extract_region(name: str):
    # 匹配 flag emoji + region
    match = re.match(r'^([\U0001F1E6-\U0001F1FF]{2})([A-Z]{2,})', name)
    if match:
        return match.group(1), match.group(2)
    # 尝试从 fragment 中匹配其他 emoji
    for e in emoji.EMOJI_DATA.keys():
        if name.startswith(e):
            remain = name[len(e):]
            m = re.match(r'^([A-Z]{2,})', remain)
            if m:
                return e, m.group(1)
    # 无法匹配返回默认
    return '🏳️', 'ZZ'

def load_available_emojis():
    all_emojis = emoji.EMOJI_DATA.keys()
    return [e for e in all_emojis if not re.match(r'^[🇦-🇿]{2}$', e)]

def generate_unique_emoji(used, available):
    choices = [e for e in available if e not in used]
    choice = random.choice(choices)
    used.add(choice)
    return choice

def decode_base64(data: str):
    data = data.strip()
    missing_padding = len(data) % 4
    if missing_padding:
        data += "=" * (4 - missing_padding)
    try:
        return base64.b64decode(data).decode('utf-8', errors='ignore')
    except:
        return data

def is_url_node_line(line: str) -> bool:
    return bool(re.match(r'^(ss|vmess|vless|trojan)://', line.strip(), re.I))

def parse_url_node(line: str):
    proto = line.split('://', 1)[0].lower()
    parsed = urlparse(line)
    name = unquote(parsed.fragment or "")
    name = clean_name(name)
    flag, region = extract_region(name)
    return {
        "raw": line.strip(),
        "type": proto.upper(),
        "name": name,
        "flag": flag,
        "region": region
    }

def parse_clash_yaml(filepath: str):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict) and "proxies" in data and isinstance(data["proxies"], list):
            return data["proxies"]
        return []
    except:
        return []

# =============================
# 核心逻辑
# =============================

def process_upstream_files():
    os.makedirs(UPSTREAM_DIR, exist_ok=True)
    files = sorted(os.listdir(UPSTREAM_DIR))
    used_emojis = set()
    available_emojis = load_available_emojis()
    output_index = 1

    for file in files:
        path = os.path.join(UPSTREAM_DIR, file)
        if not os.path.isfile(path):
            continue

        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read().strip()

        # 尝试 Base64 解码
        if re.match(r'^[A-Za-z0-9+/=\n\r]+$', content) and not content.startswith("proxies:"):
            decoded = decode_base64(content)
            if any(is_url_node_line(line) for line in decoded.splitlines()):
                content = decoded

        # URL 节点文件处理
        if any(is_url_node_line(line) for line in content.splitlines()):
            nodes = [parse_url_node(line) for line in content.splitlines() if is_url_node_line(line)]
            if not nodes:
                continue
            total = len(nodes)
            emoji_prefix = generate_unique_emoji(used_emojis, available_emojis)
            new_lines = []
            for idx, n in enumerate(nodes, start=1):
                seq = str(idx).zfill(3 if total > 100 else 2)
                new_name = f"{emoji_prefix}{total}{n['type']}{n['flag']}{n['region']}_{seq}"
                n['name'] = new_name
                new_lines.append(n["raw"].split('#')[0] + "#" + new_name)
            merged = "\n".join(new_lines)
            encoded = base64.b64encode(merged.encode()).decode()
            output_file = f"{OUTPUT_PREFIX}{str(output_index).zfill(3)}.yaml"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(encoded)
            output_index += 1
            continue

        # Clash YAML 节点文件处理
        proxies = parse_clash_yaml(path)
        if not proxies:
            continue
        total = len(proxies)
        types = set(p.get('type', 'unknown') for p in proxies)
        node_type = types.pop() if len(types) == 1 else 'Mix'
        emoji_prefix = generate_unique_emoji(used_emojis, available_emojis)
        for idx, p in enumerate(proxies, start=1):
            seq = str(idx).zfill(3 if total > 100 else 2)
            flag, region = extract_region(clean_name(p.get('name', '')))
            p['name'] = f"{emoji_prefix}{total}{node_type}{flag}{region}_{seq}"
        output_file = f"{OUTPUT_PREFIX}{str(output_index).zfill(3)}.yaml"
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"proxies": proxies}, f, allow_unicode=True, sort_keys=False)
        output_index += 1

    print("✅ 所有文件处理完成，节点命名及文件名严格遵循原脚本规则，忽略无节点文件。")

# =============================
# 主程序
# =============================
if __name__ == "__main__":
    process_upstream_files()
