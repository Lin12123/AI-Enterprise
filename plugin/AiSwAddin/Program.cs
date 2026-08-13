using System;
using System.Drawing;
using System.Windows.Forms;
using AiSwAddin;

namespace AiSwAddin
{
    /// <summary>
    /// UI 快速预览入口（临时调试用）。
    ///
    /// 目的：不启动 SolidWorks，即可在本机 F5 直接查看 AiSwTaskPaneControl 的界面，
    /// 用于调试布局（如发送按钮位置、功能卡片高度等）。
    ///
    /// 使用前提：需将本项目的 OutputType 临时设为 WinExe（见 AiSwAddin.csproj）。
    /// 【重要】发布 SolidWorks 插件前，务必把 OutputType 改回 Library，
    /// 并注释掉 StartupObject，否则生成的不是可被 SW 加载的 .dll。
    ///
    /// 说明：
    ///   - 控件构造函数只调用 BuildUi()，不依赖 SolidWorks 实例，可独立渲染。
    ///   - 未调用 SetSolidWorks()，因此“发送”后的真实业务流程不会执行，
    ///     这不影响纯 UI 布局的预览。
    /// </summary>
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            var form = new Form
            {
                Text = "AiSwAddin UI 预览（不含 SolidWorks）",
                StartPosition = FormStartPosition.CenterScreen,
                ClientSize = new Size(500, 820),
                MinimumSize = new Size(420, 400),
                FormBorderStyle = FormBorderStyle.Sizable,   // 可自由拉长拉宽
                MaximizeBox = true,
                BackColor = Color.FromArgb(230, 232, 238)     // 两侧留白颜色，模拟主机应用背景
            };

            // 真实的 SolidWorks 任务窗格宽度固定；这里让被测控件保持固定 400 宽并居中，
            // 两侧空白由窗体背景填充，避免拉宽时按 400 宽设计的自绘元素被拉伸变形。
            const int PaneWidth = 400;
            var control = new AiSwTaskPaneControl
            {
                Width = PaneWidth,
                Anchor = AnchorStyles.Top | AnchorStyles.Bottom
            };

            void Layout()
            {
                control.Left = Math.Max(0, (form.ClientSize.Width - PaneWidth) / 2);
                control.Top = 0;
                control.Height = form.ClientSize.Height;
            }
            form.Resize += (s, e) => Layout();
            form.Shown += (s, e) => Layout();

            form.Controls.Add(control);
            Application.Run(form);
        }
    }
}