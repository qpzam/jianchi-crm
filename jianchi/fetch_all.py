#!/usr/bin/env python3
"""
批量抓取2026年减持计划公告
跳过2月12日-3月2日（已有数据）
输出格式与"股票增减持计划"Excel完全一致

用法:
  cd ~/Desktop/减持获客系统
  python3 jianchi/fetch_all.py
"""
import os, sys, time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jianchi.cninfo_fetcher import search_date_range, filter_announcements, download_pdf, pdf_to_text, extract_meta
from jianchi.pdf_parser import parse_announcement, _create_ai_client

OUTPUT = "减持计划_2026汇总.xlsx"

def main():
    print("=" * 60)
    print("  批量抓取 2026 年减持计划/预披露公告")
    print("  跳过: 2/12 ~ 3/2 (已有55条)")
    print("=" * 60)

    ai_client = _create_ai_client()
    provider = ai_client[0] if ai_client else None
    print(f"  AI: {provider or '无(仅regex)'}")

    # 生成日期（跳过2/12~3/2）
    skip_s, skip_e = datetime(2026,2,12), datetime(2026,3,2)
    dates = []
    d = datetime(2026,1,1)
    end = datetime(2026,3,16)
    while d <= end:
        if d < skip_s or d > skip_e:
            dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    print(f"  搜索天数: {len(dates)}")

    # 按周批量搜索
    all_filtered = []
    seen = set()
    for i in range(0, len(dates), 7):
        batch = dates[i:i+7]
        s, e = batch[0], batch[-1]
        print(f"\n  📅 {s} ~ {e} ...", end=" ")

        try:
            raw = search_date_range(s, e)
            filtered = filter_announcements(raw)
            new = 0
            for item in filtered:
                aid = item.get("announcementId", "")
                if aid and aid not in seen:
                    seen.add(aid)
                    all_filtered.append(item)
                    new += 1
            print(f"原始{len(raw)} → 过滤{len(filtered)} → +{new}")
        except Exception as ex:
            print(f"✗ {ex}")

        time.sleep(1)

    print(f"\n{'='*60}")
    print(f"  预披露/计划公告: {len(all_filtered)} 条")
    print(f"{'='*60}")

    if not all_filtered:
        print("  无数据"); return

    # 解析
    records = []
    for i, item in enumerate(all_filtered, 1):
        meta = extract_meta(item)
        code = meta.get("stock_code", "")
        name = meta.get("stock_name", "")
        date = meta.get("announcement_date", "")
        print(f"  [{i}/{len(all_filtered)}] {code} {name} ({date})", end="")

        pdf_path = download_pdf(item)
        text = pdf_to_text(pdf_path) if pdf_path else ""

        rec = parse_announcement(text, meta, mode="auto" if provider else "regex",
                                 client_info=ai_client)

        holder = rec.get("股东名称", "")
        ratio = rec.get("减持比例(%)", "")
        print(f" → {holder[:14] if holder else '(未解析)'} {ratio}%")

        # 代码格式化为 XXXXXX.SH/SZ
        from jianchi.utils.stock import format_ts_code
        ts_code = format_ts_code(code) or code

        records.append({
            "代码": ts_code,
            "名称": name,
            "股东名称": holder,
            "股东类别": rec.get("股东类型", ""),
            "变动起始日期": rec.get("起始日期", ""),
            "变动截止日期": rec.get("截止日期", ""),
            "上限(万股)": rec.get("减持数量(万股)", ""),
            "上限占公司总股本比例(%)": ratio,
            "增减持方式": rec.get("减持方式", ""),
            "股份来源": rec.get("股份来源", ""),
            "目的": rec.get("减持原因", ""),
            "申万行业": "",
            "_公告日期": date,
        })

        if i % 20 == 0:
            time.sleep(1)

    # 按公告日期倒序（最新在前）
    records.sort(key=lambda r: r.get("_公告日期", ""), reverse=True)
    for r in records:
        r.pop("_公告日期", None)

    # 保存Excel
    from jianchi.utils.io import save_excel
    save_excel(records, OUTPUT, sheet_name="减持计划")

    # 统计
    with_holder = sum(1 for r in records if r["股东名称"])
    with_ratio = sum(1 for r in records if r["上限占公司总股本比例(%)"])
    print(f"\n📊 解析质量:")
    print(f"  股东名称: {with_holder}/{len(records)} ({with_holder/len(records)*100:.0f}%)")
    print(f"  减持比例: {with_ratio}/{len(records)} ({with_ratio/len(records)*100:.0f}%)")
    print(f"\n✓ 已保存: {OUTPUT} ({len(records)}条)")
    print(f"  列: {list(records[0].keys())}")

if __name__ == "__main__":
    main()
