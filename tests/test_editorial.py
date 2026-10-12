import json

from ppt_generate.core.editorial import review_editorial


def test_observed_instruction_disclosure_and_duplicate_failures():
    deck = {
        "slides": [
            {
                "layout": "bullets",
                "title": "经营摘要",
                "bullets": ["收入150万元", "客户300家", "毛利率62%"],
            },
            {
                "layout": "bullets",
                "title": "模拟数据与来源",
                "bullets": [
                    "所有数字与计划均为模拟数据",
                    "来源：synthetic operating ledger",
                    "示例企业面向管理层",
                    "不添加未提供指标或事实",
                ],
            },
            {
                "layout": "bullets",
                "title": "Q3 模拟经营摘要",
                "bullets": ["Q3收入150万元", "Q3客户300家", "Q3毛利率62%"],
            },
        ]
    }
    report = review_editorial(deck)
    assert report["status"] == "issues_found"
    assert {(x["page"], x["code"]) for x in report["issues"]} == {
        (2, "instruction_echo"),
        (2, "disclosure_only"),
        (3, "duplicate_content"),
    }
    assert "收入150万元" not in json.dumps(report, ensure_ascii=False)


def test_disclosures_in_notes_and_footer_are_not_rejected():
    deck = {
        "slides": [
            {"layout": "cover", "title": "Report", "subtitle": "Simulated data"},
            {
                "layout": "bullets",
                "title": "Results",
                "bullets": ["Revenue 150"],
                "notes": "Never invent data",
                "source": "Synthetic ledger",
            },
            {
                "layout": "table",
                "title": "Comparison",
                "headers": ["Quarter", "Revenue"],
                "rows": [["Q3", "150"]],
                "source": "Synthetic ledger",
            },
        ]
    }
    assert review_editorial(deck)["status"] == "passed"


def test_distinct_pages_with_shared_metric_are_allowed():
    deck = {
        "slides": [
            {
                "layout": "bullets",
                "title": "Executive summary",
                "bullets": ["Revenue increased to 150", "Customers increased to 300"],
            },
            {
                "layout": "bullets",
                "title": "Renewals",
                "bullets": [
                    "Contact all 300 customers one month ahead",
                    "Owner reviews renewals weekly",
                ],
            },
        ]
    }
    assert review_editorial(deck)["status"] == "passed"
