import os
import re
import base64
import yaml
from urllib.parse import unquote, urlparse

# =============================
# 基础配置
# =============================

UPSTREAM_DIR = "upstream_repo"
OUTPUT_PREFIX = "suiyuan8_"
EMOJI_PREFIX = "👩🏾‍❤‍👩🏼"

# =============================
# 节点协议检测正则
# =============================

NODE_URL_PATTERN = re.compile(
    r'^(?:(vmess|vless|trojan|ss)://[A-Za-z0-9=_\-~%!:/?#@.,&+]+)', re.IGNORECASE
)

# =============================
# 工具函数
# =============================

def is_url_node_line(line: str) -> bool:
    """判断是否是 URL 节点"""
    return bool(NODE_URL_PATTERN.match(line.strip()))

def decode_base64(data: str) -> str:
    """解码 Base64"""
    data = data.strip()
    # padding 处理
    missing_padding = len(data) % 4
    if missing_padding:
        data += "=" * (4 - missing_padding)
    try:
        return base64.b64decode(data).decode("utf-8", errors="ignore")
    except Exception:
        return data

def clean_name(name: str) -> str:
    """清理名称中无关符号"""
    name = unquote(name)
    name = re.sub(r'[@#%]', '', name)
    return name.strip()

def extract_region(name: str):
    """提取地区 flag + region 代码"""
    # 先尝试 flag
    flag_match = re.findall(r'[\U0001F1E6-\U0001F1FF]{2}', name)
    flag = flag_match[0] if flag_match else "🏳️"

    # 提取简写（SG, JP, US 等）
    region_match = re.search(r'(SG|JP|HK|TW|KR|US|UK|DE|FR|VN|TH|MY|IN|AU|CA|BR|RU|CN)', name, re.I)
    region = region_match.group(1).upper() if region_match else "ZZ"

    return flag, region

def parse_url_node(line: str):
    """解析 URL 节点并返回结构化信息"""
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
    """尝试解析 Clash YAML 配置"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict) and "proxies" in data and isinstance(data["proxies"], list):
            return data["proxies"]
        return []
    except Exception:
        return []

# =============================
# 核心处理逻辑
# =============================

def process_upstream_files():
    os.makedirs(UPSTREAM_DIR, exist_ok=True)
    files = os.listdir(UPSTREAM_DIR)
    node_files = []

    for file in files:
        path = os.path.join(UPSTREAM_DIR, file)
        if not os.path.isfile(path):
            continue

        # 读取文件内容
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().strip()

        # 1️⃣ Base64 内容尝试解码
        if re.match(r'^[A-Za-z0-9+/=\n\r]+$', content) and not content.startswith("proxies:"):
            decoded = decode_base64(content)
            if is_url_node_line(decoded.splitlines()[0]):
                content = decoded

        # 2️⃣ 判断是否为 URL 节点
        if any(is_url_node_line(line) for line in content.splitlines()):
            node_files.append((file, content, "url"))
            continue

        # 3️⃣ 判断是否为 Clash 节点配置
        proxies = parse_clash_yaml(path)
        if proxies:
            node_files.append((file, proxies, "clash"))

    # 4️⃣ 处理每个节点文件
    for file, data, ftype in node_files:
        base_name = os.path.splitext(os.path.basename(file))[0]
        output_file = f"{OUTPUT_PREFIX}{base_name}.yaml"

        if ftype == "url":
            # 处理 URL 节点
            nodes = []
            for line in data.splitlines():
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

            # 输出为 Base64
            merged = "\n".join(new_nodes)
            encoded = base64.b64encode(merged.encode()).decode()
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(encoded)

        elif ftype == "clash":
            # 处理 Clash 节点文件
            proxies = data
            if not proxies:
                continue

            total = len(proxies)
            for idx, p in enumerate(proxies, start=1):
                flag, region = extract_region(p.get("name", ""))
                seq = str(idx).zfill(3 if total > 100 else 2)
                node_type = p.get("type", "Mix").upper()
                p["name"] = f"{EMOJI_PREFIX}{total}{node_type}{flag}{region}_{seq}"

            with open(output_file, "w", encoding="utf-8") as f:
                yaml.safe_dump({"proxies": proxies}, f, allow_unicode=True, sort_keys=False)

    print("✅ 节点文件全部处理完成！")


if __name__ == "__main__":
    process_upstream_files()
