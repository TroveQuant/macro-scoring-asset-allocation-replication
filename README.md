# 资产配置宏观打分策略

这是从既有研究 notebook 提取出的、可独立运行的工程化项目。生产入口会在每次运行时下载真实市场数据、重算信号和回测并生成报告；不会读取历史 CSV、PNG、Excel 或 notebook 输出冒充本次结果。

> 当前状态：**公开数据 practical adaptation 已可复现运行**。由于原始专有宏观数据库、点时版本和资产定义没有完整授权说明，本项目不声称严格复现原模型的唯一收益路径，也不构成投资建议。

## 策略与调用链

```text
run_replication.py
  → 配置及资产键校验
  → Yahoo 调整价真实数据下载、SHA-256 manifest
  → 月末对齐及因果滚动去极值/标准化
  → 国内、全球、风险、美元与 AR 信号
  → 原方向权重汇总为资产仓位
  → 原组合权重 × 仓位（默认 allow_short=false 仅做多，负仓位截断为 0；true 为原始多空实现，仅作对照）
  → 信号后一期执行、显式 BIL 现金、10bp 换手成本
  → 同资产固定权重 benchmark
  → 指标、图表、JSON/HTML/Markdown 报告
```

原组合基准权重保持为：A 股 10%、中国债券 40%、美股 5%、黄金 30%、原油 5%、信用债 10%。资产信号方向权重保持在 `config/base.yml`。FX 单项不再内部滞后，所有资产仅在组合层统一滞后一期，避免双重滞后。

## 真实数据与资产定义

运行时从 Yahoo Finance chart endpoint 获取调整价，不提交上游原始快照；`outputs/input_manifest.json` 记录请求 URL、获取时间、行数、覆盖期、缓存路径和 SHA-256。

| 策略资产 | 代理 | 解释 |
|---|---|---|
| CH_EQUITY | ASHR | 沪深 300 A 股 ETF，作为原 CSI800 的实务代理 |
| CH_BOND | CBON | 中国债券 ETF 调整价；未把债券收益率水平当收益 |
| US_EQUITY | SPY | 标普 500 ETF |
| GOLD | GLD | 黄金 ETF |
| OIL | USO | 原油期货基金，提供真实月度可交易代理 |
| CREDIT | VCSH | 短久期投资级信用债 ETF，依据原 notebook “短融”注释 |
| CASH | BIL | 未配置风险预算的显式现金代理 |

`CREDIT` 与 `SHORT_BOND` 没有被强行等同：原材料的组合键是 `CREDIT`，而 `SHORT_BOND` 对应代码注释为“短融”，因此统一命名为信用债仓位。VCSH 是 practical adaptation，并非原模型唯一正确映射。benchmark 是相同六类风险资产的固定基准权重月度组合，用来隔离宏观择时影响。

宏观统计数据缺少可靠历史发布日期和未修订 vintages，因此生产版使用带交易时间戳的市场隐含代理（ASHR、CNY=X、VCSH/CBON、SPY、USO/GLD、HG=F/GC=F、TLT/BIL、DX-Y.NYB、^VIX）。它们只在月末收盘后形成信号并在下一交易月执行，不声称等同原始统计因子。完整公式见 `docs/backtest_methodology.md`。

## 安装与运行

需要 Python 3.12。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe run_replication.py --config config/base.yml
.venv\Scripts\python.exe tools/validate_backtest.py
.venv\Scripts\python.exe tools/summarize_exposure.py
```

`tools/summarize_exposure.py` 只读取 `outputs/allocation_weights.csv`，打印平均净/总/多头/空头敞口和平均现金，不下载数据、不改写输出。

当前配置固定数据截止日为 2026-08-31，以确保本地与 Actions 得到相同月份范围。上游请求失败、数据陈旧、键不一致、重复日期、缺失收益或非有限结果都会返回非零退出码，且不会采用随机/演示/合成回退。

## 当前真实回测

当前提交内结果由 `python run_replication.py --config config/base.yml` 在默认仅做多配置（`allow_short: false`）下基于 Yahoo Finance 真实调整价重新计算生成，并通过 `python tools/validate_backtest.py --require-current-run` 全部 12 项回测不变量、仅做多约束及敞口指标复核。回测区间为 `2018-01-31` 至 `2026-08-31`，共 104 个月：

| 指标 | 策略 (`allow_short=false`) | 固定权重 Benchmark (100% 满仓) |
| --- | --- | --- |
| 累计收益率 (`cumulative_return`) | `38.58%` | `98.00%` |
| 年化收益率 (`annualized_return`) | `3.84%` | `8.20%` |
| 年化波动率 (`annualized_volatility`) | `3.16%` | `7.83%` |
| 夏普比率 (`sharpe_ratio`, `rf=0`) | `1.21` | `1.05` |
| 索提诺比率 (`sortino_ratio`, `rf=0`) | `2.46` | `1.91` |
| 最大回撤 (`max_drawdown`) | `-5.94%` | `-13.74%` |
| 卡玛比率 (`calmar_ratio`) | `0.65` | `0.60` |
| 月度胜率 (`monthly_win_rate`) | `75.00%` | — |
| 年化换手率 (`annualized_turnover`) | `1.65` | — |
| 累计交易成本 (`total_transaction_cost`) | `1.43%` | — |
| 平均净/总/多头风险敞口 | `22.46%` / `22.46%` / `22.46%` | `100.00%` |
| 平均空头敞口 / 平均现金权重 (`BIL`) | `0.00%` / `77.54%` | `0.00%` / `0.00%` |

测试 fixture 只存在于 `tests/` 下（`tests/fixtures` 及离线流水线测试中生成的确定性价格，仅写入 pytest 临时目录），生产入口不会读取；测试通过不代表原模型严格复现成功。

生成文件包括绩效、月收益、净值、权重、宏观得分、调仓记录、输入 manifest、三张图和三种报告格式，均在 `outputs/`。

## 仓位、敞口与 benchmark 可比性

- 资产仓位范围为 [-1,1]，乘以原固定组合权重得到目标权重。原研究为仅做多，因此默认 `project.allow_short: false`（缺省该键时同样按 `false`）：负仓位截断为 0，释放的预算留在 BIL 现金。
- `project.allow_short: true` 只用于与原始多空实现对照，不作为正式结果：负仓位即做空该资产（例如旧多空输出中 2018-01 黄金为 -30%），空头名义金额占用等额现金预算，卖空所得不计息，也未计融券费用。报告会标明“允许做空：是（原始多空实现，仅作对照）”。
- 现金权重 `CASH = 1 - 风险资产权重绝对值之和`，由 BIL 代理。
- 按当前 `outputs/allocation_weights.csv`（默认仅做多 `allow_short=false`，2018-01 至 2026-08，104 个月）计算：平均净风险敞口 `22.46%`，平均总敞口 `22.46%`（多头 `22.46%`、空头 `0.00%`），平均现金 `77.54%`，持空月份占比 `0.00%`（原始多空实现对照下平均净敞口为 `1.5%`、总敞口 `43.5%`、现金 `56.5%`）。复核命令：`python tools/summarize_exposure.py`。
- benchmark 是同六类资产按原权重 100% 满仓的多头组合（净敞口 100%，无现金）。即使仅做多，策略平均净敞口（`22.46%`）也明显低于 100%，因此两者风险敞口不可比：策略相对 benchmark 的超额收益同时包含敞口差异（含现金拖累）和择时贡献，不能直接解读为宏观择时 alpha。比较时应同时参考敞口指标、波动率和夏普比率。
- `average_net_exposure`、`average_gross_exposure`、`average_long_exposure`、`average_short_exposure`、`average_cash_weight` 已写入 `performance_metrics.csv` 和三种报告，并在 `report.json` 的 `run.allow_short` 记录本次设置；报告“方法与限制”披露做空处理和上述可比性说明。`tools/validate_backtest.py` 按 `run.allow_short` 检查仅做多约束，并用权重文件独立复算敞口指标。

## GitHub Actions

工作流 `Macro allocation replication` 仅支持 `workflow_dispatch`。选择 `run_replication=true` 后会安装固定依赖、运行结构及敏感信息检查和 pytest、删除批准的旧输出、下载真实数据、执行正式入口、复算 12 项回测不变量（`--require-current-run`：并要求敞口指标和 `run.allow_short` 存在且与配置一致、仅做多时无负权重）、验证报告、上传完整 Artifact，并只显式提交批准的输出；不使用 `continue-on-error`、schedule、Pages、邮件、虚构 Secret 或 `git add --all`。

另有 `Tests` 工作流（`.github/workflows/tests.yml`），只在 pull request 和手动触发时运行：安装固定依赖、`pip check`、配置校验、全部离线 pytest 和上传白名单扫描。它只有 `contents: read` 权限，不下载行情、不使用 Secret、不提交任何文件。

## 复现限制与许可

- Yahoo 调整价是总收益近似，可交易代理的管理费、跟踪误差与上市前历史都会影响结果。
- 市场隐含代理避免统计数据修订的前视问题，但改变了原统计宏观指标的经济含义，属于明确适配。
- ASHR 不是 CSI800，CBON/VCSH 也未被证明是原研究使用的指数。
- 上游数据使用与再分发受其条款约束；仓库不提交原始运行时缓存。
- 原始四个本地数据文件来源与公开许可仍未确认，保留在本地并由 `.gitignore` 排除。
- 项目许可证待所有者确认；未擅自添加开源许可证。

本机搜索、历史文件登记和上传白名单分别见 `docs/local_data_inventory.csv`、`docs/legacy_manifest.json` 和 `docs/upload_candidates.txt`。
