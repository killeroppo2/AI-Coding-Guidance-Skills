@echo off
chcp 65001 >nul
REM ─── 小红书爆款采集器 - Windows 定时任务启动脚本 ───
REM 功能：运行采集脚本，日志按日期保存，错误信息同步记录

REM 项目根目录（请根据实际路径修改）
set PROJECT_DIR=C:\Users\pengaro\Documents\AI-Coding-Guidance-Skills\xhs_collector
set SCRIPT_PATH=%PROJECT_DIR%\scripts\collector.py
set LOG_DIR=%PROJECT_DIR%\logs

REM 创建日志目录
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM 日志文件按日期命名
set DATE=%date:~0,4%-%date:~5,2%-%date:~8,2%
set LOG_FILE=%LOG_DIR%\%DATE%.log

REM 记录启动时间
echo ======================================== >> "%LOG_FILE%"
echo [%date% %time%] 采集任务开始 >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"

REM 运行 Python 脚本，stdout 和 stderr 都写入日志
python "%SCRIPT_PATH%" >> "%LOG_FILE%" 2>&1
set EXIT_CODE=%ERRORLEVEL%

REM 记录结束状态
echo. >> "%LOG_FILE%"
if %EXIT_CODE% EQU 0 (
    echo [%date% %time%] 采集任务完成 ^(退出码: %EXIT_CODE%^) >> "%LOG_FILE%"
) else (
    echo [%date% %time%] 采集任务异常退出 ^(退出码: %EXIT_CODE%^) >> "%LOG_FILE%"
)
echo ======================================== >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

exit /b %EXIT_CODE%
