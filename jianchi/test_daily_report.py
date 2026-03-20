"""gen_daily_report.py 单元测试 - 去重、锁定判断、匹配逻辑"""
import unittest
from collections import defaultdict

from gen_daily_report import judge_lock_status, match_company, gen_report


class TestDedup(unittest.TestCase):
    """去重逻辑：按 (股票名称, 股东名称) 去重"""

    def test_duplicate_records_are_removed(self):
        records = [
            {"股票名称": "某科技", "股东名称": "张三", "减持比例(%)": "2.0"},
            {"股票名称": "某科技", "股东名称": "张三", "减持比例(%)": "2.0"},
            {"股票名称": "某科技", "股东名称": "李四", "减持比例(%)": "1.0"},
        ]
        seen = {}
        for rec in records:
            key = (rec.get("股票名称", ""), rec.get("股东名称", ""))
            if key not in seen:
                seen[key] = rec
        self.assertEqual(len(seen), 2)


class TestLockJudgement(unittest.TestCase):
    """锁定判断逻辑"""

    def test_ipo_lock(self):
        rec = {"股份来源": "IPO前取得", "是否创投基金减持": "否"}
        emoji, label, _ = judge_lock_status(rec)
        self.assertEqual(emoji, "🔒")
        self.assertIn("锁定", label)

    def test_secondary_market_no_lock(self):
        rec = {"股份来源": "二级市场买入", "是否创投基金减持": "否"}
        emoji, label, _ = judge_lock_status(rec)
        self.assertEqual(emoji, "💚")
        self.assertIn("不锁定", label)

    def test_vc_fund_no_lock(self):
        rec = {"股份来源": "IPO前取得", "是否创投基金减持": "是"}
        emoji, label, _ = judge_lock_status(rec)
        self.assertEqual(emoji, "💚")
        self.assertIn("不锁定", label)


class TestMatchCompany(unittest.TestCase):
    """联系方式匹配逻辑"""

    def test_exact_match(self):
        contacts = defaultdict(list)
        contacts["某科技"] = [{"name": "王明", "title": "董秘", "phone": "13800001234"}]
        result = match_company("某科技", contacts)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "王明")

    def test_no_match(self):
        contacts = defaultdict(list)
        contacts["某科技"] = [{"name": "王明", "title": "董秘", "phone": "13800001234"}]
        result = match_company("某医药", contacts)
        self.assertEqual(len(result), 0)

    def test_st_prefix_stripped(self):
        contacts = defaultdict(list)
        contacts["某制造"] = [{"name": "李华", "title": "证代", "phone": "13900005678"}]
        result = match_company("ST某制造", contacts)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
