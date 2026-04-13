"""
减持获客系统 - 主管线
串联: 抓取 → 解析 → 评分 → 匹配 → 输出

用法:
    python -m jianchi.pipeline                          # 今日公告
    python -m jianchi.pipeline --date 2026-03-04        # 指定日期
    python -m jianchi.pipeline --days 7                 # 最近7天
    python -m jianchi.pipeline --mode ai                # AI解析模式
    python -m jianchi.pipeline --no-score               # 跳过评分(无TinyShare时)
    python -m jianchi.pipeline --contacts data/contacts.xlsx  # 指定联系方式库
"""
import argparse
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

from .config import OUTPUT_DIR, DATA_DIR
from .cninfo_fetcher import fetch_and_filter, download_pdf, pdf_to_text

# 加载环境变量
load_dotenv()
from .pdf_parser import parse_announcement
from .contact_matcher import match_records, assign_priority
from .reduction_scorer import ReductionScorer, batch_fetch
from .utils.io import load_dataframe
from .utils.stock import clean_stock_code


def run_pipeline(
    dates: list[str],
    contacts_file: str = None,
    parse_mode: str = "regex",
    enable_score: bool = True,
    output_dir: str = None,
):
    """
    执行完整管线

    参数:
      dates: 日期列表 ['2026-03-04', ...]
      contacts_file: 联系方式库路径 (可选)
      parse_mode: 'regex' | 'ai' | 'auto'
      enable_score: 是否启用评分 (需要 TinyShare)
      output_dir: 输出目录
    """
    output_dir = output_dir or str(OUTPUT_DIR)
    os.makedirs(output_dir, exist_ok=True)
    today_str = datetime.now().strftime("%Y%m%d")

    # ========== 阶段1: 抓取 ==========
    print("\n" + "=" * 60)
    print("阶段1: 抓取减持公告")
    print("=" * 60)

    all_announcements = []
    for date_str in dates:
        metas = fetch_and_filter(date_str)
        all_announcements.extend(metas)

    print(f"\n共获取 {len(all_announcements)} 条预披露公告")

    if not all_announcements:
        print("未找到任何公告，流程结束")
        return []

    # ========== 阶段2: 下载PDF + 解析 ==========
    print("\n" + "=" * 60)
    print(f"阶段2: 解析公告 (模式: {parse_mode})")
    print("=" * 60)

    ai_client_info = None
    if parse_mode in ("ai", "auto"):
        try:
            from .pdf_parser import _create_ai_client
            provider, client, model = _create_ai_client()
            if provider:
                ai_client_info = (provider, client, model)
                print(f"  AI 接口已就绪 ({provider})")
            else:
                print(f"  ⚠️ 无可用 AI 接口，将使用 regex 模式")
                parse_mode = "regex"
        except Exception as e:
            print(f"  ⚠️ 创建 AI 客户端失败: {e}")
            print(f"  将使用 regex 模式")
            parse_mode = "regex"

    records = []
    for i, meta in enumerate(all_announcements, 1):
        name = meta.get("stock_name", "未知")
        code = meta.get("stock_code", "")
        print(f"\n  [{i}/{len(all_announcements)}] {code} {name}")

        # 下载PDF
        raw_item = meta.get("_raw", meta)
        pdf_path = download_pdf(raw_item)

        if pdf_path:
            text = pdf_to_text(pdf_path)
            print(f"    PDF: {len(text)} 字")
        else:
            text = ""
            print(f"    ⚠️ PDF下载失败")

        # 解析（返回列表，每个股东一条记录）
        parsed_list = parse_announcement(text, meta, mode=parse_mode, client_info=ai_client_info)
        records.extend(parsed_list)

        # 检查解析质量
        for rec in parsed_list:
            holder = rec.get("股东名称", "")
            ratio = rec.get("减持比例(%)", "")
            warnings = rec.get("warnings", [])

            # Bug2修复：股东名称为空时尝试从公告标题提取
            if not holder:
                title = meta.get("announcement_title", "")
                import re as _re
                # 尝试从标题提取股东类型描述
                title_match = _re.search(r"(控股股东|实际控制人|持股5%以上股东|股东|董事|监事|高管)", title)
                if title_match:
                    rec["股东名称"] = title_match.group(1)
                    holder = rec["股东名称"]
                    print(f"    ⚠️ 股东名称为空，从标题提取: {holder}")
                else:
                    print(f"    ⚠️ 解析异常: 未提取到股东名称 [{code} {name}]")

            if holder:
                print(f"    股东: {holder}  比例: {ratio}%")
            elif not holder:
                print(f"    ⚠️ 解析异常: 未提取到股东名称 [{code} {name}]")

            if warnings:
                for w in warnings:
                    print(f"    ⚠️ {w}")

            if parse_mode in ("ai", "auto") and not holder and not ratio:
                print(f"    ✗ AI解析失败: {code} {name}，返回空结果，请检查API连接或PDF内容")

    print(f"\n解析完成: {len(records)} 条记录")

    # 保存中间结果（原子写入：先写.tmp再rename，防止断电损坏）
    json_path = os.path.join(output_dir, f"parsed_{today_str}.json")
    tmp_path = json_path + ".tmp"
    clean_records = [{k: v for k, v in r.items() if k != "_raw"} for r in records]
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(clean_records, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, json_path)
    print(f"  中间结果: {json_path}")

    # ========== 阶段3: 评分 (可选) ==========
    if enable_score:
        print("\n" + "=" * 60)
        print("阶段3: 减持概率评分")
        print("=" * 60)

        # 收集所有股票代码
        stock_codes = set()
        for rec in records:
            code = clean_stock_code(rec.get("股票代码", ""))
            if code:
                stock_codes.add(code)

        # 批量获取市场数据
        market_data = batch_fetch(stock_codes)

        # 评分
        import pandas as pd
        ann_df = pd.DataFrame(records)
        if "股票代码" in ann_df.columns:
            ann_df["clean_code"] = ann_df["股票代码"].apply(clean_stock_code)

        scorer = ReductionScorer()
        scored_records = []
        for rec in records:
            code = clean_stock_code(rec.get("股票代码", ""))
            mdata = market_data.get(code, {})
            scored = scorer.calculate(rec, mdata, ann_df)
            scored_records.append(scored)

        # 按分数排序
        scored_records.sort(key=lambda x: x.get("总分", 0), reverse=True)
        records = scored_records

        # 打印 Top 10
        print(f"\n🏆 评分 Top 10:")
        for r in records[:10]:
            print(f"  {r.get('总分', 0):3d}分 | {r.get('股票代码', '')} {r.get('股票名称', '')} | {r.get('信号明细', '')}")
    else:
        print("\n⏭ 跳过评分阶段")

    # ========== 阶段4: 匹配联系方式 (可选) ==========
    if contacts_file:
        print("\n" + "=" * 60)
        print("阶段4: 匹配联系方式")
        print("=" * 60)

        contact_df = load_dataframe(contacts_file)
        print(f"  联系方式库: {len(contact_df)} 条")
        records = match_records(records, contact_df)
    else:
        # 尝试自动发现联系方式库
        # 优先加载文本格式联系方式文件（20万条）
        from .contact_matcher import load_text_contacts
        txt_files = [
            str(DATA_DIR / "contacts_merged.txt"),
        ]
        # 如果合并库不存在，用原始文件
        if not any(os.path.exists(f) for f in txt_files):
            txt_files = [
                str(DATA_DIR / "all_contacts_dedup.txt"),
                str(DATA_DIR / "contacts_final.txt"),
                str(DATA_DIR / "iphone_contacts.txt"),
            ]
        found_txt = [f for f in txt_files if os.path.exists(f)]
        if found_txt:
            print(f"\n自动发现联系方式库: {len(found_txt)} 个文件")
            contact_df = load_text_contacts(found_txt)
            print(f"📇 联系方式库: {len(contact_df)} 条, 按公司名匹配")
            records = match_records(records, contact_df, contact_cols={"company": "company"})
        else:
            for candidate in [
                str(DATA_DIR / "contacts.xlsx"),
                str(DATA_DIR / "联系方式库.xlsx"),
            ]:
                if os.path.exists(candidate):
                    print(f"\n自动发现联系方式库: {candidate}")
                    contact_df = load_dataframe(candidate)
                    records = match_records(records, contact_df)
                    break
            else:
                print("\n⏭ 未找到联系方式库，跳过匹配")

    # ========== 阶段5: 持久化 + 去重 + 输出 ==========
    print("\n" + "=" * 60)
    print("阶段5: 持久化 + 生成输出")
    print("=" * 60)

    for rec in records:
        rec["优先级"] = assign_priority(rec)
        rec["状态"] = "新线索"

    # 写入数据库（自动去重）
    from .db import init_db, upsert_leads, log_pipeline_run, get_stats
    init_db()
    dedup = upsert_leads(records)
    print(f"  📥 入库: 新增 {dedup['new']} | 更新 {dedup['updated']} | 跳过 {dedup['skipped']}")

    # 记录执行日志
    log_pipeline_run(
        target_dates=dates,
        total_fetched=len(all_announcements),
        total_parsed=len(records),
        new=dedup["new"],
        updated=dedup["updated"],
        duplicate=dedup["updated"],  # updated = 已存在的记录
    )

    # 统计
    high = sum(1 for r in records if r.get("优先级") == "高")
    mid = sum(1 for r in records if r.get("优先级") == "中")
    matched = sum(1 for r in records if r.get("匹配方式", "未匹配") != "未匹配")

    # 数据库累计
    db_stats = get_stats()

    # TXT日报由 gen_daily_report.py 生成，pipeline不再写简报避免覆盖冲突
    txt_path = os.path.join(output_dir, f"今日减持_{today_str}.txt")

    print(f"\n📊 本次汇总:")
    print(f"  解析: {len(records)} 条 → 新增 {dedup['new']} + 更新 {dedup['updated']}")
    print(f"  优先级: 🔴高 {high} | 🟡中 {mid} | 🟢低 {len(records) - high - mid}")
    if any(r.get("匹配方式") for r in records):
        print(f"  匹配率: {matched}/{len(records)} ({matched/max(len(records),1)*100:.0f}%)")
    print(f"  输出: {txt_path}")

    print(f"\n📦 数据库累计:")
    print(f"  总线索: {db_stats['total']} 条")
    for status, cnt in sorted(db_stats['status'].items(), key=lambda x: -x[1]):
        print(f"    {status}: {cnt}")
    if db_stats.get("window"):
        print(f"  窗口期:")
        for phase, cnt in db_stats["window"].items():
            print(f"    {phase}: {cnt}")

    return records


def main():
    parser = argparse.ArgumentParser(description="减持获客系统 - 主管线")
    parser.add_argument("--date", help="指定日期 (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=1, help="最近N天 (默认1)")
    parser.add_argument("--contacts", help="联系方式库路径")
    parser.add_argument("--mode", choices=["regex", "ai", "auto"], default="regex",
                        help="解析模式 (默认 regex)")
    parser.add_argument("--no-score", action="store_true", help="跳过评分")
    parser.add_argument("--output", help="输出目录")
    args = parser.parse_args()

    # 构造日期列表
    if args.date:
        dates = [args.date]
    else:
        today = datetime.now()
        dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d")
                 for i in range(args.days)]

    print("=" * 60)
    print("减持获客系统 v2.0")
    print(f"日期范围: {dates[-1]} ~ {dates[0]}")
    print(f"解析模式: {args.mode}")
    print(f"评分: {'开启' if not args.no_score else '关闭'}")
    print("=" * 60)

    run_pipeline(
        dates=dates,
        contacts_file=args.contacts,
        parse_mode=args.mode,
        enable_score=not args.no_score,
        output_dir=args.output,
    )


if __name__ == "__main__":
    main()
