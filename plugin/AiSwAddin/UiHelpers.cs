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
                    using (var fill = new SolidBrush(Enabled ? Accent : Color.FromArgb(180, Accent)))
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
                Text = "◎  3D 建模执行计划",
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
                Dock = DockStyle.Left
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
                        Width = Math.Max(100, ClientSize.Width - 40),
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
            int h = 68 + 2;
            if (_stepsBox.Visible)
            {
                h += _stepsHeader.Height;
                h += _stepsFlow.Padding.Top + _stepsFlow.Padding.Bottom;
                h += _stepCount * 50;
            }
            if (_footerBox.Visible) h += 52;
            Height = h;
        }

        private int _stepCount;
        private void StepsHeader_Paint(object sender, PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            TextRenderer.DrawText(g, "解析后的 3D 建模树步骤(共 " + _stepCount + " 步)", Theme.Body(9, FontStyle.Bold),
                new Rectangle(14, 4, _stepsHeader.Width - 200, 20), Theme.Primary,
                TextFormatFlags.Left | TextFormatFlags.VerticalCenter);
            TextRenderer.DrawText(g, "SolidWorks FeatureTree", Theme.Body(8.5f),
                new Rectangle(_stepsHeader.Width - 180, 4, 170, 20), Theme.TextSub,
                TextFormatFlags.Right | TextFormatFlags.VerticalCenter);
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
}