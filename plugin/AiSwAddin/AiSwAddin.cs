using System;
using System.Runtime.InteropServices;
using Microsoft.Win32;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swpublished;
using SolidWorks.Interop.swconst;

namespace AiSwAddin
{
    /// <summary>
    /// AI-SW 轻量插件主类。
    ///
    /// 职责边界(方案 Y)：
    /// - 本插件只负责 UI(任务窗格) 与 SolidWorks 集成(加载/卸载/COM 注册)。
    /// - 所有业务逻辑(自然语言解析、FeaturePlan、policy 校验、真实建模)
    ///   由本地 Python HTTP 服务完成，插件通过 ServiceClient 以 HTTP 调用。
    ///
    /// SolidWorks 通过 COM 加载实现了 ISwAddin 的类。ProgId/GUID 必须唯一，
    /// 且需在注册表 SolidWorks\Addins 与 AddInsStartup 下登记，才能被识别。
    /// </summary>
    [Guid("A7E4C2D0-1B3F-4A8E-9C6D-2F5B8E1D4A90")]
    [ComVisible(true)]
    public class AiSwAddin : ISwAddin
    {
        // 注册表中登记插件所用的 GUID(需与上方 [Guid] 一致)
        private const string AddinGuid = "A7E4C2D0-1B3F-4A8E-9C6D-2F5B8E1D4A90";
        private const string AddinTitle = "AI-SW 智能建模";
        private const string AddinDescription = "通过本地 AI 服务把自然语言转为 SolidWorks 建模操作";

        private ISldWorks _swApp;
        private int _addinCookie;
        private ITaskpaneView _taskPaneView;
        private AiSwTaskPaneControl _taskPaneControl;

        #region ISwAddin 实现

        /// <summary>SolidWorks 加载插件时调用。</summary>
        public bool ConnectToSW(object thisSW, int cookie)
        {
            _swApp = (ISldWorks)thisSW;
            _addinCookie = cookie;

            // 告知 SolidWorks 本插件的回调对象
            _swApp.SetAddinCallbackInfo2(0, this, _addinCookie);

            CreateTaskPane();
            return true;
        }

        /// <summary>SolidWorks 卸载插件时调用，需释放所有 COM 资源。</summary>
        public bool DisconnectFromSW()
        {
            RemoveTaskPane();

            if (_swApp != null)
            {
                Marshal.ReleaseComObject(_swApp);
                _swApp = null;
            }

            GC.Collect();
            GC.WaitForPendingFinalizers();
            return true;
        }

        #endregion

        #region 任务窗格

        /// <summary>创建右侧任务窗格并放入自定义 UI 控件。</summary>
        private void CreateTaskPane()
        {
            // 第二参数为任务窗格图标(空字符串表示使用默认)，第三参数为提示文本
            _taskPaneView = _swApp.CreateTaskpaneView2(string.Empty, AddinTitle);

            _taskPaneControl = (AiSwTaskPaneControl)_taskPaneView.AddControl(
                AiSwTaskPaneControl.ProgId, string.Empty);

            // 把 SolidWorks 应用实例注入 UI 控件，供其执行 SW API(如获取当前文档)
            if (_taskPaneControl != null)
            {
                _taskPaneControl.SetSolidWorks(_swApp);
            }
        }

        /// <summary>移除任务窗格。</summary>
        private void RemoveTaskPane()
        {
            if (_taskPaneView != null)
            {
                _taskPaneView.DeleteView();
                Marshal.ReleaseComObject(_taskPaneView);
                _taskPaneView = null;
            }
            _taskPaneControl = null;
        }

        #endregion

        #region COM 注册(regasm 会调用以下方法写入 SolidWorks 识别所需的注册表项)

        [ComRegisterFunction]
        public static void RegisterFunction(Type t)
        {
            try
            {
                string keyPath = string.Format(@"SOFTWARE\SolidWorks\Addins\{{{0}}}", AddinGuid);
                using (RegistryKey addinKey = Registry.LocalMachine.CreateSubKey(keyPath))
                {
                    // 值为 0 表示默认不随启动加载，用户可在插件管理器中开启；1 表示默认加载
                    addinKey.SetValue(null, 0);
                    addinKey.SetValue("Title", AddinTitle);
                    addinKey.SetValue("Description", AddinDescription);
                }

                string startupPath = string.Format(
                    @"SOFTWARE\SolidWorks\AddInsStartup\{{{0}}}", AddinGuid);
                using (RegistryKey startupKey = Registry.CurrentUser.CreateSubKey(startupPath))
                {
                    startupKey.SetValue(null, 1); // 1 = 启动时自动加载
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine("AI-SW 插件注册失败: " + ex.Message);
            }
        }

        [ComUnregisterFunction]
        public static void UnregisterFunction(Type t)
        {
            try
            {
                Registry.LocalMachine.DeleteSubKey(
                    string.Format(@"SOFTWARE\SolidWorks\Addins\{{{0}}}", AddinGuid), false);
                Registry.CurrentUser.DeleteSubKey(
                    string.Format(@"SOFTWARE\SolidWorks\AddInsStartup\{{{0}}}", AddinGuid), false);
            }
            catch (Exception ex)
            {
                Console.WriteLine("AI-SW 插件反注册失败: " + ex.Message);
            }
        }

        #endregion
    }
}