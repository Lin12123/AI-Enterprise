using System;
using System.Drawing;
using System.Windows.Forms;

namespace AiSwAddin
{
    /// <summary>
    /// 技术日志弹出窗：从底部任务栏「📄日志」小按钮触发。
    ///
    /// 因为产品需求把主 UI 的日志区改为 AI 会话，技术日志(生成/校验/执行/异常等)
    /// 从主界面收起，只在需要排查问题时通过此弹窗查看。
    /// </summary>
    internal class LogPopupForm : Form
    {
        private readonly TextBox _box;

        public LogPopupForm()
        {
            Text = "技术日志";
            Width = 640;
            Height = 480;
            StartPosition = FormStartPosition.CenterParent;
            MinimizeBox = false;
            ShowInTaskbar = false;
            BackColor = Theme.PageBg;

            _box = new TextBox
            {
                Multiline = true,
                ReadOnly = true,
                ScrollBars = ScrollBars.Vertical,
                Dock = DockStyle.Fill,
                BorderStyle = BorderStyle.None,
                BackColor = Color.White,
                ForeColor = Theme.TextMain,
                Font = new Font("Consolas", 9),
                WordWrap = true
            };
            var host = new Panel
            {
                Dock = DockStyle.Fill,
                BackColor = Color.White,
                Padding = new Padding(10)
            };
            host.Controls.Add(_box);
            Controls.Add(host);
        }

        /// <summary>初始化时把已积累的日志内容一次性写入。</summary>
        public void SetLog(string text)
        {
            _box.Text = text ?? "";
            _box.SelectionStart = _box.TextLength;
            _box.ScrollToCaret();
        }

        /// <summary>窗体已打开状态下追加新日志(可选, 目前主 UI 每次点开都新建实例, 用不到)。</summary>
        public void AppendLine(string line)
        {
            if (string.IsNullOrEmpty(line)) return;
            _box.AppendText(line + Environment.NewLine);
        }
    }
}