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
            Padding = new Padding(6, 6, 6, 16);
            // 底部固定留白：滚动到底时最后一张卡片与输入框之间保留空隙
            AutoScrollMargin = new Size(0, 16);
        }

        /// <summary>追加一条新消息并滚动到底部。</summary>
        public void Append(ChatRole role, string text)
        {
            if (string.IsNullOrEmpty(text)) return;

            var bubble = new ChatBubble(role, text);
            int maxW = Math.Max(120, ClientSize.Width - 40);
            bubble.MeasureAndSet(maxW);

            AppendControl(role, bubble);
            _bubbles.Add(bubble);
        }

        /// <summary>
        /// 追加一个自定义 Control 作为一条 AI 侧消息(如"执行面板卡片"、"诊断清单卡片")。
        /// 该控件应已设置合适的 Width/Height；本方法会用 wrapper row 把它挂到会话流里。
        /// </summary>
        public Panel AppendControl(ChatRole role, Control content)
        {
            if (content == null) return null;

            // row 的最终宽度 = ChatView 可用内容宽度(此时 row 尚未加入容器，不能用 row.ClientSize.Width，否则为 0)
            int rowWidth = ClientSize.Width - Padding.Horizontal;

            var row = new Panel
            {
                BackColor = Color.Transparent,
                Margin = new Padding(0),
                Padding = new Padding(0, 0, 0, 6),
                Width = rowWidth
            };

            // 用户侧靠右, AI 侧靠左；纯控件消息(如面板)通常按 AI 处理，占据大部分宽度
            if (role == ChatRole.User)
            {
                content.Left = Math.Max(8, rowWidth - content.Width - 8);
            }
            else
            {
                content.Left = 8;
                // AI 侧的大卡片消息：如果宽度小于可用宽，就让它拉伸到近满宽，视觉更贴合"卡片消息"
                int available = rowWidth - 12;
                if (content.Width > available - 16 || content is CardPanel)
                {
                    content.Width = available;
                    content.Left = 8;
                }
            }
            content.Top = 0;
            row.Height = content.Height + row.Padding.Bottom;
            row.Controls.Add(content);

            LayoutBubbles(row);
            Controls.Add(row);

            // 加入容器后 row 已获得真实宽度，再对用户侧气泡做一次右对齐校正，避免"先左后瞬移"
            if (role == ChatRole.User)
                content.Left = Math.Max(8, row.ClientSize.Width - content.Width - 8);

            // 添加到容器后触发一次布局，让面板内部子控件(TableLayoutPanel 等)按新宽度重排
            content.PerformLayout();

            // 面板拉宽后其内部(如成果卡的换行按钮行)高度可能变化，
            // 用最新的 content.Height 重新校正 row 高度，避免按钮被裁。
            row.Height = content.Height + row.Padding.Bottom;

            // 内容总高度：最后一条 row 的底部即为全部内容高度
            int contentBottom = row.Bottom;
            int visible = ClientSize.Height - Padding.Vertical;
            if (contentBottom > visible)
            {
                // 内容超过一屏：滚到底部，露出最新消息
                AutoScrollPosition = new Point(0, contentBottom);
            }
            else
            {
                // 内容不足一屏：保持顶部，避免消息整体下沉、顶部留白
                AutoScrollPosition = new Point(0, 0);
            }

            return row;
        }

        /// <summary>移除指定的消息 row(如临时"思考中"气泡)，并重排剩余会话。</summary>
        public void RemoveRow(Panel row)
        {
            if (row == null) return;
            if (InvokeRequired) { BeginInvoke(new Action<Panel>(RemoveRow), row); return; }
            if (!Controls.Contains(row)) return;

            Controls.Remove(row);
            row.Dispose();

            // 重排剩余 row 的 Top
            int y = Padding.Top;
            foreach (Control c in Controls)
            {
                c.Top = y;
                c.Left = 0;
                c.Width = ClientSize.Width - Padding.Horizontal;
                y += c.Height;
            }
            int visible = ClientSize.Height - Padding.Vertical;
            if (y <= visible) AutoScrollPosition = new Point(0, 0);
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

            // 内容不足一屏时，强制滚动位置回到顶部，避免容器变高后消息整体下沉、顶部留大片空白
            int visible = ClientSize.Height - Padding.Vertical;
            if (y <= visible)
                AutoScrollPosition = new Point(0, 0);
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