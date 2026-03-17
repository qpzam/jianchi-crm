"""
减持获客系统 - CLI

用法:
  python -m jianchi                                # 抓取今日 (= run)
  python -m jianchi run --days 7 --mode auto       # 抓取最近7天
  python -m jianchi dash                           # 仪表盘
  python -m jianchi todo                           # 今日工作清单
  python -m jianchi leads --status 新线索           # 按状态筛选
  python -m jianchi leads --window 已开窗           # 按窗口期
  python -m jianchi search 海能                     # 搜索
  python -m jianchi detail 1                       # 线索详情
  python -m jianchi log 1 电话 有意向 "张总说下周签"   # 记录跟进
  python -m jianchi log 2 电话 未接通                # 未接通(自动排重拨)
  python -m jianchi log 3 短信 发了资料 "发了方案书"   # 短信记录
  python -m jianchi log 5 备注 "" "客户是老张介绍的"   # 纯备注
  python -m jianchi status 1 已签约                 # 手动改状态
  python -m jianchi batch 1,2,3 未接通              # 批量改状态
  python -m jianchi followup                       # 今日待跟进
  python -m jianchi funnel                         # 转化漏斗
"""
import argparse
import sys
from datetime import datetime

from .db import (
    init_db, get_leads, get_lead_detail, get_stats, get_followups,
    get_todo, get_funnel, search_leads, update_status, add_interaction,
    batch_update_status, LEAD_STATUSES, ACTION_TYPES, RESULT_STATUS_MAP,
)


def _lead_row(l, show_action=False):
    """格式化一行线索"""
    action = ""
    if show_action and l.get("last_action"):
        action = f" {l['last_action'][:10]}"
    followup = ""
    if l.get("next_followup"):
        followup = f" →{l['next_followup'][5:]}"
    return (
        f"  [{l['id']:3d}] {l['stock_code']} {l['stock_name'][:6]:6s} "
        f"| {l['shareholder'][:12]:12s} "
        f"| {l.get('priority',''):1s} {l['status'][:4]:4s} "
        f"| {(l.get('contact_name','') or '')[:4]:4s} {(l.get('phone','') or ''):13s}"
        f"{action}{followup}"
    )


# ============================================================
# 子命令
# ============================================================

def cmd_dash(args):
    """仪表盘"""
    init_db()
    s = get_stats()
    todo = get_todo()

    print("=" * 55)
    print(f"  减持获客 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 55)

    print(f"\n📦 线索: {s['total']}  本周+{s['new_this_week']}  跟进: {s['total_interactions']}次(今日{s['today_interactions']})")

    if s["status"]:
        icons = {"新线索":"🆕","未接通":"📵","已联系":"📞","有意向":"💰",
                 "方案沟通":"📝","已签约":"✅","执行中":"⚡","已完成":"🎉",
                 "无意向":"❌","暂缓":"⏸"}
        parts = []
        for st in LEAD_STATUSES:
            cnt = s["status"].get(st, 0)
            if cnt > 0:
                parts.append(f"{icons.get(st,'·')}{st}:{cnt}")
        print(f"\n  {'  '.join(parts)}")

    if s["window"]:
        wicons = {"未开窗":"⏳","已开窗":"🟢","过半":"🟡","即将关窗":"🔴","已关窗":"⬛","未知":"❓"}
        parts = [f"{wicons.get(p,'·')}{p}:{c}" for p,c in s["window"].items() if c>0]
        print(f"  {'  '.join(parts)}")

    # 今日工作摘要
    n_new = len(todo["new_leads"])
    n_fup = len(todo["followups"])
    n_retry = len(todo["retries"])
    n_win = len(todo["window_alerts"])
    total_todo = n_new + n_fup + n_retry + n_win

    if total_todo > 0:
        print(f"\n📋 今日待办: {total_todo} 条")
        if n_fup:  print(f"  📌 到期跟进: {n_fup}")
        if n_retry: print(f"  🔄 未接通重拨: {n_retry}")
        if n_win:  print(f"  🪟 窗口提醒: {n_win}")
        if n_new:  print(f"  🆕 新线索待联系: {n_new}")
        print(f"  👉 python3 -m jianchi todo 查看详情")

    if s["last_run"]:
        lr = s["last_run"]
        print(f"\n⏱ 上次抓取: {lr['created_at'][:16]} (+{lr['new_leads']}新)")


def cmd_todo(args):
    """今日工作清单"""
    init_db()
    todo = get_todo()

    print("=" * 55)
    print(f"  📋 今日工作清单 | {datetime.now().strftime('%Y-%m-%d')}")
    print("=" * 55)

    sections = [
        ("📌 到期跟进（优先处理）", todo["followups"]),
        ("🔄 未接通重拨", todo["retries"]),
        ("🪟 窗口提醒（已开窗/即将关窗）", todo["window_alerts"]),
        ("🆕 新线索", todo["new_leads"]),
    ]

    total = 0
    for title, items in sections:
        if not items:
            continue
        print(f"\n{title} ({len(items)}条)")
        print("-" * 55)
        for l in items:
            extra = ""
            if l.get("window_phase") in ("已开窗","即将关窗"):
                extra = f" [{l['window_phase']}]"
            if l.get("retry_count",0) > 0:
                extra = f" [第{l['retry_count']+1}次]"
            print(_lead_row(l) + extra)
        total += len(items)

    if total == 0:
        print("\n  今日无待办，可以摸鱼了 🐟")
    else:
        print(f"\n合计: {total} 条待办")
        print("记录结果: python3 -m jianchi log <ID> 电话 <结果> [备注]")


def cmd_leads(args):
    """列出线索"""
    init_db()
    leads = get_leads(status=args.status, priority=args.priority,
                      window_phase=args.window, limit=args.limit)
    if not leads:
        print("无匹配线索")
        return

    print(f"\n{'ID':>5s} {'代码':8s} {'公司':6s} {'股东':12s} {'比例':6s} {'优先':2s} {'状态':4s} {'窗口':4s} {'联系人':4s} {'手机':13s} {'最近操作':10s}")
    print("-" * 100)
    for l in leads:
        action = (l.get("last_action","") or "")[:10]
        print(
            f"{l['id']:5d} {l['stock_code']:8s} {l['stock_name'][:6]:6s} "
            f"{l['shareholder'][:12]:12s} {l['reduction_ratio'][:6]:6s} "
            f"{l['priority']:2s} {l['status'][:4]:4s} "
            f"{l.get('window_phase','')[:4]:4s} "
            f"{(l['contact_name'] or '')[:4]:4s} {(l['phone'] or ''):13s} "
            f"{action}")
    print(f"\n共 {len(leads)} 条")


def cmd_search(args):
    """搜索"""
    init_db()
    leads = search_leads(args.keyword)
    if not leads:
        print(f"未找到 '{args.keyword}'")
        return
    print(f"\n搜索 '{args.keyword}' ({len(leads)}条):")
    for l in leads:
        print(_lead_row(l, show_action=True))


def cmd_detail(args):
    """线索详情"""
    init_db()
    l = get_lead_detail(args.lead_id)
    if not l:
        print(f"线索 #{args.lead_id} 不存在")
        return

    print(f"\n{'='*50}")
    print(f"  #{l['id']} {l['stock_code']} {l['stock_name']} — {l['status']}")
    print(f"{'='*50}")
    print(f"  股东: {l['shareholder']}")
    print(f"  类型: {l['shareholder_type']}  来源: {l['share_source']}")
    print(f"  比例: {l['reduction_ratio']}%  方式: {l['reduction_method']}")
    print(f"  窗口: {l['start_date']} ~ {l['end_date']} ({l['window_phase']})")
    if l['score']:
        print(f"  评分: {l['score']}分 {l['score_detail']}")

    print(f"\n  📇 联系人: {l['contact_name']}  {l['position']}")
    print(f"     手机: {l['phone']}  邮箱: {l['email']}")
    print(f"     匹配: {l['match_type']}")

    print(f"\n  优先: {l['priority']}  状态: {l['status']}  重试: {l.get('retry_count',0)}次")
    if l.get("next_followup"):
        print(f"  📌 下次跟进: {l['next_followup']}")

    if l["interactions"]:
        print(f"\n  📞 跟进记录 ({l['interaction_count']}条):")
        for i in l["interactions"]:
            fu = f" → 跟进:{i['next_followup']}" if i['next_followup'] else ""
            nt = f" | {i['notes']}" if i['notes'] else ""
            print(f"    {i['created_at'][:16]} {i['action']} [{i['result']}]{nt}{fu}")
    else:
        print(f"\n  📞 暂无跟进记录")
    print(f"\n  🔗 {l['announcement_url']}")


def cmd_log(args):
    """记录跟进"""
    init_db()
    lead = get_lead_detail(args.lead_id)
    if not lead:
        print(f"线索 #{args.lead_id} 不存在")
        return

    ok = add_interaction(
        lead_id=args.lead_id,
        action=args.action,
        result=args.result or "",
        notes=args.notes or "",
        next_followup=args.followup or "",
    )
    if not ok:
        return

    # 重新读取最新状态
    updated = get_lead_detail(args.lead_id)
    name = f"{lead['stock_code']} {lead['stock_name']}"
    print(f"✓ #{args.lead_id} {name}")
    print(f"  {args.action} → {args.result or '(无结果)'}")
    if args.notes:
        print(f"  备注: {args.notes}")
    print(f"  状态: {lead['status']} → {updated['status']}")
    if updated.get("next_followup"):
        print(f"  📌 下次跟进: {updated['next_followup']}")


def cmd_status(args):
    """手动改状态"""
    init_db()
    if update_status(args.lead_id, args.new_status):
        print(f"✓ #{args.lead_id} → {args.new_status}")


def cmd_batch(args):
    """批量改状态"""
    init_db()
    try:
        ids = [int(x.strip()) for x in args.ids.split(",")]
    except ValueError:
        print("ID格式错误，用逗号分隔: 1,2,3")
        return

    n = batch_update_status(ids, args.new_status)
    print(f"✓ {n} 条线索 → {args.new_status}")


def cmd_followup(args):
    """今日待跟进"""
    init_db()
    leads = get_followups()
    if not leads:
        print("今日无待跟进")
        return
    print(f"\n📌 今日待跟进 ({len(leads)}条):")
    for l in leads:
        extra = f" [重试{l.get('retry_count',0)+1}]" if l["status"] == "未接通" else ""
        print(_lead_row(l, show_action=True) + extra)


def cmd_funnel(args):
    """转化漏斗"""
    init_db()
    stages = get_funnel()
    print(f"\n📊 转化漏斗")
    print("=" * 45)

    max_count = stages[0][1] if stages[0][1] > 0 else 1
    for i, (name, count) in enumerate(stages):
        bar_len = int(count / max_count * 30)
        bar = "█" * bar_len
        rate = ""
        if i > 0 and stages[i-1][1] > 0:
            r = count / stages[i-1][1] * 100
            rate = f" ({r:.0f}%)"
        print(f"  {name:4s} {count:4d} {bar}{rate}")

    if stages[0][1] > 0:
        total_rate = stages[-1][1] / stages[0][1] * 100
        print(f"\n  全程转化: {stages[0][1]} → {stages[-1][1]} ({total_rate:.1f}%)")


# ============================================================
# CLI 路由
# ============================================================

def build_parser():
    p = argparse.ArgumentParser(description="减持获客系统 v2.0")
    sub = p.add_subparsers(dest="command")

    # run
    r = sub.add_parser("run", help="抓取管线")
    r.add_argument("--date"); r.add_argument("--days", type=int, default=1)
    r.add_argument("--contacts"); r.add_argument("--mode", default="regex", choices=["regex","ai","auto"])
    r.add_argument("--no-score", action="store_true"); r.add_argument("--output")

    sub.add_parser("dash", help="仪表盘")
    sub.add_parser("todo", help="今日工作清单")

    # leads
    l = sub.add_parser("leads", help="线索列表")
    l.add_argument("--status"); l.add_argument("--priority"); l.add_argument("--window")
    l.add_argument("--limit", type=int, default=50)

    s = sub.add_parser("search", help="搜索"); s.add_argument("keyword")
    d = sub.add_parser("detail", help="详情"); d.add_argument("lead_id", type=int)

    # log (核心交互命令)
    lg = sub.add_parser("log", help="记录跟进")
    lg.add_argument("lead_id", type=int)
    lg.add_argument("action", help=f"操作: {'/'.join(ACTION_TYPES)}")
    lg.add_argument("result", nargs="?", default="",
                    help=f"结果: {'/'.join(RESULT_STATUS_MAP.keys())}")
    lg.add_argument("notes", nargs="?", default="", help="备注")
    lg.add_argument("--followup", help="下次跟进 YYYY-MM-DD")

    # call (log 的快捷方式)
    c = sub.add_parser("call", help="记录电话 (= log X 电话)")
    c.add_argument("lead_id", type=int)
    c.add_argument("result", help="结果")
    c.add_argument("notes", nargs="?", default="")
    c.add_argument("--followup")

    st = sub.add_parser("status", help="改状态")
    st.add_argument("lead_id", type=int); st.add_argument("new_status")

    b = sub.add_parser("batch", help="批量改状态")
    b.add_argument("ids", help="ID列表,用逗号分隔"); b.add_argument("new_status")

    sub.add_parser("followup", help="今日待跟进")
    sub.add_parser("funnel", help="转化漏斗")

    return p


def cli_main():
    p = build_parser()

    # 兼容旧用法: --date/--days/--mode/--no-score 直接当 run
    if len(sys.argv) > 1 and sys.argv[1].startswith("--"):
        sys.argv.insert(1, "run")
    if len(sys.argv) == 1:
        sys.argv.append("run")

    args = p.parse_args()

    handlers = {
        "run": _run_pipeline,
        "dash": cmd_dash, "todo": cmd_todo, "leads": cmd_leads,
        "search": cmd_search, "detail": cmd_detail,
        "log": cmd_log, "call": lambda a: _call_shortcut(a),
        "status": cmd_status, "batch": cmd_batch,
        "followup": cmd_followup, "funnel": cmd_funnel,
    }

    h = handlers.get(args.command)
    if h:
        h(args)
    else:
        p.print_help()


def _call_shortcut(args):
    """call → log 的转换"""
    args.action = "电话"
    cmd_log(args)


def _run_pipeline(args):
    from .pipeline import run_pipeline
    from datetime import timedelta
    dates = [args.date] if args.date else \
        [(datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d") for i in range(args.days)]

    print("="*60)
    print(f"减持获客系统 v2.0 | {dates[-1]} ~ {dates[0]} | {args.mode}")
    print("="*60)

    run_pipeline(dates=dates, contacts_file=args.contacts, parse_mode=args.mode,
                 enable_score=not args.no_score, output_dir=args.output)
