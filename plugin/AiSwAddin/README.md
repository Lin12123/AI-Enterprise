# AI-SW 轻量 SolidWorks 插件

一个"轻插件"实现：C# SwAddin 只负责**任务窗格 UI + SolidWorks 集成**，
所有业务逻辑（自然语言解析、FeaturePlan、policy 校验、真实建模）都由本地
Python HTTP 服务完成，插件通过 `http://127.0.0.1:8765` 调用。

## 架构

```
SolidWorks
  └── AI-SW 任务窗格插件 (C#, 本目录)
        │  HTTP (127.0.0.1:8765)
        ▼
  Python 本地服务 (service/http_service.py)
        ├── 自然语言解析 (app/providers, 支持本机 Ollama)
        ├── policy 校验 (src/policy)
        └── 真实建模 (src/solidworks_api, pywin32 连接当前 SW)
```

职责边界：插件不含任何建模代码；Python 复用现有引擎，通过 pywin32 用
`GetActiveObject` 连接**当前已打开**的 SolidWorks 实例。

## 组成文件

- `AiSwAddin.cs`：插件主类，实现 `ISwAddin`，负责加载/卸载、创建任务窗格、COM 注册。
- `AiSwTaskPaneControl.cs`：任务窗格 UI（输入框、模型选择、生成/校验/预演/执行按钮、日志区）。
- `ServiceClient.cs`：HTTP 客户端，调用 Python 服务四个接口。
- `Properties/AssemblyInfo.cs`：COM 可见性与程序集信息。
- `AiSwAddin.csproj`：.NET Framework 4.7.2 工程，`RegisterForComInterop=true`。

## 前置条件

1. Windows + 已安装 SolidWorks。
2. Visual Studio（含 .NET Framework 4.7.2 开发工具）。
3. 已按项目根说明启动 Python 服务，且（真实执行时）Python 环境已 `pip install pywin32`。
4. 本机 Ollama 已运行并拉取 `qwen2.5-coder:7b`（使用 local 模型时）。

## 构建步骤

1. 用 Visual Studio 打开 `AiSwAddin.csproj`。
2. **重新引用 SolidWorks 互操作程序集**（工程中的引用为占位路径）：
   - 右键"引用" → 添加引用 → 浏览到本机
     `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\api\redist`
   - 添加：`SolidWorks.Interop.sldworks.dll`、`SolidWorks.Interop.swconst.dll`、
     `SolidWorks.Interop.swpublished.dll`
   - 将这三个引用的"嵌入互操作类型"设为 **False**。
3. 选择 **Release / Any CPU**，生成解决方案，产物为 `bin\Release\AiSwAddin.dll`。

## 注册插件（让 SolidWorks 识别）

以**管理员身份**打开命令行，执行（路径按实际 .NET Framework 版本调整）：

```
cd bin\Release
"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe" /codebase AiSwAddin.dll
```

成功后会在注册表写入 `SOFTWARE\SolidWorks\Addins\{GUID}` 与
`AddInsStartup\{GUID}`。重启 SolidWorks，即可在右侧任务窗格看到「AI-SW 智能建模」。

反注册：
```
"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe" /unregister AiSwAddin.dll
```

## 使用流程

1. 双击 `service/start_service.bat` 启动 Python 本地服务。
2. 打开 SolidWorks，在任务窗格找到「AI-SW 智能建模」。
3. 输入建模需求 → 依次点击 ① 生成计划 → ② 校验 → ③ 预演 → ④ 执行建模。
4. 「执行建模」会弹出确认框，确认后 Python 通过 pywin32 在当前 SolidWorks 建模。

## 常见问题

- **任务窗格无插件**：确认已用管理员权限 RegAsm 注册，并在 SolidWorks
  "工具 → 插件"里勾选启用。
- **点按钮报"无法连接本地 AI 服务"**：Python 服务未启动，先运行 start_service.bat。
- **执行报"未安装 pywin32"**：在 Python 服务所用环境执行 `pip install pywin32`。
- **端口冲突**：设置环境变量 `AI_SW_SERVICE_PORT` 并同步修改 `ServiceClient` 的 baseUrl。