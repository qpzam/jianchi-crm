#!/usr/bin/env python3
"""
自动触达：短信(iMessage) + 邮件
"""
import subprocess, time, os, json, re, sys
from datetime import datetime
from collections import defaultdict

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

BASE = os.environ.get('PROJECT_ROOT', os.path.expanduser("~/Desktop/减持获客系统"))

SMS_TEMPLATE_COLD = """{surname}总您好，打扰了。

我是{contact_company} {contact_name}（电微{contact_phone}）。

关注到{stock_name}近期有股份减持计划，我们对贵司26-27年发展非常看好，希望通过大宗交易方式承接股份，共同参与成长。

如有大宗减持需求，我们可第一时间对接，诚意全额承接。

期待与您合作，祝商祺！

{date}"""

SMS_TEMPLATE_FOLLOWUP = """{surname}总您好，刚才和您联系。

{contact_company} {contact_name}，电微{contact_phone}，烦请惠存。

我们看好{stock_name} 26-27年业绩前景，想通过大宗承接贵司股份，共同参与成长。

请教您，这次减持是您在统筹负责吗，我们有兴趣全接。

若有需求，烦请联系，我们第一时间来接。

非常感谢您的大力支持！

{date}"""

def send_sms(phone, message):
    phone = re.sub(r'[^\d]', '', phone)
    if len(phone) == 11:
        phone = "+86" + phone
    safe_msg = message.replace('"', '\\"').replace("'", "\\'")
    script = f'tell application "Messages"\nsend "{safe_msg}" to buddy "{phone}" of (service 1 whose service type is iMessage)\nend tell'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
    return result.returncode == 0

def gen_sms(template, stock_name, contact_name=""):
    if not contact_name:
        contact_name = "领导"
    surname = contact_name[0] if len(contact_name) >= 2 else contact_name

    # Load environment variables for template formatting
    contact_company = os.environ.get('CONTACT_COMPANY', '示例基金')
    contact_name_env = os.environ.get('CONTACT_NAME', '张三')
    contact_phone = os.environ.get('CONTACT_PHONE', '138xxxx1234')

    return template.format(
        surname=surname,
        stock_name=stock_name,
        date=datetime.now().strftime("%Y年%m月%d日"),
        contact_company=contact_company,
        contact_name=contact_name_env,
        contact_phone=contact_phone
    )

def load_contacts():
    contacts = defaultdict(list)
    cf = os.path.join(BASE, "jianchi/data/contacts_final.txt")
    if not os.path.exists(cf):
        return contacts
    with open(cf, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            phone_match = re.search(r"电话[：:]\s*(\d{11})", line)
            phone = phone_match.group(1) if phone_match else ""
            if not phone: continue
            text = re.sub(r"电话[：:].*$", "", line).strip()
            text = re.sub(r"^[0-9A-Za-z\*\.]+", "", text).strip()
            parts = text.split()
            if len(parts) >= 2:
                company = parts[0].replace("ST","").replace("*","").strip()
                person = parts[1]
                title = " ".join(parts[2:]) if len(parts) > 2 else ""
                contacts[company].append({"name": person, "phone": phone, "title": title})
    return contacts

def batch_sms(date_str=None, template="cold", dry_run=True):
    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")
    parsed_file = os.path.join(BASE, f"jianchi/daily_output/parsed_{date_str}.json")
    if not os.path.exists(parsed_file):
        print(f"未找到: {parsed_file}")
        return
    with open(parsed_file, "r", encoding="utf-8") as f:
        records = json.load(f)
    seen = {}
    for rec in records:
        key = (rec.get("股票名称",""), rec.get("股东名称",""))
        if key not in seen: seen[key] = rec
    unique = list(seen.values())
    contacts = load_contacts()
    tmpl = SMS_TEMPLATE_COLD if template == "cold" else SMS_TEMPLATE_FOLLOWUP
    sent_file = os.path.join(BASE, "jianchi/daily_output/sent_sms.json")
    sent = {}
    if os.path.exists(sent_file):
        with open(sent_file, "r", encoding="utf-8") as f: sent = json.load(f)
    print("=" * 60)
    print(f"  批量短信 {'[预览模式]' if dry_run else '[发送模式]'}")
    print(f"  模板: {'首次触达' if template=='cold' else '电话跟进'}")
    print("=" * 60)
    to_send = []
    for rec in unique:
        stock = rec.get("股票名称","")
        clean = stock.replace("ST","").replace("*","").strip()
        people = contacts.get(stock, []) or contacts.get(clean, [])
        if not people: continue
        best = people[0]
        for p in people:
            if any(kw in p.get("title","") for kw in ["董秘","秘书","证代"]):
                best = p; break
        phone = best["phone"]
        name = best["name"]
        if phone in sent: continue
        msg = gen_sms(tmpl, stock, name)
        to_send.append({"stock": stock, "phone": phone, "name": name, "title": best.get("title",""), "msg": msg})
    print(f"\n  待发送: {len(to_send)} 条\n")
    for i, item in enumerate(to_send, 1):
        print(f"[{i:2d}] {item['stock']} -> {item['name']} ({item['title']}) {item['phone']}")
        if dry_run:
            print(f"    内容预览: {item['msg'][:50]}...")
        else:
            ok = send_sms(item['phone'], item['msg'])
            print(f"    {'✅ 已发送' if ok else '❌ 发送失败'}")
            if ok:
                sent[item['phone']] = {"stock": item['stock'], "name": item['name'], "time": datetime.now().isoformat()}
            time.sleep(30)
    if not dry_run and sent:
        with open(sent_file, "w", encoding="utf-8") as f: json.dump(sent, f, ensure_ascii=False, indent=2)
    print(f"\n{'='*60}")
    if dry_run:
        print(f"  预览完成。确认后执行:")
        print(f"  python3 jianchi/auto_outreach.py sms --send")
    else:
        print(f"  发送完成: {len(to_send)} 条")

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "help":
        print("用法:")
        print("  python3 jianchi/auto_outreach.py test 15011332355")
        print("  python3 jianchi/auto_outreach.py sms")
        print("  python3 jianchi/auto_outreach.py sms --send")
        print("  python3 jianchi/auto_outreach.py sms --followup")
    elif args[0] == "test" and len(args) >= 2:
        phone = args[1]
        msg = gen_sms(SMS_TEMPLATE_COLD, "测试公司", "常")
        print(f"发送测试短信到 {phone}:\n")
        print(msg)
        print(f"\n{'='*40}")
        ok = send_sms(phone, msg)
        print("✅ 发送成功" if ok else "❌ 发送失败")
    elif args[0] == "sms":
        is_send = "--send" in args
        tmpl = "followup" if "--followup" in args else "cold"
        batch_sms(template=tmpl, dry_run=not is_send)
