# CLAUDE.md - 项目规则

## 工作区
所有代码必须写入: `./workspace/create-a-calculator/`
FILES_WRITTEN 路径必须以 `./workspace/create-a-calculator/` 开头。

## 目标
Create a calculator

## 输出格式（强制）
每次响应必须以以下内容结尾（纯文本，不要放在代码块中）：

STATUS: success
TRANSITION: <condition>

如果创建了文件：
FILES_WRITTEN: ./workspace/create-a-calculator/src/file.py, ./workspace/create-a-calculator/tests/test.py

## 规则
1. 不要在工作区目录外写文件
2. 不要忘记 STATUS 和 TRANSITION 行
3. 所有新代码必须包含测试
