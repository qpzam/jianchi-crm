import os, sys, subprocess, time, re, json
import pandas as pd

BASE = os.path.expanduser("~/Desktop/减持获客系统")
SCREENSHOT_DIR = os.path.join(BASE, "wechat_phone_verify")
RESULT_FILE = os.path.join(BASE, "phone_verify_results.json")
OUTPUT_EXCEL = os.path.join(BASE, "股东电话验证结果.xlsx")
OCR = "/tmp/ocr_tool"

os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def asc(script):
    return subprocess.run(["osascript","-e",script], capture_output=True, text=True, timeout=10).stdout.strip()

def wechat_search(phone):
    subprocess.run(["pbcopy"], input=phone.encode("utf-8"))
    asc('''tell application "System Events" to tell process "WeChat"
        keystroke "f" using command down
        delay 0.3
        keystroke "a" using command down
        delay 0.1
        keystroke "v" using command down
    end tell''')
    time.sleep(2)

def screenshot(name):
    fp = os.path.join(SCREENSHOT_DIR, name)
    subprocess.run(["screencapture","-x","-o",fp], capture_output=True, timeout=5)
    return fp

def close_search():
    asc('tell application "System Events" to tell process "WeChat" to key code 53')
    time.sleep(0.3)

def ocr(path):
    try:
        return subprocess.run([OCR, path], capture_output=True, text=True, timeout=15).stdout
    except:
        return ""

def extract_wechat_info(text, phone):
    """从微信搜索截图OCR中提取联系人信息"""
    lines = text.strip().split("\n")
    result = {"name": "", "region": "", "has_wechat": False}

    for i, line in enumerate(lines):
        line = line.strip()
        # 跳过噪音
        if any(kw in line for kw in ["搜一搜","文章","公众号","视频号","网络查找",
            "QQ号","折叠","Reply","Claude"]):
            continue
        # 找到"地区"行，上面一行通常是姓名
        if "地区" in line:
            region = line.replace("地区","").strip()
            result["region"] = region
            result["has_wechat"] = True
            # 往上找名字（通常是地区上方1-3行内的短文本）
            for j in range(max(0, i-3), i):
                prev = lines[j].strip()
                if 2 <= len(prev) <= 6 and not any(kw in prev for kw in [
                    "搜索","地区","朋友圈","添加","电话","手机","QQ","网络"]):
                    result["name"] = prev
                    break
            break

        # 也匹配 "姓名 头像" 模式
        if len(line) >= 2 and len(line) <= 8 and i > 0:
            next_lines = lines[i+1:i+4] if i+1 < len(lines) else []
            for nl in next_lines:
                if "地区" in nl:
                    result["name"] = line
                    result["region"] = nl.replace("地区","").strip()
                    result["has_wechat"] = True
                    break

    return result

def main():
    print("=" * 55)
    print("  微信号码验证 - 自动搜索电话查真实身份")
    print("=" * 55)

    # 读取启信宝查询结果或股东联系方式库
    phones_to_verify = []

    # 优先读启信宝结果
    qxb_result = os.path.join(BASE, "qxb_results.json")
    if os.path.exists(qxb_result):
        with open(qxb_result, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key, info in data.items():
            for phone in (info.get("电话","") or "").split(","):
                phone = phone.strip()
                if re.match(r"^1[3-9]\d{9}$", phone):
                    phones_to_verify.append({
                        "phone": phone,
                        "stock": info.get("stock",""),
                        "code": info.get("code",""),
                        "holder": info.get("holder",""),
                        "gp": info.get("法人GP",""),
                        "source": "启信宝",
                    })
        print(f"  从启信宝结果读取: {len(phones_to_verify)} 个手机号")

    # 也读股东联系方式库
    lib_file = os.path.join(BASE, "股东联系方式库.xlsx")
    if os.path.exists(lib_file):
        df = pd.read_excel(lib_file, dtype=str)
        seen = set(p["phone"] for p in phones_to_verify)
        for _, r in df.iterrows():
            # 从董秘邮箱等字段也提取
            for col in ["联系电话", "董秘"]:
                val = str(r.get(col, ""))
                for phone in re.findall(r"1[3-9]\d{9}", val):
                    if phone not in seen:
                        seen.add(phone)
                        phones_to_verify.append({
                            "phone": phone,
                            "stock": str(r.get("股票名称","")),
                            "code": str(r.get("证券代码","")),
                            "holder": str(r.get("股东名称","")),
                            "gp": "",
                            "source": "TinyShare",
                        })
        print(f"  合并后: {len(phones_to_verify)} 个手机号")

    if not phones_to_verify:
        print("  未找到待验证电话，请先运行启信宝查询")
        return

    # 去重
    seen = set()
    unique = []
    for p in phones_to_verify:
        if p["phone"] not in seen:
            seen.add(p["phone"])
            unique.append(p)
    phones_to_verify = unique
    print(f"  去重后: {len(phones_to_verify)} 个")

    # 加载已验证的
    done = {}
    if os.path.exists(RESULT_FILE):
        with open(RESULT_FILE, "r", encoding="utf-8") as f:
            done = json.load(f)

    todo = [p for p in phones_to_verify if p["phone"] not in done]
    print(f"  已验证: {len(done)}, 待验证: {len(todo)}")

    if not todo:
        print("  全部完成！")
        generate_excel(phones_to_verify, done)
        return

    print(f"\n  确保微信已登录 + 终端有辅助功能权限")
    input("  按 Enter 开始...")

    asc('tell application "WeChat" to activate')
    time.sleep(1)

    total = len(todo)
    for i, p in enumerate(todo, 1):
        phone = p["phone"]
        print(f"[{i}/{total}] {phone} ({p['stock']} {p['holder'][:8]})", end="")

        wechat_search(phone)
        fn = f"{i:03d}_{phone}.png"
        fp = screenshot(fn)

        text = ocr(fp)
        info = extract_wechat_info(text, phone)

        if info["has_wechat"]:
            print(f" → ✅ {info['name']} ({info['region']})")
        else:
            print(f" → ❌ 未找到微信")

        done[phone] = {
            "wechat_name": info["name"],
            "region": info["region"],
            "has_wechat": info["has_wechat"],
            "stock": p["stock"],
            "code": p["code"],
            "holder": p["holder"],
            "gp": p.get("gp",""),
            "source": p["source"],
        }

        close_search()
        time.sleep(0.5)

        if i % 20 == 0:
            with open(RESULT_FILE,"w",encoding="utf-8") as f:
                json.dump(done, f, ensure_ascii=False, indent=2)
            print(f"  --- 进度已保存 ({i}/{total}) ---")

    with open(RESULT_FILE,"w",encoding="utf-8") as f:
        json.dump(done, f, ensure_ascii=False, indent=2)

    generate_excel(phones_to_verify, done)


def generate_excel(phones, done):
    rows = []
    for p in phones:
        phone = p["phone"]
        d = done.get(phone, {})
        wechat_name = d.get("wechat_name","")
        holder = p["holder"].replace("女士","").replace("先生","")
        gp = p.get("gp") or d.get("gp","")

        # 自动判断验证结果
        verify = ""
        if d.get("has_wechat"):
            # 微信名是否匹配股东名或法人名
            if wechat_name and (wechat_name in holder or holder in wechat_name
                or (gp and (wechat_name in gp or gp in wechat_name))):
                verify = "A-确认本人"
            elif wechat_name:
                verify = "B-有微信待确认"
            else:
                verify = "B-有微信无名字"
        else:
            verify = "D-无微信"

        rows.append({
            "证券代码": p["code"],
            "股票名称": p["stock"],
            "减持股东": p["holder"],
            "法人/GP": gp,
            "电话": phone,
            "微信姓名": wechat_name,
            "微信地区": d.get("region",""),
            "验证结果": verify,
            "数据来源": p["source"],
            "备注": "",
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("验证结果")
    df.to_excel(OUTPUT_EXCEL, index=False, sheet_name="电话验证")

    n = len(df)
    n_a = len(df[df["验证结果"].str.startswith("A")])
    n_b = len(df[df["验证结果"].str.startswith("B")])
    n_d = len(df[df["验证结果"].str.startswith("D")])
    n_wx = len(df[df["微信姓名"] != ""])

    print(f"\n{'='*55}")
    print(f"  总计: {n} 个电话")
    print(f"  A-确认本人: {n_a}")
    print(f"  B-有微信待确认: {n_b}")
    print(f"  D-无微信: {n_d}")
    print(f"  有微信名: {n_wx}")
    print(f"  ✓ 已保存: {OUTPUT_EXCEL}")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
