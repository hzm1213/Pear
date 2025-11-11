import os
import re
import base64
import yaml
from urllib.parse import unquote, urlparse

# =============================
# 配置
# =============================
UPSTREAM_DIR = "upstream_repo"
OUTPUT_PREFIX = "suiyuan8_"
EMOJI_PREFIX = "👩🏾‍❤‍👩🏼"

NODE_URL_PATTERN = re.compile(
    r'^(ss|vmess|vless|trojan)://', re.IGNORECASE
)

# =============================
# 工具函数
# =============================

def is_url_node_line(line: str) -> bool:
    return bool(NODE_URL_PATTERN.match(line.strip()))

def decode_base64(data: str) -> str:
    data = data.strip()
    missing_padding = len(data) % 4
    if missing_padding:
        data += "=" * (4 - missing_padding)
    try:
        return base64.b64decode(data).decode("utf-8", errors="ignore")
    except:
        return data

def clean_name(name: str) -> str:
    name = unquote(name)
    name = re.sub(r'[@#%]', '', name)
    return name.strip()

def extract_region(name: str):
    flag_match = re.findall(r'[\U0001F1E6-\U0001F1FF]{2}', name)
    flag = flag_match[0] if flag_match else "🏳️"
    region_match = re.search(r'(SG|JP|HK|TW|KR|US|UK|DE|FR|VN|TH|MY|IN|AU|CA|BR|RU|CN)', name, re.I)
    region = region_match.group(1).upper() if region_match else "ZZ"
    return flag, region

def parse_url_node(line: str):
    line = line.strip()
    proto = line.split("://", 1)[0].lower()
    parsed = urlparse(line)
    name = unquote(parsed.fragment or "")
    name = clean_name(name)
    flag, region = extract_region(name)
    return {
        "raw": line,
        "type": proto.upper(),
        "name": name,
        "flag": flag,
        "region": region
    }

def parse_clash_yaml(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict) and "proxies" in data and isinstance(data["proxies"], list):
            if len(data["proxies"]) == 0:
                return []
            return data["proxies"]
        return []
    except Exception:
        return []

# =============================
# 核心逻辑
# =============================

def process_upstream_files():
    os.makedirs(UPSTREAM_DIR, exist_ok=True)
    files = sorted(os.listdir(UPSTREAM_DIR))
    output_index = 1

    for file in files:
        path = os.path.join(UPSTREAM_DIR, file)
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().strip()

        # 尝试 Base64 解码
        if re.match(r'^[A-Za-z0-9+/=\n\r]+$', content) and not content.startswith("proxies:"):
            decoded = decode_base64(content)
            if decoded and any(is_url_node_line(line) for line in decoded.splitlines()):
                content = decoded

        # 判断 URL 节点文件
        if any(is_url_node_line(line) for line in content.splitlines()):
            nodes = []
            for line in content.splitlines():
                if is_url_node_line(line):
                    n = parse_url_node(line)
                    nodes.append(n)
            if not nodes:
                continue

            total = len(nodes)
            new_nodes = []
            for idx, n in enumerate(nodes, start=1):
                seq = str(idx).zfill(3 if total > 100 else 2)
                new_name = f"{EMOJI_PREFIX}{total}{n['type']}{n['flag']}{n['region']}_{seq}"
                n['name'] = new_name
                new_nodes.append(n["raw"].split("#")[0] + "#" + n["name"])

            merged = "\n".join(new_nodes)
            encoded = base64.b64encode(merged.encode()).decode()
            output_file = f"{OUTPUT_PREFIX}{str(output_index).zfill(3)}.yaml"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(encoded)
            output_index += 1
            continue

        # 判断 Clash YAML 节点
        proxies = parse_clash_yaml(path)
        if not proxies:
            continue

        total = len(proxies)
        for idx, p in enumerate(proxies, start=1):
            flag, region = extract_region(p.get("name", ""))
            seq = str(idx).zfill(3 if total > 100 else 2)
            node_type = p.get("type", "Mix").upper()
            p["name"] = f"{EMOJI_PREFIX}{total}{node_type}{flag}{region}_{seq}"

        output_file = f"{OUTPUT_PREFIX}{str(output_index).zfill(3)}.yaml"
        with open(output_file, "w", encoding="utf-8") as f:
            yaml.safe_dump({"proxies": proxies}, f, allow_unicode=True, sort_keys=False)
        output_index += 1

    print("✅ 所有节点文件已处理完成，文件名按顺序生成，忽略无节点文件！")


if __name__ == "__main__":
    process_upstream_files()
