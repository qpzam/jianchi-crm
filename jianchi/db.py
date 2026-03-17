"""
SQLite 持久化层
功能: 线索存储、去重、状态管理、跟进记录、工作清单、漏斗统计

表结构:
  leads         - 线索 (每条 = 一个股东的一次减持计划)
  interactions  - 跟进记录 (电话/短信/微信/邮件/面访/备注)
  pipeline_runs - 管线执行日志
"""
import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager

from .config import PROJECT_ROOT

DB_PATH = str(PROJECT_ROOT / "jianchi.db")

# ============================================================
# 常量定义
# ============================================================

LEAD_STATUSES = [
    "新线索", "未接通", "已联系", "有意向",
    "方案沟通", "已签约", "执行中", "已完成",
    "无意向", "暂缓",
]
ACTIVE_STATUSES = ["新线索", "未接通", "已联系", "有意向", "方案沟通"]
ACTION_TYPES = ["电话", "短信", "微信", "邮件", "面访", "备注"]
RETRY_INTERVALS = [1, 2, 3]  # 未接通自动重拨间隔（天）

# 结果 → 状态映射
RESULT_STATUS_MAP = {
    "有意向": "有意向", "无意向": "无意向", "未接通": "未接通",
    "已签约": "已签约", "方案沟通": "方案沟通", "待跟进": "已联系",
    "已接通": "已联系", "了解一下": "已联系", "发了资料": "已联系",
    "暂缓": "暂缓",
}

# ============================================================
# Schema + 迁移
# ============================================================

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    stock_name TEXT DEFAULT '',
    shareholder TEXT NOT NULL,
    announcement_date TEXT DEFAULT '',
    announcement_title TEXT DEFAULT '',
    announcement_url TEXT DEFAULT '',
    shareholder_type TEXT DEFAULT '',
    reduction_shares TEXT DEFAULT '',
    reduction_ratio TEXT DEFAULT '',
    reduction_method TEXT DEFAULT '',
    share_source TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    reduction_reason TEXT DEFAULT '',
    score INTEGER DEFAULT 0,
    score_detail TEXT DEFAULT '',
    contact_name TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    email TEXT DEFAULT '',
    wechat TEXT DEFAULT '',
    position TEXT DEFAULT '',
    match_type TEXT DEFAULT '',
    priority TEXT DEFAULT '低',
    status TEXT DEFAULT '新线索',
    next_followup TEXT DEFAULT '',
    retry_count INTEGER DEFAULT 0,
    last_action TEXT DEFAULT '',
    last_action_at TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(stock_code, shareholder, announcement_date)
);
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    result TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    next_followup TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (lead_id) REFERENCES leads(id)
);
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TEXT, target_dates TEXT,
    total_fetched INTEGER DEFAULT 0, total_parsed INTEGER DEFAULT 0,
    new_leads INTEGER DEFAULT 0, updated_leads INTEGER DEFAULT 0,
    duplicate_leads INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_code ON leads(stock_code);
CREATE INDEX IF NOT EXISTS idx_leads_priority ON leads(priority);
CREATE INDEX IF NOT EXISTS idx_leads_followup ON leads(next_followup);
CREATE INDEX IF NOT EXISTS idx_interactions_lead ON interactions(lead_id);
"""

MIGRATIONS = [
    "ALTER TABLE leads ADD COLUMN next_followup TEXT DEFAULT ''",
    "ALTER TABLE leads ADD COLUMN retry_count INTEGER DEFAULT 0",
    "ALTER TABLE leads ADD COLUMN last_action TEXT DEFAULT ''",
    "ALTER TABLE leads ADD COLUMN last_action_at TEXT DEFAULT ''",
    "ALTER TABLE leads ADD COLUMN notes TEXT DEFAULT ''",
]


@contextmanager
def get_db(db_path: str = None):
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str = None):
    with get_db(db_path) as conn:
        conn.executescript(SCHEMA)
        for sql in MIGRATIONS:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass
    print(f"✓ 数据库就绪: {db_path or DB_PATH}")


# ============================================================
# 线索 CRUD
# ============================================================

def _record_to_lead(rec: dict) -> dict:
    return {
        "stock_code": rec.get("股票代码", ""),
        "stock_name": rec.get("股票名称", ""),
        "shareholder": rec.get("股东名称", ""),
        "announcement_date": rec.get("公告日期", ""),
        "announcement_title": rec.get("公告标题", ""),
        "announcement_url": rec.get("公告链接", ""),
        "shareholder_type": rec.get("股东类型", ""),
        "reduction_shares": rec.get("减持数量(万股)", ""),
        "reduction_ratio": rec.get("减持比例(%)", ""),
        "reduction_method": rec.get("减持方式", ""),
        "share_source": rec.get("股份来源", ""),
        "start_date": rec.get("起始日期", ""),
        "end_date": rec.get("截止日期", ""),
        "reduction_reason": rec.get("减持原因", ""),
        "score": rec.get("总分", 0) or 0,
        "score_detail": rec.get("信号明细", ""),
        "contact_name": rec.get("联系人", ""),
        "phone": rec.get("手机", ""),
        "email": rec.get("邮箱", ""),
        "wechat": rec.get("微信", ""),
        "position": rec.get("职务", ""),
        "match_type": rec.get("匹配方式", ""),
        "priority": rec.get("优先级", "低"),
    }


def upsert_leads(records: list[dict], db_path: str = None) -> dict:
    stats = {"new": 0, "updated": 0, "skipped": 0}
    with get_db(db_path) as conn:
        for rec in records:
            lead = _record_to_lead(rec)
            if not lead["stock_code"] or not lead["shareholder"]:
                stats["skipped"] += 1
                continue
            existing = conn.execute(
                "SELECT id FROM leads WHERE stock_code=? AND shareholder=? AND announcement_date=?",
                (lead["stock_code"], lead["shareholder"], lead["announcement_date"])
            ).fetchone()
            if existing is None:
                cols = list(lead.keys())
                conn.execute(
                    f"INSERT INTO leads ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})",
                    list(lead.values()))
                stats["new"] += 1
            else:
                uf = ["stock_name","announcement_title","announcement_url",
                      "shareholder_type","reduction_shares","reduction_ratio",
                      "reduction_method","share_source","start_date","end_date",
                      "reduction_reason","score","score_detail",
                      "contact_name","phone","email","wechat","position",
                      "match_type","priority"]
                sets = ",".join([f"{f}=?" for f in uf])
                vals = [lead[f] for f in uf]
                vals += [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), existing["id"]]
                conn.execute(f"UPDATE leads SET {sets},updated_at=? WHERE id=?", vals)
                stats["updated"] += 1
    return stats


# ============================================================
# 跟进记录 + 状态自动流转
# ============================================================

def add_interaction(lead_id: int, action: str, result: str = "",
                    notes: str = "", next_followup: str = "",
                    db_path: str = None) -> bool:
    """
    添加跟进记录

    未接通: 自动递增 retry_count，自动排下次重拨(1/2/3天后)
    有意向/无意向/已签约: 自动流转状态
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db(db_path) as conn:
        lead = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        if not lead:
            print(f"⚠️ 线索 #{lead_id} 不存在")
            return False

        conn.execute(
            "INSERT INTO interactions (lead_id,action,result,notes,next_followup) VALUES (?,?,?,?,?)",
            (lead_id, action, result, notes, next_followup))

        updates = {"last_action": f"{action}:{result}" if result else action,
                   "last_action_at": now, "updated_at": now}

        # 状态流转
        new_status = RESULT_STATUS_MAP.get(result)
        if new_status:
            updates["status"] = new_status

        # 未接通: 累加重试 + 自动排下次
        if result == "未接通":
            retry = (lead["retry_count"] or 0) + 1
            updates["retry_count"] = retry
            if not next_followup and retry <= len(RETRY_INTERVALS):
                auto = (datetime.now() + timedelta(days=RETRY_INTERVALS[retry-1])).strftime("%Y-%m-%d")
                updates["next_followup"] = auto
                next_followup = auto
        elif result and result != "未接通":
            updates["retry_count"] = 0

        if next_followup:
            updates["next_followup"] = next_followup
        if result in ("已签约", "无意向", "已完成"):
            updates["next_followup"] = ""

        sets = ",".join([f"{k}=?" for k in updates])
        conn.execute(f"UPDATE leads SET {sets} WHERE id=?",
                     list(updates.values()) + [lead_id])
    return True


def update_status(lead_id: int, new_status: str, db_path: str = None) -> bool:
    if new_status not in LEAD_STATUSES:
        print(f"⚠️ 无效状态: {new_status}, 可选: {', '.join(LEAD_STATUSES)}")
        return False
    with get_db(db_path) as conn:
        conn.execute("UPDATE leads SET status=?,updated_at=datetime('now','localtime') WHERE id=?",
                     (new_status, lead_id))
    return True


def batch_update_status(lead_ids: list[int], new_status: str, db_path: str = None) -> int:
    if new_status not in LEAD_STATUSES:
        return 0
    with get_db(db_path) as conn:
        ph = ",".join(["?"]*len(lead_ids))
        conn.execute(f"UPDATE leads SET status=?,updated_at=datetime('now','localtime') WHERE id IN ({ph})",
                     [new_status]+lead_ids)
    return len(lead_ids)


# ============================================================
# 窗口期
# ============================================================

def get_window_phase(start_date: str, end_date: str) -> str:
    today = datetime.now().date()
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
        end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None
    except ValueError:
        return "未知"
    if not start and not end:
        return "未知"
    if start and today < start:
        return "未开窗"
    if end and today > end:
        return "已关窗"
    if start and end:
        remaining = (end - today).days
        elapsed = (today - start).days
        total = (end - start).days
        if remaining <= 7:
            return "即将关窗"
        if total > 0 and elapsed > total / 2:
            return "过半"
        return "已开窗"
    return "已开窗"


def _enrich(rows) -> list[dict]:
    results = [dict(r) for r in rows]
    for r in results:
        r["window_phase"] = get_window_phase(r.get("start_date",""), r.get("end_date",""))
    return results


# ============================================================
# 工作清单
# ============================================================

def get_todo(db_path: str = None) -> dict:
    """
    今日工作清单:
    1. new_leads: 新线索（有电话优先）
    2. followups: 到期跟进
    3. retries: 未接通重拨
    4. window_alerts: 窗口提醒（已开窗/即将关窗）
    """
    today = datetime.now().strftime("%Y-%m-%d")
    with get_db(db_path) as conn:
        new_leads = conn.execute("""
            SELECT * FROM leads WHERE status='新线索'
            ORDER BY CASE WHEN phone!='' THEN 0 ELSE 1 END, priority ASC, score DESC
            LIMIT 20""").fetchall()

        followups = conn.execute("""
            SELECT * FROM leads
            WHERE next_followup!='' AND next_followup<=?
              AND status NOT IN ('已签约','已完成','无意向','暂缓','新线索','未接通')
            ORDER BY next_followup ASC""", (today,)).fetchall()

        retries = conn.execute("""
            SELECT * FROM leads
            WHERE status='未接通' AND next_followup!='' AND next_followup<=?
            ORDER BY retry_count ASC""", (today,)).fetchall()

        active = conn.execute("""
            SELECT * FROM leads
            WHERE status IN ('新线索','未接通','已联系','有意向','方案沟通')
              AND start_date!='' AND end_date!=''""").fetchall()

    window_alerts = []
    for lead in active:
        phase = get_window_phase(lead["start_date"], lead["end_date"])
        if phase in ("已开窗", "即将关窗"):
            d = dict(lead)
            d["window_phase"] = phase
            window_alerts.append(d)

    seen = set()
    def _dedup(items):
        out = []
        for item in items:
            d = dict(item)
            if d["id"] not in seen:
                seen.add(d["id"])
                if "window_phase" not in d:
                    d["window_phase"] = get_window_phase(d.get("start_date",""), d.get("end_date",""))
                out.append(d)
        return out

    return {
        "new_leads": _dedup(new_leads),
        "followups": _dedup(followups),
        "retries": _dedup(retries),
        "window_alerts": _dedup(window_alerts),
    }


# ============================================================
# 查询
# ============================================================

def get_leads(status=None, priority=None, window_phase=None, limit=50, db_path=None):
    with get_db(db_path) as conn:
        sql, params = "SELECT * FROM leads WHERE 1=1", []
        if status:
            sql += " AND status=?"; params.append(status)
        if priority:
            sql += " AND priority=?"; params.append(priority)
        sql += f" ORDER BY score DESC, priority ASC, created_at DESC LIMIT {limit}"
        results = _enrich(conn.execute(sql, params).fetchall())
        if window_phase:
            results = [r for r in results if r["window_phase"]==window_phase]
        return results


def get_lead_detail(lead_id: int, db_path=None) -> dict | None:
    with get_db(db_path) as conn:
        lead = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        if not lead:
            return None
        result = dict(lead)
        result["window_phase"] = get_window_phase(result.get("start_date",""), result.get("end_date",""))
        ints = conn.execute("SELECT * FROM interactions WHERE lead_id=? ORDER BY created_at DESC",
                            (lead_id,)).fetchall()
        result["interactions"] = [dict(i) for i in ints]
        result["interaction_count"] = len(ints)
        return result


def get_followups(db_path=None):
    today = datetime.now().strftime("%Y-%m-%d")
    with get_db(db_path) as conn:
        return _enrich(conn.execute("""
            SELECT * FROM leads
            WHERE next_followup!='' AND next_followup<=?
              AND status NOT IN ('已签约','已完成','无意向')
            ORDER BY CASE status WHEN '未接通' THEN 1 ELSE 0 END, next_followup ASC
        """, (today,)).fetchall())


def get_stats(db_path=None):
    with get_db(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        status_counts = {r["status"]:r["cnt"] for r in conn.execute(
            "SELECT status, COUNT(*) as cnt FROM leads GROUP BY status")}
        priority_counts = {r["priority"]:r["cnt"] for r in conn.execute(
            "SELECT priority, COUNT(*) as cnt FROM leads GROUP BY priority")}
        all_leads = conn.execute("SELECT start_date, end_date FROM leads").fetchall()
        window_counts = {}
        for l in all_leads:
            p = get_window_phase(l["start_date"], l["end_date"])
            window_counts[p] = window_counts.get(p,0)+1
        week_ago = (datetime.now()-timedelta(days=7)).strftime("%Y-%m-%d")
        new_week = conn.execute("SELECT COUNT(*) FROM leads WHERE created_at>=?", (week_ago,)).fetchone()[0]
        total_int = conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
        today = datetime.now().strftime("%Y-%m-%d")
        today_int = conn.execute("SELECT COUNT(*) FROM interactions WHERE created_at>=?", (today,)).fetchone()[0]
        last_run = conn.execute("SELECT * FROM pipeline_runs ORDER BY created_at DESC LIMIT 1").fetchone()
        return {"total":total, "status":status_counts, "priority":priority_counts,
                "window":window_counts, "new_this_week":new_week,
                "total_interactions":total_int, "today_interactions":today_int,
                "last_run":dict(last_run) if last_run else None}


def get_funnel(db_path=None):
    """转化漏斗: 线索→已联系→有意向→方案沟通→已签约→已完成"""
    with get_db(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        contacted = conn.execute("SELECT COUNT(*) FROM leads WHERE status!='新线索'").fetchone()[0]
        interested = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE status IN ('有意向','方案沟通','已签约','执行中','已完成')").fetchone()[0]
        negotiating = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE status IN ('方案沟通','已签约','执行中','已完成')").fetchone()[0]
        signed = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE status IN ('已签约','执行中','已完成')").fetchone()[0]
        done = conn.execute("SELECT COUNT(*) FROM leads WHERE status='已完成'").fetchone()[0]

    stages = [("线索",total),("已联系",contacted),("有意向",interested),
              ("方案沟通",negotiating),("已签约",signed),("已完成",done)]
    return stages


def log_pipeline_run(target_dates, total_fetched, total_parsed, new, updated, duplicate, db_path=None):
    with get_db(db_path) as conn:
        conn.execute("""INSERT INTO pipeline_runs
            (run_date,target_dates,total_fetched,total_parsed,new_leads,updated_leads,duplicate_leads)
            VALUES (?,?,?,?,?,?,?)""",
            (datetime.now().strftime("%Y-%m-%d"), ",".join(target_dates),
             total_fetched, total_parsed, new, updated, duplicate))


def search_leads(keyword, db_path=None):
    with get_db(db_path) as conn:
        return _enrich(conn.execute("""
            SELECT * FROM leads
            WHERE stock_code LIKE ? OR stock_name LIKE ? OR shareholder LIKE ? OR contact_name LIKE ?
            ORDER BY score DESC LIMIT 50""", (f"%{keyword}%",)*4).fetchall())
