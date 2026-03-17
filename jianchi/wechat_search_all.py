import os, subprocess, time, pandas as pd

OUTPUT_DIR = os.path.expanduser("~/Desktop/减持获客系统/wechat_match_all")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def asc(script):
    return subprocess.run(["osascript","-e",script], capture_output=True, text=True, timeout=10).stdout.strip()

def search(kw):
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
    subprocess.run(["screencapture","-x","-o", os.path.join(OUTPUT_DIR, name)], capture_output=True, timeout=5)

def close_search():
    asc('tell application "System Events" to tell process "WeChat" to key code 53')
    time.sleep(0.3)

# 读取两份文件
base = os.path.expanduser("~/Desktop/减持获客系统")
dfs = []
for f in ["减持计划_2026汇总.xlsx"] + [os.path.join("jianchi/data", x) for x in os.listdir(os.path.join(base,"jianchi/data")) if x.endswith(".xlsx")]:
    fp = os.path.join(base, f)
    if os.path.exists(fp):
        try:
            dfs.append(pd.read_excel(fp, dtype=str))
        except:
            pass

if not dfs:
    print("未找到Excel文件"); exit()

df = pd.concat(dfs, ignore_index=True)
companies = {}
for _, r in df.iterrows():
    name = str(r.get("名称") or r.get("股票名称") or "").strip()
    code = str(r.get("代码") or r.get("股票代码") or "").strip()
    if name and name not in companies:
        companies[name] = code

# 断点续搜
done = set()
for f in os.listdir(OUTPUT_DIR):
    if f.endswith(".png"):
        n = f.split("_", 2)[-1].replace(".png","")
        done.add(n)

todo = {n:c for n,c in companies.items() if n not in done}
print(f"总公司: {len(companies)}, 已完成: {len(done)}, 待搜索: {len(todo)}")
if not todo:
    print("全部完成!"); exit()

input("确保微信已登录，按 Enter 开始...")

asc('tell application "WeChat" to activate')
time.sleep(1)

for i,(name,code) in enumerate(todo.items(),1):
    idx = len(done) + i
    print(f"[{i}/{len(todo)}] {code} {name}", end="")
    search(name)
    safe = name.replace("/","_").replace("*","x")
    screenshot(f"{idx:03d}_{code}_{safe}.png")
    print(" -> OK")
    close_search()
    time.sleep(0.3)
    if i % 50 == 0:
        print(f"  --- 休息3秒 ---"); time.sleep(3)

print(f"\n完成! 截图在: {OUTPUT_DIR}")
