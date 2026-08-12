using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using SolidWorks.Interop.sldworks;

namespace AiSwAddin
{
    /// <summary>
    /// 任务窗格中的 UI 控件(WinForms UserControl)。
    ///
    /// 作为 COM 控件被 SolidWorks 任务窗格加载，因此需 ComVisible + ProgId。
    /// 界面元素：需求输入框、provider 选择、四个流程按钮(生成/校验/预演/执行)、日志区。
    /// 业务逻辑全部通过 ServiceClient 走本地 Python HTTP 服务，本控件不含建模代码。
    /// </summary>
    [ComVisible(true)]
    [ProgId(ProgId)]
    [ClassInterface(ClassInterfaceType.AutoDual)]
    public class AiSwTaskPaneControl : UserControl
    {
        // SolidWorks 通过该 ProgId 在任务窗格中实例化本控件
        public const string ProgId = "AiSwAddin.AiSwTaskPaneControl";

        private ISldWorks _swApp;
        private readonly ServiceClient _client = new ServiceClient();

        // 保存最近一次生成的 FeaturePlan(JSON 字符串)，供校验/预演/执行复用
        private string _currentPlanJson = null;

        // ---- UI 控件字段 ----
        private TextBox _inputBox;
        private ComboBox _providerBox;
        private Button _generateBtn;
        private Button _validateBtn;
        private Button _dryRunBtn;
        private Button _executeBtn;
        private TextBox _logBox;

        public AiSwTaskPaneControl()
        {
            BuildUi();
        }

        /// <summary>由插件主类注入 SolidWorks 应用实例。</summary>
        public void SetSolidWorks(ISldWorks swApp)
        {
            _swApp = swApp;
            AppendLog("[就绪] AI-SW 插件已加载。请先启动本地 Python 服务(start_service.bat)。");
        }

        /// <summary>构建界面布局。</summary>
        private void BuildUi()
        {
            Width = 340;
            Height = 640;
            Padding = new Padding(8);

            var layout = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 1,
                RowCount = 6,
                AutoSize = true
            };
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 30));   // 标题
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 120));  // 输入框
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 34));   // provider
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 80));   // 按钮区
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 24));   // 日志标题
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));   // 日志区

            var title = new Label
            {
                Text = "AI-SW 智能建模",
                Font = new Font("Microsoft YaHei", 11, FontStyle.Bold),
                Dock = DockStyle.Fill,
                TextAlign = ContentAlignment.MiddleLeft
            };
            layout.Controls.Add(title, 0, 0);

            _inputBox = new TextBox
            {
                Multiline = true,
                ScrollBars = ScrollBars.Vertical,
                Dock = DockStyle.Fill,
                Text = "例如：做一个长100宽80厚10的底板，四角各开一个直径6的通孔"
            };
            layout.Controls.Add(_inputBox, 0, 1);

            var providerPanel = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.LeftToRight };
            providerPanel.Controls.Add(new Label { Text = "模型：", AutoSize = true, TextAlign = ContentAlignment.MiddleLeft, Padding = new Padding(0, 6, 0, 0) });
            _providerBox = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 160 };
            _providerBox.Items.AddRange(new object[] { "local", "rule_based", "openai" });
            _providerBox.SelectedIndex = 0;
            providerPanel.Controls.Add(_providerBox);
            layout.Controls.Add(providerPanel, 0, 2);

            var buttonPanel = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.LeftToRight, WrapContents = true };
            _generateBtn = MakeButton("① 生成计划", OnGenerateClick);
            _validateBtn = MakeButton("② 校验", OnValidateClick);
            _dryRunBtn = MakeButton("③ 预演", OnDryRunClick);
            _executeBtn = MakeButton("④ 执行建模", OnExecuteClick);
            _validateBtn.Enabled = false;
            _dryRunBtn.Enabled = false;
            _executeBtn.Enabled = false;
            buttonPanel.Controls.Add(_generateBtn);
            buttonPanel.Controls.Add(_validateBtn);
            buttonPanel.Controls.Add(_dryRunBtn);
            buttonPanel.Controls.Add(_executeBtn);
            layout.Controls.Add(buttonPanel, 0, 3);

            layout.Controls.Add(new Label { Text = "运行日志：", Dock = DockStyle.Fill }, 0, 4);

            _logBox = new TextBox
            {
                Multiline = true,
                ReadOnly = true,
                ScrollBars = ScrollBars.Vertical,
                Dock = DockStyle.Fill,
                BackColor = Color.White,
                Font = new Font("Consolas", 9)
            };
            layout.Controls.Add(_logBox, 0, 5);

            Controls.Add(layout);
        }

        private Button MakeButton(string text, EventHandler onClick)
        {
            var btn = new Button { Text = text, Width = 150, Height = 32, Margin = new Padding(2) };
            btn.Click += onClick;
            return btn;
        }

        /// <summary>向日志区追加一行(自动滚动到底部，线程安全)。</summary>
        private void AppendLog(string message)
        {
            if (_logBox.InvokeRequired)
            {
                _logBox.BeginInvoke(new Action<string>(AppendLog), message);
                return;
            }
            _logBox.AppendText(string.Format("[{0:HH:mm:ss}] {1}{2}",
                DateTime.Now, message, System.Environment.NewLine));
        }

        private void SetBusy(bool busy)
        {
            _generateBtn.Enabled = !busy;
            // 后续按钮的可用性由各步骤结果决定，忙碌时统一禁用
            if (busy)
            {
                _validateBtn.Enabled = false;
                _dryRunBtn.Enabled = false;
                _executeBtn.Enabled = false;
            }
        }

        // ---- 事件处理：串联 生成 → 校验 → 预演 → 执行 四个步骤 ----

        /// <summary>① 生成计划：自然语言 → FeaturePlan。</summary>
        private async void OnGenerateClick(object sender, EventArgs e)
        {
            string prompt = _inputBox.Text.Trim();
            if (string.IsNullOrEmpty(prompt))
            {
                AppendLog("[错误] 请先输入建模需求。");
                return;
            }

            SetBusy(true);
            AppendLog("[生成] 正在调用本地 AI 服务解析需求...");
            try
            {
               string provider = _providerBox.SelectedItem?.ToString() ?? "local";
                string resp = await _client.GeneratePlanAsync(prompt, provider);

                // 从响应中提取 plan 子对象(避免引入 JSON 库，做最小化提取)
                _currentPlanJson = ExtractPlanJson(resp);
                if (_currentPlanJson == null)
                {
                    AppendLog("[生成失败] 服务返回未包含有效 plan：" + Truncate(resp));
                    return;
                }
                AppendLog("[生成成功] 已生成 FeaturePlan。");
                _validateBtn.Enabled = true;
            }
            catch (Exception ex)
            {
                AppendLog("[生成异常] " + ex.Message);
            }
            finally
            {
                SetBusy(false);
            }
        }

        /// <summary>② 校验：policy 引擎校验计划合法性。</summary>
        private async void OnValidateClick(object sender, EventArgs e)
        {
            if (_currentPlanJson == null) { AppendLog("[错误] 请先生成计划。"); return; }
            SetBusy(true);
            AppendLog("[校验] 正在进行安全与几何规则校验...");
            try
            {
                string resp = await _client.ValidateAsync(_currentPlanJson);
                bool allowed = resp.Contains("\"allowed\": true") || resp.Contains("\"allowed\":true");
                if (allowed)
                {
                    AppendLog("[校验通过] 计划符合规则。");
                    _dryRunBtn.Enabled = true;
                }
                else
                {
                    AppendLog("[校验未通过] " + Truncate(resp));
                }
            }
            catch (Exception ex)
            {
                AppendLog("[校验异常] " + ex.Message);
            }
            finally
            {
                _generateBtn.Enabled = true;
                SetBusy(false);
                _generateBtn.Enabled = true;
            }
        }

        /// <summary>③ 预演：不连接 SolidWorks，仅输出执行计划。</summary>
        private async void OnDryRunClick(object sender, EventArgs e)
        {
            if (_currentPlanJson == null) { AppendLog("[错误] 请先生成计划。"); return; }
            SetBusy(true);
            AppendLog("[预演] 正在生成执行计划(不修改模型)...");
            try
            {
                string resp = await _client.DryRunAsync(_currentPlanJson);
                bool ok = resp.Contains("\"ok\": true") || resp.Contains("\"ok\":true");
                if (ok)
                {
                    AppendLog("[预演通过] 执行计划已就绪，可执行真实建模。");
                    _executeBtn.Enabled = true;
                }
                else
                {
                    AppendLog("[预演失败] " + Truncate(resp));
                }
            }
            catch (Exception ex)
            {
                AppendLog("[预演异常] " + ex.Message);
            }
            finally
            {
                _generateBtn.Enabled = true;
                SetBusy(false);
                _generateBtn.Enabled = true;
            }
        }

        /// <summary>④ 执行建模：Python 侧通过 pywin32 驱动当前 SolidWorks 真实建模。</summary>
        private async void OnExecuteClick(object sender, EventArgs e)
        {
            if (_currentPlanJson == null) { AppendLog("[错误] 请先生成计划。"); return; }

            var confirm = MessageBox.Show(
                "即将在当前 SolidWorks 中真实执行建模操作，是否继续？\n请确认已打开 SolidWorks。",
                "确认执行", MessageBoxButtons.YesNo, MessageBoxIcon.Warning);
            if (confirm != DialogResult.Yes)
            {
                AppendLog("[执行取消] 用户取消了真实建模。");
                return;
            }

            SetBusy(true);
            AppendLog("[执行] 正在通过本地服务驱动 SolidWorks 建模...");
            try
            {
                string resp = await _client.ExecuteAsync(_currentPlanJson);
                bool ok = resp.Contains("\"ok\": true") || resp.Contains("\"ok\":true");
                if (ok)
                {
                    AppendLog("[执行完成] SolidWorks 建模成功。");
                }
                else
                {
                    AppendLog("[执行失败] " + Truncate(resp));
                }
            }
            catch (Exception ex)
            {
                AppendLog("[执行异常] " + ex.Message);
            }
            finally
            {
                _generateBtn.Enabled = true;
                SetBusy(false);
                _generateBtn.Enabled = true;
            }
        }

        // ---- 轻量 JSON 辅助(避免引入外部 JSON 库) ----

        /// <summary>从 generate_plan 响应中提取 "plan" 对象的 JSON 子串。</summary>
        private static string ExtractPlanJson(string resp)
        {
            if (string.IsNullOrEmpty(resp)) return null;
            int keyIndex = resp.IndexOf("\"plan\"", StringComparison.Ordinal);
            if (keyIndex < 0) return null;
            int braceStart = resp.IndexOf('{', keyIndex);
            if (braceStart < 0) return null;

            // 括号配平，找到与 plan 对应的闭合大括号
            int depth = 0;
            for (int i = braceStart; i < resp.Length; i++)
            {
                if (resp[i] == '{') depth++;
                else if (resp[i] == '}')
                {
                    depth--;
                    if (depth == 0)
                        return resp.Substring(braceStart, i - braceStart + 1);
                }
            }
            return null;
        }

        /// <summary>截断过长文本用于日志显示。</summary>
        private static string Truncate(string text)
        {
            if (string.IsNullOrEmpty(text)) return "";
            return text.Length > 300 ? text.Substring(0, 300) + " ..." : text;
        }
    }
}