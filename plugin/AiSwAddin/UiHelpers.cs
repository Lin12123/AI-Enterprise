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

    /// <summary>圆角卡片面板，可选边框高亮（用于功能卡片、输入区等）。</summary>
    internal class CardPanel : Panel
    {
        public int Radius { get; set; } = 10;
        public Color BorderColor { get; set; } = Theme.CardBorder;
        public Color FillColor { get; set; } = Theme.CardBg;
        public int BorderWidth { get; set; } = 1;

        public CardPanel()
        {
            DoubleBuffered = true;
            BackColor = Color.Transparent;
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            var r = new Rectangle(0, 0, Width - 1, Height - 1);
            using (var path = GfxUtil.RoundedRect(r, Radius))
            using (var fill = new SolidBrush(FillColor))
            using (var pen = new Pen(BorderColor, BorderWidth))
            {
                e.Graphics.FillPath(fill, path);
                e.Graphics.DrawPath(pen, path);
            }
            base.OnPaint(e);
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
}