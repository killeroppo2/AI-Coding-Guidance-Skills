# 用户登录 API 执行计划

## 技术栈
- **框架**: FastAPI (Python)
- **数据库**: SQLite + SQLAlchemy
- **认证**: JWT (python-jose) + bcrypt (passlib)
- **测试**: pytest

## 任务分解

### T-001: 项目脚手架与环境配置
搭建 FastAPI 项目结构，安装依赖。

### T-002: 用户模型与数据库初始化
定义 User 数据模型（id, username, email, hashed_password, created_at），配置 SQLite 数据库。

### T-003: 密码哈希与 JWT 工具函数
实现密码哈希验证和 JWT token 生成/校验工具。

### T-004: 用户注册 API (POST /api/register)
接收 username, email, password，创建用户，返回 201。

### T-005: 用户登录 API (POST /api/login)
验证凭证，返回 JWT access token。

### T-006: 测试覆盖
撰写 pytest 全量测试，确保 >90% 覆盖率。

## 依赖关系
```
T-001 → T-002 → T-004 → T-006
  ↓                    ↑
T-003 → → → → → T-005 → 
```
