# 数据来源说明

本系统仅使用公开可访问的行情接口，不依赖任何付费数据服务。

---

## 主要数据源

### AKShare（首选）

- **用途**：全市场行情快照、K线历史、交易日历
- **安装**：`pip install akshare`
- **接口**：
  - `stock_zh_a_spot()` — 沪深京 A 股实时快照
  - `stock_zh_a_daily()` — 个股日线历史
  - `tool_trade_date_hist_sina()` — 交易日历

### 东方财富（备用）

- **用途**：行情快照备用源，部分字段（换手率/市值）更完整
- **限制**：部分环境下翻页不稳定，因此仅作 fallback

### 腾讯行情

- **用途**：单股价格交叉验证，用于数据健康检查

---

## 数据质量等级

| 等级 | 含义 | 对主榜的影响 |
|------|------|------------|
| `complete` | 快照、候选字段、风险检查均完整 | 正常出候选 |
| `partial` | 快照可用，公告/板块/执行质量不完整 | 主榜限 1 只或不出 |
| `stale` | 数据延迟或时间戳不明确 | 不出主榜候选 |
| `failed` | 数据源不可用 | 输出数据质量失败报告 |

---

## 数据完整性门控

每次运行 `monitor_data_health.py` 后生成 `data_health.json`：

```json
{
  "health_status": "ok",
  "can_rank_paper_watch": true,
  "snapshot_rows": 5527,
  "quote_source": "complete",
  "risk_check": "complete",
  "execution_check": "complete"
}
```

`can_rank_paper_watch=false` 时，系统不生成主榜候选，属于正常保护机制。

---

## 数据使用规范

- 每次报告保存原始快照到 `data/watchpool/<yyyymmdd>_<stage>/`
- 记录数据时间戳，防止跨日数据混用
- 不使用未经时间戳标注的数据
- 不将候选种子（`candidate_seed.csv`）直接等同于最终选股结果

---

## 新闻催化剂数据

`collect_policy_news.py` 采集以下维度：

| 类型 | 权重上限 | 说明 |
|------|---------|------|
| 政策级催化 | 中高 | 国家政策、央行动作等 |
| 行业级催化 | 中 | 行业景气、主题热点 |
| 公司级正面 | 低 | 业绩超预期、大订单等 |
| 公司级负面 | 覆盖 | 直接降级候选（不受权重限制） |
| 情绪/传言 | 极低 | 仅作参考，不加分 |

> 新闻数据质量标记为 `partial` 时（部分新闻源失败），主榜额外限制为 1 只。
