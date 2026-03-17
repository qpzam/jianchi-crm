import os, subprocess, re

MATCH_DIR = os.path.expanduser("~/Desktop/减持获客系统/wechat_match")
OCR = "/tmp/ocr_tool"

# 搜索建议噪音词（这些行不是联系人）
NOISE = ["搜一搜","文章","公众号","视频号","招聘","股票代码","有没有","属于",
    "校招","有矿","对比","板块","转债","怎么样","是什么","退市","主营","目标价",
    "值得","生产","业绩","前景","最新消息","为什么","是国企","国有","营业厅",
    "缴费","机顶盒","小程序","估值","股票价格","怎么充电","激活","控制权",
    "摘帽","产品与服务","出口","重组","是做什么","是干什么","有限公司","科技有限",
    "集团股份","装备有限","电子厂","Q ","股份有限","产业园","发展有限",
    "郑州公司","网络","etc","国企还是","股价","投资价值"]

files = sorted([f for f in os.listdir(MATCH_DIR) if f.endswith(".png")])
print(f"分析 {len(files)} 张截图...\n")

results = []
for f in files:
    path = os.path.join(MATCH_DIR, f)
    company = f.split("_", 2)[-1].replace(".png","")
    code = f.split("_")[1] if "_" in f else ""
    clean = company.replace("*ST","").replace("ST","")

    try:
        text = subprocess.run([OCR, path], capture_output=True, text=True, timeout=15).stdout
    except:
        text = ""

    lines = text.strip().split("\n")
    
    contacts = []  # 确认的微信联系人
    groups = []    # 群聊
    chats = []     # 聊天记录提及

    for line in lines:
        line = line.strip()
        if not line or len(line) < 4:
            continue
        if clean not in line and company not in line:
            continue
        # 排除噪音
        if any(n in line for n in NOISE):
            continue
        # 排除纯公司名
        if line.strip() in [company, clean, f"Q {company}", f"Q {clean}"]:
            continue

        # 模式1: 微信联系人 "数字+公司名+人名+职务" 如 "3腾远钴业 李舒平 古鑫咨询 LP"
        m = re.match(r'^(\d+)\s*' + re.escape(clean) + r'\s+(.{2,})', line)
        if m:
            contacts.append(line)
            continue

        # 模式2: 群聊 "公司名-XX基金(N)" 如 "安联锐视-长富基金（5)"
        if re.search(r'[-\-].*[基金长富].*[\(（]\d', line):
            groups.append(line)
            continue
        
        # 模式3: 标签 "标签：公司名"
        if "标签" in line:
            chats.append(line)
            continue

        # 模式4: 聊天内容提及 如 "中熔电气 证代：内部沟通过"
        if "：" in line or ":" in line or "已加微信" in line or "股东有联系" in line or "盘后协议" in line:
            chats.append(line)
            continue

    # 去重
    contacts = list(dict.fromkeys(contacts))
    groups = list(dict.fromkeys(groups))
    chats = list(dict.fromkeys(chats))

    has_wechat = len(contacts) > 0
    has_group = len(groups) > 0
    has_chat = len(chats) > 0

    if contacts:
        tag = "🎯 有联系人"
    elif groups:
        tag = "👥 有群聊"
    elif chats:
        tag = "💬 有聊天"
    else:
        tag = "❌ 未找到"

    print(f"  {tag:8s} {code} {company}")
    for c in contacts[:3]:
        print(f"           👤 {c}")
    for g in groups[:2]:
        print(f"           👥 {g}")
    for c in chats[:2]:
        print(f"           💬 {c}")

    results.append({"code":code,"company":company,
        "contacts":contacts,"groups":groups,"chats":chats,
        "has_wechat":has_wechat,"has_group":has_group,"has_chat":has_chat})

# 汇总
n_contact = sum(1 for r in results if r["has_wechat"])
n_group = sum(1 for r in results if r["has_group"] and not r["has_wechat"])
n_chat = sum(1 for r in results if r["has_chat"] and not r["has_wechat"] and not r["has_group"])
n_none = len(results) - n_contact - n_group - n_chat

print(f"\n{'='*55}")
print(f"  🎯 有微信联系人: {n_contact} 家 (可直接发消息)")
print(f"  👥 有群聊:       {n_group} 家 (可在群里找)")
print(f"  💬 聊天提及:     {n_chat} 家 (有过交集)")
print(f"  ❌ 未找到:       {n_none} 家")
print(f"{'='*55}")

print(f"\n🎯 可直接微信联系的目标:")
for r in results:
    if r["has_wechat"]:
        # 提取人名
        for c in r["contacts"]:
            m = re.match(r'^\d+\s*\S+\s+(.+)', c)
            name = m.group(1).strip() if m else c
            print(f"  {r['code']} {r['company']:8s} → {name}")

print(f"\n👥 通过群聊可联系:")
for r in results:
    if r["has_group"] and not r["has_wechat"]:
        for g in r["groups"][:2]:
            print(f"  {r['code']} {r['company']:8s} → {g}")
