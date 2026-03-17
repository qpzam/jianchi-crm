"""
减持获客系统 v2.0

模块:
  config          - 统一配置
  utils/          - 公共工具 (stock, date_parser, io)
  cninfo_fetcher  - 巨潮网抓取
  pdf_parser      - 公告PDF解析 (regex + AI)
  contact_matcher - 联系方式匹配
  reduction_scorer - 减持概率评分
  pipeline        - 主管线 (串联以上所有)
"""
__version__ = "2.0.0"
