# CLAUDE.md - 项目规则

## 工作区
所有代码必须写入: `./workspace/test-violation-logging/`
FILES_WRITTEN 路径必须以 `./workspace/test-violation-logging/` 开头。

## 目标
test violation logging

## 输出格式（强制）
每次响应必须以以下内容结尾（纯文本，不要放在代码块中）：

STATUS: success
TRANSITION: <condition>

如果创建了文件：
FILES_WRITTEN: ./workspace/test-violation-logging/src/file.py, ./workspace/test-violation-logging/tests/test.py

## 规则
1. 不要在工作区目录外写文件
2. 不要忘记 STATUS 和 TRANSITION 行
3. 所有新代码必须包含测试
