#!/usr/bin/env python3
"""
批量拉取减持公告涉及公司的全量股东数据
读取减持计划Excel → TinyShare拉股东 → 输出股东联系方式库

用法:
  cd ~/Desktop/减持获客系统
  python3 jianchi/pull_shareholders.py
"""
import os, sys, time
import pandas as pd

TOKEN = "TCc2U01ac5KMMama6xJCqQzt3r7xe3lVkn4am3k4y0nBi7wjGkVgwfSU90451d60"
BASE = os.path.expanduser("~/Desktop/减持获客系统")
OUTPUT = os.path.join(BASE, "股东联系方式库.xlsx")
CACHE_DIR = os.path.join(BASE, "shareholder_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# 最近几个报告期（从新到旧尝试）
PERIODS = ["20241231", "20240930", "20240630", "20240331"]


def init_api():
    import tinyshare as ts
    ts.REQUEST_VERIFY = False
    ts.set_token(TOKEN)
    return ts.pro_api()


def pull_top10(pro, ts_code):
    """拉取前十大股东，自动尝试多个报告期"""
    cache = os.path.join(CACHE_DIR, f"{ts_code}_holders.csv")
    if os.path.exists(cache):
        return pd.read_csv(cache)

    for period in PERIODS:
        try:
            df = pro.top10_holders(ts_code=ts_code, period=period)
            if df is not None and len(df) > 0:
                df.to_csv(cache, index=False)
                return df
        except Exception as e:
            if "每分钟" in str(e) or "频次" in str(e):
                time.sleep(15)
                continue
            pass
        time.sleep(0.3)

    # 空结果也缓存，避免重复请求
    pd.DataFrame().to_csv(cache, index=False)
    return pd.DataFrame()


def pull_company(pro, ts_code):
    """拉取公司基本信息（含董秘/邮箱）"""
    cache = os.path.join(CACHE_DIR, f"{ts_code}_company.csv")
    if os.path.exists(cache):
        return pd.read_csv(cache)

    try:
        df = pro.stock_company(ts_code=ts_code)
        if df is not None and len(df) > 0:
            df.to_csv(cache, index=False)
            return df
    except:
        pass
    time.sleep(0.3)
    return pd.DataFrame()


def main():
    print("=" * 55)
    print("  股东联系方式库 - 批量拉取")
    print("=" * 55)

    # 读取减持计划
    dfs = []
    for f in ["减持计划_2026汇总.xlsx"]:
        fp = os.path.join(BASE, f)
        if os.path.exists(fp):
            dfs.append(pd.read_excel(fp, dtype=str))
            print(f"  读取 {f}: {len(dfs[-1])} 条")

    # 也扫描 jianchi/data 目录
    data_dir = os.path.join(BASE, "jianchi/data")
    if os.path.isdir(data_dir):
        for f in os.listdir(data_dir):
            if f.endswith(".xlsx"):
                fp = os.path.join(data_dir, f)
                try:
                    dfs.append(pd.read_excel(fp, dtype=str))
                    print(f"  读取 data/{f}: {len(dfs[-1])} 条")
                except:
                    pass

    if not dfs:
        print("  未找到减持计划Excel"); return

    df_all = pd.concat(dfs, ignore_index=True)

    # 提取唯一股票代码
    codes = {}
    for _, r in df_all.iterrows():
        code = str(r.get("代码") or r.get("股票代码") or "").strip()
        name = str(r.get("名称") or r.get("股票名称") or "").strip()
        holder = str(r.get("股东名称") or "").strip()
        if code and "." in code and code != "nan":
            if code not in codes:
                codes[code] = {"name": name, "holders": set()}
            if holder and holder != "nan":
                codes[code]["holders"].add(holder)

    print(f"\n  去重后: {len(codes)} 只股票, {sum(len(v['holders']) for v in codes.values())} 个减持股东")

    pro = init_api()
    print(f"  TinyShare 已连接\n")

    results = []
    total = len(codes)

    for i, (ts_code, info) in enumerate(codes.items(), 1):
        stock_name = info["name"]
        reduction_holders = info["holders"]

        print(f"[{i}/{total}] {ts_code} {stock_name}", end="")

        # 1. 拉前十大股东
        holders = pull_top10(pro, ts_code)
        h_count = len(holders) if holders is not None else 0

        # 2. 拉公司信息
        company = pull_company(pro, ts_code)
        secretary = ""
        email = ""
        chairman = ""
        if company is not None and len(company) > 0:
            row = company.iloc[0]
            secretary = str(row.get("secretary", "") or "")
            email = str(row.get("email", "") or "")
            chairman = str(row.get("chairman", "") or "")

        print(f" → 股东{h_count}人 董秘:{secretary or '无'}")

        # 3. 整理每个股东
        if holders is not None and len(holders) > 0:
            for _, h in holders.iterrows():
                holder_name = str(h.get("holder_name", ""))
                holder_type = str(h.get("holder_type", ""))
                hold_ratio = h.get("hold_ratio", 0)
                hold_change = h.get("hold_change", "")

                # 标记是否是减持公告中的股东
                is_reduction = "是" if any(
                    holder_name in rh or rh in holder_name
                    for rh in reduction_holders
                ) else ""

                # 判断联系路径
                if holder_type == "自然人":
                    contact_path = "启信宝查名下公司→年报电话"
                elif holder_type in ["投资公司", "信托公司集合信托计划"]:
                    contact_path = "启信宝查GP/执行事务合伙人→电话"
                elif holder_type == "一般企业":
                    contact_path = "启信宝查法人代表→电话"
                else:
                    contact_path = "上市公司前台转接"

                results.append({
                    "证券代码": ts_code,
                    "股票名称": stock_name,
                    "股东名称": holder_name,
                    "股东类型": holder_type,
                    "持股比例(%)": hold_ratio,
                    "持股变动(股)": hold_change,
                    "是否减持股东": is_reduction,
                    "联系路径": contact_path,
                    "董秘": secretary,
                    "董秘邮箱": email,
                    "董事长": chairman,
                    "启信宝查询状态": "",
                    "联系电话": "",
                    "验证状态": "",
                    "备注": "",
                })

        # 如果没拉到股东数据，至少保留公司信息
        if (holders is None or len(holders) == 0):
            for rh in reduction_holders:
                results.append({
                    "证券代码": ts_code,
                    "股票名称": stock_name,
                    "股东名称": rh,
                    "股东类型": "",
                    "持股比例(%)": "",
                    "持股变动(股)": "",
                    "是否减持股东": "是",
                    "联系路径": "待查",
                    "董秘": secretary,
                    "董秘邮箱": email,
                    "董事长": chairman,
                    "启信宝查询状态": "",
                    "联系电话": "",
                    "验证状态": "",
                    "备注": "",
                })

        # 频率控制：每5只股票暂停1秒
        if i % 5 == 0:
            time.sleep(1)
        # 每30只暂停5秒
        if i % 30 == 0:
            print(f"  --- 已完成 {i}/{total}, 休息5秒 ---")
            time.sleep(5)

    # 保存
    df_out = pd.DataFrame(results)

    # 减持股东排前面
    df_out["_sort"] = df_out["是否减持股东"].apply(lambda x: 0 if x == "是" else 1)
    df_out = df_out.sort_values(["_sort", "证券代码"]).drop(columns=["_sort"])

    df_out.to_excel(OUTPUT, index=False, sheet_name="股东库")

    # 统计
    n_total = len(df_out)
    n_reduction = len(df_out[df_out["是否减持股东"] == "是"])
    n_natural = len(df_out[df_out["股东类型"] == "自然人"])
    n_company = len(df_out[df_out["股东类型"].isin(["投资公司", "一般企业"])])
    n_with_sec = len(df_out[df_out["董秘"] != ""])

    print(f"\n{'='*55}")
    print(f"  总计: {n_total} 条股东记录")
    print(f"  减持股东: {n_reduction} 条")
    print(f"  自然人: {n_natural} | 法人: {n_company}")
    print(f"  有董秘信息: {n_with_sec}")
    print(f"  缓存: {CACHE_DIR}")
    print(f"\n  ✓ 已保存: {OUTPUT}")
    print(f"{'='*55}")
    print(f"\n  下一步: 用启信宝逐个穿透查询自然人/法人股东的联系电话")


if __name__ == "__main__":
    main()
