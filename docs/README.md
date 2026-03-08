# ETFTool 文档中心

欢迎来到 ETFTool 项目文档中心。本文档提供了项目所有文档的导航和组织说明。

## 📚 快速导航

### 新手入门
- [项目主文档](../README.md) - 项目概述、功能介绍、快速开始
- [产品需求文档 (PRD)](planning/PRD.md) - 产品功能需求和规格说明
- [项目规划 (PLAN)](planning/PLAN.md) - 项目开发计划和路线图

### 部署运维
- [Docker 部署指南](deployment/docker-guide.md) - Docker 容器化部署说明
- [Docker 多架构支持](deployment/docker-multiarch-guide.md) - 多平台镜像构建指南
- [远程调试配置](deployment/remote-debug.md) - 生产环境远程调试指南
- [GitHub Actions 配置指南](deployment/github-actions-setup.md) - CI/CD 自动化构建配置
- [Docker 统一设计](deployment/docker-unified-design.md) - Docker 架构设计文档
- [Docker 多平台设计](deployment/docker-multiplatform-design.md) - 多平台构建设计方案

### 项目规划
- [产品需求文档 (PRD)](planning/PRD.md) - 完整的产品需求规格
- [项目开发计划 (PLAN)](planning/PLAN.md) - 开发路线图和里程碑
- [功能路线图 (FEATURE-ROADMAP)](planning/FEATURE-ROADMAP.md) - 新功能规划与优先级
- [到价提醒设计评审](planning/2026-03-08-price-alert-design-review.md) - 到价提醒设计缺陷与修订建议

### 技术研究
- [ETF 估值研究](research/etf-valuation-research.md) - ETF 估值方法和指标研究
- [PE 分位数研究](research/pe-percentile-research.md) - PE 分位数计算和应用研究

## 📁 文档分类

### planning/ - 规划类文档
项目规划、产品需求等战略性文档。

**文档列表：**
- `PRD.md` - 产品需求文档
- `PLAN.md` - 项目开发计划
- `FEATURE-ROADMAP.md` - 新功能规划与优先级路线图
- `2026-03-08-price-alert-design-review.md` - 到价提醒设计评审与修订清单

### research/ - 研究类文档
技术研究、算法分析、业务逻辑研究等。

**文档列表：**
- `etf-valuation-research.md` - ETF 估值研究
- `pe-percentile-research.md` - PE 分位数研究

### design/ - 设计文档
功能设计、架构设计、技术方案设计等。

**文档列表：**
- `2026-01-24-grid-trading-suggestion-design.md` - 网格交易建议设计
- `2026-01-25-frontend-design-upgrade.md` - 前端设计升级方案
- `2026-01-25-phase1-security-hardening-design.md` - 第一阶段安全加固设计
- `2026-01-26-etf-index-mapper-design.md` - ETF 指数映射器设计
- `2026-01-29-metrics-cache-design.md` - 指标缓存设计
- `2026-01-29-trend-temperature-design.md` - 趋势温度设计
- `2026-01-29-watchlist-compact-indicators.md` - 自选列表紧凑指标设计
- `2026-02-03-alert-notification-design.md` - 告警通知设计
- `2026-02-04-admin-system-design.md` - 管理系统设计
- `2026-02-06-admin-frontend-design.md` - 管理员前端界面设计
- `2026-02-04-alert-optimization-design.md` - 告警优化设计
- `alert-intraday-check-design.md` - 告警盘中检查设计
- `grid-performance-optimization.md` - 网格性能优化设计
- `2026-02-07-daily-summary-design.md` - 每日市场摘要推送设计
- `2026-02-08-fund-flow-analysis-design.md` - ETF 资金流向分析设计
- `2026-02-10-etf-auto-classification-design.md` - ETF 自动分类标签设计

### implementation/ - 实现计划
具体功能的实现步骤、技术细节、代码结构等。

**文档列表：**
- `2026-01-24-grid-suggestion-implementation.md` - 网格建议实现计划
- `2026-01-27-etf-index-mapper-impl.md` - ETF 指数映射器实现
- `2026-01-29-metrics-cache-impl.md` - 指标缓存实现
- `2026-01-29-trend-temperature-impl.md` - 趋势温度实现
- `2026-01-30-grid-cache-phase1.md` - 网格缓存第一阶段实现
- `2026-02-03-alert-intraday-check-impl.md` - 告警盘中检查实现
- `2026-02-03-alert-notification-impl.md` - 告警通知实现
- `2026-02-05-github-actions-docker-build.md` - GitHub Actions Docker 多平台构建实现
- `2026-02-06-admin-frontend-impl.md` - 管理员前端界面实现
- `2026-02-07-daily-summary-impl.md` - 每日市场摘要推送实现
- `2026-02-09-fund-flow-analysis-impl.md` - ETF 资金流向分析实现

### deployment/ - 部署文档
部署指南、运维手册、环境配置等。

**文档列表：**
- `docker-guide.md` - Docker 部署指南
- `docker-multiarch-guide.md` - Docker 多架构支持指南
- `remote-debug.md` - 生产环境远程调试配置
- `github-actions-setup.md` - GitHub Actions CI/CD 配置指南
- `docker-unified-design.md` - Docker 统一设计方案
- `docker-multiplatform-design.md` - Docker 多平台设计方案

### testing/ - 测试报告
测试计划、测试报告、测试结果等。

**文档列表：**
- `alert-notification-test-report.md` - 告警通知测试报告
- `alert-scheduler-test-report.md` - 告警调度器测试报告
- `auth-flow-test-report.md` - 认证流程测试报告

## 📝 文档命名规范

为了保持文档的一致性和可维护性，请遵循以下命名规范：

| 文档类型 | 命名格式 | 示例 |
|---------|---------|------|
| 设计文档 | `YYYY-MM-DD-feature-design.md` | `2026-02-04-admin-system-design.md` |
| 实现计划 | `YYYY-MM-DD-feature-impl.md` 或 `YYYY-MM-DD-feature-implementation.md` | `2026-02-03-alert-notification-impl.md` |
| 测试报告 | `feature-test-report.md` | `auth-flow-test-report.md` |
| 研究文档 | `topic-research.md` | `etf-valuation-research.md` |
| 部署指南 | `platform-guide.md` 或 `topic-design.md` | `docker-guide.md` |

**命名原则：**
- 使用小写字母和连字符（kebab-case）
- 设计和实现文档使用日期前缀（YYYY-MM-DD）便于追溯
- 使用描述性的功能名称
- 文件扩展名统一使用 `.md`

## 🔍 文档查找指南

### 按需求查找

**我想了解项目整体情况**
→ 阅读 [项目主文档](../README.md) 和 [PRD](planning/PRD.md)

**我想部署项目**
→ 查看 [deployment/](deployment/) 目录下的部署指南

**我想了解某个功能的设计**
→ 在 [design/](design/) 目录中搜索相关功能名称

**我想了解某个功能的实现细节**
→ 在 [implementation/](implementation/) 目录中查找对应的实现文档

**我想了解测试情况**
→ 查看 [testing/](testing/) 目录下的测试报告

**我想了解技术原理**
→ 查看 [research/](research/) 目录下的研究文档

### 按时间查找

设计文档和实现文档使用日期前缀，可以按时间顺序查看项目演进：

```bash
# 查看最近的设计文档
ls -lt docs/design/

# 查看最近的实现文档
ls -lt docs/implementation/
```

## 🤝 贡献指南

### 创建新文档

1. **确定文档类型**：根据文档内容选择合适的目录
2. **遵循命名规范**：使用上述命名规范命名文件
3. **更新本索引**：在相应分类下添加文档链接
4. **提交变更**：使用清晰的 commit message

### 更新现有文档

1. **直接编辑**：修改对应的文档文件
2. **保持一致性**：遵循原有的格式和风格
3. **更新日期**：在文档中标注更新日期（如适用）
4. **提交变更**：说明更新内容

### 文档维护原则

- **及时更新**：代码变更后及时更新相关文档
- **保持同步**：确保文档与实际实现保持一致
- **清晰简洁**：使用清晰的语言，避免冗余
- **结构化**：使用标题、列表、表格等组织内容
- **中文优先**：项目文档使用中文撰写，专业术语可保留英文

## 📖 相关资源

- [项目主仓库](https://github.com/yourusername/ETFTool)
- [CHANGELOG](../CHANGELOG.md) - 版本变更记录
- [AGENTS.md](../AGENTS.md) - AI 协作上下文和开发规范
- [CODE_NAVIGATION.md](../CODE_NAVIGATION.md) - 代码导航参考（前后端关键文件、配置文件、常见任务）
- [API_REFERENCE.md](../API_REFERENCE.md) - API 接口参考（完整端点列表）

---

**最后更新：** 2026-02-13
