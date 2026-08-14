using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;

namespace AiSwAddin
{
    /// <summary>会话消息的角色：用户 / AI 系统。</summary>
    internal enum ChatRole
    {
        User = 0,
        Ai = 1,
    }

    /// <summary>单条会话消息数据。</summary>
    internal class ChatMessage
    {
        public ChatRole Role;
        public string Text;
        public ChatMessage(ChatRole role, string text)
        {
            Role = role;
            Text = text ?? "";
        }
    }

    /// <summary>
    /// AI 会话流视图：用户消息靠右蓝气泡、AI 回复靠左白气泡。
    ///
    /// 外壳是一个开启 AutoScroll 的 Panel，内部每条消息都是一个 <see cref="ChatBubble"/> 控件，
    /// 按 Dock=Top 逆序添加(即最新消息永远最靠下)，容器自动出现纵向滚动条。
    /// </summary>
    internal class ChatView : Panel
    {
        private readonly List<ChatBubble> _bubbles = new List<ChatBubble>();

        public ChatView()
        {
            DoubleBuffered = true;
            BackColor = Color.FromArgb(247, 249, 252);
            AutoScroll = true;
            Padding = new Padding(6, 6, 6, 6);
        }

        /// <summary>追加一条新消息并滚动到底部。</summary>
        public void Append(ChatRole role, string text)
        {
            if (string.IsNullOrEmpty(text)) return;

            // 用一个 wrapper 容器控制气泡的左右对齐：用户消息靠右、AI 消息靠左
            var row = new Panel
            {
                Dock = DockStyle.Top,
                BackColor = Color.Transparent,
                Margin = new Padding(0),
                Padding = new Padding(0, 0, 0, 6)
            };

            var bubble = new ChatBubble(role, text);
            // 先估算气泡宽/高，再据角色贴左/贴右
            int maxW = Math.Max(120, ClientSize.Width - 40);
            bubble.MeasureAndSet(maxW);

            if (role == ChatRole.User)
            {
                bubble.Anchor = AnchorStyles.Top | AnchorStyles.Right;
                bubble.Left = row.ClientSize.Width - bubble.Width - 8;
                if (bubble.Left < 40) bubble.Left = 40;   // 极窄时避免贴到左边
            }
            else
            {
                bubble.Anchor = AnchorStyles.Top | AnchorStyles.Left;
                bubble.Left = 8;
            }
            bubble.Top = 0;
            row.Height = bubble.Height + row.Padding.Bottom;
            row.Controls.Add(bubble);

            // 每次插入到最上方前先把已有 rows 全部 Detach，再按"最老在最上、最新在最下"重新加
            // 简化做法：直接 Add 到 Panel 顶部，Dock=Top 会让新加的在最上——不是我们要的顺序
            // 因此改用 FlowLayoutPanel 或手动逆序管理。为简单起见，这里用手动追加到底：
            // Panel.Controls.Add + Dock=Top 需要按逆序添加。改用非 Dock 布局：
            row.Dock = DockStyle.None;
            LayoutBubbles(row);

            _bubbles.Add(bubble);
            Controls.Add(row);

            // 滚动到底部：把最新一条 row 滚入可见范围
            AutoScrollPosition = new Point(0, row.Bottom);
        }

        /// <summary>清空所有会话。</summary>
        public void Clear()
        {
            _bubbles.Clear();
            Controls.Clear();
        }

        /// <summary>手动布局所有 row 从上到下堆叠，返回新 row 应放置的 Y 坐标。</summary>
        private void LayoutBubbles(Panel newRow)
        {
            int y = Padding.Top;
            foreach (Control c in Controls)
            {
                if (c == newRow) continue;
                c.Top = y;
                c.Left = 0;
                c.Width = ClientSize.Width - Padding.Horizontal;
                y += c.Height;
            }
            newRow.Top = y;
            newRow.Left = 0;
            newRow.Width = ClientSize.Width - Padding.Horizontal;
        }

        protected override void OnResize(EventArgs eventargs)
        {
            base.OnResize(eventargs);
            // 宽度变化时，让所有已存在的气泡按新宽度重新测量并重排
            int maxW = Math.Max(120, ClientSize.Width - 40);
            foreach (var bubble in _bubbles) bubble.MeasureAndSet(maxW);
            foreach (Control row in Controls)
            {
                if (row.Controls.Count == 0) continue;
                var b = row.Controls[0] as ChatBubble;
                if (b == null) continue;
                row.Height = b.Height + row.Padding.Bottom;
                if (b.Role == ChatRole.User) b.Left = row.ClientSize.Width - b.Width - 8;
                else b.Left = 8;
            }
            // 重新排列 Top
            int y = Padding.Top;
            foreach (Control row in Controls)
            {
                row.Top = y;
                row.Left = 0;
                row.Width = ClientSize.Width - Padding.Horizontal;
                y += row.Height;
            }
        }
    }

    /// <summary>
    /// 单条会话气泡：自绘圆角背景 + 内嵌文本。用户蓝底白字，AI 白底深灰字。
    /// </summary>
    internal class ChatBubble : Control
    {
        public ChatRole Role { get; private set; }
        private readonly string _text;

        public ChatBubble(ChatRole role, string text)
        {
            Role = role;
            _text = text ?? "";
            SetStyle(ControlStyles.UserPaint
                     | ControlStyles.AllPaintingInWmPaint
                     | ControlStyles.OptimizedDoubleBuffer
                     | ControlStyles.ResizeRedraw
                     | ControlStyles.SupportsTransparentBackColor, true);
            BackColor = Color.Transparent;
        }

        /// <summary>按可用最大宽度测量文本，设置本控件的宽/高。</summary>
        public void MeasureAndSet(int maxWidth)
        {
            const int padH = 10, padV = 7;
            int textMax = Math.Max(60, maxWidth - padH * 2);
            using (var g = CreateGraphics())
            using (var font = Theme.Body(9.5f))
            {
                Size textSize = TextRenderer.MeasureText(g, _text, font,
                    new Size(textMax, int.MaxValue),
                    TextFormatFlags.WordBreak | TextFormatFlags.NoPadding);
                Width = Math.Min(maxWidth, textSize.Width + padH * 2 + 2);
                Height = textSize.Height + padV * 2;
            }
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.PixelOffsetMode = PixelOffsetMode.Half;

            bool isUser = Role == ChatRole.User;
            Color bgColor = isUser ? Theme.Primary : Color.White;
            Color textColor = isUser ? Color.White : Theme.TextMain;
            Color borderColor = isUser ? Theme.Primary : Theme.CardBorder;

            var rf = new RectangleF(0.5f, 0.5f, Width - 2, Height - 2);
            using (var path = RoundedRectF(rf, 8))
            using (var fill = new SolidBrush(bgColor))
            using (var pen = new Pen(borderColor, 1))
            {
                g.FillPath(fill, path);
                if (!isUser) g.DrawPath(pen, path);   // 白气泡加淡边框；蓝气泡纯色不需要
            }

            const int padH = 10, padV = 7;
            var textRect = new Rectangle(padH, padV, Width - padH * 2, Height - padV * 2);
            using (var font = Theme.Body(9.5f))
                TextRenderer.DrawText(g, _text, font, textRect, textColor,
                    TextFormatFlags.WordBreak | TextFormatFlags.Left | TextFormatFlags.Top | TextFormatFlags.NoPadding);
        }

        private static GraphicsPath RoundedRectF(RectangleF r, float radius)
        {
            float d = radius * 2;
            var path = new GraphicsPath();
            path.AddArc(r.X, r.Y, d, d, 180, 90);
            path.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            path.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            path.CloseFigure();
            return path;
        }
    }
}