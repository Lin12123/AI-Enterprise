using System.Reflection;
using System.Runtime.InteropServices;

// 程序集基本信息
[assembly: AssemblyTitle("AiSwAddin")]
[assembly: AssemblyDescription("AI-SW 轻量 SolidWorks 插件(UI + SW 集成，业务逻辑经本地 HTTP 调用 Python 服务)")]
[assembly: AssemblyProduct("AiSwAddin")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]

// 程序集整体默认对 COM 可见。SolidWorks 通过 COM 加载插件，
// 因此需要 ComVisible(true)；具体导出的类型再各自标注 [ComVisible].
[assembly: ComVisible(true)]

// 供 regasm 生成的类型库使用的唯一 GUID
[assembly: Guid("B1C3D5E7-2F49-4A6B-8C0D-3E5F7A9B1C2D")]