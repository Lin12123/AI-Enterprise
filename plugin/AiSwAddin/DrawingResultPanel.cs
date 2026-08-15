using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;

namespace AiSwAddin
{
    /// <summary>
    /// 2D 出图完成成果卡：3D 转 2D 出图执行完成后，作为一条 AI 消息卡片挂进会话流。
    ///
    /// 视觉结构（对应设计稿绿色成功卡）：
    ///   ┌───────────────────────────────────────────┐
    ///   │ ✓  2D 出图执行完成 (成功)        [状态：成功] │
    ///   │    全部 N 个视图及 M 项尺寸标注已绘制并导出     │
    ///   │  图纸规格与投影   A3 横向 / 1:2 / 第一角        │
    ///   │  视图明细        主/俯/左/轴测 + A-A 全剖 ...   │
    ///   │  标注与公差      28 项驱动尺寸 100% 自动覆盖 ... │
    ///   │  图层与线型规范   Q/HW2026.2 粗 0.5 细 0.25mm    │
    ///   │  文件导出格式    SLDDRW / DWG / PDF/A          │
    ///   │        [上传企业云平台]   [撤销本次修改]        │
    ///   └───────────────────────────────────────────┘
    ///
    /// 与 ResultBoardPanel 一致：继承 CardPanel，用 TableLayoutPanel 分行；
    /// header 自绘(✓圆图标 + 标题 + 状态徽章)，中间参数列表自绘(标签:值两列)，footer 两个 RoundButton。
    /// </summary>
    internal class DrawingResultPanel : CardPanel
    {
        private readonly TableLayoutPanel _root;
        private readonly Panel _headerBox;
        private readonly Panel _specBox;
        private readonly TableLayoutPanel _footerBox;
        private readonly RoundButton _uploadBtn;  // 上传企业云平台
        private readonly RoundButton _undoBtn;     // 撤销本次修改

        /// <summary>点击「上传企业云平台」时触发。</summary>
        public event EventHandler UploadClicked;
        /// <summary>点击「撤销本次修改」时触发。</summary>
        public event EventHandler UndoClicked;

        private string _title = "2D 出图执行完成 (成功)";
        private string _subtitle = "全部视图及尺寸标注已绘制并导出";
        private string _statusText = "成功";

        // 参数列表(标签 -> 值)，自绘为两列
        private readonly List<KeyValuePair<string, string>> _specs = new List<KeyValuePair<string, string>>();

        private const int HeaderH = 68;
        private const int SpecRowH = 26;    // 每条参数行高
        private const int SpecPadV = 6;     // 参数区上下留白
        private const int LabelW = 132;     // 标签列宽

        public DrawingResultPanel()
        {
            // 绿色成功卡：浅绿描边 + 淡绿底
            BorderColor = Theme.GreenPillBorder;
            BorderWidth = 1;
            Radius = 10;
            FillColor = Color.FromArgb(240, 250, 245);
            Padding = new Padding(1);

            _root = new TableLayoutPanel
            {
                Dock = DockStyle.Top,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                ColumnCount = 1,
                RowCount = 3,
                BackColor = Color.Transparent,
                Padding = new Padding(0),
                Margin = new Padding(0)
            };
            _root.RowStyles.Add(new RowStyle(SizeType.Absolute, HeaderH));  // header
            _root.RowStyles.Add(new RowStyle(SizeType.AutoSize));          // 参数列表
            _root.RowStyles.Add(new RowStyle(SizeType.AutoSize));          // footer 按钮行

            // === Header：自绘 ✓圆标 + 标题 + 副标题 + 状态徽章 ===
            _headerBox = new Panel
            {
                Dock = DockStyle.Fill,
                BackColor = Color.Transparent,
                Margin = new Padding(0),
                Padding = new Padding(0)
            };
            _headerBox.Paint += Header_Paint;

            // === 参数列表：自绘标签:值两列，高度随条数自适应 ===
            _specBox = new Panel
            {
                Dock = DockStyle.Fill,
                BackColor = Color.Transparent,
                Margin = new Padding(10, 0, 10, 4),
                Padding = new Padding(0),
                Height = SpecPadV * 2
            };
            _specBox.Paint += Spec_Paint;

            // === Footer：两个操作按钮，等宽铺满卡片 ===
            _footerBox = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 2,
                RowCount = 1,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                BackColor = Color.Transparent,
                Padding = new Padding(10, 4, 10, 12),
                Margin = new Padding(0)
            };
            _footerBox.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50f));
            _footerBox.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50f));
            _footerBox.RowStyles.Add(new RowStyle(SizeType.Absolute, 46));
            _uploadBtn = new RoundButton
            {
                Text = "上传企业云平台",
                Filled = true,
                Accent = Theme.Green,
                Dock = DockStyle.Fill,
                Margin = new Padding(4, 3, 4, 3)
            };
            _undoBtn = new RoundButton
            {
                Text = "撤销本次修改",
                Filled = false,
                Accent = Color.FromArgb(214, 90, 90),
                Dock = DockStyle.Fill,
                Margin = new Padding(4, 3, 4, 3)
            };
            _uploadBtn.Click += (s, e) => UploadClicked?.Invoke(this, EventArgs.Empty);
            _undoBtn.Click += (s, e) => UndoClicked?.Invoke(this, EventArgs.Empty);
            _footerBox.Controls.Add(_uploadBtn, 0, 0);
            _footerBox.Controls.Add(_undoBtn, 1, 0);

            _root.Controls.Add(_headerBox, 0, 0);
            _root.Controls.Add(_specBox, 0, 1);
            _root.Controls.Add(_footerBox, 0, 2);
            Controls.Add(_root);
        }

        // 卡片底部固定留白
        private const int CardBottomPad = 10;

        protected override void OnSizeChanged(EventArgs e)
        {
            base.OnSizeChanged(e);
            SyncHeight();
        }

        private void SyncHeight()
        {
            if (_root == null) return;
            int contentH = _root.PreferredSize.Height;
            int target = contentH + CardBottomPad + Padding.Vertical;
            if (Height != target) Height = target;
        }

        /// <summary>设置出图成果卡文案与参数列表。</summary>
        /// <param name="viewCount">视图数量</param>
        /// <param name="dimCount">尺寸标注数量</param>
        /// <param name="specs">参数列表(标签 -> 值)，为 null 时用默认占位示例</param>
        public void SetResult(int viewCount, int dimCount, IEnumerable<KeyValuePair<string, string>> specs)
        {
            _title = "2D 出图执行完成 (成功)";
            _subtitle = string.Format("全部 {0} 个视图及 {1} 项尺寸标注已绘制并导出", viewCount, dimCount);
            _statusText = "成功";

            _specs.Clear();
            if (specs != null)
            {
                foreach (var kv in specs) _specs.Add(kv);
            }
            if (_specs.Count == 0)
            {
                // 无后端明细时，用占位示例展示样式
                _specs.Add(new KeyValuePair<string, string>("图纸规格与投影", "A3 横向 / 1:2 / 第一角"));
                _specs.Add(new KeyValuePair<string, string>("视图明细", "主/俯/左/轴测 · A-A 全剖 · 详图 B（共 6 视图）"));
                _specs.Add(new KeyValuePair<string, string>("标注与公差", "28 项驱动尺寸 100% 自动覆盖 · GB/T 14689 · IT8"));
                _specs.Add(new KeyValuePair<string, string>("图层与线型规范", "Q/HW2026.2 · 粗实线 0.5mm · 细实线 0.25mm"));
                _specs.Add(new KeyValuePair<string, string>("文件导出格式", "SLDDRW · DWG · PDF/A"));
            }

            // 参数区高度随条数自适应
            _specBox.Height = _specs.Count * SpecRowH + SpecPadV * 2;
            _headerBox.Invalidate();
            _specBox.Invalidate();
            SyncHeight();
        }

        private void Header_Paint(object sender, PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;

            int pad = 12;
            int r = 22, cx = pad, cy = (_headerBox.Height - r) / 2;
            var iconRect = new Rectangle(cx, cy, r, r);
            using (var fill = new SolidBrush(Theme.Green))
                g.FillEllipse(fill, iconRect);
            using (var font = Theme.Body(11, FontStyle.Bold))
                TextRenderer.DrawText(g, "✓", font, iconRect, Color.White,
                    TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);

            int textLeft = cx + r + 10;

            // 状态徽章（右上）：浅绿底 + 绿字
            int badgeLeft = _headerBox.Width;
            using (var badgeFont = Theme.Body(8.5f, FontStyle.Bold))
            {
                string badge = "状态：" + _statusText;
                Size bs = TextRenderer.MeasureText(g, badge, badgeFont);
                int bw = bs.Width + 18, bh = 22;
                badgeLeft = _headerBox.Width - bw - pad;
                var bRect = new Rectangle(badgeLeft, (_headerBox.Height - bh) / 2, bw, bh);
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

            using (var titleFont = Theme.Body(10.5f, FontStyle.Bold))
            using (var subFont = Theme.Body(9f))
            {
                int titleW = Math.Max(80, badgeLeft - 8 - textLeft);
                var titleRect = new Rectangle(textLeft, 12,titleW, 22);
                TextRenderer.DrawText(g, _title, titleFont, titleRect, Theme.TextMain,
                    TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);

                var subRect = new Rectangle(textLeft, 36, _headerBox.Width - textLeft - pad, 22);
                TextRenderer.DrawText(g, _subtitle, subFont, subRect, Theme.TextSub,
                    TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis);
            }
        }

        private void Spec_Paint(object sender, PaintEventArgs e)
        {
            if (_specs.Count == 0) return;
            var g = e.Graphics;
       g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;

            int pad = 2;
            int y = SpecPadV;
            int valLeft = pad + LabelW + 8;
            int valW = Math.Max(60, _specBox.Width - valLeft - pad);

            using (var labelFont = Theme.Body(9f, FontStyle.Bold))
            using (var valFont = Theme.Body(9f))
            {
                foreach (var kv in _specs)
                {
                    var labelRect = new Rectangle(pad, y, LabelW, SpecRowH);
                    TextRenderer.DrawText(g, kv.Key, labelFont, labelRect, Theme.TextSub,
                        TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);

                    var valRect = new Rectangle(valLeft, y, valW, SpecRowH);
                    TextRenderer.DrawText(g, kv.Value, valFont, valRect, Theme.TextMain,
                        TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis);
                    y += SpecRowH;
                }
            }
        }

        protected override void OnResize(EventArgs eventargs)
        {
            base.OnResize(eventargs);
            if (_headerBox != null) _headerBox.Invalidate();
            if (_specBox != null) _specBox.Invalidate();
        }
    }
}