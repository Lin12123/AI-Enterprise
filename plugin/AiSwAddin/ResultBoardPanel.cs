using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;

namespace AiSwAddin
{
    /// <summary>
    /// 成果看板卡片：建模成功后由「查看成果与提交」触发，作为一条 AI 消息卡片挂进会话流。
    ///
    /// 视觉结构（对应设计稿绿色成功卡）：
    ///   ┌───────────────────────────────────────────┐
    ///   │ ✓  3D 建模执行完成 (成功)        [状态：成功] │
    ///   │    全部 N 项 3D CAD 几何特征已成功建树写入模型  │
    ///   │ [3D转2D出图] [上传企业云平台] [撤销本次修改]   │
    ///   └───────────────────────────────────────────┘
    ///
    /// 与 PlanReviewPanel / DiagnosticPanel 一致：继承 CardPanel，用 TableLayoutPanel 分行；
    /// header 自绘(✓圆图标 + 标题 + 状态徽章)，footer 放三个 RoundButton。
    /// </summary>
    internal class ResultBoardPanel : CardPanel
    {
        private readonly TableLayoutPanel _root;
        private readonly Panel _headerBox;
        private readonly FlowLayoutPanel _footerBox;
        private readonly RoundButton _drawBtn;    // 3D 转 2D 出图
        private readonly RoundButton _uploadBtn;  // 上传企业云平台
        private readonly RoundButton _undoBtn;    // 撤销本次修改
        /// <summary>点击「3D转2D出图」时触发。</summary>
        public event EventHandler DrawClicked;
        /// <summary>点击「上传企业云平台」时触发。</summary>
        public event EventHandler UploadClicked;
        /// <summary>点击「撤销本次修改」时触发。</summary>
        public event EventHandler UndoClicked;

        private string _title = "3D 建模执行完成 (成功)";
        private string _subtitle = "全部特征已成功建树写入模型";
        private string _statusText = "成功";

        public ResultBoardPanel()
        {
            // 绿色成功卡：浅绿描边 + 淡绿底
            BorderColor = Theme.GreenPillBorder;
            BorderWidth = 1;
            Radius = 10;
            FillColor = Color.FromArgb(240, 250, 245);
            Padding = new Padding(1);

            _root = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 1,
                RowCount = 2,
                BackColor = Color.Transparent,
                Padding = new Padding(0),
                Margin = new Padding(0)
            };
            _root.RowStyles.Add(new RowStyle(SizeType.Absolute, 62));  // header
            _root.RowStyles.Add(new RowStyle(SizeType.AutoSize));      // footer 按钮行(可换行)

            // === Header：自绘 ✓圆标 + 标题 + 副标题 + 状态徽章 ===
            _headerBox = new Panel
            {
                Dock = DockStyle.Fill,
                BackColor = Color.Transparent,
                Margin = new Padding(0),
                Padding = new Padding(0)
            };
            _headerBox.Paint += Header_Paint;

            // === Footer：三个操作按钮(FlowLayoutPanel 自动换行，窄窗格不截断) ===
            _footerBox = new FlowLayoutPanel
            {
                Dock = DockStyle.Fill,
                FlowDirection = FlowDirection.LeftToRight,
                WrapContents = true,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                BackColor = Color.Transparent,
                Padding = new Padding(12, 8, 12, 12),
                Margin = new Padding(0)
            };
            _drawBtn = new RoundButton
            {
                Text = "📄  3D 转 2D 出图",
                Filled = true,
                Accent = Theme.Purple,
                Size = new Size(150, 40),
                Margin = new Padding(6, 6, 6, 6)
            };
            _uploadBtn = new RoundButton
            {
                Text = "☁  上传企业云平台",
                Filled = true,
                Accent = Theme.Green,
                Size = new Size(162, 40),
                Margin = new Padding(6, 6, 6, 6)
            };
            _undoBtn = new RoundButton
            {
                Text = "↩  撤销本次修改",
                Filled = false,
                Accent = Color.FromArgb(214, 90, 90),
                Size = new Size(146, 40),
                Margin = new Padding(6, 6, 6, 6)
            };
            _drawBtn.Click += (s, e) => DrawClicked?.Invoke(this, EventArgs.Empty);
            _uploadBtn.Click += (s, e) => UploadClicked?.Invoke(this, EventArgs.Empty);
            _undoBtn.Click += (s, e) => UndoClicked?.Invoke(this, EventArgs.Empty);
            _footerBox.Controls.Add(_drawBtn);
            _footerBox.Controls.Add(_uploadBtn);
            _footerBox.Controls.Add(_undoBtn);

            _root.Controls.Add(_headerBox, 0, 0);
            _root.Controls.Add(_footerBox, 0, 1);
            Controls.Add(_root);
        }

        /// <summary>设置成果卡文案。featureCount 为已写入的几何特征数量。</summary>
        public void SetResult(int featureCount)
        {
            _title = "3D 建模执行完成 (成功)";
            _subtitle = string.Format("全部 {0} 项 3D CAD 几何特征已成功建树写入模型", featureCount);
            _statusText = "成功";
            _headerBox.Invalidate();
        }

        private void Header_Paint(object sender, PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;

            int pad = 12;
            // ✓ 圆图标
            int r = 22, cx = pad, cy = (_headerBox.Height - r) / 2;
            var iconRect = new Rectangle(cx, cy, r, r);
            using (var fill = new SolidBrush(Theme.Green))
                g.FillEllipse(fill, iconRect);
            using (var font = Theme.Body(11, FontStyle.Bold))
                TextRenderer.DrawText(g, "✓", font, iconRect, Color.White,
                    TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);

            int textLeft = cx + r + 10;

            // 状态徽章（右上）：浅绿底 + 绿字
            using (var badgeFont = Theme.Body(8.5f, FontStyle.Bold))
            {
                string badge = "状态：" + _statusText;
                Size bs = TextRenderer.MeasureText(g, badge, badgeFont);
                int bw = bs.Width + 18, bh = 22;
                var bRect = new Rectangle(_headerBox.Width - bw - pad, (_headerBox.Height - bh) / 2, bw, bh);
                using (var path = GfxUtil.RoundedRect(bRect, 11))
                using (var bfill = new SolidBrush(Theme.GreenPillBg))
                using (var bpen = new Pen(Theme.GreenPillBorder, 1))
                {
                    g.FillPath(bfill, path);
                    g.DrawPath(bpen, path);
                }
                TextRenderer.DrawText(g, badge, badgeFont, bRect, Theme.Green,
                    TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);
            }

            // 标题 + 副标题
            using (var titleFont = Theme.Body(10.5f, FontStyle.Bold))
            using (var subFont = Theme.Body(9f))
            {
                var titleRect = new Rectangle(textLeft, 10, _headerBox.Width - textLeft - 110, 22);
                TextRenderer.DrawText(g, _title, titleFont, titleRect, Theme.TextMain,
                    TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis);

                var subRect = new Rectangle(textLeft, 32, _headerBox.Width - textLeft - pad, 22);
                TextRenderer.DrawText(g, _subtitle, subFont, subRect, Theme.TextSub,
                    TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis);
            }
        }

        /// <summary>宽度变化时重绘 header（状态徽章右对齐、副标题裁剪宽度需要跟随）。</summary>
        protected override void OnResize(EventArgs eventargs)
        {
            base.OnResize(eventargs);
            if (_headerBox != null) _headerBox.Invalidate();
        }
    }
}