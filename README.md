# Stock Analysis Lite — Session 3 课程工具包

Session 3「AI 炒股分析系统」配套工具包。包含 4 个核心 skills，只需 yfinance，无需配置复杂 MCP。

## 快速开始

**Step 1：安装依赖**
```bash
pip install yfinance pandas
```

**Step 2：用 Claude Code 打开这个文件夹**
Claude Code → File → Open Folder → 选这个文件夹

**Step 3：跑第一条命令**
在 Claude Code 对话框输入：
```
/ticker-scan
```

## 包含的 Skills

| 命令 | 用途 |
|------|------|
| `/ticker-scan` | 扫 热门赛道方法论 7 大赛道，筛出候选股 |
| `/stock-analyze <TICKER>` | 个股基本面 + 技术面深度分析 |
| `/stock-entry <TICKER>` | 入场区间、止损位、仓位建议 |
| `/stock-exit <TICKER>` | 止盈条件、减仓逻辑 |

## 参考资料

| 文件 | 用途 |
|------|------|
| `wiki/frameworks/hot-sector-method.md` | 热门赛道方法论 方法论：七大赛道 + 九大翻倍股特征 |
| `wiki/frameworks/sepa.md` | SEPA：技术面入场标准（Stage 2 / 趋势模板）|
| `wiki/frameworks/bait.md` | BAIT：基本面评分框架 |
| `wiki/frameworks/moneyball.md` | Moneyball：非对称风险计算 + 退出逻辑 |
| `wiki/frameworks/synthesis.md` | 五框架协作总览 |

## 课后作业

参考 `homework-guide.md`：用 Claude Code 建一个自己的 `/market-daily` skill。
