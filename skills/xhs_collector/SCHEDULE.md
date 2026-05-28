# 定时任务配置指南

自动在每天凌晨 0:00 运行小红书爆款采集脚本，日志按日期保存至 `logs/` 目录。

---

## Mac（launchd）

### 一键安装

```bash
# 1. 给启动脚本添加执行权限
chmod +x /Users/pengaro/Documents/work/codeDevelop/ideaSpace/AI-Coding-Guidance-Skills/xhs_collector/scripts/run_collector.sh

# 2. 创建日志目录
mkdir -p /Users/pengaro/Documents/work/codeDevelop/ideaSpace/AI-Coding-Guidance-Skills/xhs_collector/logs

# 3. 复制 plist 到 LaunchAgents 目录
cp /Users/pengaro/Documents/work/codeDevelop/ideaSpace/AI-Coding-Guidance-Skills/xhs_collector/scripts/com.pengaro.xhs-collector.plist ~/Library/LaunchAgents/

# 4. 加载定时任务
launchctl load ~/Library/LaunchAgents/com.pengaro.xhs-collector.plist
```

### 常用命令

```bash
# 查看任务状态
launchctl list | grep xhs-collector

# 手动触发一次（测试用）
launchctl start com.pengaro.xhs-collector

# 停止/卸载任务
launchctl unload ~/Library/LaunchAgents/com.pengaro.xhs-collector.plist

# 重新加载（修改 plist 后）
launchctl unload ~/Library/LaunchAgents/com.pengaro.xhs-collector.plist
launchctl load ~/Library/LaunchAgents/com.pengaro.xhs-collector.plist
```

### 文件说明

| 文件 | 说明 |
|------|------|
| `scripts/com.pengaro.xhs-collector.plist` | launchd 任务配置 |
| `scripts/run_collector.sh` | 启动包装脚本（处理日志） |
| `logs/YYYY-MM-DD.log` | 每日采集日志 |

### 注意事项

- launchd 在用户登录后生效，**电脑关机期间不会执行**
- 如果错过执行时间，开机后会**补执行一次**（已配置 `StartInterval`）
- 确保 `python3` 在系统 PATH 中可用

---

## Windows（任务计划程序）

### 方式一：命令行安装（推荐）

以**管理员权限**打开 PowerShell：

```powershell
# 1. 创建日志目录
New-Item -ItemType Directory -Force -Path "C:\Users\pengaro\Documents\AI-Coding-Guidance-Skills\xhs_collector\logs"

# 2. 导入计划任务
schtasks /create /tn "XHS-Collector" /xml "C:\Users\pengaro\Documents\AI-Coding-Guidance-Skills\xhs_collector\scripts\xhs-collector-task.xml" /f
```

### 方式二：图形界面安装

1. 按 `Win + R`，输入 `taskschd.msc` 打开任务计划程序
2. 右键点击「任务计划程序库」→「导入任务」
3. 选择 `xhs_collector/scripts/xhs-collector-task.xml`
4. 确认后保存

### 常用命令

```powershell
# 查看任务状态
schtasks /query /tn "XHS-Collector" /v

# 手动触发一次（测试用）
schtasks /run /tn "XHS-Collector"

# 删除任务
schtasks /delete /tn "XHS-Collector" /f

# 禁用任务
schtasks /change /tn "XHS-Collector" /disable

# 启用任务
schtasks /change /tn "XHS-Collector" /enable
```

### 文件说明

| 文件 | 说明 |
|------|------|
| `scripts/xhs-collector-task.xml` | 任务计划程序配置 |
| `scripts/run_collector.bat` | 启动批处理脚本（处理日志） |
| `logs\YYYY-MM-DD.log` | 每日采集日志 |

### 注意事项

- 确保 `python` 已添加到系统 PATH 环境变量
- XML 中的路径默认为 `C:\Users\pengaro\Documents\AI-Coding-Guidance-Skills\`，请根据实际路径修改
- `StartWhenAvailable=true`：如果错过执行时间，登录后会补执行
- `RunOnlyIfNetworkAvailable=true`：仅在有网络时执行

---

## 日志格式

每日日志文件示例 `logs/2025-05-18.log`：

```
========================================
[2025-05-18 00:00:01] 采集任务开始
========================================
============================================================
🌟 小红书爆款笔记采集器 启动
============================================================

📋 待采集关键词: 10 个
...（采集过程输出）...

✅ 采集完成！
📂 文件保存目录: .../01-内容生产/爆款参考库

[2025-05-18 00:05:23] ✅ 采集任务完成 (退出码: 0)
========================================
```

如果脚本报错，错误信息也会记录在同一个日志文件中：

```
========================================
[2025-05-18 00:00:01] 采集任务开始
========================================
Traceback (most recent call last):
  File "collector.py", line xx, in <module>
    ...
ConnectionError: 网络连接失败

[2025-05-18 00:00:03] ❌ 采集任务异常退出 (退出码: 1)
========================================
```

---

## 路径自定义

如果你的项目路径不同，需要修改以下文件中的路径：

| 平台 | 文件 | 需修改内容 |
|------|------|-----------|
| Mac | `com.pengaro.xhs-collector.plist` | `ProgramArguments`、`WorkingDirectory`、`StandardOutPath`、`StandardErrorPath` |
| Mac | `run_collector.sh` | `PROJECT_DIR` 变量 |
| Windows | `xhs-collector-task.xml` | `<Arguments>` 和 `<WorkingDirectory>` |
| Windows | `run_collector.bat` | `PROJECT_DIR` 变量 |
