@echo off
rem AI-SW 本地 HTTP 服务启动脚本(供 SolidWorks 插件调用)
rem 用法：双击本脚本，或在命令行执行 start_service.bat
setlocal
cd /d %~dp0\..

rem 优先使用项目自带虚拟环境的 Python，否则回退到系统 python
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON=.venv\Scripts\python.exe"
)

rem 可选：自定义监听地址与端口(默认 127.0.0.1:8765)
rem set "AI_SW_SERVICE_HOST=127.0.0.1"
rem set "AI_SW_SERVICE_PORT=8765"启动服务 start_service.bat


rem 可选：选择大模型 provider(local=本机 Ollama, rule_based=规则解析)
rem set "AI_SW_LLM_PROVIDER=local"

rem 本地 LLM 调试输出目录：开启后会把模型原始输出、被 Policy 拒的 featureplan、
rem 以及每轮修复产物 dump 到该目录，便于定位生成失败(500)。排查完可注释掉本段。
set "AI_SW_LOCAL_LLM_DEBUG_DIR=%~dp0..\workspace\logs\local_llm_debug"
if not exist "%AI_SW_LOCAL_LLM_DEBUG_DIR%" (
  mkdir "%AI_SW_LOCAL_LLM_DEBUG_DIR%"
)
echo 本地 LLM 调试输出目录: %AI_SW_LOCAL_LLM_DEBUG_DIR%

echo 正在启动 AI-SW 本地服务...
"%PYTHON%" service\http_service.py

if errorlevel 1 (
  echo 服务异常退出。
  pause
)
endlocal