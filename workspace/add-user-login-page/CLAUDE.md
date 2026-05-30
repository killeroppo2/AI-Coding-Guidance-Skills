# CLAUDE.md - 项目规则

## 工作区
所有代码必须写入: `./workspace/add-user-login-page/`
FILES_WRITTEN 路径必须以 `./workspace/add-user-login-page/` 开头。

## 目标
Add user login page

## 输出格式（强制）
每次响应必须以以下内容结尾（纯文本，不要放在代码块中）：

STATUS: success
TRANSITION: <condition>

如果创建了文件：
FILES_WRITTEN: ./workspace/add-user-login-page/src/file.py, ./workspace/add-user-login-page/tests/test.py

## 规则
1. 不要在工作区目录外写文件
2. 不要忘记 STATUS 和 TRANSITION 行
3. 所有新代码必须包含测试
