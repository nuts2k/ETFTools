# ETFTools 项目改进计划

> 基于代码库质量分析生成的最佳实践改进路线图
> 生成时间: 2026-01-24

---

## 📊 项目现状总结

**项目类型**: 全栈 ETF 分析工具  
**技术栈**: 
- 后端: Python + FastAPI + SQLModel + AkShare
- 前端: Next.js 16 + React 19 + TypeScript + Tailwind CSS

**代码规模**:
- 后端: ~1,589 行 Python 代码
- 前端: ~2,587 行 TypeScript/TSX 代码
- 测试覆盖: ❌ 无测试文件

**综合评分**: ⭐⭐⚪⚪⚪ (2.2/5)

| 维度 | 评分 | 说明 |
|------|------|------|
| 代码质量 | ⭐⭐⭐⚪⚪ (3/5) | 架构清晰，但存在过长函数和重复代码 |
| 类型安全 | ⭐⭐⭐⚪⚪ (3/5) | TS严格模式开启，但Python类型注解不完整 |
| 错误处理 | ⭐⭐⚪⚪⚪ (2/5) | 有回退机制，但异常捕获过于宽泛 |
| 安全性 | ⭐⚪⚪⚪⚪ (1/5) | ❌ 硬编码密钥、CORS过宽，存在严重风险 |
| 测试覆盖 | ⚪⚪⚪⚪⚪ (0/5) | ❌ 完全无测试 |
| 依赖管理 | ⭐⭐⭐⭐⚪ (4/5) | 依赖组织良好，但缺少版本锁定 |

---

## 🎯 改进计划概览

### 🔴 阶段一: 安全加固 (P0 - 立即执行)

**目标**: 修复严重安全漏洞，确保基础安全  
**工时**: 1-2 天  
**详细设计**: 参见 [`docs/design/2026-01-25-phase1-security-hardening-design.md`](../design/2026-01-25-phase1-security-hardening-design.md)

#### 设计原则
- **环境分离优先**: 通过 `.env` 文件区分开发和生产配置
- **最小影响原则**: 改动集中在配置层，不修改业务逻辑
- **渐进式防御**: 先保护关键端点，再逐步扩展
- **开发友好**: 支持局域网访问，速率限制可选启用

#### 1. 环境变量管理
- **问题**: `SECRET_KEY` 硬编码在代码中
- **位置**: `backend/app/services/auth_service.py:10`
- **风险等级**: 🔴 CRITICAL
- **影响**: JWT 可被伪造，用户会话可被劫持
- **解决方案**: 
  - 使用 `.env` 文件 + `pydantic-settings` 管理配置
  - 创建 `.env.example` 作为配置模板
  - 提供 `scripts/generate_secret.py` 生成安全密钥
  - 启动时验证配置有效性（SECRET_KEY 长度、环境匹配等）
- **任务**:
  - [ ] 创建 `.env.example` 配置模板
  - [ ] 生成 SECRET_KEY 并创建本地 `.env`
  - [ ] 安装 `pydantic-settings` 和 `python-dotenv`
  - [ ] 重构 `backend/app/core/config.py` 使用 Pydantic Settings
  - [ ] 修改 `auth_service.py` 从配置读取 SECRET_KEY
  - [ ] 添加配置验证逻辑（启动时检查）

#### 2. CORS 配置优化
- **问题**: CORS 允许所有来源 `["*"]`
- **位置**: `backend/app/core/config.py:9`
- **风险等级**: 🔴 HIGH
- **影响**: 易受 CSRF 攻击
- **需求**: 支持本地开发 + 局域网多设备访问（手机/平板）
- **解决方案**:
  - 明确白名单：`localhost:3000`, `127.0.0.1:3000`
  - 正则匹配局域网 IP：`192.168.x.x:3000`（仅开发环境）
  - 生产环境强制禁止 `*` 和宽松策略
  - 配置 `uvicorn` 监听 `0.0.0.0` 允许局域网访问
- **任务**:
  - [ ] 更新 `main.py` 的 CORS 中间件配置
  - [ ] 添加 `allow_origin_regex` 支持局域网 IP
  - [ ] 配置 `BACKEND_HOST=0.0.0.0` 允许外部访问
  - [ ] 添加环境区分逻辑（开发/生产）

#### 3. 修复缺失依赖
- **问题**: 代码使用但未在 `pyproject.toml` 中声明的依赖
- **缺失包**: `pydantic-settings`, `python-dotenv`, `bcrypt`, `slowapi`
- **风险等级**: 🟡 MEDIUM
- **影响**: 部署失败，环境不一致
- **解决方案**:
  - 在 `pyproject.toml` 中明确所有依赖
  - 为关键依赖（akshare）添加版本约束
  - 生成 `requirements.txt` 锁定精确版本
  - 提供 `scripts/freeze_requirements.sh` 自动化脚本
- **任务**:
  - [ ] 更新 `pyproject.toml` 添加所有缺失依赖
  - [ ] 为 `akshare` 添加版本约束 `>=1.12.0,<2.0.0`
  - [ ] 创建 `scripts/freeze_requirements.sh` 脚本
  - [ ] 生成 `requirements.txt` 锁定版本
  - [ ] 更新开发依赖（pytest-cov, pytest-asyncio 等）

#### 4. 添加速率限制（关键端点优先）
- **问题**: API 端点无速率限制
- **风险等级**: 🟡 MEDIUM
- **影响**: 易受 DDoS 和暴力破解攻击
- **策略**: 关键端点优先，开发环境可禁用
- **解决方案**:
  - 使用 `slowapi` 实现速率限制
  - 登录端点：5次/分钟（防暴力破解）
  - 注册端点：3次/小时（防批量注册）
  - 搜索端点：30次/分钟（防接口滥用）
  - 通过 `ENABLE_RATE_LIMIT` 环境变量控制启用/禁用
- **任务**:
  - [ ] 安装 `slowapi` 库
  - [ ] 创建 `app/middleware/rate_limit.py` 中间件
  - [ ] 为 `/auth/login` 添加 5次/分钟限制
  - [ ] 为 `/auth/register` 添加 3次/小时限制
  - [ ] 为 `/etf/search` 添加 30次/分钟限制
  - [ ] 注册全局异常处理器
  - [ ] 添加 `ENABLE_RATE_LIMIT` 配置项（默认 false）

#### 实施顺序
1. **环境配置基础** → 2. **安装新依赖** → 3. **配置系统重构** → 4. **CORS 优化** → 5. **速率限制** → 6. **依赖锁定** → 7. **测试验证**

#### 验证标准
- [ ] `auth_service.py` 中无硬编码 SECRET_KEY
- [ ] `.env` 文件在 `.gitignore` 中
- [ ] CORS 支持 localhost + 127.0.0.1 + 局域网正则
- [ ] 生产环境不允许 CORS `*`（启动验证）
- [ ] 所有依赖已声明且版本锁定
- [ ] 关键端点速率限制生效（可选启用）
- [ ] 从手机/平板可访问局域网 API
- [ ] 所有现有功能正常工作

**预期效果**: 安全评分从 ⭐ (1/5) 提升到 ⭐⭐⭐⭐ (4/5)

---

### 🟡 阶段二: 测试框架建立 (P1 - 两周内)

**目标**: 建立完整的测试基础设施

#### 5. 后端单元测试框架
- **问题**: 后端无任何测试文件
- **当前状态**: 0 测试覆盖
- **目标覆盖率**: 核心逻辑 > 80%
- **任务**:
  - 创建测试目录结构 `backend/tests/`
  - 配置 pytest fixtures (`conftest.py`)
  - 编写认证服务测试 (`test_auth.py`)
    - 密码哈希验证测试
    - JWT 生成/验证测试
    - 登录/注册流程测试
  - 编写指标计算测试 (`test_metrics.py`)
    - CAGR 计算准确性
    - 最大回撤计算验证
    - 波动率计算验证
  - 编写 API 端点测试 (`test_etf_api.py`)
  - 集成测试覆盖率报告

#### 6. 前端测试框架
- **问题**: 前端无测试配置
- **当前状态**: 无测试框架
- **目标覆盖率**: 组件 > 50%
- **任务**:
  - 安装测试依赖：`vitest`, `@testing-library/react`, `@testing-library/jest-dom`
  - 配置 `vitest.config.ts`
  - 编写组件测试
    - StockCard 渲染测试
    - ConfirmationDialog 交互测试
    - 自选列表操作测试
  - 编写 Hook 测试
    - `use-watchlist` 逻辑测试
    - `use-settings` 测试
  - 设置测试脚本到 `package.json`

---

### 🟢 阶段三: 代码质量提升 (P2 - 持续优化)

**目标**: 重构代码，消除技术债务

#### 7. 拆分过长函数
- **问题识别**:
  - `backend/app/api/v1/endpoints/etf.py::get_etf_metrics()` - 230 行
  - `backend/app/services/akshare_service.py::fetch_all_etfs()` - 112 行
  - `frontend/app/etf/[code]/page.tsx` - 355 行
- **任务**:
  - 创建 `backend/app/services/metrics_calculator.py`
  - 将指标计算逻辑拆分为独立方法：
    - `calculate_cagr()`
    - `calculate_max_drawdown()`
    - `calculate_volatility()`
    - `find_drawdown_dates()`
  - 使用数据类 (dataclass) 封装返回结果
  - 前端拆分 ETF 详情页为更小的子组件
  - 提取自定义 Hooks 封装数据获取逻辑

#### 8. 统一错误处理
- **问题**: 
  - 15 处使用 `except Exception`
  - 前端仅 `console.error`，无用户提示
  - 缺少全局异常处理
- **任务**:
  - 创建自定义异常类层次结构
    - `ETFToolException` (基类)
    - `DataFetchError`
    - `CacheError`
    - `AuthenticationError`
  - 实现全局异常处理器（FastAPI middleware）
  - 前端实现 Toast 通知系统
  - 前端创建 Error Boundary 组件
  - 统一错误响应格式

#### 9. 类型安全改进
- **后端任务**:
  - 为所有函数添加完整类型注解
  - 使用 Pydantic 模型替代 `Dict[str, Any]`
  - 在 CI/CD 中集成 mypy 类型检查
  - 减少泛化类型使用
- **前端任务**:
  - 消除所有 `any` 类型（当前 6 处）
  - 为组件 Props 定义严格接口
  - 使用 `unknown` 替代 `any` 在必要时
  - 增强空值检查

#### 10. 消除代码重复
- **识别的重复模式**:
  - 数据库操作的 try-except 块
  - 缓存 get/set 逻辑
  - API 错误处理
- **任务**:
  - 创建数据库操作装饰器/上下文管理器
  - 封装缓存服务类统一缓存操作
  - 提取公共错误处理逻辑为高阶函数
  - 创建前端 API 请求封装函数

---

### 🚀 阶段四: 工程化提升 (P2 - 持续)

**目标**: 建立现代化开发流程

#### 11. CI/CD 流程建立
- **任务**:
  - 创建 GitHub Actions 工作流
  - 后端流水线:
    - 依赖安装
    - Ruff 代码检查
    - mypy 类型检查
    - pytest 测试执行
    - 覆盖率报告
  - 前端流水线:
    - 依赖安装
    - ESLint 检查
    - TypeScript 类型检查
    - 单元测试执行
    - 安全审计 (npm audit)
  - 设置分支保护规则

#### 12. 日志与监控
- **任务**:
  - 后端集成 `loguru` 结构化日志
  - 配置日志轮转和保留策略
  - 添加 Prometheus 指标暴露
  - 前端集成错误监控（Sentry 或类似）
  - 记录关键业务指标

#### 13. 数据库迁移管理
- **任务**:
  - 安装配置 Alembic
  - 初始化迁移环境
  - 为现有数据库生成基线迁移
  - 建立数据库版本管理流程
  - 编写迁移最佳实践文档

#### 14. API 文档增强
- **任务**:
  - 完善 FastAPI 端点文档字符串
  - 添加请求/响应示例
  - 为所有模型添加字段描述
  - 配置 Swagger UI 和 ReDoc
  - 生成 API 使用指南

#### 15. 性能优化
- **任务**:
  - 分析并优化数据库查询（添加索引）
  - 优化前端打包配置（代码分割）
  - 实现 API 响应压缩
  - 添加静态资源 CDN 配置
  - 设置合理的缓存策略

---

## 📋 执行时间线

### 第 1 周: 安全加固
- [ ] Day 1-2: 环境变量配置和 SECRET_KEY 修复
- [ ] Day 3: CORS 配置优化
- [ ] Day 4: 修复依赖问题并生成 requirements.txt
- [ ] Day 5: 添加速率限制

**里程碑**: 所有 P0 安全问题修复完成

### 第 2-3 周: 测试建立
- [ ] Week 2 Day 1-2: 后端测试框架搭建
- [ ] Week 2 Day 3-5: 编写核心功能测试（认证、指标计算）
- [ ] Week 3 Day 1-2: 前端测试框架搭建
- [ ] Week 3 Day 3-5: 编写组件和 Hook 测试

**里程碑**: 核心功能测试覆盖率 > 60%

### 第 4-6 周: 代码重构
- [ ] Week 4: 拆分 `get_etf_metrics` 和相关服务
- [ ] Week 5: 实现统一错误处理和类型安全改进
- [ ] Week 6: 消除代码重复，前端组件拆分

**里程碑**: 代码质量评分提升至 4/5

### 持续进行
- [ ] 建立 CI/CD 流程
- [ ] 集成日志和监控系统
- [ ] 配置数据库迁移管理
- [ ] 完善 API 文档
- [ ] 性能优化和监控

---

## 🎯 关键指标目标

### 质量指标
- **代码覆盖率**: 从 0% → 70%+
- **类型安全**: Python 类型注解 100%, TypeScript `any` 使用 < 5 处
- **代码异味**: 消除所有 200+ 行函数
- **安全评分**: 从 1/5 → 4/5

### 工程指标
- **CI/CD 覆盖**: 100% PR 必须通过自动化检查
- **部署频率**: 支持每日部署
- **平均修复时间**: < 1 小时（P0 问题）
- **文档覆盖**: 所有 API 端点有完整文档

---

## 💡 实施原则

### 1. 安全优先
在添加任何新功能前，必须先解决 P0 安全问题。不在脆弱的基础上构建。

### 2. 测试驱动
建立测试框架后，所有新功能必须遵循 TDD 原则：先写测试，再写实现。

### 3. 渐进式重构
避免大规模重写，采用小步快跑的方式逐步改进代码质量。

### 4. 文档同步
代码变更必须同步更新文档，保持文档与实现一致。

### 5. 代码审查
所有变更必须经过 Code Review，确保质量标准。

---

## 📚 参考资源

### 最佳实践
- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/)
- [React Testing Library Guide](https://testing-library.com/docs/react-testing-library/intro/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [OWASP Security Guidelines](https://owasp.org/)

### 工具文档
- [pytest Documentation](https://docs.pytest.org/)
- [Vitest Guide](https://vitest.dev/guide/)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [GitHub Actions Workflow](https://docs.github.com/en/actions)

---

## 🔄 计划更新日志

- **2026-01-25**: 阶段一详细设计完成
  - 通过头脑风暴明确需求：本地开发为主、支持局域网访问、关键端点限流
  - 创建详细设计文档：`docs/plans/2026-01-25-phase1-security-hardening-design.md`
  - 更新阶段一任务列表，添加具体实施步骤和验证标准
- **2026-01-24**: 初始版本，基于代码库质量分析生成

---

**注意**: 此计划为动态文档，随着项目进展和新问题发现将持续更新。执行前请确保团队对优先级和时间线达成共识。
