#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import yaml
import random
import base64
import emoji
import ipaddress
from urllib.parse import urlparse, parse_qs, unquote, quote

UPSTREAM_DIR = "upstream_repo"
OUTPUT_PREFIX = "suiyuan8_"

# ------- utils -------
def clean_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    # 替换 🇨🇳TW 为 🇹🇼TW
    name = name.replace('🇨🇳TW', '🇹🇼TW')
    # 去掉 @wangcai_8（大小写不敏感），多余下划线和空格规整
    name = re.sub(r'[_\s]*@wangcai_8[_\s]*', ' ', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def extract_region(name: str):
    """从解码后的名称里提取 flag 与 region（两个大写字母或常见缩写）。"""
    if not name:
        return '🏳️', 'ZZ'
    # 直接寻找国旗 emoji（两个unicode区域符号）
    flag_match = re.match(r'^([\U0001F1E6-\U0001F1FF]{2})', name)
    flag = flag_match.group(1) if flag_match else None

    # 寻找常见两个字母区域代码（优先使用紧跟在flag后的）
    region_match = None
    if flag:
        remain = name[len(flag):]
        region_match = re.match(r'^([A-Z]{2,})', remain, flags=re.I)
    if not region_match:
        region_match = re.search(r'(SG|JP|HK|TW|KR|US|UK|DE|FR|VN|TH|MY|IN|AU|CA|BR|RU|CN|VN)', name, flags=re.I)

    region = region_match.group(1).upper() if region_match else 'ZZ'
    if not flag:
        # 再尝试从 name 中任意位置匹配 flag（少见）
        flags = re.findall(r'[\U0001F1E6-\U0001F1FF]{2}', name)
        flag = flags[0] if flags else '🏳️'
    return flag, region

def load_available_emojis():
    """返回 emoji 列表，排除国旗 emoji（两个区域符号）"""
    all_emojis = list(emoji.EMOJI_DATA.keys())
    filtered = [e for e in all_emojis if not re.match(r'^[\U0001F1E6-\U0001F1FF]{2}$', e)]
    # 保证不为空
    return filtered if filtered else ["★"]

def generate_unique_emoji(used_set, available):
    choices = [e for e in available if e not in used_set]
    if not choices:
        # 重置（极少见）
        used_set.clear()
        choices = available[:]
    choice = random.choice(choices)
    used_set.add(choice)
    return choice

def decode_base64_if_plain_text(s: str) -> str:
    """
    如果文件看起来像 base64（只含 base64 字符），尝试解码并返回解码后的文本；
    否则返回原文本。
    """
    txt = s.strip()
    # 允许换行的 base64 block 判断
    if re.fullmatch(r'[A-Za-z0-9+/=\s\r\n]+', txt) and len(txt) > 0:
        try:
            # remove whitespace/newlines before decoding
            compact = re.sub(r'\s+', '', txt)
            missing = len(compact) % 4
            if missing:
                compact += "=" * (4 - missing)
            decoded = base64.b64decode(compact).decode('utf-8', errors='ignore')
            # 如果解码后包含 URL 行则使用
            if any(re.match(r'^(ss|vmess|vless|trojan)://', l.strip(), flags=re.I) for l in decoded.splitlines()):
                return decoded
        except Exception:
            return s
    return s

def is_url_line(line: str) -> bool:
    return bool(re.match(r'^\s*(ss|vmess|vless|trojan)://', line.strip(), flags=re.I))

def parse_url_line(line: str):
    """解析一条 URL，返回 dict 包含 raw, proto, remark(original, decoded)"""
    raw = line.strip()
    proto = raw.split("://", 1)[0].lower()
    # parse fragment if any
    parsed = urlparse(raw)
    frag = parsed.fragment or ""
    frag_decoded = unquote(frag)
    frag_clean = clean_name(frag_decoded)
    # extract flag/region from decoded remark
    flag, region = extract_region(frag_clean)
    return {
        "raw": raw,
        "proto": proto.upper(),
        "fragment_orig": frag,
        "fragment_decoded": frag_decoded,
        "fragment_clean": frag_clean,
        "flag": flag,
        "region": region
    }

def parse_clash_proxies(filepath: str):
    """
    尝试完整解析文件中的 proxies 块（返回 proxies 列表，或者空列表）
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        data = yaml.safe_load(content)
        if isinstance(data, dict) and 'proxies' in data and isinstance(data['proxies'], list):
            return data['proxies']
        return []
    except Exception:
        return []

def check_real_nodes(proxies):
    """过滤掉 direct/dns/reject 等不是代理的节点"""
    real = [p for p in proxies if p.get('type') not in ('direct', 'dns', 'reject')]
    return real

# ------- main processing -------

def process_file(filepath, out_filename, used_emojis, available_emojis):
    print(f"\n🔍 Processing file: {filepath}")
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        raw = f.read()

    # if file looks like base64, try decode
    text = decode_base64_if_plain_text(raw)

    # 1) URL file detection (line-by-line)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    url_lines = [ln for ln in lines if is_url_line(ln)]

    if url_lines:
        print(f"ℹ️ Detected URL node file: {len(url_lines)} nodes")
        nodes = [parse_url_line(ln) for ln in url_lines]
        total = len(nodes)
        emoji_prefix = generate_unique_emoji(used_emojis, available_emojis)
        print(f"✨ emoji prefix: {emoji_prefix}")

        renamed_lines = []
        for idx, n in enumerate(nodes, start=1):
            seq = str(idx).zfill(3 if total > 100 else 2)
            node_type = n['proto']  # SS / VMESS / VLESS / TROJAN
            flag = n['flag'] or '🏳️'
            region = n['region'] or 'ZZ'
            new_name = f"{emoji_prefix}{total}{node_type}{flag}{region}_{seq}"
            # need to replace fragment with the URL-encoded new_name
            base = n['raw'].split('#', 1)[0]
            frag_enc = quote(new_name, safe='')  # percent-encode fragment
            new_url = f"{base}#{frag_enc}"
            renamed_lines.append(new_url)
            print(f"  → Renamed: {n['fragment_decoded']!r} -> {new_name}")

        # join and base64 encode whole subscription (airport format)
        joined = "\n".join(renamed_lines).strip() + "\n"
        encoded = base64.b64encode(joined.encode('utf-8')).decode('utf-8')

        with open(out_filename, 'w', encoding='utf-8') as outf:
            outf.write(encoded + "\n")  # write base64 text to file
        print(f"✅ Wrote Base64 subscription to {out_filename} ({total} nodes)")
        return True

    # 2) Not URL file -> try parse as clash yaml proxies block
    proxies = parse_clash_proxies(filepath)
    if not proxies:
        print("⚠️ No 'proxies:' block or empty - skip")
        return False

    real_nodes = check_real_nodes(proxies)
    if not real_nodes:
        print("⚠️ Clash file contains no real proxy nodes (only direct/dns/reject). Skipping.")
        return False

    # determine node_type: same type -> that type, else Mix
    types = set(p.get('type', 'unknown') for p in real_nodes)
    node_type = types.pop() if len(types) == 1 else 'Mix'
    total = len(real_nodes)
    emoji_prefix = generate_unique_emoji(used_emojis, available_emojis)
    print(f"✨ emoji prefix: {emoji_prefix}, node_type: {node_type}, total: {total}")

    # detect IP sequence regularity (if all servers are IPs)
    ip_regular = True
    ip_list = []
    for p in real_nodes:
        s = p.get('server')
        try:
            ip_obj = ipaddress.ip_address(s)
            ip_list.append(int(ip_obj))
        except Exception:
            ip_regular = False
            break
    if ip_regular and len(ip_list) == 256 and max(ip_list) - min(ip_list) == 255:
        ip_regular = True
    else:
        ip_regular = False

    # group by region
    groups = {}
    for p in real_nodes:
        name0 = clean_name(p.get('name', ''))
        flag, region = extract_region(name0)
        key = (flag, region)
        groups.setdefault(key, []).append(p)

    # produce names
    for (flag, region), group in groups.items():
        # order group: if ip_regular and group has 256 nodes, sort by last octet
        if ip_regular and len(group) == 256:
            def last_octet(pp):
                try:
                    ip = ipaddress.ip_address(pp.get('server'))
                    return int(str(ip).split('.')[-1])
                except:
                    return 999
            group_sorted = sorted(group, key=last_octet)
            start = 0
        else:
            group_sorted = group
            start = 1
        num_len = 2 if total <= 100 else 3
        for i, p in enumerate(group_sorted):
            seq = str(start + i).zfill(num_len)
            p['name'] = f"{emoji_prefix}{total}{node_type}{flag}{region}_{seq}"

    out = {'proxies': real_nodes}
    with open(out_filename, 'w', encoding='utf-8') as outf:
        yaml.safe_dump(out, outf, allow_unicode=True, sort_keys=False, default_flow_style=False)
    print(f"✅ Wrote Clash proxies to {out_filename} ({total} nodes, type={node_type})")
    return True

def main():
    used_emojis = set()
    available_emojis = load_available_emojis()

    os.makedirs(UPSTREAM_DIR, exist_ok=True)
    files = sorted([f for f in os.listdir(UPSTREAM_DIR) if os.path.isfile(os.path.join(UPSTREAM_DIR, f))])

    out_index = 1
    any_written = False
    for fname in files:
        path = os.path.join(UPSTREAM_DIR, fname)
        out_name = f"{OUTPUT_PREFIX}{str(out_index).zfill(3)}.yaml"
        ok = process_file(path, out_name, used_emojis, available_emojis)
        if ok:
            out_index += 1
            any_written = True

    if not any_written:
        print("ℹ️ No output files were generated (no valid URL files or valid Clash proxies found).")

if __name__ == "__main__":
    main()
