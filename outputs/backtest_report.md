# 本次回测报告

本报告由当前运行的真实市场数据重新计算；它是原策略思想的 practical adaptation，不是原始专有宏观数据库的严格复现。

## 绩效

| 指标 | 值 |
|---|---:|
| data_cutoff_date | 2026-08-31 |
| backtest_start | 2018-01-31 |
| backtest_end | 2026-08-31 |
| observations | 104 |
| cumulative_return | 0.3858396710182004 |
| annualized_return | 0.038368485383365014 |
| annualized_volatility | 0.03164381685736644 |
| sharpe_ratio | 1.212511295849986 |
| max_drawdown | -0.05942130403086565 |
| monthly_win_rate | 0.75 |
| rebalance_count | 104 |
| annualized_turnover | 1.649230769230769 |
| total_transaction_cost | 0.014293333333333332 |
| benchmark_cumulative_return | 0.9799513615747009 |
| benchmark_annualized_return | 0.0820052496935797 |
| excess_cumulative_return | -0.5941116905565005 |
| excess_annualized_return | -0.04363676431021468 |
| average_net_exposure | 0.22461996336996337 |
| average_gross_exposure | 0.22461996336996337 |
| average_long_exposure | 0.22461996336996337 |
| average_short_exposure | 0.0 |
| average_cash_weight | 0.7753800366300366 |

## 复现限制

- CREDIT 依据原注释‘短融’使用 VCSH；没有与 SHORT_BOND 或现金合并。
- CBON、VCSH 等调整价是可交易代理，不等于原研究的唯一正确资产定义。
- 宏观输入改用带时间戳的市场隐含代理，因此不存在统计数据修订值，但不能代表原始统计宏观因子。
- Yahoo 原始数据只在运行时获取且不随仓库再分发；上游可用性与条款可能变化。
- 测试通过只说明工程约束成立，不等于原策略收益得到严格复现。
- allow_short=false（默认，原研究为仅做多）：负仓位截断为 0，对应预算留在现金代理。
- 策略平均净风险敞口 22.5%、平均总敞口 22.5%、平均现金 77.5%；benchmark 为 100% 满仓的固定权重多头组合；策略净敞口明显低于 100% 时，超额收益同时包含敞口差异（含现金拖累）与择时贡献，不能直接解读为择时 alpha。
