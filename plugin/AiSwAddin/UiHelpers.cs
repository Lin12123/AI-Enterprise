using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;

namespace AiSwAddin
{
    /// <summary>
    /// UI 主题色与字体常量。集中管理，便于统一风格。
    /// 取色参考目标设计稿（蓝紫渐变、浅灰背景、圆角卡片）。
    /// </summary>
    internal static class Theme
    {
        // 顶部标题栏渐变（左蓝 → 右青绿）
        public static readonly Color HeaderLeft = Color.FromArgb(59, 91, 219);
        public static readonly Color HeaderRight = Color.FromArgb(38, 166, 154);

        // 主体背景与卡片
        public static readonly Color PageBg = Color.FromArgb(245, 247, 250);
        public static readonly Color CardBg = Color.White;
        public static readonly Color CardBorder = Color.FromArgb(224, 228, 234);
        public static readonly Color CardBorderActive = Color.FromArgb(59, 91, 219);

        // 文本
        public static readonly Color TextMain = Color.FromArgb(33, 41, 54);
        public static readonly Color TextSub = Color.FromArgb(108, 117, 130);
        public static readonly Color TextWhite = Color.White;

        // 强调色
        public static readonly Color Primary = Color.FromArgb(59, 91, 219);
        public static readonly Color Purple = Color.FromArgb(139, 92, 246);
        public static readonly Color Green = Color.FromArgb(34, 160, 120);
        public static readonly Color Amber = Color.FromArgb(214, 158, 46);

        // 模式药丸按钮：浅绿底 + 绿字/绿边
        public static readonly Color GreenPillBg = Color.FromArgb(226, 245, 236);
        public static readonly Color GreenPillBorder = Color.FromArgb(150, 210, 180);
        public static Font Title(float size, FontStyle style = FontStyle.Bold)
            => new Font("Microsoft YaHei", size, style);
        public static Font Body(float size, FontStyle style = FontStyle.Regular)
            => new Font("Microsoft YaHei", size, style);
    }

    /// <summary>绘图工具：生成圆角矩形路径。</summary>
    internal static class GfxUtil
    {
        public static GraphicsPath RoundedRect(Rectangle r, int radius)
        {
            int d = radius * 2;
            var path = new GraphicsPath();
            if (radius <= 0)
            {
                path.AddRectangle(r);
                path.CloseFigure();
                return path;
            }
            path.AddArc(r.X, r.Y, d, d, 180, 90);
            path.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            path.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            path.CloseFigure();
            return path;
        }
    }

    /// <summary>横向渐变面板，用于顶部标题栏。</summary>
    internal class GradientPanel : Panel
    {
        private Color _left, _right;
        public GradientPanel(Color left, Color right)
        {
            _left = left;
            _right = right;
            DoubleBuffered = true;
            SetStyle(ControlStyles.ResizeRedraw, true);   // 拉伸时整体重绘，避免残影
        }
        protected override void OnPaint(PaintEventArgs e)
        {
            if (Width <= 0 || Height <= 0) { base.OnPaint(e); return; }
            using (var brush = new LinearGradientBrush(
                ClientRectangle, _left, _right, LinearGradientMode.Horizontal))
            {
                e.Graphics.FillRectangle(brush, ClientRectangle);
            }
            base.OnPaint(e);
        }
    }

    /// <summary>
    /// 顶部标题栏：渐变背景 + 全自绘的图标/标题/版本徽章/关闭按钮。
    /// 文字直接绘制在渐变上，避免子 Label 在自绘背景上产生白底。
    /// </summary>
    internal class HeaderPanel : Panel
    {
        private readonly Color _left, _right;
        public event EventHandler CloseClicked;
        private Rectangle _closeRect;

        public HeaderPanel(Color left, Color right)
        {
            _left = left;
            _right = right;
            DoubleBuffered = true;
            // 拉宽/拉高时整体重绘，避免关闭按钮等右对齐元素残留旧位置的重影
            SetStyle(ControlStyles.ResizeRedraw, true);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            if (Width <= 0 || Height <= 0) { base.OnPaint(e); return; }
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;

            using (var brush = new LinearGradientBrush(
                ClientRectangle, _left, _right, LinearGradientMode.Horizontal))
            {
                g.FillRectangle(brush, ClientRectangle);
            }

            int cy = Height / 2;

            // 图标：半透明白圆角块 + 星形字符
            var iconBox = new Rectangle(12, cy - 16, 32, 32);
            using (var iconBg = new SolidBrush(Color.FromArgb(60, 255, 255, 255)))
            using (var path = GfxUtil.RoundedRect(iconBox, 8))
                g.FillPath(iconBg, path);
            using (var iconFont = new Font("Segoe UI Symbol", 14f, FontStyle.Bold))
                TextRenderer.DrawText(g, "✦", iconFont, iconBox, Color.White,
                    TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);

            // 标题：无底白字
            int titleW;
            using (var titleFont = new Font("Microsoft YaHei", 12f, FontStyle.Bold))
            {
                titleW = TextRenderer.MeasureText(g, "ThinkForm AI 绘图助手", titleFont).Width;
                var titleRect = new Rectangle(52, 0, titleW + 8, Height);
                TextRenderer.DrawText(g, "ThinkForm AI 绘图助手", titleFont, titleRect,
                    Color.White, TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
            }

            // 版本徽章：半透明白圆角框 + 白字
            using (var verFont = new Font("Microsoft YaHei", 8.5f, FontStyle.Bold))
            {
                Size verSize = TextRenderer.MeasureText(g, "v1.0", verFont);
                var verRect = new Rectangle(52 + titleW + 12, cy - 11, verSize.Width + 16, 22);
                using (var verBg = new SolidBrush(Color.FromArgb(70, 255, 255, 255)))
                using (var path = GfxUtil.RoundedRect(verRect, 6))
                    g.FillPath(verBg, path);
                TextRenderer.DrawText(g, "v2.4", verFont, verRect, Color.White,
                    TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);
            }

            // 关闭按钮：右上角白色 ✕，无底
            _closeRect = new Rectangle(Width - 40, cy - 15, 30, 30);
            using (var closeFont = new Font("Microsoft YaHei", 12f, FontStyle.Bold))
                TextRenderer.DrawText(g, "✕", closeFont, _closeRect, Color.White,
                    TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);
        }

        protected override void OnMouseClick(MouseEventArgs e)
        {
            base.OnMouseClick(e);
            if (_closeRect.Contains(e.Location) && CloseClicked != null)
                CloseClicked(this, EventArgs.Empty);
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            base.OnMouseMove(e);
            Cursor = _closeRect.Contains(e.Location) ? Cursors.Hand : Cursors.Default;
        }
    }

    /// <summary>圆角卡片面板，可选边框高亮（用于功能卡片、输入区等）。</summary>
    internal class CardPanel : Panel
    {
        public int Radius { get; set; } = 10;
        public Color BorderColor { get; set; } = Theme.CardBorder;
        public Color FillColor { get; set; } = Theme.CardBg;
        public int BorderWidth { get; set; } = 1;
        /// <summary>该卡片的主题强调色，用于选中态的边框与浅色底。</summary>
        public Color Accent { get; set; } = Theme.Primary;

        public CardPanel()
        {
            DoubleBuffered = true;
            BackColor = Color.Transparent;
            // 让自绘随尺寸变化整体重绘，避免 Dock=Fill 缩放时底/右边框残缺
            SetStyle(ControlStyles.ResizeRedraw, true);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.PixelOffsetMode = PixelOffsetMode.Half;

            // 用浮点矩形并按边框宽度的一半内缩，使描边正好落在控件内部；
            // 底部/右侧再各留 1px 安全余量，防止控件最后一像素被父容器裁剪导致底边框缺失。
            float half = BorderWidth / 2f;
            var rf = new RectangleF(
                half, half,
                Width - BorderWidth - 1,
                Height - BorderWidth - 1);

            using (var path = RoundedRectF(rf, Radius))
            using (var fill = new SolidBrush(FillColor))
            using (var pen = new Pen(BorderColor, BorderWidth))
            {
                g.FillPath(fill, path);
                g.DrawPath(pen, path);
            }
            base.OnPaint(e);
        }

        /// <summary>浮点版圆角矩形路径。</summary>
        private static GraphicsPath RoundedRectF(RectangleF r, float radius)
        {
            float d = radius * 2;
            var path = new GraphicsPath();
            if (radius <= 0)
            {
                path.AddRectangle(r);
                path.CloseFigure();
                return path;
            }
            path.AddArc(r.X, r.Y, d, d, 180, 90);
            path.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            path.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            path.CloseFigure();
            return path;
        }
    }

    /// <summary>
    /// 功能卡片：图标 + 文字全部在控件内自绘（不使用子 Label），
    /// 从根本上避免子控件覆盖底部边框导致边框缺失。
    /// 支持选中态：选中时用 Accent 色 2px 边框 + 浅色底。
    /// </summary>
    internal class FeatureCard : Control
    {
        public string Glyph { get; set; } = "";
        public Color Accent { get; set; } = Theme.Primary;
        public int Radius { get; set; } = 10;

        /// <summary>true 时用自绘 3D 立方体线框代替 Glyph 字符（用于"新建 3D 零件"卡片）。</summary>
        public bool DrawCubeIcon { get; set; } = false;

        private bool _selected;
        public bool Selected
        {
            get { return _selected; }
            set { _selected = value; Invalidate(); }
        }

        public FeatureCard()
        {
            SetStyle(ControlStyles.UserPaint
                     | ControlStyles.AllPaintingInWmPaint
                     | ControlStyles.OptimizedDoubleBuffer
                     | ControlStyles.ResizeRedraw
                     | ControlStyles.SupportsTransparentBackColor, true);
            DoubleBuffered = true;
            BackColor = Color.Transparent;
            Cursor = Cursors.Hand;
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.PixelOffsetMode = PixelOffsetMode.Half;

            int bw = _selected ? 2 : 1;
            Color border = _selected ? Accent : Theme.CardBorder;
            Color fillColor = _selected ? TintColor(Accent) : Theme.CardBg;

            float half = bw / 2f;
            var rf = new RectangleF(half, half, Width - bw - 1, Height - bw - 1);

            using (var path = RoundedRectF(rf, Radius))
            using (var fill = new SolidBrush(fillColor))
            using (var pen = new Pen(border, bw))
            {
                g.FillPath(fill, path);
                g.DrawPath(pen, path);
            }

            int iconH = 26;
            const int iconTop = 4;    // 顶部留白减少，把空间让给下方文字
            const int gap = 1;        // 图标与文字的垂直间距
            const int bottomPad = 4;  // 底部留白

            if (DrawCubeIcon)
            {
                // 自绘 3D 立方体线框：等轴测视图（画三个可见面的轮廓 + 前面X形对角）
                DrawIsoCube(g, new Rectangle(0, iconTop, Width, iconH), Accent);
            }
            else
            {
                using (var iconFont = Theme.Title(15))
                    TextRenderer.DrawText(g, Glyph, iconFont,
                        new Rectangle(0, iconTop, Width, iconH), Accent,
                        TextFormatFlags.HorizontalCenter | TextFormatFlags.Bottom | TextFormatFlags.NoPadding);
            }

            using (var textFont = Theme.Body(9, FontStyle.Bold))
                TextRenderer.DrawText(g, Text, textFont,
                    new Rectangle(0, iconTop + iconH + gap, Width,
                                  Height - (iconTop + iconH + gap) - bottomPad),
                    Theme.TextMain,
                    TextFormatFlags.HorizontalCenter | TextFormatFlags.Top | TextFormatFlags.NoPadding);
        }

        private static Color TintColor(Color c)
        {
            const double k = 0.88;
            int r = (int)(c.R * (1 - k) + 255 * k);
            int g = (int)(c.G * (1 - k) + 255 * k);
            int b = (int)(c.B * (1 - k) + 255 * k);
            return Color.FromArgb(r, g, b);
        }

        /// <summary>
        /// 在给定矩形区域内居中绘制一个等轴测（isometric）风格的 3D 立方体线框。
        /// 六边形外轮廓 + 中心到三个可见顶点（正下、左下、右下）的三条内边，
        /// 形成经典的"3D 立方体"视觉。
        /// </summary>
        private static void DrawIsoCube(Graphics g, Rectangle area, Color color)
        {
            // 取区域内可用的最大偶数尺寸，并缩到 0.7 倍，视觉上与字符图标(▤/☁)大小接近
            int s = (int)((Math.Min(area.Width, area.Height) - 2) * 0.7f);
            if (s < 8) return;

            float cx = area.X + area.Width / 2f;
            float cy = area.Y + area.Height / 2f;

            // 六边形顶点：hw = 半宽, hh = 半高, qh = 半高的一半(上/下顶点到中心水平线的距离)
            float hw = s * 0.45f;
            float hh = s * 0.5f;
            float qh = hh / 2f;

            var top     = new PointF(cx, cy - hh);
            var right   = new PointF(cx + hw, cy - qh);
            var brRight = new PointF(cx + hw, cy + qh);
            var bottom  = new PointF(cx, cy + hh);
            var blLeft  = new PointF(cx - hw, cy + qh);
            var left    = new PointF(cx - hw, cy - qh);
            var center  = new PointF(cx, cy);

            using (var pen = new Pen(color, 1.6f))
            {
                pen.LineJoin = LineJoin.Round;
                pen.StartCap = LineCap.Round;
                pen.EndCap = LineCap.Round;

                // 六边形外轮廓
                var outline = new[] { top, right, brRight, bottom, blLeft, left, top };
                g.DrawLines(pen, outline);

                // 三条内边：中心连接到"正下、左下、右下"三个顶点
                g.DrawLine(pen, center, bottom);
                g.DrawLine(pen, center, blLeft);
                g.DrawLine(pen, center, brRight);
            }
        }

        private static GraphicsPath RoundedRectF(RectangleF r, float radius)
        {
            float d = radius * 2;
            var path = new GraphicsPath();
            if (radius <= 0) { path.AddRectangle(r); path.CloseFigure(); return path; }
            path.AddArc(r.X, r.Y, d, d, 180, 90);
            path.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            path.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            path.CloseFigure();
            return path;
        }
    }

    /// <summary>
    /// 徽章标签：圆角描边小标签（如 GB/T 14689-2024）。
    /// 通过设置前景/边框色区分不同类别。
    /// </summary>
    internal class BadgeLabel : Label
    {
        public Color AccentColor { get; set; } = Theme.Primary;
        public int Radius { get; set; } = 8;

        public BadgeLabel()
        {
            DoubleBuffered = true;
            AutoSize = false;
            BackColor = Color.Transparent;
            ForeColor = Theme.TextMain;
            TextAlign = ContentAlignment.MiddleCenter;
            Font = Theme.Body(8.5f);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            var r = new Rectangle(0, 0, Width - 1, Height - 1);
            using (var path = GfxUtil.RoundedRect(r, Radius))
            using (var fill = new SolidBrush(Color.White))
            using (var pen = new Pen(AccentColor, 1))
            {
                e.Graphics.FillPath(fill, path);
                e.Graphics.DrawPath(pen, path);
            }
            TextRenderer.DrawText(e.Graphics, Text, Font, ClientRectangle,
                AccentColor, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);
        }
    }

    /// <summary>
    /// 圆角按钮：支持实心（发送）与描边两种风格。
    /// </summary>
    internal class RoundButton : Button
    {
        public int Radius { get; set; } = 8;
        public bool Filled { get; set; } = true;
        public Color Accent { get; set; } = Theme.Primary;

        public RoundButton()
        {
            DoubleBuffered = true;
            FlatStyle = FlatStyle.Flat;
            FlatAppearance.BorderSize = 0;
            BackColor = Color.Transparent;
            Font = Theme.Body(9.5f, FontStyle.Bold);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            var r = new Rectangle(0, 0, Width - 1, Height - 1);
            using (var path = GfxUtil.RoundedRect(r, Radius))
            {
                if (Filled)
                {
                    // 禁用态用不透明的实色(而非半透明 alpha)，否则圆角外四角透出父容器内容形成"灰方块"背景
                    Color fillColor = Enabled
                        ? Accent
                        : Color.FromArgb(
                            (Accent.R + 255) / 2,
                            (Accent.G + 255) / 2,
                            (Accent.B + 255) / 2);
                    using (var fill = new SolidBrush(fillColor))
                        e.Graphics.FillPath(fill, path);
                    TextRenderer.DrawText(e.Graphics, Text, Font, ClientRectangle,
                        Theme.TextWhite, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);
                }
                else
                {
                    using (var fill = new SolidBrush(Color.White))
                    using (var pen = new Pen(Accent, 1))
                    {
                        e.Graphics.FillPath(fill, path);
                        e.Graphics.DrawPath(pen, path);
                    }
                    TextRenderer.DrawText(e.Graphics, Text, Font, ClientRectangle,
                        Enabled ? Accent : Theme.TextSub,
                        TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);
                }
            }
        }
    }

    /// <summary>
    /// 模式选择「药丸」按钮：浅绿圆角底 + 左侧图标 + 文字 + 右侧下拉箭头。
    /// 点击时触发 Click 事件，由外部弹出下拉菜单。
    /// </summary>
    internal class ModePillButton : Control
    {
        public string Glyph { get; set; } = "☁";
        public int Radius { get; set; } = 14;

        public ModePillButton()
        {
            // 启用透明背景与自绘所需样式，否则设置 Color.Transparent 会抛异常
            SetStyle(ControlStyles.SupportsTransparentBackColor
                     | ControlStyles.UserPaint
                     | ControlStyles.AllPaintingInWmPaint
                     | ControlStyles.OptimizedDoubleBuffer, true);
            DoubleBuffered = true;
            BackColor = Color.Transparent;
            Cursor = Cursors.Hand;
            Font = Theme.Body(9.5f, FontStyle.Bold);
            ForeColor = Theme.Green;
            Size = new Size(120, 30);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            var r = new Rectangle(0, 0, Width - 1, Height - 1);
            using (var path = GfxUtil.RoundedRect(r, Radius))
            using (var fill = new SolidBrush(Theme.GreenPillBg))
            using (var pen = new Pen(Theme.GreenPillBorder, 1))
            {
                e.Graphics.FillPath(fill, path);
                e.Graphics.DrawPath(pen, path);
            }

            // 图标
            int x = 10;
            TextRenderer.DrawText(e.Graphics, Glyph, Font,
                new Rectangle(x, 0, 18, Height), Theme.Green,
                TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
            x += 20;

            // 文字
            TextRenderer.DrawText(e.Graphics, Text, Font,
                new Rectangle(x, 0, Width - x - 20, Height), Theme.Green,
                TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);

            // 右侧下拉箭头
            TextRenderer.DrawText(e.Graphics, "▾", Theme.Body(9),
                new Rectangle(Width - 18, 0, 16, Height), Theme.Green,
                TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
        }
    }

    /// <summary>
    /// 一个模式选项数据：图标、主标题、副标题。
    /// </summary>
    internal class ModeItem
    {
        public string Glyph;
        public string Title;
        public string Subtitle;
        public ModeItem(string glyph, string title, string subtitle)
        {
            Glyph = glyph; Title = title; Subtitle = subtitle;
        }
    }

    /// <summary>
    /// 模式切换的弹出下拉面板（无边框浮层）。
    /// 顶部一个「切换运行模式」标题，下面若干模式项：图标 + 主标题 + 副标题，
    /// 当前选中项右侧显示绿色对勾。点击某项触发 ItemSelected，失去焦点自动关闭。
    /// </summary>
    internal class ModeDropdownForm : Form
    {
        private readonly ModeItem[] _items;
        private int _selectedIndex;
        private readonly int _rowHeight = 68;
        private readonly int _headerHeight = 36;

        /// <summary>选中项回调：参数为项索引。</summary>
        public event Action<int> ItemSelected;

        public ModeDropdownForm(ModeItem[] items, int selectedIndex)
        {
            _items = items;
            _selectedIndex = selectedIndex;

            FormBorderStyle = FormBorderStyle.None;
            ShowInTaskbar = false;
            StartPosition = FormStartPosition.Manual;
            DoubleBuffered = true;
            BackColor = Color.White;
            Width = 300;
            Height = _headerHeight + _rowHeight * _items.Length + 10;
        }

        protected override void OnDeactivate(EventArgs e)
        {
            base.OnDeactivate(e);
            Close();   // 点击面板外部时自动关闭
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;

            var r = new Rectangle(0, 0, Width - 1, Height - 1);
            using (var path = GfxUtil.RoundedRect(r, 12))
            using (var fill = new SolidBrush(Color.White))
            using (var pen = new Pen(Theme.CardBorder, 1))
            {
                g.FillPath(fill, path);
                g.DrawPath(pen, path);
            }

            TextRenderer.DrawText(g, "切换运行模式", Theme.Body(9, FontStyle.Bold),
                new Rectangle(16, 8, Width - 32, 20), Theme.TextSub,
                TextFormatFlags.Left | TextFormatFlags.VerticalCenter);

            for (int i = 0; i < _items.Length; i++)
            {
                int top = _headerHeight + i * _rowHeight;
                var it = _items[i];

                TextRenderer.DrawText(g, it.Glyph, Theme.Title(15),
                    new Rectangle(16, top, 28, _rowHeight), Theme.Green,
                    TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);

                TextRenderer.DrawText(g, it.Title, Theme.Body(11, FontStyle.Bold),
                    new Rectangle(52, top + 10, Width - 100, 26), Theme.TextMain,
                    TextFormatFlags.Left | TextFormatFlags.NoPadding);

                TextRenderer.DrawText(g, it.Subtitle, Theme.Body(8.5f),
                    new Rectangle(52, top + 38, Width - 100, 22), Theme.TextSub,
                    TextFormatFlags.Left | TextFormatFlags.NoPadding);

                if (i == _selectedIndex)
                {
                    TextRenderer.DrawText(g, "✓", Theme.Title(13),
                        new Rectangle(Width - 40, top, 28, _rowHeight), Theme.Green,
                        TextFormatFlags.Right | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
                }
            }
        }

        protected override void OnMouseClick(MouseEventArgs e)
        {
            base.OnMouseClick(e);
            int idx = (e.Y - _headerHeight) / _rowHeight;
            if (idx >= 0 && idx < _items.Length)
            {
                _selectedIndex = idx;
                ItemSelected?.Invoke(idx);
                Close();
            }
        }
    }

    /// <summary>3D 建模执行计划中的一个步骤条目。</summary>
    internal class PlanStep
    {
        public int Index;              // 从 1 开始
        public string NameCn;          // 中文步骤名，如 "草图1 (Sketch1)"
        public string ApiName;         // 右侧 API 名，如 "Sketch.CreateRectangle"
        public string Description;     // 灰色描述文字，如 "在前视基准面上绘制 120×80 mm 中心矩形草图"

        public PlanStep(int index, string nameCn, string apiName, string description)
        {
            Index = index;
            NameCn = nameCn ?? "";
            ApiName = apiName ?? "";
            Description = description ?? "";
        }
    }

    /// <summary>
    /// 3D 建模执行计划面板：顶部标题区(蓝底) + 步骤列表 + 底部"修改计划"/"确认并执行"双按钮。
    /// 用 TableLayoutPanel(3 行)精确控制视觉顺序，避免 Dock=Top 堆叠顺序踩坑。
    /// </summary>
    internal class PlanReviewPanel : CardPanel
    {
        private readonly TableLayoutPanel _root;
        private readonly Panel _headerBox;
        private readonly Label _titleLine;
        private readonly Label _descLine;
        private readonly Panel _stepsBox;
        private readonly Panel _stepsHeader;
        private readonly FlowLayoutPanel _stepsFlow;
        private readonly Panel _footerBox;
        private readonly RoundButton _modifyBtn;
        private readonly RoundButton _confirmBtn;

        public event EventHandler ModifyClicked;
        public event EventHandler ConfirmClicked;

        public string PlanTitle
        {
            get { return _titleLine.Text; }
            set { _titleLine.Text = value; }
        }
        public string PlanDescription
        {
            get { return _descLine.Text; }
            set { _descLine.Text = value; }
        }

        public PlanReviewPanel()
        {
            BorderColor = Theme.Primary;
            BorderWidth = 1;
            Radius = 10;
            Padding = new Padding(1);

            // === 主容器：TableLayoutPanel 3 行(顶部 header / 中部 steps / 底部 footer) ===
            _root = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 1,
                RowCount = 3,
                BackColor = Color.White,
                Padding = new Padding(0),
                Margin = new Padding(0)
            };
            _root.RowStyles.Add(new RowStyle(SizeType.Absolute, 68));
            _root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            _root.RowStyles.Add(new RowStyle(SizeType.Absolute, 52));

            // === Header ===
            _headerBox = new Panel
            {
                Dock = DockStyle.Fill,
                BackColor = Color.FromArgb(238, 243, 255),
                Padding = new Padding(14, 8, 14, 8),
                Margin = new Padding(0)
            };
            _titleLine = new Label
            {
                Text = "◎  执行面板",
                Font = Theme.Body(10, FontStyle.Bold),
                ForeColor = Theme.Primary,
                Dock = DockStyle.Top,
                Height = 22,
                BackColor = Color.Transparent
            };
            _descLine = new Label
            {
                Text = "",
                Font = Theme.Body(9),
                ForeColor = Theme.TextMain,
                Dock = DockStyle.Fill,
                BackColor = Color.Transparent
            };
            _headerBox.Controls.Add(_descLine);
            _headerBox.Controls.Add(_titleLine);

            // === Steps 区：内部 StepsHeader(顶) + StepsFlow(填充) ===
            _stepsBox = new Panel
            {
                Dock = DockStyle.Fill,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                BackColor = Color.White,
                Margin = new Padding(0),
                Padding = new Padding(0)
            };
            _stepsHeader = new Panel
            {
                Dock = DockStyle.Top,
                Height = 26,
                BackColor = Color.White,
                Padding = new Padding(14, 4, 14, 0)
            };
            _stepsHeader.Paint += StepsHeader_Paint;
            _stepsFlow = new FlowLayoutPanel
            {
                Dock = DockStyle.Top,
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                WrapContents = false,
                BackColor = Color.White,
                Padding = new Padding(10, 4, 10, 8)
            };
            // Dock=Top 添加顺序：先加 Flow 后加 Header → Header 在上, Flow 在下
            _stepsBox.Controls.Add(_stepsFlow);
            _stepsBox.Controls.Add(_stepsHeader);

            // === Footer ===
            _footerBox = new Panel
            {
                Dock = DockStyle.Fill,
                BackColor = Color.White,
                Padding = new Padding(10, 6, 10, 6),
                Margin = new Padding(0)
            };
            _modifyBtn = new RoundButton
            {
                Text = "✎ 修改计划",
                Filled = false,
                Accent = Theme.TextSub,
                Size = new Size(100, 34),
                Dock = DockStyle.Left,
                Visible = false   // 移除「修改计划」按钮：用户想改直接在下方输入框重发即可
            };
            _modifyBtn.Click += (s, e) => ModifyClicked?.Invoke(this, EventArgs.Empty);
            _confirmBtn = new RoundButton
            {
                Text = "▶ 确认并执行",
                Filled = true,
                Accent = Theme.Green,
                Size = new Size(130, 34),
                Dock = DockStyle.Right
            };
            _confirmBtn.Click += (s, e) => ConfirmClicked?.Invoke(this, EventArgs.Empty);
            _footerBox.Controls.Add(_confirmBtn);
            _footerBox.Controls.Add(_modifyBtn);

            // === 按行号精确放入 TableLayoutPanel ===
            _root.Controls.Add(_headerBox, 0, 0);
            _root.Controls.Add(_stepsBox, 0, 1);
            _root.Controls.Add(_footerBox, 0, 2);

            Controls.Add(_root);
        }

        /// <summary>刷新步骤列表并显示。</summary>
        public void SetSteps(System.Collections.Generic.IList<PlanStep> steps)
        {
            _stepsFlow.SuspendLayout();
            _stepsFlow.Controls.Clear();
            _stepCount = steps != null ? steps.Count : 0;
            if (steps != null)
            {
                foreach (var step in steps)
                {
                    var row = new PlanStepRow(step)
                    {
                        Width = Math.Max(240, ClientSize.Width - 40),
                        Height = 44,
                        Margin = new Padding(0, 0, 0, 6)
                    };
                    _stepsFlow.Controls.Add(row);
                }
            }
            _stepsFlow.ResumeLayout();
            _stepsBox.Visible = true;
            _footerBox.Visible = true;
            SetRowVisibility();
            _stepsHeader.Invalidate();
            RecalcHeight();
        }

        /// <summary>宽度变化后，让内部步骤行也拉伸到新宽度，避免文字重叠。</summary>
        protected override void OnResize(EventArgs eventargs)
        {
            base.OnResize(eventargs);
            if (_stepsFlow == null) return;
            int rowWidth = Math.Max(240, ClientSize.Width - 40);
            foreach (Control c in _stepsFlow.Controls)
            {
                var row = c as PlanStepRow;
                if (row != null) row.Width = rowWidth;
            }
            if (_stepsHeader != null) _stepsHeader.Invalidate();
        }

        /// <summary>禁用/启用「确认并执行」按钮（点击后应禁用避免重复触发）。</summary>
        public void SetConfirmEnabled(bool enabled)
        {
            if (_confirmBtn == null) return;
            _confirmBtn.Enabled = enabled;
            _confirmBtn.Text = enabled ? "▶ 确认并执行" : "✓ 已执行";
            // 禁用时切换到中性灰底，避免和"未执行"绿色态视觉混淆；启用时恢复绿色
            _confirmBtn.Accent = enabled ? Theme.Green : Color.FromArgb(180, 188, 200);
            _confirmBtn.Invalidate();
        }

        /// <summary>切换回初始占位态：显示"AI 助手就绪"提示，隐藏步骤列表与按钮。</summary>
        public void ShowIdleState(string title, string description)
        {
            PlanTitle = title;
            PlanDescription = description;
            _stepsBox.Visible = false;
            _footerBox.Visible = false;
            _stepsFlow.Controls.Clear();
            _stepCount = 0;
            SetRowVisibility();
            RecalcHeight();
        }

        /// <summary>按各行是否可见调整对应 RowStyle，隐藏时把行高置 0。</summary>
        private void SetRowVisibility()
        {
            _root.RowStyles[1].SizeType = _stepsBox.Visible ? SizeType.AutoSize : SizeType.Absolute;
            if (!_stepsBox.Visible) _root.RowStyles[1].Height = 0;

            _root.RowStyles[2].SizeType = SizeType.Absolute;
            _root.RowStyles[2].Height = _footerBox.Visible ? 52 : 0;
        }

        /// <summary>依据当前状态计算整体高度(header + steps + footer)并设置。</summary>
        private void RecalcHeight()
        {
            int h = 68 + 2;                  // header + border
            if (_stepsBox.Visible)
            {
                h += _stepsHeader.Height;    // steps header 26
                h += _stepsFlow.Padding.Top + _stepsFlow.Padding.Bottom;
                h += _stepCount * 50;        // 每步 44 + 间距 6
            }
            if (_footerBox.Visible) h += 56; // footer 52 + 底部 4px 视觉呼吸
            Height = h;
        }

        private int _stepCount;
        private void StepsHeader_Paint(object sender, PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;

            // 先精确测量右侧标签宽度，再据此切分左右两块，避免右侧文字被左裁
            const string rightLabel = "SolidWorks FeatureTree";
            using (var rightFont = Theme.Body(8.5f))
            {
                Size rSize = TextRenderer.MeasureText(g, rightLabel, rightFont);
                int rightX = _stepsHeader.Width - rSize.Width - 14;
                if (rightX < 8) rightX = 8;   // 极窄时避免负值

                TextRenderer.DrawText(g, rightLabel, rightFont,
                    new Rectangle(rightX, 4, rSize.Width + 2, 20), Theme.TextSub,
                    TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);

                string leftText = "自然语言 → 结构化建模步骤(共 " + _stepCount + " 步)";
                int leftW = rightX - 14 - 8;
                if (leftW < 20) leftW = 20;
                TextRenderer.DrawText(g, leftText, Theme.Body(9, FontStyle.Bold),
                    new Rectangle(14, 4, leftW, 20), Theme.Primary,
                    TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis);
            }
        }
    }

    /// <summary>
    /// PlanReviewPanel 中的一行步骤：左侧圆圈编号 + 右侧上行(中文名+API 名) + 右侧下行(灰色描述)。
    /// 全自绘，避免子控件产生额外背景。
    /// </summary>
    internal class PlanStepRow : Control
    {
        private readonly PlanStep _step;

        public PlanStepRow(PlanStep step)
        {
            _step = step;
            SetStyle(ControlStyles.UserPaint
                     | ControlStyles.AllPaintingInWmPaint
                     | ControlStyles.OptimizedDoubleBuffer
                     | ControlStyles.ResizeRedraw
                     | ControlStyles.SupportsTransparentBackColor, true);
            BackColor = Color.Transparent;
            Height = 44;
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;

            // 左侧编号圆圈
            int circleD = 22;
            int cx = 4, cy = (Height - circleD) / 2;
            var circleRect = new Rectangle(cx, cy, circleD, circleD);
            using (var bg = new SolidBrush(Color.FromArgb(238, 243, 255)))
                g.FillEllipse(bg, circleRect);
            TextRenderer.DrawText(g, _step.Index.ToString(), Theme.Body(9, FontStyle.Bold),
                circleRect, Theme.Primary,
                TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);

            int leftPad = cx + circleD + 8;
            int rightPad = 6;
            int contentW = Width - leftPad - rightPad;

            // 上行右侧：API 名(灰色)
            using (var apiFont = Theme.Body(8.5f))
            {
                Size apiSize = TextRenderer.MeasureText(g, _step.ApiName, apiFont);
                var apiRect = new Rectangle(leftPad + contentW - apiSize.Width, 4, apiSize.Width, 18);
                TextRenderer.DrawText(g, _step.ApiName, apiFont, apiRect, Theme.TextSub,
                    TextFormatFlags.Right | TextFormatFlags.Top | TextFormatFlags.NoPadding);

                // 上行左侧：中文步骤名(粗体)
                var nameRect = new Rectangle(leftPad, 4, contentW - apiSize.Width - 6, 18);
                using (var nameFont = Theme.Body(9, FontStyle.Bold))
                    TextRenderer.DrawText(g, _step.NameCn, nameFont, nameRect, Theme.TextMain,
                        TextFormatFlags.Left | TextFormatFlags.Top | TextFormatFlags.NoPadding | TextFormatFlags.EndEllipsis);
            }

            // 下行：描述(灰色, 可换行)
            using (var descFont = Theme.Body(8.5f))
                TextRenderer.DrawText(g, _step.Description, descFont,
                    new Rectangle(leftPad, 22, contentW, Height - 24), Theme.TextSub,
                    TextFormatFlags.Left | TextFormatFlags.Top | TextFormatFlags.NoPadding | TextFormatFlags.WordBreak);
        }
    }

    /// <summary>规则合规与几何质量诊断清单中的一条诊断项数据。</summary>
    internal class DiagnosticItem
    {
        public string Level;      // "warning" | "suggestion"
        public string Code;       // 规则代码
        public string Title;      // 简短标题
        public string Feature;    // 受影响的特征标识，如 "特征：切除-拉伸 1"
        public string Body;       // 正文描述
        public string Reference;  // 依据/标准
        public string FixHint;    // 一键修的提示动作(非空即启用按钮)
    }

    /// <summary>
    /// 单条诊断项的自绘卡片：警告=黄色系，建议=浅蓝色系。
    /// 顶部图标 + 标题 + 右侧特征标签；中部正文；底部依据行 + 定位/一键修按钮。
    /// </summary>
    internal class DiagnosticCard : Control
    {
        private readonly DiagnosticItem _item;
        private readonly RoundButton _locateBtn;
        private readonly RoundButton _fixBtn;

        public event EventHandler LocateClicked;
        public event EventHandler FixClicked;

        public DiagnosticCard(DiagnosticItem item)
        {
            _item = item;
            SetStyle(ControlStyles.UserPaint
                     | ControlStyles.AllPaintingInWmPaint
                     | ControlStyles.OptimizedDoubleBuffer
                     | ControlStyles.ResizeRedraw
                     | ControlStyles.SupportsTransparentBackColor, true);
            BackColor = Color.Transparent;

            // 底部两个小按钮：定位 / 一键修
            _locateBtn = new RoundButton
            {
                Text = "◎ 定位",
                Filled = false,
                Accent = Theme.TextSub,
                Size = new Size(72, 26),
                Font = Theme.Body(8.5f, FontStyle.Bold)
            };
            _locateBtn.Click += (s, e) => LocateClicked?.Invoke(this, EventArgs.Empty);

            _fixBtn = new RoundButton
            {
                Text = "🔧 一键修",
                Filled = true,
                Accent = Theme.Primary,
                Size = new Size(86, 26),
                Font = Theme.Body(8.5f, FontStyle.Bold),
                Enabled = !string.IsNullOrEmpty(item.FixHint)
            };
            _fixBtn.Click += (s, e) => FixClicked?.Invoke(this, EventArgs.Empty);

            Controls.Add(_locateBtn);
            Controls.Add(_fixBtn);

            Resize += (s, e) => LayoutButtons();
        }

        private void LayoutButtons()
        {
            // 按钮固定在卡片右上角(feature 标签下方)与底部
            int rightPad = 10;
            _fixBtn.Location = new Point(Width - _fixBtn.Width - rightPad, Height - _fixBtn.Height - 8);
            _locateBtn.Location = new Point(_fixBtn.Left - _locateBtn.Width - 6, _fixBtn.Top);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.PixelOffsetMode = PixelOffsetMode.Half;

            bool isWarning = _item.Level == "warning";
            Color fillColor = isWarning
                ? Color.FromArgb(255, 249, 231)   // 浅黄
                : Color.FromArgb(238, 246, 255);  // 浅蓝
            Color borderColor = isWarning
                ? Color.FromArgb(230, 190, 90)
                : Color.FromArgb(150, 190, 240);
            Color iconColor = isWarning ? Theme.Amber : Theme.Primary;
            string glyph = isWarning ? "⚠" : "💡";

            // 卡片圆角背景
            var rf = new RectangleF(0.5f, 0.5f, Width - 2, Height - 2);
            using (var path = RoundedRectF(rf, 10))
            using (var fill = new SolidBrush(fillColor))
            using (var pen = new Pen(borderColor, 1))
            {
                g.FillPath(fill, path);
                g.DrawPath(pen, path);
            }

            // 左上图标
            using (var gf = Theme.Title(13))
                TextRenderer.DrawText(g, glyph, gf,
                    new Rectangle(10, 10, 22, 22), iconColor,
                    TextFormatFlags.Left | TextFormatFlags.Top | TextFormatFlags.NoPadding);

            // 右上「特征」标签：白底灰边圆角
            int tagPad = 8;
            using (var tagFont = Theme.Body(8.5f))
            {
                string feat = _item.Feature ?? "";
                Size fSize = TextRenderer.MeasureText(g, feat, tagFont);
                int tagW = Math.Min(fSize.Width + tagPad * 2, Math.Max(60, Width / 2));
                int tagH = 22;
                var tagRect = new Rectangle(Width - tagW - 10, 10, tagW, tagH);
                using (var tagPath = RoundedRectF(new RectangleF(tagRect.X, tagRect.Y, tagRect.Width - 1, tagRect.Height - 1), 6))
                using (var tagFill = new SolidBrush(Color.White))
                using (var tagPen = new Pen(Color.FromArgb(220, 224, 232), 1))
                {
                    g.FillPath(tagFill, tagPath);
                    g.DrawPath(tagPen, tagPath);
                }
                TextRenderer.DrawText(g, feat, tagFont, tagRect, Theme.TextSub,
                    TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPadding);
            }

            // 标题：图标右侧、feature 标签下方之间
            using (var titleFont = Theme.Body(10, FontStyle.Bold))
            {
                var titleRect = new Rectangle(36, 8, Width - 36 - 100, 26);
                TextRenderer.DrawText(g, _item.Title ?? "", titleFont, titleRect, Theme.TextMain,
                    TextFormatFlags.Left | TextFormatFlags.Top | TextFormatFlags.NoPadding | TextFormatFlags.WordBreak);
            }

            // 正文
            int bodyTop = 38;
            using (var bodyFont = Theme.Body(9))
            {
                var bodyRect = new Rectangle(12, bodyTop, Width - 24, Height - bodyTop - 62);
                TextRenderer.DrawText(g, _item.Body ?? "", bodyFont, bodyRect, Theme.TextMain,
                    TextFormatFlags.Left | TextFormatFlags.Top | TextFormatFlags.NoPadding | TextFormatFlags.WordBreak);
            }

            // 依据行
            using (var refFont = Theme.Body(8.5f))
            {
                string refText = "依据：" + (_item.Reference ?? "");
                var refRect = new Rectangle(12, Height - 52, Width - 24, 20);
                TextRenderer.DrawText(g, refText, refFont, refRect, Theme.TextSub,
                    TextFormatFlags.Left | TextFormatFlags.Top | TextFormatFlags.NoPadding | TextFormatFlags.EndEllipsis);
            }
        }

        private static GraphicsPath RoundedRectF(RectangleF r, float radius)
        {
            float d = radius * 2;
            var path = new GraphicsPath();
            if (radius <= 0) { path.AddRectangle(r); path.CloseFigure(); return path; }
            path.AddArc(r.X, r.Y, d, d, 180, 90);
            path.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            path.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            path.CloseFigure();
            return path;
        }
    }

    /// <summary>
    /// 规则合规与几何质量诊断清单面板：顶部标题+警告徽章 / 中部诊断卡列表 / 底部提示+提交按钮。
    /// 结构与 PlanReviewPanel 类似：TableLayoutPanel 3 行控制视觉顺序。
    /// </summary>
    internal class DiagnosticPanel : CardPanel
    {
        private readonly TableLayoutPanel _root;
        private readonly Panel _headerBox;
        private readonly Panel _bodyBox;
        private readonly FlowLayoutPanel _cardsFlow;
        private readonly Panel _footerBox;
        private readonly Label _footerHint;
        private readonly RoundButton _submitBtn;

        /// <summary>用户点击「查看成果与提交 →」时触发。</summary>
        public event EventHandler SubmitClicked;
        /// <summary>用户点击某条诊断的「定位」按钮时触发，参数为诊断项。</summary>
        public event Action<DiagnosticItem> LocateItem;
        /// <summary>用户点击某条诊断的「一键修」按钮时触发，参数为诊断项。</summary>
        public event Action<DiagnosticItem> FixItem;

        private int _warningCount;
        private int _cardCount;

        public DiagnosticPanel()
        {
            BorderColor = Theme.CardBorder;
            BorderWidth = 1;
            Radius = 10;
            Padding = new Padding(1);

            _root = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 1,
                RowCount = 3,
                BackColor = Color.White,
                Padding = new Padding(0),
                Margin = new Padding(0)
            };
            _root.RowStyles.Add(new RowStyle(SizeType.Absolute, 44));
            _root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            _root.RowStyles.Add(new RowStyle(SizeType.Absolute, 52));

            // === Header (标题 + 警告数徽章)，自绘 ===
            _headerBox = new Panel
            {
                Dock = DockStyle.Fill,
                BackColor = Color.White,
                Margin = new Padding(0),
                Padding = new Padding(0)
            };
            _headerBox.Paint += Header_Paint;

            // === Body: 诊断卡片纵向流式 ===
            _bodyBox = new Panel
            {
                Dock = DockStyle.Fill,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                BackColor = Color.White,
                Margin = new Padding(0),
                Padding = new Padding(0)
            };
            _cardsFlow = new FlowLayoutPanel
            {
                Dock = DockStyle.Top,
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                WrapContents = false,
                BackColor = Color.White,
                Padding = new Padding(10, 4, 10, 8)
            };
            _bodyBox.Controls.Add(_cardsFlow);

            // === Footer (左侧提示 + 右侧提交按钮) ===
            _footerBox = new Panel
            {
                Dock = DockStyle.Fill,
                BackColor = Color.White,
                Padding = new Padding(10, 6, 10, 6),
                Margin = new Padding(0)
            };
            _footerHint = new Label
            {
                Text = "阻断项需处理后方可提交与保存",
                Font = Theme.Body(8.5f),
                ForeColor = Theme.TextSub,
                Dock = DockStyle.Left,
                AutoSize = false,
                TextAlign = ContentAlignment.MiddleLeft,
                Width = 180,
                BackColor = Color.Transparent
            };
            _submitBtn = new RoundButton
            {
                Text = "查看成果与提交",
                Filled = true,
                Accent = Theme.Green,
                Size = new Size(150, 34),
                Dock = DockStyle.Right
            };
            _submitBtn.Click += (s, e) => SubmitClicked?.Invoke(this, EventArgs.Empty);
            _footerBox.Controls.Add(_submitBtn);
            _footerBox.Controls.Add(_footerHint);

            _root.Controls.Add(_headerBox, 0, 0);
            _root.Controls.Add(_bodyBox, 0, 1);
            _root.Controls.Add(_footerBox, 0, 2);
            Controls.Add(_root);
        }

        /// <summary>设置诊断项列表并显示。</summary>
        public void SetItems(System.Collections.Generic.IList<DiagnosticItem> items, int warningCount)
        {
            _warningCount = warningCount;
            _cardsFlow.SuspendLayout();
            _cardsFlow.Controls.Clear();
            _cardCount = items != null ? items.Count : 0;
            if (items != null)
            {
                foreach (var item in items)
                {
                    var card = new DiagnosticCard(item)
                    {
                        Width = Math.Max(240, ClientSize.Width - 40),
                        Height = EstimateCardHeight(item),
                        Margin = new Padding(0, 0, 0, 8)
                    };
                    var captured = item;   // 捕获用于事件回调
                    card.LocateClicked += (s, e) => LocateItem?.Invoke(captured);
                    card.FixClicked += (s, e) => FixItem?.Invoke(captured);
                    _cardsFlow.Controls.Add(card);
                }
            }
            _cardsFlow.ResumeLayout();
            _headerBox.Invalidate();
            RecalcHeight();
        }

        /// <summary>估算一张诊断卡的高度：标题行 + 正文按字符估行 + 依据行 + 按钮行。</summary>
        private int EstimateCardHeight(DiagnosticItem item)
        {
            int titleLines = 1;
            if (!string.IsNullOrEmpty(item.Title) && item.Title.Length > 16) titleLines = 2;
            int bodyLen = item.Body != null ? item.Body.Length : 0;
            int bodyLines = Math.Max(1, (bodyLen + 22) / 22);  // 粗略估计：22 中文字符一行
            return 12 + 22 * titleLines + 4 + 18 * bodyLines + 22 + 32;
        }

        private void RecalcHeight()
        {
            int h = _headerBox.Height + 2;
            h += _cardsFlow.Padding.Top + _cardsFlow.Padding.Bottom;
            foreach (Control c in _cardsFlow.Controls)
                h += c.Height + c.Margin.Vertical;
            h += 56;   // footer + 呼吸
            Height = h;
        }

        /// <summary>宽度变化时，让内部诊断卡片跟随拉伸(否则子卡片保持构造时的初始宽度，造成文字截断)。</summary>
        protected override void OnResize(EventArgs eventargs)
        {
            base.OnResize(eventargs);
            if (_cardsFlow == null) return;
            int cardW = Math.Max(240, ClientSize.Width - 40);
            foreach (Control c in _cardsFlow.Controls)
            {
                if (c is DiagnosticCard) c.Width = cardW;
            }
            if (_headerBox != null) _headerBox.Invalidate();
        }

        private void Header_Paint(object sender, PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;

            const string title = "⊘  规则合规与几何质量诊断清单";
            using (var titleFont = Theme.Body(10, FontStyle.Bold))
            {
                var titleRect = new Rectangle(14, 0, _headerBox.Width - 100, _headerBox.Height);
                TextRenderer.DrawText(g, title, titleFont, titleRect, Theme.TextMain,
                    TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding | TextFormatFlags.EndEllipsis);
            }

            // 右侧警告徽章：琥珀色描边 + amber 文字 "N 警告"
            if (_warningCount > 0)
            {
                string txt = _warningCount + " 警告";
                using (var bFont = Theme.Body(8.5f, FontStyle.Bold))
                {
                    Size bSize = TextRenderer.MeasureText(g, txt, bFont);
                    int bw = bSize.Width + 16, bh = 22;
                    var brect = new Rectangle(_headerBox.Width - bw - 12, (_headerBox.Height - bh) / 2, bw, bh);
                    using (var path = GfxUtil.RoundedRect(brect, 6))
                    using (var fill = new SolidBrush(Color.FromArgb(255, 249, 231)))
                    using (var pen = new Pen(Color.FromArgb(230, 190, 90), 1))
                    {
                        g.FillPath(fill, path);
                        g.DrawPath(pen, path);
                    }
                    TextRenderer.DrawText(g, txt, bFont, brect, Theme.Amber,
                        TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
                }
            }
        }
    }
}