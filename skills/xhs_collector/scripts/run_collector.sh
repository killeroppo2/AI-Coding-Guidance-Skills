#!/bin/bash
# ─── 小红书爆款采集器 - Mac 定时任务启动脚本 ───
# 功能：运行采集脚本，日志按日期保存，错误信息同步记录

# 项目根目录
PROJECT_DIR="/Users/pengaro/Documents/work/codeDevelop/ideaSpace/AI-Coding-Guidance-Skills/xhs_collector"
SCRIPT_PATH="${PROJECT_DIR}/scripts/collector.py"
LOG_DIR="${PROJECT_DIR}/logs"

# 创建日志目录
mkdir -p "${LOG_DIR}"

# 日志文件按日期命名
DATE=$(date +"%Y-%m-%d")
LOG_FILE="${LOG_DIR}/${DATE}.log"

# 记录启动时间
echo "========================================" >> "${LOG_FILE}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 采集任务开始" >> "${LOG_FILE}"
echo "========================================" >> "${LOG_FILE}"

# 运行 Python 脚本，stdout 和 stderr 都写入日志
python3 "${SCRIPT_PATH}" >> "${LOG_FILE}" 2>&1
EXIT_CODE=$?

# 记录结束状态
echo "" >> "${LOG_FILE}"
if [ ${EXIT_CODE} -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ 采集任务完成 (退出码: ${EXIT_CODE})" >> "${LOG_FILE}"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ 采集任务异常退出 (退出码: ${EXIT_CODE})" >> "${LOG_FILE}"
fi
echo "========================================" >> "${LOG_FILE}"
echo "" >> "${LOG_FILE}"

exit ${EXIT_CODE}
