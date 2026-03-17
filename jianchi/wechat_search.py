import os, sys, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jianchi.db import init_db, get_leads

OUTPUT_DIR = os.path.expanduser("~/Desktop/减持获客系统/wechat_match")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def asc(script):
    return subprocess.run(["osascript","-e",script], capture_output=True, text=True, timeout=10).stdout.strip()

def search(kw):
    # 用剪贴板粘贴中文，不用keystroke
    subprocess.run(["pbcopy"], input=kw.encode("utf-8"))
    asc('''tell application "System Events" to tell process "WeChat"
        keystroke "f" using command down
        delay 0.3
        keystroke "a" using command down
        delay 0.1
        keystroke "v" using command down
    end tell''')
    time.sleep(2)

def screenshot(name):
    fp = os.path.join(OUTPUT_DIR, name)
    subprocess.run(["screencapture","-x","-o",fp], capture_output=True, timeout=5)
    return fp

def close_search():
    asc('tell application "System Events" to tell process "WeChat" to key code 53')
    time.sleep(0.3)

init_db()
leads = get_leads(limit=500)
companies = {}
for l in leads:
    n = l.get("stock_name","")
    if n and n not in companies:
        companies[n] = {"code":l["stock_code"]}

print(f"待搜索: {len(companies)} 家")
print("确保: 微信已登录 + 终端有辅助功能权限")
input("按 Enter 开始...")

asc('tell application "WeChat" to activate')
time.sleep(1)

for i,(name,info) in enumerate(companies.items(),1):
    print(f"[{i}/{len(companies)}] {info['code']} {name}", end="")
    search(name)
    fn = f"{i:03d}_{info['code']}_{name}.png"
    screenshot(fn)
    print(f" -> OK")
    close_search()
    time.sleep(0.5)

print(f"\n完成! 截图在: {OUTPUT_DIR}")
