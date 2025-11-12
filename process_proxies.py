import os
import base64
import re
import yaml
import urllib.parse

# 🏳️ 地区标识映射
FLAG_FIX = {
    "🇨🇳TW": "🇹🇼TW",
    "🏳️ZZ": "🏴‍☠️ZZ",
}

REGION_MAP = {
    "SG": ["🇸🇬", "新加坡", "Singapore", "SG_"],
    "JP": ["🇯🇵", "日本", "Tokyo", "JP_"],
    "TW": ["🇹🇼", "台湾", "Taiwan", "TW_"],
    "HK": ["🇭🇰", "香港", "HongKong", "HK_"],
    "US": ["🇺🇸", "美国", "UnitedStates", "洛杉矶", "芝加哥", "US_"],
    "KR": ["🇰🇷", "韩国", "Korea", "KR_"],
    "ZZ": ["🏴‍☠️", "直连", "Direct"],
}

file_index = 0

def detect_region(name):
    for code, keywords in REGION_MAP.items():
        for kw in keywords:
            if kw in name:
                return code
    return "ZZ"

def rename_node(raw_name, index):
    region = detect_region(raw_name)
    flag = next((f for f, v in REGION_MAP.items() if region in v or f.endswith(region)), "🏴‍☠️")
    flag = FLAG_FIX.get(flag + region, flag + region)
    return f"🫱🏼‍🫲🏻157{region}_{index:03d}"

def generate_base64(nodes):
    return base64.b64encode("\n".join(nodes).encode("utf-8")).decode("utf-8")

def process_file(filepath):
    global file_index
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read().strip()

    if not content:
        return None

    # 🔍 URL 类型节点文件
    url_lines = [l.strip() for l in content.splitlines() if l.startswith(("ss://", "vmess://", "vless://", "trojan://"))]
    if url_lines:
        file_index += 1
        renamed = []
        for i, url in enumerate(url_lines, 1):
            decoded = urllib.parse.unquote(url.split("#")[-1]) if "#" in url else url
            new_name = rename_node(decoded, i)
            if "#" in url:
                url = url[:url.rfind("#")] + "#" + new_name
            else:
                url += "#" + new_name
            renamed.append(url)

        outname = f"suiyuan8_{file_index:03d}.yaml"
        with open(outname, "w", encoding="utf-8") as out:
            out.write(generate_base64(renamed))
        print(f"✅ URL文件 → {outname} ({len(renamed)} 个节点)")
        return outname

    # 🔍 Clash YAML 类型
    try:
        data = yaml.safe_load(content)
        if data and isinstance(data, dict) and "proxies" in data and data["proxies"]:
            file_index += 1
            outname = f"suiyuan8_{file_index:03d}.yaml"
            with open(outname, "w", encoding="utf-8") as out:
                yaml.safe_dump(data, out, allow_unicode=True, sort_keys=False)
            print(f"✅ Clash文件 → {outname}")
            return outname
    except Exception:
        pass

    return None

def main():
    upstream_dir = "upstream_repo"
    if not os.path.exists(upstream_dir):
        print("❌ 未找到上游仓库目录")
        return

    generated = []
    for root, _, files in os.walk(upstream_dir):
        for name in files:
            if name.endswith((".yaml", ".yml", ".txt", ".conf", ".list")):
                result = process_file(os.path.join(root, name))
                if result:
                    generated.append(result)

    if not generated:
        print("⚠️ No valid proxy files found. Removing old local suiyuan8_*.yaml files.")
        os.system("rm -f suiyuan8_*.yaml")
    else:
        print(f"✅ 共生成 {len(generated)} 个 suiyuan8_*.yaml 文件：{generated}")

if __name__ == "__main__":
    main()
