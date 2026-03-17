import os, subprocess, re

MATCH_DIR = os.path.expanduser("~/Desktop/减持获客系统/wechat_match_all")
OCR = "/tmp/ocr_tool"

NOISE = ["搜一搜","文章","公众号","视频号","招聘","股票代码","有没有","属于",
    "校招","有矿","对比","板块","转债","怎么样","是什么","退市","主营","目标价",
    "值得","生产","业绩","前景","最新消息","为什么","是国企","国有","营业厅",
    "缴费","机顶盒","小程序","估值","股票价格","怎么充电","激活","控制权",
    "摘帽","产品与服务","出口","重组","是做什么","是干什么","有限公司","科技有限",
    "集团股份","装备有限","电子厂","Q ","股份有限","产业园","发展有限",
    "网络","etc","国企还是","股价","投资价值","怎么连接",
    "是央企","概念股","涨停","跌停","分红","市值","融资","研报","年报",
    "半年报","季报","增发","可转债","期权","基本面","充电","激活小程序"]

files = sorted([f for f in os.listdir(MATCH_DIR) if f.endswith(".png")])
print(f"分析 {len(files)} 张截图...\n")

all_contacts = []
all_groups = []
all_chats = []
none_count = 0

for f in files:
    path = os.path.join(MATCH_DIR, f)
    parts = f.replace(".png","").split("_", 2)
    code = parts[1] if len(parts)>1 else ""
    company = parts[2] if len(parts)>2 else ""
    if not company or company=="nan":
        continue
    clean = company.replace("xST","").replace("ST","").replace("*","")

    try:
        text = subprocess.run([OCR, path], capture_output=True, text=True, timeout=15).stdout
    except:
        text = ""

    lines = text.strip().split("\n")
    contacts, groups, chats = [], [], []

    for line in lines:
        line = line.strip()
        if not line or len(line) < 4:
            continue
        if clean not in line and company not in line:
            continue
        if any(n in line for n in NOISE):
            continue
        if line.strip() in [company, clean, "Q "+company, "Q "+clean]:
            continue

        m = re.match(r'^(\d+)\s*\S*' + re.escape(clean) + r'\S*\s+(.{2,})', line)
        if m:
            contacts.append(line)
            continue
        if re.search(r'[-\-].*[基金长富].*[\(（]\d', line):
            groups.append(line)
            continue
        if any(kw in line for kw in ["：","已加微信","股东有联系","盘后协议","标签","证代"]):
            chats.append(line)
            continue

    contacts = list(dict.fromkeys(contacts))
    groups = list(dict.fromkeys(groups))
    chats = list(dict.fromkeys(chats))

    if contacts:
        all_contacts.append({"code":code,"company":company,"contacts":contacts,"groups":groups})
        print(f"  🎯 {code} {company}")
        for c in contacts[:2]:
            print(f"     👤 {c}")
        for g in groups[:1]:
            print(f"     👥 {g}")
    elif groups:
        all_groups.append({"code":code,"company":company,"groups":groups})
        print(f"  👥 {code} {company}")
        for g in groups[:2]:
            print(f"     👥 {g}")
    elif chats:
        all_chats.append({"code":code,"company":company,"chats":chats})
        print(f"  💬 {code} {company}")
        for c in chats[:1]:
            print(f"     💬 {c}")
    else:
        none_count += 1

print(f"\n{'='*55}")
print(f"  🎯 有微信联系人: {len(all_contacts)} 家")
print(f"  👥 有群聊:       {len(all_groups)} 家")
print(f"  💬 聊天提及:     {len(all_chats)} 家")
print(f"  ❌ 未找到:       {none_count} 家")
print(f"  总计: {len(files)} 家")
print(f"{'='*55}")

if all_contacts:
    print(f"\n🎯 可直接微信联系 ({len(all_contacts)}家):")
    for r in all_contacts:
        for c in r["contacts"][:2]:
            m = re.match(r'^\d+\s*\S+\s+(.+)', c)
            name = m.group(1).strip() if m else c
            print(f"  {r['code']:12s} {r['company']:10s} -> {name}")

if all_groups:
    print(f"\n👥 有群聊 ({len(all_groups)}家):")
    for r in all_groups:
        print(f"  {r['code']:12s} {r['company']:10s} -> {r['groups'][0]}")
