# ticker_scan.py — 数据层说明

## 为什么不直接在 Skill 里用 yfinance？

Claude Code Skill（`.claude/commands/*.md`）运行时是 LLM 在读文件、调工具——它**不能执行 Python**，也没有 Python 运行时。

yfinance 是 Python 库，必须由 Python 进程调用。所以流程是：

```
/ticker-scan
  └─ Step 1: bash → python scripts/ticker_scan.py MRVL MU ... --json
               └─ yfinance 拉数据，计算指标，输出 JSON
  └─ Step 2: LLM 读 JSON，做定性分析，输出报告
```

两层分离：**Python 管数字，LLM 管判断**。

---

## ticker_scan.py 封装了什么？

直接用 yfinance 有几个问题，脚本统一处理了：

| 问题 | yfinance 原始 | ticker_scan.py 做了什么 |
|------|-------------|----------------------|
| 字段名不稳定 | `.info` 有 200+ 字段，版本间变化 | 只提取需要的字段，做 null 兜底 |
| 营收要自己算 | `.quarterly_financials` 返回 DataFrame | 算好 YoY %、加速度、连续季度数 |
| OTC 判断复杂 | `exchange` 值多样（OTC/PNK/GREY/BTS…）| `_is_otc()` 统一判断，直接给 `is_otc: bool` |
| MA 要手算 | `.history()` 只给原始价格 | 算好 MA50/MA200，输出偏离百分比 |
| 并发慢 | 单线程串行，10 只股 ~60s | `ThreadPoolExecutor` 并发，~10s |
| 编码报错 | Windows 默认 cp1252，中文/特殊字符崩 | `sys.stdout.reconfigure(encoding="utf-8")` |

---

## 输出字段说明

```json
{
  "ticker": "MRVL",
  "exchange": "NMS",           // 交易所代码
  "is_otc": false,             // true = OTC，ticker-scan 会排除
  "market_cap_m": 44200.0,    // 市值（百万美元）
  "revenue_yoy_pct": 37.5,   // 最新季度营收 YoY %（null = 数据不足）
  "revenue_accel": true,      // 营收增速是否在加快
  "consecutive_growth_q": 4,  // 连续几个季度营收正增长
  "eps_trend": "improving",   // loss→profit / profit→loss / improving / declining / stable / unknown
  "inst_pct": 71.3,           // 机构持仓 %（null = 无数据）
  "ma50_pct": 4.2,            // 现价偏离 MA50 %（正数 = 在 MA50 上方）
  "ma200_pct": 18.7,          // 现价偏离 MA200 %（null = 上市不足 200 天）
  "max_gap_up_pct": 14.2      // 过去 1 年最大单日跳空高开 %（财报 gap 信号）
}
```

---

## 用法

```bash
# 基本用法：传 ticker，人类可读输出
python scripts/ticker_scan.py MRVL MU QMCO

# JSON 模式：供 Skill/LLM 解析
python scripts/ticker_scan.py MRVL MU QMCO --json

# 单股验证
python scripts/ticker_scan.py LWLG --json
```

---

## 局限

- 数据来自 yfinance（Yahoo Finance），有时延（非实时），偶尔字段缺失
- `revenue_yoy_pct` 需要至少 5 个季度数据，新股/新上市可能为 null
- `inst_pct` 需要额外 HTTP 请求（较慢），小市值股可能无机构持仓数据
- 不含实时新闻、订单 backlog、机构 13F 变化——这些由 LLM + WebSearch 处理
