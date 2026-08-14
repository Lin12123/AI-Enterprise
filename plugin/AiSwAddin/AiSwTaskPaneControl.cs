using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using SolidWorks.Interop.sldworks;

namespace AiSwAddin
{
    /// <summary>
    /// 任务窗格 UI 控件（WinForms UserControl），按设计稿重做视觉。
    ///
    /// 结构（自上而下）：
    ///   顶部渐变标题栏 → 模式/项目行 → 标准徽章行 → 三个功能卡片
    ///   → AI 助手就绪信息卡 + 日志区 → 底部输入卡 → 底部任务中心栏
    ///
    /// 说明：部分元素（项目下拉、标准徽章、云平台、任务中心栏）为展示性 UI，
    /// 暂不接后端；核心的“生成/校验/预演/执行”四步业务逻辑保留并接入功能卡与发送按钮。
    /// </summary>
    [ComVisible(true)]
    [ProgId(ProgId)]
    [ClassInterface(ClassInterfaceType.AutoDual)]
    public class AiSwTaskPaneControl : UserControl
    {
        public const string ProgId = "AiSwAddin.AiSwTaskPaneControl";

        /// <summary>用户点击标题栏 ✕ 时触发，用于通知宿主(AiSwAddin)关闭任务窗格。</summary>
        public event EventHandler CloseRequested;

        private ISldWorks _swApp;
        private readonly ServiceClient _client = new ServiceClient();
        private string _currentPlanJson = null;

        // 需要在事件中访问的控件
        private TextBox _inputBox;
        private TextBox _logBox;
        private FeatureCard _cardNew3d, _card3dTo2d, _cardUpload;
        private RoundButton _sendBtn;
        private ComboBox _targetBox;   // 目标：新建零件 / 当前文档

        /// <summary>3D 建模执行计划面板；生成/校验/预演通过后填充并显示，用户点"确认并执行"才真正建模。</summary>
        private PlanReviewPanel _planPanel;

        // 运行模式：0=企业协同, 1=离线本地
        private ModePillButton _modePill;
        private int _modeIndex = 0;
        private static readonly ModeItem[] _modeItems = new[]
        {
            new ModeItem("☁", "企业协同模式", "实时检索知识库与标准"),
            new ModeItem("⛆", "离线本地模式", "使用缓存规则，不受断网影响")
        };

        public AiSwTaskPaneControl()
        {
            BuildUi();
        }

        public void SetSolidWorks(ISldWorks swApp)
        {
            _swApp = swApp;
            AppendLog("[就绪] AI 助手已加载。请先启动本地服务(start_service.bat)。");
        }

        /// <summary>构建整体界面。</summary>
        private void BuildUi()
        {
            Width = 400;
            Height = 900;
            BackColor = Theme.PageBg;
            AutoScroll = true;                 // 高度不足时整体可滚动，避免内容被裁

            var root = new TableLayoutPanel
            {
                // 关键：Top + AutoSize，让容器按内容所需高度撑开；
                // 当撑开高度 > 可视区时，外层 UserControl 的 AutoScroll 会出现滚动条，
                // 而不是压缩 Absolute 行导致内容被裁切。
                Dock = DockStyle.Top,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                ColumnCount = 1,
                RowCount = 7,
                BackColor = Theme.PageBg,
                Padding = new Padding(0),
                // 保证整体不小于内容所需的最小高度（各固定行之和 + 日志最小高）
                MinimumSize = new Size(0, 62 + 52 + 88 + 90 + 160 + 180 + 40)
            };
            root.RowStyles.Add(new RowStyle(SizeType.Absolute, 62));   // 标题栏
            root.RowStyles.Add(new RowStyle(SizeType.Absolute, 52));   // 模式行(含标准徽章)
            root.RowStyles.Add(new RowStyle(SizeType.Absolute, 88));   // 功能卡片
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));       // 执行计划面板(高度随步骤数自适应)
            root.RowStyles.Add(new RowStyle(SizeType.Absolute, 160));  // 日志区(最小高度, 随窗口拉伸见下)
            root.RowStyles.Add(new RowStyle(SizeType.Absolute, 180));  // 输入卡
            root.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));   // 任务中心栏

            root.Controls.Add(BuildHeader(), 0, 0);
            root.Controls.Add(BuildModeRow(), 0, 1);
            root.Controls.Add(BuildFeatureCards(), 0, 2);
            root.Controls.Add(BuildReadyCard(), 0, 3);
            root.Controls.Add(BuildLogArea(), 0, 4);
            root.Controls.Add(BuildInputCard(), 0, 5);
            root.Controls.Add(BuildTaskBar(), 0, 6);

            Controls.Add(root);

            // 当空间富余时，让日志区随可视高度自动拉伸（填满剩余空间），
            // 空间不足时保持最小高度并由外层滚动条兜底。
            Resize += (s, e) => AdjustRootHeight(root);
            AdjustRootHeight(root);
        }

        /// <summary>
        /// 根据当前可视高度动态调整 root 高度：
        /// - 可视区足够高：root 撑满可视区，日志区(第4行)吃掉多余空间；
        /// - 可视区不够高：root 保持内容最小高度，触发外层 AutoScroll 滚动。
        /// </summary>
        private void AdjustRootHeight(TableLayoutPanel root)
        {
            if (root.RowStyles.Count < 5) return;

            // 除日志区外的行(0,1,2,3=执行计划,5,6)当前实际占用高度总和
            int[] heights = root.GetRowHeights();
            int fixedOthers = 0;
            for (int i = 0; i < heights.Length; i++)
            {
                if (i == 4) continue;   // 第 4 行 = 日志区，跳过
                fixedOthers += heights[i];
            }

            const int logMin = 160;
            int avail = ClientSize.Height;

            int logHeight = Math.Max(logMin, avail - fixedOthers);
            root.RowStyles[4].Height = logHeight;
        }

        // ---- 顶部渐变标题栏（全自绘，无白底）----
        private Control BuildHeader()
        {
            var header = new HeaderPanel(Theme.HeaderLeft, Theme.HeaderRight) { Dock = DockStyle.Fill };
            header.CloseClicked += (s, e) =>
            {
                // 通知宿主关闭当前任务窗格；订阅者会调用 ITaskpaneView.DeleteView() 移除窗格
                CloseRequested?.Invoke(this, EventArgs.Empty);
            };
            return header;
        }

        // ---- 模式行：离线模式下拉 + 标准徽章 ----
        private Control BuildModeRow()
        {
            var host = new Panel { Dock = DockStyle.Fill, BackColor = Theme.PageBg, Padding = new Padding(12, 8, 12, 4) };

            // 用横向 FlowLayoutPanel 承载：模式药丸按钮 + 三个徽章，自动排布、自适应宽度
            var flow = new FlowLayoutPanel
            {
                Dock = DockStyle.Fill,
                BackColor = Theme.PageBg,
                FlowDirection = FlowDirection.LeftToRight,
                WrapContents = true,   // 放不下时自动换行，避免溢出被裁切
                AutoScroll = false,
                Padding = new Padding(0)
            };

            // 模式药丸按钮（绿色圆角，图标+文字+箭头），点击弹出模式菜单
            _modePill = new ModePillButton
            {
                Glyph = _modeItems[_modeIndex].Glyph,
                Text = _modeItems[_modeIndex].Title.Replace("模式", ""),
                Size = new Size(130, 30),
                Margin = new Padding(0, 3, 8, 0)
            };
            _modePill.Click += OnModePillClick;

            flow.Controls.Add(_modePill);
            flow.Controls.Add(MakeBadge("📖", "GB/T 14689-2024", Theme.Primary));
            flow.Controls.Add(MakeBadge("🛡", "Q/HW 2026.2", Theme.Amber));
            flow.Controls.Add(MakeBadge("▣", "v2.4.1-sp2", Theme.Green));

            host.Controls.Add(flow);
            return host;
        }

        /// <summary>点击模式药丸：在按钮下方弹出模式选择浮层。</summary>
        private void OnModePillClick(object sender, EventArgs e)
        {
            var popup = new ModeDropdownForm(_modeItems, _modeIndex);
            // 定位到药丸按钮左下角
            var pt = _modePill.PointToScreen(new Point(0, _modePill.Height + 2));
            popup.Location = pt;
            popup.ItemSelected += OnModeSelected;
            popup.Show();
            popup.Activate();
        }

        /// <summary>选中某个模式后，更新药丸按钮显示并记录日志。</summary>
        private void OnModeSelected(int index)
        {
            _modeIndex = index;
            _modePill.Glyph = _modeItems[index].Glyph;
            _modePill.Text = _modeItems[index].Title.Replace("模式", "");
            _modePill.Invalidate();
            AppendLog("[模式] 已切换为：" + _modeItems[index].Title);
        }

        private BadgeLabel MakeBadge(string glyph, string text, Color accent)
        {
            return new BadgeLabel
            {
                Text = glyph + " " + text,
                AccentColor = accent,
                AutoSize = true,                        // 按文字自适应宽度
                Padding = new Padding(8, 3, 8, 3),      // 文字与圆角边框留白
                Margin = new Padding(0, 5, 4, 0)
            };
        }

        // ---- 三个功能卡片 ----
        private Control BuildFeatureCards()
        {
            var host = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                BackColor = Theme.PageBg,
                ColumnCount = 3,
                RowCount = 1,
                Padding = new Padding(12, 2, 12, 10)
            };
            host.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 33.3f));
            host.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 33.3f));
            host.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 33.3f));

            _cardNew3d = MakeFeatureCard("⬡", "新建 3D 零件", Theme.Primary, true, OnGenerateClick, drawCube: true);
            _card3dTo2d = MakeFeatureCard("▤", "3D 转 2D 出图", Theme.Purple, false,
                (s, e) => AppendLog("[提示] 3D 转 2D 出图为展示性功能。"));
            _cardUpload = MakeFeatureCard("☁", "上传云平台", Theme.Green, false,
                (s, e) => AppendLog("[提示] 上传云平台为展示性功能。"));

            host.Controls.Add(_cardNew3d, 0, 0);
            host.Controls.Add(_card3dTo2d, 1, 0);
            host.Controls.Add(_cardUpload, 2, 0);
            return host;
        }

        private FeatureCard MakeFeatureCard(string glyph, string text, Color accent, bool active, EventHandler onClick, bool drawCube = false)
        {
            var card = new FeatureCard
            {
                Dock = DockStyle.Fill,
                Margin = new Padding(4, 4, 4, 6),
                Glyph = glyph,
                Text = text,
                Accent = accent,
                DrawCubeIcon = drawCube,
                Selected = active
            };

            // 点击时先切换选中态，再执行各卡片自身的业务回调
            card.Click += (s, e) =>
            {
                SelectFeatureCard(card);
                if (onClick != null) onClick(s, e);
            };
            return card;
        }

        /// <summary>设置�张功能卡片为选中态，其余恢复未选中。</summary>
        private void SelectFeatureCard(FeatureCard selected)
        {
            foreach (var card in new[] { _cardNew3d, _card3dTo2d, _cardUpload })
            {
                if (card == null) continue;
                card.Selected = (card == selected);
            }
        }

        // ---- AI 助手就绪信息卡 / 执行计划面板（同一位置切换） ----
        private Control BuildReadyCard()
        {
            var host = new Panel { Dock = DockStyle.Fill, BackColor = Theme.PageBg, Padding = new Padding(12, 0, 12, 6) };
            _planPanel = new PlanReviewPanel { Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink };
            _planPanel.ShowIdleState("✦  AI 助手就绪",
                "请在上方选择功能模式或在下方输入框直接描述 CAD 建模、修改参数或工程图出图需求。");
            _planPanel.ModifyClicked += (s, e) => OnModifyPlan();
            _planPanel.ConfirmClicked += (s, e) => OnConfirmExecute();
            host.Controls.Add(_planPanel);
            return host;
        }

        /// <summary>「修改计划」按钮：把当前 prompt 保留在输入框，隐藏计划面板回到就绪态。</summary>
        private void OnModifyPlan()
        {
            _planPanel.ShowIdleState("✦  AI 助手就绪",
                "已放弃当前计划，请在下方修改需求后重新发送。");
            _currentPlanJson = null;
            if (_inputBox != null) _inputBox.Focus();
            AppendLog("[提示] 用户放弃当前计划，等待修改后重新发送。");
        }

        /// <summary>「确认并执行」按钮：走真实 SolidWorks 建模。</summary>
        private async void OnConfirmExecute()
        {
            if (string.IsNullOrEmpty(_currentPlanJson))
            {
                AppendLog("[错误] 当前没有可执行的计划。");
                return;
            }
            SetBusy(true);
            try
            {
                await ExecuteAsync();
                _planPanel.ShowIdleState("✦  执行完成",
                    "本次 3D 建模已完成，可继续在下方输入下一条需求。");
                _currentPlanJson = null;
            }
            finally
            {
                SetBusy(false);
            }
        }

        // ---- 运行日志区 ----
        private Control BuildLogArea()
        {
            var host = new Panel { Dock = DockStyle.Fill, BackColor = Theme.PageBg, Padding = new Padding(12, 0, 12, 6) };
            var card = new CardPanel { Dock = DockStyle.Fill, Padding = new Padding(6) };

            _logBox = new TextBox
            {
                Multiline = true,
                ReadOnly = true,
                ScrollBars = ScrollBars.Vertical,
                Dock = DockStyle.Fill,
                BorderStyle = BorderStyle.None,
                BackColor = Color.White,
                ForeColor = Theme.TextMain,
                Font = new Font("Consolas", 9)
            };
            card.Controls.Add(_logBox);
            host.Controls.Add(card);
            return host;
        }

        // ---- 底部输入卡：输入框 + 附件/指令 + 发送 ----
        private Control BuildInputCard()
        {
            var host = new Panel { Dock = DockStyle.Fill, BackColor = Theme.PageBg, Padding = new Padding(12, 0, 12, 6) };
            var card = new CardPanel { Dock = DockStyle.Fill, Padding = new Padding(10) };

            _inputBox = new TextBox
            {
                Multiline = true,
                BorderStyle = BorderStyle.None,
                Dock = DockStyle.Top,
                Height = 70,
                Font = Theme.Body(9.5f),
                ForeColor = Theme.TextMain,
                Text = "请描述建模需求，例如：做一个长100宽80厚10的底板，四角各开一个直径6的通孔"
            };

            var bottomBar = new Panel { Dock = DockStyle.Bottom, Height = 46, BackColor = Color.Transparent, Padding = new Padding(0, 4, 0, 4) };

            _sendBtn = new RoundButton
            {
                Text = "➤ 发送",
                Filled = true,
                Accent = Theme.Primary,
                Size = new Size(96, 38),
                Dock = DockStyle.Right
            };
            _sendBtn.Click += OnSendClick;

            var attach = new Label
            {
                Text = "📎 附件      ⌘ /指令",
                Font = Theme.Body(9),
                ForeColor = Theme.TextSub,
                Dock = DockStyle.Fill,
                TextAlign = ContentAlignment.MiddleLeft,
                BackColor = Color.Transparent
            };

            // 先加 Fill，再加 Right，确保发送按钮固定在右侧、附件标签填充左侧剩余空间
            bottomBar.Controls.Add(attach);
            bottomBar.Controls.Add(_sendBtn);

            card.Controls.Add(bottomBar);
            card.Controls.Add(_inputBox);
            host.Controls.Add(card);
            return host;
        }

        // ---- 底部任务中心栏 ----
        private Control BuildTaskBar()
        {
            var bar = new Panel { Dock = DockStyle.Fill, BackColor = Color.FromArgb(237, 240, 245) };
            var left = new Label
            {
                Text = "☰ 抽屉内任务中心 (非阻塞后台队列)",
                Font = Theme.Body(9, FontStyle.Bold),
                ForeColor = Theme.TextMain,
                AutoSize = true,
                Location = new Point(12, 11),
                BackColor = Color.Transparent
            };
            var right = new Label
            {
                Text = "SolidWorks 写入锁  ⌃",
                Font = Theme.Body(9),
                ForeColor = Theme.TextSub,
                AutoSize = true,
                Anchor = AnchorStyles.Top | AnchorStyles.Right,
                Location = new Point(250, 11),
                BackColor = Color.Transparent
            };
            bar.Controls.Add(left);
            bar.Controls.Add(right);
            return bar;
        }

        // ==== 通用工具 ====

        private void AppendLog(string message)
        {
            if (_logBox == null) return;
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
            if (_sendBtn != null) _sendBtn.Enabled = !busy;
            if (_cardNew3d != null) _cardNew3d.Enabled = !busy;
        }

        // ==== 业务逻辑：发送 = 生成→校验→预演→执行(带确认) 的一体化流程 ====

        /// <summary>"发送"按钮：解析→校验→预演，通过后把计划展示到面板中，等用户确认执行。</summary>
        private async void OnSendClick(object sender, EventArgs e)
        {
            string prompt = _inputBox.Text.Trim();
            if (string.IsNullOrEmpty(prompt))
            {
                AppendLog("[错误] 请先输入建模需求。");
                return;
            }

            SetBusy(true);
            try
            {
                if (!await GeneratePlanAsync(prompt)) return;
                if (!await ValidateAsync()) return;
                if (!await DryRunAsync()) return;

                // 生成/校验/预演通过：解析步骤 → 填充 PlanReviewPanel，等用户点"确认并执行"
                var steps = ExtractSteps(_currentPlanJson);
                string partName = ExtractStringField(_currentPlanJson, "part_name") ?? "AI-Part";
                _planPanel.PlanTitle = "◎  3D 建模执行计划";
                _planPanel.PlanDescription = string.Format(
                    "为当前 {0} 模型生成 3D 参数建树与工程图关联控制，共 {1} 步。",
                    partName, steps.Count);
                _planPanel.SetSteps(steps);
                AppendLog("[待确认] 计划已就绪，请在计划面板中点击「确认并执行」。");
            }
            finally
            {
                SetBusy(false);
            }
        }

        /// <summary>功能卡“新建 3D 零件”：等同于发送流程。</summary>
        private void OnGenerateClick(object sender, EventArgs e)
        {
            OnSendClick(sender, e);
        }

        private async System.Threading.Tasks.Task<bool> GeneratePlanAsync(string prompt)
        {
            AppendLog("[生成] 正在调用本地 AI 服务解析需求...");
            try
            {
                string resp = await _client.GeneratePlanAsync(prompt, "local");
                _currentPlanJson = ExtractPlanJson(resp);
                if (_currentPlanJson == null)
                {
                    AppendLog("[生成失败] 服务返回未包含有效 plan：" + Truncate(resp));
                    return false;
                }
                AppendLog("[生成成功] 已生成 FeaturePlan。");
                return true;
            }
            catch (Exception ex)
            {
                AppendLog("[生成异常] " + ex.Message);
                return false;
            }
        }

        private async System.Threading.Tasks.Task<bool> ValidateAsync()
        {
            AppendLog("[校验] 正在进行安全与几何规则校验...");
            try
            {
                string resp = await _client.ValidateAsync(_currentPlanJson);
                bool allowed = resp.Contains("\"allowed\": true") || resp.Contains("\"allowed\":true");
                if (allowed) { AppendLog("[校验通过] 计划符合规则。"); return true; }
                AppendLog("[校验未通过] " + Truncate(resp));
                return false;
            }
            catch (Exception ex)
            {
                AppendLog("[校验异常] " + ex.Message);
                return false;
            }
        }

        private async System.Threading.Tasks.Task<bool> DryRunAsync()
        {
            AppendLog("[预演] 正在生成执行计划(不修改模型)...");
            try
            {
                string resp = await _client.DryRunAsync(_currentPlanJson);
                bool ok = resp.Contains("\"ok\": true") || resp.Contains("\"ok\":true");
                if (ok) { AppendLog("[预演通过] 执行计划已就绪。"); return true; }
                AppendLog("[预演失败] " + Truncate(resp));
                return false;
            }
            catch (Exception ex)
            {
                AppendLog("[预演异常] " + ex.Message);
                return false;
            }
        }

        private async System.Threading.Tasks.Task ExecuteAsync()
        {
            bool useActiveDoc = _targetBox != null && _targetBox.SelectedIndex == 1;
            AppendLog(useActiveDoc
                ? "[执行] 正在当前文档中驱动 SolidWorks 建模..."
                : "[执行] 正在新建零件并驱动 SolidWorks 建模...");
            try
            {
                string resp = await _client.ExecuteAsync(_currentPlanJson, useActiveDoc);
                bool ok = resp.Contains("\"ok\": true") || resp.Contains("\"ok\":true");
                AppendLog(ok ? "[执行完成] SolidWorks 建模成功。" : "[执行失败] " + Truncate(resp));
            }
            catch (Exception ex)
            {
                AppendLog("[执行异常] " + ex.Message);
            }
        }

        // ---- 轻量 JSON 辅助 ----

        private static string ExtractPlanJson(string resp)
        {
            if (string.IsNullOrEmpty(resp)) return null;
            int keyIndex = resp.IndexOf("\"plan\"", StringComparison.Ordinal);
            if (keyIndex < 0) return null;
            int braceStart = resp.IndexOf('{', keyIndex);
            if (braceStart < 0) return null;
            int depth = 0;
            for (int i = braceStart; i < resp.Length; i++)
            {
                if (resp[i] == '{') depth++;
                else if (resp[i] == '}')
                {
                    depth--;
                    if (depth == 0) return resp.Substring(braceStart, i - braceStart + 1);
                }
            }
            return null;
        }

        /// <summary>从 FeaturePlan JSON 的 operations 数组中提取用于 UI 展示的步骤列表。</summary>
        private static System.Collections.Generic.List<PlanStep> ExtractSteps(string planJson)
        {
            var list = new System.Collections.Generic.List<PlanStep>();
            if (string.IsNullOrEmpty(planJson)) return list;

            int opsIdx = planJson.IndexOf("\"operations\"", StringComparison.Ordinal);
            if (opsIdx < 0) return list;
            int arrStart = planJson.IndexOf('[', opsIdx);
            if (arrStart < 0) return list;

            // 逐个提取顶层 { ... } 对象
            int depth = 0;
            int objStart = -1;
            int index = 0;
            for (int i = arrStart; i < planJson.Length; i++)
            {
                char c = planJson[i];
                if (c == '[') { depth++; continue; }
                if (c == ']') { depth--; if (depth == 0) break; continue; }
                if (c == '{')
                {
                    if (depth == 1) objStart = i;
                    depth++;
                }
                else if (c == '}')
                {
                    depth--;
                    if (depth == 1 && objStart >= 0)
                    {
                        string obj = planJson.Substring(objStart, i - objStart + 1);
                        index++;
                        list.Add(BuildStepFromJsonObject(index, obj));
                        objStart = -1;
                    }
                }
            }
            return list;
        }

        /// <summary>基于一个 operation 的 JSON 对象文本，产出用于 UI 展示的 PlanStep。</summary>
        private static PlanStep BuildStepFromJsonObject(int index, string obj)
        {
            string op = ExtractStringField(obj, "op") ?? "unknown";
            string id = ExtractStringField(obj, "id") ?? ("op" + index);

            // 中文名 & API 名映射（覆盖常见 op；其余走通用兜底）
            string nameCn, apiName;
            switch (op)
            {
                case "sketch_rectangle":
                    nameCn = "草图 (Sketch)"; apiName = "Sketch.CreateRectangle"; break;
                case "sketch_circle":
                    nameCn = "草图 (Sketch)"; apiName = "Sketch.CreateCircle"; break;
                case "extrude_boss":
                    nameCn = "凸台-拉伸 (Boss-Extrude)"; apiName = "FeatureExtrude.Boss"; break;
                case "extrude_cut":
                case "cut_extrude":
                    nameCn = "切除-拉伸 (Cut-Extrude)"; apiName = "FeatureCut.Extrude"; break;
                case "fillet":
                    nameCn = "圆角 (Fillet)"; apiName = "FeatureFillet.Corner"; break;
                case "chamfer":
                    nameCn = "倒角 (Chamfer)"; apiName = "FeatureChamfer.Edge"; break;
                case "hole":
                case "hole_wizard":
                    nameCn = "异型孔向导 (Hole)"; apiName = "HoleWizard.CutExtrude"; break;
                case "revolve":
                    nameCn = "旋转 (Revolve)"; apiName = "FeatureRevolve.Boss"; break;
                case "pattern":
                case "linear_pattern":
                    nameCn = "线性阵列 (Linear Pattern)"; apiName = "FeaturePattern.Linear"; break;
                case "circular_pattern":
                    nameCn = "圆周阵列 (Circular Pattern)"; apiName = "FeaturePattern.Circular"; break;
                case "mirror":
                    nameCn = "镜像 (Mirror)"; apiName = "FeatureMirror.Body"; break;
                case "shell":
                    nameCn = "抽壳 (Shell)"; apiName = "FeatureShell.Thin"; break;
                case "material_properties":
                    nameCn = "材料属性 (Material)"; apiName = "PartDoc.SetMaterial"; break;
                default:
                    nameCn = op + " (" + id + ")"; apiName = "Feature." + op; break;
            }

            string desc = BuildStepDescription(op, obj);
            return new PlanStep(index, nameCn, apiName, desc);
        }

        /// <summary>基于 operation 的关键参数生成一句简短描述（尽量像"绘制中心 Φ20 mm 通孔"这样的可读文本）。</summary>
        private static string BuildStepDescription(string op, string obj)
        {
            string width = ExtractNumberField(obj, "width");
            string length = ExtractNumberField(obj, "length");
            string height = ExtractNumberField(obj, "height");
            string depth = ExtractNumberField(obj, "depth");
            string diameter = ExtractNumberField(obj, "diameter");
            string radius = ExtractNumberField(obj, "radius");
            string plane = ExtractStringField(obj, "plane") ?? ExtractStringField(obj, "sketch_plane");
            string material = ExtractStringField(obj, "material");

            switch (op)
            {
                case "sketch_rectangle":
                    return string.Format("{0}绘制 {1}×{2} mm 矩形草图",
                        plane != null ? "在" + plane + "上" : "", length ?? "?", width ?? "?");
                case "sketch_circle":
                    return string.Format("{0}绘制 Φ{1} mm 圆形草图",
                        plane != null ? "在" + plane + "上" : "", diameter ?? "?");
                case "extrude_boss":
                    return "拉伸凸台生成实体" + (depth != null ? "，深 " + depth + " mm" : "")
                        + (material != null ? "，赋予 " + material : "");
                case "extrude_cut":
                case "cut_extrude":
                    return "拉伸切除移除材料" + (depth != null ? "，深 " + depth + " mm" : "");
                case "fillet":
                    return "添加圆角" + (radius != null ? " R" + radius + " mm" : "");
                case "chamfer":
                    return "添加倒角" + (radius != null ? " " + radius + " mm" : "");
                case "hole":
                case "hole_wizard":
                    return "打孔" + (diameter != null ? " Φ" + diameter + " mm" : "");
                case "material_properties":
                    return material != null ? "设置材质：" + material : "设置材料属性";
                default:
                    return "执行 " + op + " 操作";
            }
        }

        /// <summary>从 JSON 文本中读取顶层字符串字段（简易，不支持转义嵌套）。</summary>
        private static string ExtractStringField(string json, string key)
        {
            if (string.IsNullOrEmpty(json) || string.IsNullOrEmpty(key)) return null;
            string needle = "\"" + key + "\"";
            int i = json.IndexOf(needle, StringComparison.Ordinal);
            if (i < 0) return null;
            i = json.IndexOf(':', i);
            if (i < 0) return null;
            // 跳过空白
            while (++i < json.Length && (json[i] == ' ' || json[i] == '\t')) { }
            if (i >= json.Length || json[i] != '"') return null;
            int start = i + 1;
            int end = json.IndexOf('"', start);
            if (end < 0) return null;
            return json.Substring(start, end - start);
        }

        /// <summary>从 JSON 文本中读取顶层数值字段（返回原始文本，保留精度/单位习惯）。</summary>
        private static string ExtractNumberField(string json, string key)
        {
            if (string.IsNullOrEmpty(json) || string.IsNullOrEmpty(key)) return null;
            string needle = "\"" + key + "\"";
            int i = json.IndexOf(needle, StringComparison.Ordinal);
            if (i < 0) return null;
            i = json.IndexOf(':', i);
            if (i < 0) return null;
            while (++i < json.Length && (json[i] == ' ' || json[i] == '\t')) { }
            if (i >= json.Length) return null;
            int start = i;
            int end = start;
            while (end < json.Length && "0123456789.-eE".IndexOf(json[end]) >= 0) end++;
            if (end == start) return null;
            // 去除末尾的小数点
            string s = json.Substring(start, end - start).TrimEnd('.');
            return s;
        }

        private static string Truncate(string text)
        {
            if (string.IsNullOrEmpty(text)) return "";
            return text.Length > 300 ? text.Substring(0, 300) + " ..." : text;
        }
    }
}