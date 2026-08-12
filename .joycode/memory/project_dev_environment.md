---
name: 开发环境约定
description: AI-Enterprise 项目在 Windows 上的统一 IDE 与运行环境约定（C# 插件 + Python 服务）
type: project
---

统一使用 Visual Studio（Community 版）开发本项目的两部分代码：C# SolidWorks 插件（plugin/AiSwAddin，需 ".NET 桌面开发" 工作负载）和 Python 服务（service/http_service.py，需 "Python 开发" 工作负载）。不再使用 PyCharm。沿用此前在 PyCharm 中创建的 .venv（已含 pywin32），VS 的 Python 解释器直接指向该 .venv，不重建。

**Why:** 用户决定弃用 PyCharm，改为一个 IDE 覆盖 C# 与 Python 两种语言，减少工具切换。C# 插件必须用 VS 编译（PyCharm/VS Code 不适合）。

**How to apply:** 涉及编译/调试 C# 插件时默认走 Visual Studio；Python 服务日常运行只需双击 service/start_service.bat，不强依赖 IDE。给出环境相关指引时以 Windows + VS + 现有 .venv 为前提。用户 Windows 项目路径为 C:\Users\LVBO_ZY\PycharmProjects\AI-Enterprise。