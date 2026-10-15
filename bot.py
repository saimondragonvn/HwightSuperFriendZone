# -*- coding: utf-8 -*-
"""
=============================================================================
DISCORD BOT QUẢN LÝ SERVER & TỰ ĐỘNG HÓA STORE (COOKIE STORE STYLE)
Phiên bản: discord.py v2.x | Database: SQLite3 (bot_data.db)
Tính năng: Auto AST Calc, VietQR, Secret Paste, Ticket + HTML Transcript,
           Legit System, VIP Key Auto-Revoke, Moderation, Anti-Spam,
           Pillow BannerGen, Gemini AI FAQ, Revenue Tracking, Bank Webhook.
=============================================================================
"""

import os
import re
import io
import ast
import time
import html
import random
import string
import sqlite3
import asyncio
import operator
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
from urllib.parse import quote

import aiohttp
from aiohttp import web
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

import discord
from discord.ext import commands, tasks
from discord import ui

import sys
if sys.platform.startswith("win"):
    try:
        if sys.stdout:
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr:
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Tải biến môi trường từ file .env (nếu có)
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")  # Token bảo mật SePay/Casso (tùy chọn)
PORT = int(os.getenv("PORT", 8080))
DB_PATH = os.getenv("DB_PATH", "bot_data.db")

# Múi giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

# Màu sắc chủ đạo chuẩn Store Discord
COLOR_STORE = 0x2B2D31      # Xám đen sang trọng
COLOR_CYAN = 0x00FFFF       # Viền Cyan chuẩn bảng Legit
COLOR_GOLD = 0xF1C40F       # Vàng VIP / Doanh thu
COLOR_SUCCESS = 0x2ECC71    # Xanh lá thành công
COLOR_DANGER = 0xE74C3C     # Đỏ cảnh báo / Scam
COLOR_PRIMARY = 0x5865F2    # Xanh Blurple Discord


# =============================================================================
# I. CƠ SỞ DỮ LIỆU SQLITE (bot_data.db)
# =============================================================================
def get_db():
    """Tạo kết nối tới SQLite database với row_factory dạng dict."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Khởi tạo toàn bộ bảng dữ liệu cần thiết cho Store & Quản lý Server."""
    with get_db() as conn:
        c = conn.cursor()
        # 1. Bảng cấu hình chung của từng Server (VietQR, AutoRole, NotifyRole, Legit)
        c.execute("""
            CREATE TABLE IF NOT EXISTS store_settings (
                guild_id INTEGER PRIMARY KEY,
                bank_code TEXT DEFAULT 'MB',
                account_no TEXT DEFAULT '0000000000',
                account_name TEXT DEFAULT 'CHU CUA HANG',
                autorole_id INTEGER DEFAULT 0,
                notify_role_id INTEGER DEFAULT 0,
                ticket_log_channel_id INTEGER DEFAULT 0,
                legit_channel_id INTEGER DEFAULT 0,
                legit_message_id INTEGER DEFAULT 0
            )
        """)
        # Tự động thêm cột mới nếu DB đã tạo từ trước (migration an toàn)
        cols = [r["name"] for r in c.execute("PRAGMA table_info(store_settings)").fetchall()]
        if "legit_channel_id" not in cols:
            c.execute("ALTER TABLE store_settings ADD COLUMN legit_channel_id INTEGER DEFAULT 0")
        if "legit_message_id" not in cols:
            c.execute("ALTER TABLE store_settings ADD COLUMN legit_message_id INTEGER DEFAULT 0")
        if "stock_channel_id" not in cols:
            c.execute("ALTER TABLE store_settings ADD COLUMN stock_channel_id INTEGER DEFAULT 0")
        if "stock_message_id" not in cols:
            c.execute("ALTER TABLE store_settings ADD COLUMN stock_message_id INTEGER DEFAULT 0")
        if "store_name" not in cols:
            c.execute("ALTER TABLE store_settings ADD COLUMN store_name TEXT DEFAULT 'Cookie Store'")
        if "store_author" not in cols:
            c.execute("ALTER TABLE store_settings ADD COLUMN store_author TEXT DEFAULT 'made by ngocngann'")
        # 2. Bảng lưu trữ dữ liệu bảo mật (>paste / >taoban)
        c.execute("""
            CREATE TABLE IF NOT EXISTS secret_pastes (
                paste_id TEXT PRIMARY KEY,
                guild_id INTEGER,
                channel_id INTEGER,
                author_id INTEGER,
                title TEXT,
                secret_content TEXT,
                note TEXT,
                created_at TEXT
            )
        """)
        # 3. Bảng đánh giá uy tín (Legit / Feedback)
        c.execute("""
            CREATE TABLE IF NOT EXISTS legit_feedbacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                customer_id INTEGER,
                seller_text TEXT,
                item_text TEXT,
                stars INTEGER DEFAULT 5,
                comment TEXT,
                created_at TEXT
            )
        """)
        # 4. Bảng Key VIP bản quyền
        c.execute("""
            CREATE TABLE IF NOT EXISTS license_keys (
                key_code TEXT PRIMARY KEY,
                guild_id INTEGER,
                role_id INTEGER,
                duration_days INTEGER,
                is_used INTEGER DEFAULT 0,
                used_by INTEGER DEFAULT 0,
                used_at TEXT
            )
        """)
        # 5. Bảng theo dõi thời hạn Role VIP của khách
        c.execute("""
            CREATE TABLE IF NOT EXISTS active_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                role_id INTEGER,
                key_code TEXT,
                expires_at INTEGER,
                is_active INTEGER DEFAULT 1
            )
        """)
        # 6. Bảng lịch sử cảnh cáo (Warnings)
        c.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                created_at TEXT
            )
        """)
        # 7. Bảng câu hỏi thường gặp (FAQ)
        c.execute("""
            CREATE TABLE IF NOT EXISTS faqs (
                guild_id INTEGER,
                keyword TEXT,
                answer TEXT,
                PRIMARY KEY (guild_id, keyword)
            )
        """)
        # 8. Bảng danh sách đen / Scammer (>checkscam)
        c.execute("""
            CREATE TABLE IF NOT EXISTS scam_blacklist (
                target_id TEXT PRIMARY KEY,
                reason TEXT,
                added_by INTEGER,
                created_at TEXT
            )
        """)
        # 9. Bảng thống kê doanh thu (>done, >doanhthu)
        c.execute("""
            CREATE TABLE IF NOT EXISTS sales_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                staff_id INTEGER,
                customer_id INTEGER,
                amount INTEGER,
                item TEXT,
                created_at TEXT,
                day_str TEXT,
                month_str TEXT
            )
        """)
        # 10. Bảng quản lý kho hàng chuẩn Cookie Store • STOCK (>stock, >addstock)
        c.execute("""
            CREATE TABLE IF NOT EXISTS store_stocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                category TEXT,
                price INTEGER DEFAULT 0,
                item_name TEXT,
                item_channel TEXT DEFAULT '',
                status TEXT DEFAULT 'available',
                created_at TEXT
            )
        """)
        stock_cols = [r["name"] for r in c.execute("PRAGMA table_info(store_stocks)").fetchall()]
        if "channel_id" not in stock_cols:
            c.execute("ALTER TABLE store_stocks ADD COLUMN channel_id INTEGER DEFAULT 0")
        if "hold_until" not in stock_cols:
            c.execute("ALTER TABLE store_stocks ADD COLUMN hold_until INTEGER DEFAULT 0")
        if "holder_id" not in stock_cols:
            c.execute("ALTER TABLE store_stocks ADD COLUMN holder_id INTEGER DEFAULT 0")
        # 11. Bảng Giveaways / Phát Quà Tự Động (>gstart, >gend)
        c.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                message_id INTEGER PRIMARY KEY,
                guild_id INTEGER,
                channel_id INTEGER,
                prize TEXT,
                winners_count INTEGER DEFAULT 1,
                end_time INTEGER,
                is_ended INTEGER DEFAULT 0,
                host_id INTEGER
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS giveaway_entries (
                message_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (message_id, user_id)
            )
        """)
        # 12. Bảng Ví Xu & Mini-Game Giải Trí (>daily, >taixiu, >flip, >pay)
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_economy (
                user_id INTEGER,
                guild_id INTEGER,
                balance INTEGER DEFAULT 0,
                last_daily TEXT DEFAULT '',
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        conn.commit()


# =============================================================================
# II. HÀM TIỆN ÍCH & MÁY TÍNH CÂY CÚ PHÁP AN TOÀN (PYTHON AST)
# =============================================================================
def parse_smart_amount(val_str: str) -> int:
    """
    Chuyển đổi định dạng tiền thông minh sang số nguyên VNĐ.
    Ví dụ: '50k' -> 50000, '1.5m' -> 1500000, '2tr5' -> 2500000, '200000' -> 200000
    """
    s = val_str.strip().lower().replace(",", "").replace("_", "")
    # Xử lý dạng 2tr5, 1m5, 50k5
    m_mid = re.match(r"^(\d+)(tr|m|k)(\d+)$", s)
    if m_mid:
        main_part, unit, sub_part = m_mid.groups()
        mult = 1_000_000 if unit in ("tr", "m") else 1_000
        sub_val = int(sub_part) * (mult // (10 ** len(sub_part)))
        return int(main_part) * mult + sub_val

    m_suffix = re.match(r"^(\d+(?:\.\d+)?)\s*(k|m|tr|b|ty)?$", s)
    if not m_suffix:
        raise ValueError("Số tiền không hợp lệ.")
    num_str, unit = m_suffix.groups()
    num = float(num_str)
    multipliers = {
        None: 1,
        "k": 1_000,
        "m": 1_000_000,
        "tr": 1_000_000,
        "b": 1_000_000_000,
        "ty": 1_000_000_000,
    }
    return int(num * multipliers[unit])


def format_vnd(amount: int) -> str:
    """Định dạng số nguyên thành chuỗi tiền tệ VNĐ (VD: 50.000 VNĐ)."""
    return f"{amount:,}".replace(",", ".") + " VNĐ"


# Các toán tử được phép trong AST Calculator
ALLOWED_AST_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Biểu thức chính quy kiểm tra chuỗi có phải phép tính toán học không
MATH_PATTERN = re.compile(
    r"^\s*[\(\+\-]?\s*\d+(?:\.\d+)?[kmb]?\s*"
    r"(?:[\+\-\*xX\/÷\^\%]\s*[\(\+\-]?\s*\d+(?:\.\d+)?[kmb]?\s*[\)]*\s*)+$"
)


def _eval_ast_node(node):
    """Đệ quy tính giá trị cây cú pháp AST an toàn tuyệt đối (không dùng eval)."""
    if isinstance(node, ast.Expression):
        return _eval_ast_node(node.body)
    elif isinstance(node, ast.Constant):  # Python 3.8+
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Hằng số không hợp lệ")
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in ALLOWED_AST_OPS:
            raise ValueError("Toán tử không được hỗ trợ")
        left = _eval_ast_node(node.left)
        right = _eval_ast_node(node.right)
        # Giới hạn số mũ để chống treo bot (DoS)
        if op_type is ast.Pow and abs(right) > 1000:
            raise ValueError("Số mũ quá lớn")
        return ALLOWED_AST_OPS[op_type](left, right)
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in ALLOWED_AST_OPS:
            raise ValueError("Toán tử đơn không hợp lệ")
        return ALLOWED_AST_OPS[op_type](_eval_ast_node(node.operand))
    else:
        raise ValueError("Cú pháp không nằm trong danh mục cho phép")


def safe_inline_calculate(raw_text: str):
    """
    Kiểm tra và tính toán biểu thức nếu tin nhắn là phép tính.
    Trả về chuỗi kết quả hoặc None nếu không phải phép tính.
    """
    text = raw_text.strip()
    if len(text) > 80 or not MATH_PATTERN.match(text):
        return None

    # Chuẩn hóa ký tự: x -> *, ÷ -> /, ^ -> **, 50k -> (50*1000)
    normalized = text.lower()
    normalized = re.sub(r"(\d+(?:\.\d+)?)k\b", r"(\1*1000)", normalized)
    normalized = re.sub(r"(\d+(?:\.\d+)?)m\b", r"(\1*1000000)", normalized)
    normalized = re.sub(r"(\d+(?:\.\d+)?)b\b", r"(\1*1000000000)", normalized)
    normalized = normalized.replace("x", "*").replace("÷", "/").replace("^", "**")

    try:
        tree = ast.parse(normalized, mode="eval")
        result = _eval_ast_node(tree)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        elif isinstance(result, float):
            result = round(result, 4)

        # Định dạng dấu phẩy ngăn cách hàng nghìn nếu kết quả lớn
        res_str = f"{result:,}" if isinstance(result, (int, float)) else str(result)
        return res_str
    except Exception:
        return None


def get_guild_settings(guild_id: int) -> dict:
    """Lấy thông tin cấu hình Store của server, nếu chưa có thì khởi tạo mặc định."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM store_settings WHERE guild_id = ?", (guild_id,)
        ).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO store_settings (guild_id) VALUES (?)", (guild_id,)
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM store_settings WHERE guild_id = ?", (guild_id,)
            ).fetchone()
        return dict(row)


def build_vietqr_url(bank_code: str, account_no: str, account_name: str, amount: int = 0, add_info: str = "") -> str:
    """Tạo đường dẫn ảnh mã QR chuẩn API VietQR."""
    bank_clean = quote(bank_code.strip().upper())
    acc_clean = quote(account_no.strip())
    name_clean = quote(account_name.strip().upper())
    info_clean = quote(add_info.strip())
    url = f"https://img.vietqr.io/image/{bank_clean}-{acc_clean}-compact2.png?accountName={name_clean}"
    if amount > 0:
        url += f"&amount={amount}"
    if info_clean:
        url += f"&addInfo={info_clean}"
    return url


# =============================================================================
# III. KHỞI TẠO BOT & ANTI-SPAM TRACKER
# =============================================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=">", intents=intents, help_command=None)

# Bộ nhớ đệm chống Spam: lưu lịch sử thời gian nhắn tin của từng user
spam_tracker = defaultdict(lambda: deque(maxlen=6))
webserver_started = False


# =============================================================================
# IV. CÁC MODAL & PERSISTENT VIEWS (GIAO DIỆN NÚT BẤM CHUẨN STORE)
# =============================================================================

# --- 1. HỆ THỐNG DÁN TOKEN / COOKIE BẢO MẬT (>paste / >taoban) ---
class SecretPasteModal(ui.Modal, title="🔐 Trình Dán Dữ Liệu Bảo Mật Store"):
    item_title = ui.TextInput(
        label="Tiêu đề / Loại tài khoản",
        placeholder="VD: Cookie Netflix 4K / Token Discord / Link VIP...",
        required=True,
        max_length=100,
    )
    secret_data = ui.TextInput(
        label="Nội dung bí mật (Token / Cookie / Acc / Link)",
        style=discord.TextStyle.paragraph,
        placeholder="Dán toàn bộ chuỗi token, cookie hoặc thông tin tài khoản vào đây...",
        required=True,
        max_length=3500,
    )
    note = ui.TextInput(
        label="Ghi chú bảo hành / Hướng dẫn ngắn",
        placeholder="VD: Không đổi mật khẩu, không đăng xuất thiết bị khác...",
        required=False,
        default="Tuyệt đối không chia sẻ dữ liệu này cho người thứ 3.",
        max_length=200,
    )

    async def on_submit(self, interaction: discord.Interaction):
        paste_id = "SEC-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        now_str = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")

        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO secret_pastes (paste_id, guild_id, channel_id, author_id, title, secret_content, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paste_id,
                    interaction.guild_id,
                    interaction.channel_id,
                    interaction.user.id,
                    self.item_title.value,
                    self.secret_data.value,
                    self.note.value,
                    now_str,
                ),
            )
            conn.commit()

        # Tạo bản xem trước đã che dấu để chống lộ trên kênh chat
        raw_val = self.secret_data.value.strip()
        preview = raw_val[:8] + "••••••••••••••••••••" if len(raw_val) > 12 else "••••••••••••••••"

        embed = discord.Embed(
            title=f"✨ DỮ LIỆU BẢO MẬT: {self.item_title.value.upper()}",
            description=(
                f"┃ ➡️ **Mã dữ liệu:** `{paste_id}`\n"
                f"┃ ➡️ **Người tạo:** {interaction.user.mention}\n"
                f"┃ ➡️ **Thời gian:** `{now_str}`\n\n"
                f"💎 **Bản xem trước (Đã mã hóa hiển thị):**\n"
                f"```text\n{preview}\n```\n"
                f"• **Lưu ý:** *{self.note.value}*"
            ),
            color=COLOR_STORE,
        )
        embed.set_footer(text="Bấm nút bên dưới để xem đầy đủ & sao chép an toàn (Chỉ hiện với bạn)")

        view = SecretPasteView()
        await interaction.response.send_message(embed=embed, view=view)


class OpenPasteModalView(ui.View):
    """Nút bấm mở Modal nhập dữ liệu khi Admin gõ lệnh >paste hoặc >taoban."""
    def __init__(self, author_id: int):
        super().__init__(timeout=180)
        self.author_id = author_id

    @ui.button(label="📝 Nhập Token / Cookie / Link Bí Mật", style=discord.ButtonStyle.primary)
    async def open_modal(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.author_id and not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message(
                "❌ Chỉ người gọi lệnh hoặc Quản trị viên mới được mở bảng này!", ephemeral=True
            )
        await interaction.response.send_modal(SecretPasteModal())


class SecretPasteView(ui.View):
    """Persistent View cho nút [📋 Xem Đầy Đủ / Copy]."""
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="📋 Xem Đầy Đủ / Copy",
        style=discord.ButtonStyle.success,
        custom_id="store:secret_paste_view",
    )
    async def view_secret(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.message.embeds:
            return await interaction.response.send_message("❌ Không tìm thấy dữ liệu.", ephemeral=True)

        desc = interaction.message.embeds[0].description or ""
        m = re.search(r"`(SEC-[A-Z0-9]+)`", desc)
        if not m:
            return await interaction.response.send_message("❌ Mã dữ liệu không hợp lệ.", ephemeral=True)

        paste_id = m.group(1)
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM secret_pastes WHERE paste_id = ?", (paste_id,)
            ).fetchone()

        if not row:
            return await interaction.response.send_message("❌ Dữ liệu không tồn tại trong hệ thống.", ephemeral=True)

        # Kiểm tra quyền: Người tạo, Staff (manage_messages), hoặc đang ở trong đúng kênh Ticket
        is_staff = interaction.user.guild_permissions.manage_messages
        is_author = interaction.user.id == row["author_id"]
        is_in_ticket = (
            hasattr(interaction.channel, "name")
            and interaction.channel.name.startswith("ticket-")
            and (interaction.channel_id == row["channel_id"])
        )

        if not (is_staff or is_author or is_in_ticket):
            return await interaction.response.send_message(
                "⛔ Bạn không có thẩm quyền xem dữ liệu mật này!", ephemeral=True
            )

        secret_embed = discord.Embed(
            title=f"🔓 NỘI DUNG ĐẦY ĐỦ ({row['title']})",
            description=(
                f"┃ ➡️ **Mã bảo mật:** `{paste_id}`\n"
                f"┃ ➡️ **Hướng dẫn:** Giữ lì hoặc bấm nút Copy ở góc khung bên dưới:\n"
                f"```text\n{row['secret_content']}\n```\n"
                f"⚠️ *{row['note']}*"
            ),
            color=COLOR_SUCCESS,
        )
        await interaction.response.send_message(embed=secret_embed, ephemeral=True)


# --- 2. HỆ THỐNG TICKET THUÊ ACC / MUA HÀNG (>createticket & >banggia) ---
class TicketCreateModal(ui.Modal, title="🪽 Đăng Ký Thuê Acc / Mua Dịch Vụ"):
    category_input = ui.TextInput(
        label="Danh mục thuê / Mặt hàng cần mua",
        placeholder="VD: Gemini Advanced / Claude API / Netflix 4K / Nitro...",
        required=True,
        max_length=100,
    )
    duration_input = ui.TextInput(
        label="Thời hạn thuê / Gói đăng ký",
        placeholder="VD: 1 Tháng / 3 Tháng / Vĩnh viễn...",
        required=True,
        max_length=80,
    )
    note_input = ui.TextInput(
        label="Ghi chú thêm (Nâng chính chủ / Cấp sẵn...)",
        placeholder="VD: Nâng chính chủ qua mail cá nhân...",
        required=False,
        default="Cấp tài khoản/dịch vụ chuẩn bảo hành 1 đổi 1",
        max_length=200,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await create_store_ticket_channel(
            interaction=interaction,
            category_name=self.category_input.value,
            duration_name=self.duration_input.value,
            extra_note=self.note_input.value,
        )


async def create_store_ticket_channel(
    interaction: discord.Interaction,
    category_name: str,
    duration_name: str,
    extra_note: str = "Hỗ trợ trực tiếp 1-1",
):
    """Hàm tạo kênh Ticket riêng tư chuẩn giao diện thiên thần 🪽🪽."""
    guild = interaction.guild
    user = interaction.user

    # Phân quyền kênh kín: chỉ khách hàng, bot và Admin/Staff thấy
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True, attach_files=True
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, manage_channels=True, manage_messages=True
        ),
    }
    # Cấp quyền cho các role có quyền manage_messages (Staff)
    for role in guild.roles:
        if role.permissions.manage_messages or role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            )

    clean_username = re.sub(r"[^a-z0-9]", "", user.name.lower())[:12] or "khach"
    ticket_num = random.randint(1000, 9999)
    channel_name = f"ticket-{clean_username}-{ticket_num}"

    ticket_channel = await guild.create_text_channel(
        name=channel_name,
        overwrites=overwrites,
        topic=f"Ticket của {user.display_name} ({user.id}) | Mã: TICKET{ticket_num}",
    )

    embed = discord.Embed(
        title="🪽🪽 TICKET THUÊ ACC & DỊCH VỤ SỐ 🪽🪽",
        description=(
            f"Chào mừng quý khách {user.mention} đến với hệ thống hỗ trợ tự động!\n\n"
            f"┃ ➡️ **Khách hàng:** {user.mention} (`{user.id}`)\n"
            f"┃ ➡️ **Danh mục thuê:** ✨ `{category_name}`\n"
            f"┃ ➡️ **Thời hạn gói:** 💎 `{duration_name}`\n"
            f"┃ ➡️ **Ghi chú:** `{extra_note}`\n"
            f"┃ ➡️ **Mã thanh toán tự động:**\n"
            f"```text\nTICKET{ticket_num}\n```\n"
            f"• **Trạng thái:** ⏳ *Đang chờ nhân viên tiếp nhận...*\n"
            f"• Quý khách có thể bấm **`[💳 Xem STK / VietQR]`** bên dưới để thanh toán nhanh!"
        ),
        color=COLOR_CYAN,
        timestamp=datetime.now(VN_TZ),
    )
    embed.set_footer(text="Store Automation • Bảo hành uy tín 1 đổi 1")

    await ticket_channel.send(
        content=f"🔔 {user.mention} | Đội ngũ Quản trị viên sẽ hỗ trợ bạn ngay!",
        embed=embed,
        view=TicketControlView(),
    )

    if interaction.response.is_done():
        await interaction.followup.send(
            f"✅ Đã khởi tạo phòng giao dịch của bạn tại: {ticket_channel.mention}", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"✅ Đã khởi tạo phòng giao dịch của bạn tại: {ticket_channel.mention}", ephemeral=True
        )


class RenameTicketModal(ui.Modal, title="✏️ Đổi Tên Kênh Ticket v2"):
    new_name = ui.TextInput(
        label="Tên phòng mới (Hỗ trợ Emoji ✅ ⏳ 💎)",
        placeholder="VD: ✅-cape-hero, cho-bank, done-acc, vip-khach...",
        required=True,
        max_length=50,
    )

    async def on_submit(self, interaction: discord.Interaction):
        is_staff = interaction.user.guild_permissions.manage_messages or interaction.user.guild_permissions.administrator
        is_author = str(interaction.user.id) in (interaction.channel.topic or "")
        if not (is_staff or is_author):
            return await interaction.response.send_message(
                "❌ Chỉ Nhân viên / Admin hoặc Người tạo Ticket mới có quyền đổi tên kênh!", ephemeral=True
            )

        # Chuẩn hóa tên kênh: thay khoảng trắng bằng gạch nối, loại bỏ ký tự không hợp lệ nhưng giữ emoji
        raw_val = self.new_name.value.strip().replace(" ", "-")
        clean = re.sub(r"[\s#@:/\\]+", "-", raw_val).strip("-")
        if not clean:
            clean = "ticket-updated"
        clean = clean[:100].lower()
        old_name = interaction.channel.name

        try:
            await interaction.channel.edit(name=clean, reason=f"Đổi tên bởi {interaction.user}")
            embed = discord.Embed(
                title="✏️ ĐỔI TÊN KÊNH TICKET THÀNH CÔNG",
                description=(
                    f"┃ ➡️ **Kênh cũ:** `#{old_name}`\n"
                    f"┃ ➡️ **Kênh mới:** **`#{clean}`**\n"
                    f"┃ ➡️ **Thực hiện bởi:** {interaction.user.mention}"
                ),
                color=COLOR_SUCCESS,
                timestamp=datetime.now(VN_TZ),
            )
            await interaction.response.send_message(embed=embed)
        except discord.HTTPException as e:
            if getattr(e, "status", None) == 429:
                await interaction.response.send_message(
                    "⚠️ Discord giới hạn đổi tên kênh tối đa **2 lần trong vòng 10 phút**! Vui lòng chờ ít phút rồi thử lại nhé.",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"⚠️ Không thể đổi tên kênh lúc này: {e}",
                    ephemeral=True,
                )


class TicketControlView(ui.View):
    """6 Nút chức năng trực tiếp trong Ticket v2 + Đổi Tên + Đánh Giá + Transcript (2 hàng chuẩn UI)."""
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="✅ Claim Ticket",
        style=discord.ButtonStyle.success,
        custom_id="store:ticket_claim",
        row=0,
    )
    async def claim_ticket(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message(
                "❌ Chỉ Nhân viên / Admin mới có thể nhận (Claim) Ticket này!", ephemeral=True
            )

        if not interaction.message.embeds:
            return await interaction.response.send_message("❌ Không tìm thấy thông tin Ticket.", ephemeral=True)

        embed = interaction.message.embeds[0]
        desc = embed.description or ""
        new_desc = re.sub(
            r"• \*\*Trạng thái:\*\* .*",
            f"• **Trạng thái:** ✅ *Đã được tiếp nhận bởi {interaction.user.mention}*",
            desc,
        )
        embed.description = new_desc
        embed.color = COLOR_SUCCESS

        button.disabled = True
        button.label = f"Đã nhận: {interaction.user.display_name}"
        await interaction.response.edit_message(embed=embed, view=self)

        # Tự động gắn tiền tố ✅- vào tên kênh Ticket
        old_ch_name = interaction.channel.name
        if not old_ch_name.startswith("✅-"):
            clean_part = old_ch_name.replace("ticket-", "")
            try:
                await interaction.channel.edit(name=f"✅-{clean_part}", reason=f"Claim bởi {interaction.user}")
            except Exception:
                pass

        await interaction.channel.send(
            f"✨ Nhân viên {interaction.user.mention} đã nhận hỗ trợ Ticket này. Quý khách vui lòng chờ trong giây lát!"
        )

    @ui.button(
        label="✏️ Đổi Tên Kênh",
        style=discord.ButtonStyle.secondary,
        custom_id="store:ticket_rename",
        row=0,
    )
    async def rename_ticket_btn(self, interaction: discord.Interaction, button: ui.Button):
        is_staff = interaction.user.guild_permissions.manage_messages or interaction.user.guild_permissions.administrator
        is_author = str(interaction.user.id) in (interaction.channel.topic or "")
        if not (is_staff or is_author):
            return await interaction.response.send_message(
                "❌ Bạn không có thẩm quyền đổi tên Ticket này!", ephemeral=True
            )
        await interaction.response.send_modal(RenameTicketModal())

    @ui.button(
        label="💳 Xem STK / VietQR",
        style=discord.ButtonStyle.primary,
        custom_id="store:ticket_qr",
        row=0,
    )
    async def show_qr(self, interaction: discord.Interaction, button: ui.Button):
        settings = get_guild_settings(interaction.guild_id)
        # Trích xuất mã TICKETxxxx từ topic kênh hoặc tên kênh nếu có
        ticket_code = interaction.channel.name.split("-")[-1].upper()
        add_info = f"TICKET {ticket_code}"
        qr_url = build_vietqr_url(
            settings["bank_code"], settings["account_no"], settings["account_name"], 0, add_info
        )

        embed = discord.Embed(
            title="💳 THÔNG TIN CHUYỂN KHOẢN & VIETQR TỰ ĐỘNG",
            description=(
                f"Quý khách vui lòng quét mã QR bên dưới hoặc chuyển khoản theo thông tin:\n\n"
                f"```text\n"
                f"Ngân hàng : {settings['bank_code']}\n"
                f"Số TK     : {settings['account_no']}\n"
                f"Chủ TK    : {settings['account_name']}\n"
                f"Nội dung  : {add_info}\n"
                f"```\n"
                f"✨ *Hệ thống Check Bill tự động sẽ xác nhận ngay khi chuyển khoản thành công!*"
            ),
            color=COLOR_CYAN,
        )
        embed.set_image(url=qr_url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(
        label="⭐ Gửi Đánh Giá",
        style=discord.ButtonStyle.success,
        custom_id="store:ticket_legit_btn",
        row=1,
    )
    async def ticket_feedback_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(LegitFeedbackModal())

    @ui.button(
        label="📌 Hướng Dẫn Bảo Mật",
        style=discord.ButtonStyle.secondary,
        custom_id="store:ticket_security",
        row=1,
    )
    async def show_security(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="📌 QUY ĐỊNH BẢO HÀNH & HƯỚNG DẪN BẢO MẬT",
            description=(
                "Để đảm bảo quyền lợi **Bảo hành 1 đổi 1 Full thời gian**, quý khách vui lòng tuân thủ:\n\n"
                "```text\n"
                "1. Tuyệt đối KHÔNG tự ý đổi mật khẩu / Email đối với tài khoản dùng chung hoặc tài khoản thuê.\n"
                "2. Không chia sẻ Cookie / Token ra ngoài hoặc đăng nhập vượt quá số thiết bị quy định.\n"
                "3. Đối với gói Nâng Chính Chủ / Add Family: Bảo mật tuyệt đối 100% trên tài khoản riêng của quý khách.\n"
                "4. Nếu gặp sự cố đăng nhập, vui lòng nhắn ngay tại Ticket để được cấp đổi mới trong 1 phút!\n"
                "```"
            ),
            color=COLOR_GOLD,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(
        label="⏹️ Đóng Ticket",
        style=discord.ButtonStyle.danger,
        custom_id="store:ticket_close",
        row=1,
    )
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            "⏳ **Đang lưu lịch sử giao dịch (Transcript) và đóng Ticket sau 5 giây...**"
        )
        channel = interaction.channel
        guild = interaction.guild

        # 1. Thu thập toàn bộ tin nhắn để xuất file HTML Transcript
        messages = [msg async for msg in channel.history(limit=500, oldest_first=True)]
        html_lines = [
            "<!DOCTYPE html><html><head><meta charset='utf-8'>",
            f"<title>Transcript - {html.escape(channel.name)}</title>",
            "<style>body{background:#1e1f22;color:#dbdee1;font-family:sans-serif;padding:20px;}",
            ".msg{border-bottom:1px solid #2b2d31;padding:10px 0;}",
            ".author{color:#00ffff;font-weight:bold;} .time{color:#949ba4;font-size:12px;margin-left:8px;}",
            ".content{margin-top:5px;white-space:pre-wrap;}</style></head><body>",
            f"<h2>🪽 Lịch sử Ticket: {html.escape(channel.name)}</h2>",
            f"<p>Đóng bởi: {html.escape(str(interaction.user))} | Tổng số tin nhắn: {len(messages)}</p><hr>",
        ]
        for m in messages:
            t_str = m.created_at.astimezone(VN_TZ).strftime("%H:%M:%S %d/%m/%Y")
            clean_content = html.escape(m.content or "")
            if m.embeds:
                clean_content += f"\n[Đính kèm {len(m.embeds)} Embed]"
            html_lines.append(
                f"<div class='msg'><span class='author'>{html.escape(m.author.display_name)}</span>"
                f"<span class='time'>{t_str}</span><div class='content'>{clean_content}</div></div>"
            )
        html_lines.append("</body></html>")
        transcript_bytes = "\n".join(html_lines).encode("utf-8")

        # 2. Tìm kênh #ticket-logs để gửi file lưu trữ đối soát
        settings = get_guild_settings(guild.id)
        log_channel = None
        if settings["ticket_log_channel_id"]:
            log_channel = guild.get_channel(settings["ticket_log_channel_id"])
        if not log_channel:
            log_channel = discord.utils.get(guild.text_channels, name="ticket-logs")

        if log_channel:
            file_obj = discord.File(
                io.BytesIO(transcript_bytes), filename=f"transcript-{channel.name}.html"
            )
            log_embed = discord.Embed(
                title="📁 LƯU TRỮ LỊCH SỬ TICKET (TRANSCRIPT)",
                description=(
                    f"┃ ➡️ **Tên kênh:** `{channel.name}`\n"
                    f"┃ ➡️ **Người đóng:** {interaction.user.mention}\n"
                    f"┃ ➡️ **Số tin nhắn:** `{len(messages)}`\n"
                    f"┃ ➡️ **Thời gian:** `{datetime.now(VN_TZ).strftime('%H:%M %d/%m/%Y')}`"
                ),
                color=COLOR_GOLD,
            )
            try:
                await log_channel.send(embed=log_embed, file=file_obj)
            except Exception:
                pass

        await asyncio.sleep(5)
        try:
            await channel.delete(reason=f"Ticket đóng bởi {interaction.user}")
        except Exception:
            pass


class StorePriceListView(ui.View):
    """Nút bấm đi kèm bảng giá (>banggia) và bảng tạo Ticket."""
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="🪽 Tạo Ticket Mua Hàng / Thuê Acc",
        style=discord.ButtonStyle.success,
        custom_id="store:open_ticket_modal",
    )
    async def open_ticket_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(TicketCreateModal())

    @ui.button(
        label="💳 Xem STK / VietQR",
        style=discord.ButtonStyle.primary,
        custom_id="store:price_qr_btn",
    )
    async def price_qr_btn(self, interaction: discord.Interaction, button: ui.Button):
        settings = get_guild_settings(interaction.guild_id)
        qr_url = build_vietqr_url(
            settings["bank_code"], settings["account_no"], settings["account_name"], 0, f"MUA HANG {interaction.user.name}"
        )
        embed = discord.Embed(
            title="💳 THÔNG TIN THANH TOÁN STORE",
            description=(
                f"```text\n"
                f"Ngân hàng : {settings['bank_code']}\n"
                f"Số TK     : {settings['account_no']}\n"
                f"Chủ TK    : {settings['account_name']}\n"
                f"```"
            ),
            color=COLOR_CYAN,
        )
        embed.set_image(url=qr_url)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# --- 3. HỆ THỐNG ĐÁNH GIÁ UY TÍN (>setuplegit) ---
class LegitFeedbackModal(ui.Modal, title="⭐ Gửi Đánh Giá Uy Tín (Feedback)"):
    seller_input = ui.TextInput(
        label="Người bán / Nhân viên hỗ trợ",
        placeholder="VD: @Admin / Tên nhân viên...",
        required=True,
        max_length=100,
    )
    item_input = ui.TextInput(
        label="Mặt hàng / Dịch vụ đã mua",
        placeholder="VD: 1x Gemini Pro 1 Tháng / Nitro Full...",
        required=True,
        max_length=150,
    )
    stars_input = ui.TextInput(
        label="Số sao đánh giá (Từ 1 đến 5)",
        placeholder="Nhập số từ 1 đến 5 (Mặc định: 5)",
        default="5",
        required=True,
        max_length=1,
    )
    comment_input = ui.TextInput(
        label="Lời nhận xét của bạn",
        style=discord.TextStyle.paragraph,
        placeholder="VD: Giao acc siêu nhanh, hỗ trợ nhiệt tình, +1 uy tín!",
        required=True,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            stars = int(self.stars_input.value.strip())
            stars = max(1, min(5, stars))
        except ValueError:
            stars = 5

        now_str = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO legit_feedbacks (guild_id, customer_id, seller_text, item_text, stars, comment, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    interaction.guild_id,
                    interaction.user.id,
                    self.seller_input.value,
                    self.item_input.value,
                    stars,
                    self.comment_input.value,
                    now_str,
                ),
            )
            total_legit = conn.execute(
                "SELECT COUNT(*) FROM legit_feedbacks WHERE guild_id = ?",
                (interaction.guild_id,),
            ).fetchone()[0]
            conn.commit()

        star_str = "⭐" * stars
        embed = discord.Embed(
            title=f"💎 ĐÁNH GIÁ UY TÍN MỚI (#{total_legit})",
            description=(
                f"┃ ➡️ **Khách hàng:** {interaction.user.mention}\n"
                f"┃ ➡️ **Người bán:** `{self.seller_input.value}`\n"
                f"┃ ➡️ **Sản phẩm:** ✨ `{self.item_input.value}`\n"
                f"┃ ➡️ **Đánh giá:** {star_str} (`{stars}/5`)\n\n"
                f"💬 **Nhận xét từ khách hàng:**\n"
                f"```text\n+1 legit {self.seller_input.value} | {self.item_input.value}\n\"{self.comment_input.value}\"\n```"
            ),
            color=COLOR_CYAN,
            timestamp=datetime.now(VN_TZ),
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Tổng số giao dịch uy tín: {total_legit} Legit")

        await interaction.response.send_message(
            "✅ Cảm ơn quý khách đã gửi đánh giá uy tín cho Store!", ephemeral=True
        )

        settings = get_guild_settings(interaction.guild_id)
        legit_ch_id = settings.get("legit_channel_id", 0)
        legit_ch = interaction.guild.get_channel(legit_ch_id) if legit_ch_id else None
        target_ch = legit_ch or interaction.channel

        msg = await target_ch.send(embed=embed)
        try:
            await msg.add_reaction("💖")
            await msg.add_reaction("💎")
        except Exception:
            pass

        # Nếu interaction ở trong Ticket và có kênh Legit riêng, thông báo xác nhận trong Ticket
        if legit_ch and interaction.channel_id != legit_ch.id:
            try:
                await interaction.channel.send(f"💖 Đánh giá của bạn đã được đăng công khai tại kênh {legit_ch.mention}!")
            except Exception:
                pass

        # Tự động đẩy bảng Menu xuống dưới cùng kênh Legit (Chống trôi)
        if legit_ch:
            await send_or_bump_legit_panel(interaction.guild, legit_ch)


class LegitPanelView(ui.View):
    """Persistent View cho bảng >setuplegit."""
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="⭐ Gửi Đánh Giá",
        style=discord.ButtonStyle.success,
        custom_id="store:legit_submit_btn",
    )
    async def submit_legit_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(LegitFeedbackModal())

    @ui.button(
        label="💎 Số legit",
        style=discord.ButtonStyle.secondary,
        custom_id="store:legit_count_btn",
    )
    async def count_legit_btn(self, interaction: discord.Interaction, button: ui.Button):
        with get_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt, AVG(stars) as avg_star FROM legit_feedbacks WHERE guild_id = ?",
                (interaction.guild_id,),
            ).fetchone()
            cnt = row["cnt"] or 0
            avg_star = round(row["avg_star"] or 5.0, 2)

        embed = discord.Embed(
            title="💎 THỐNG KÊ ĐỘ UY TÍN CỦA STORE",
            description=(
                f"┃ ➡️ **Tổng số lượt Legit / Feedback:** `{cnt:,} giao dịch`\n"
                f"┃ ➡️ **Điểm hài lòng trung bình:** ⭐ `{avg_star} / 5.0`\n"
                f"┃ ➡️ **Chứng nhận:** `100% Uy Tín - Bảo Hành Tự Động`"
            ),
            color=COLOR_CYAN,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def send_or_bump_legit_panel(guild: discord.Guild, target_channel: discord.TextChannel = None):
    """
    Gửi hoặc tự động đẩy bảng Menu Đánh Giá xuống tin nhắn cuối cùng của kênh Legit,
    quét sạch toàn bộ bảng menu cũ trong kênh để menu KHÔNG BAO GIỜ BỊ TRÔI khi có feedback mới.
    """
    settings = get_guild_settings(guild.id)
    ch_id = (target_channel.id if target_channel else 0) or settings.get("legit_channel_id", 0)
    channel = target_channel or guild.get_channel(ch_id)
    if not channel:
        # Tự động tìm kênh có tên feedback/legit nếu chưa cấu hình
        channel = discord.utils.find(
            lambda c: any(k in c.name.lower() for k in ["legit", "feedback", "uy-tin", "danh-gia"]),
            guild.text_channels,
        )
    if not channel:
        return None

    # Quét sạch TẤT CẢ các bảng menu cũ của Bot trong kênh để không bao giờ bị trôi
    try:
        async for old_m in channel.history(limit=30):
            if old_m.author.id == bot.user.id and old_m.embeds:
                t = old_m.embeds[0].title or ""
                if "HỆ THỐNG ĐÁNH GIÁ UY TÍN" in t or "LEGIT / FEEDBACK" in t:
                    try:
                        await old_m.delete()
                    except Exception:
                        pass
    except Exception:
        pass

    embed = discord.Embed(
        title="💎 HỆ THỐNG ĐÁNH GIÁ UY TÍN (LEGIT / FEEDBACK) 💎",
        description=(
            "Cảm ơn quý khách đã tin tưởng và ủng hộ **Store**!\n"
            "Mỗi lượt đánh giá của quý khách là động lực để Store nâng cao chất lượng dịch vụ.\n\n"
            "┃ ➡️ **Cách 1 (Khuyên dùng):** Bấm nút **`[⭐ Gửi Đánh Giá]`** bên dưới để điền biểu mẫu nhanh.\n"
            "┃ ➡️ **Cách 2 (Nhập trực tiếp tại kênh):** Gõ theo cú pháp chuẩn:\n"
            "```text\n+1 legit [@người bán] [số lượng] [mặt hàng]\n```\n"
            "• *Ví dụ:* `+1 legit @Admin 1x Gemini Pro 1 tháng uy tín nhanh gọn`"
        ),
        color=COLOR_CYAN,
    )
    embed.set_footer(text="✨ Bảng menu tự động ghim ở cuối kênh (Chống trôi) • Cập nhật 24/7!")

    new_msg = await channel.send(embed=embed, view=LegitPanelView())

    with get_db() as conn:
        conn.execute(
            "UPDATE store_settings SET legit_channel_id = ?, legit_message_id = ? WHERE guild_id = ?",
            (channel.id, new_msg.id, guild.id),
        )
        conn.commit()
    return new_msg


# --- 4. NÚT TỰ NHẬN THÔNG BÁO SALE / HÀNG MỚI VỀ (>setupnotify) ---
class NotificationRoleView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="🔔 Nhận / Hủy Thông Báo Sale & Hàng Mới Về",
        style=discord.ButtonStyle.primary,
        custom_id="store:toggle_notify_role",
    )
    async def toggle_notify(self, interaction: discord.Interaction, button: ui.Button):
        settings = get_guild_settings(interaction.guild_id)
        role_id = settings["notify_role_id"]
        role = interaction.guild.get_role(role_id) if role_id else None

        if not role:
            return await interaction.response.send_message(
                "⚠️ Admin chưa cấu hình Role thông báo hoặc Role đã bị xóa.", ephemeral=True
            )

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role, reason="Khách tự tắt thông báo Sale")
            await interaction.response.send_message(
                f"🔕 Đã gỡ Role {role.mention}. Bạn sẽ không nhận thông báo Sale nữa.", ephemeral=True
            )
        else:
            await interaction.user.add_roles(role, reason="Khách đăng ký nhận thông báo Sale")
            await interaction.response.send_message(
                f"🔔 Đã cấp Role {role.mention}! Bạn sẽ là người đầu tiên nhận thông báo khi có Flash Sale & Hàng mới về!",
                ephemeral=True,
            )


# --- 5. HỆ THỐNG KHO HÀNG TỰ ĐỘNG CHUẨN COOKIE STORE • STOCK ---
def format_vietnam_time_stock(dt: datetime) -> str:
    """Định dạng thời gian chuẩn: 07/10/2026 6:59 SA / 15/10/2026 10:50 CH."""
    ampm = "SA" if dt.hour < 12 else "CH"
    hour_12 = dt.hour % 12
    if hour_12 == 0:
        hour_12 = 12
    return f"{dt.strftime('%d/%m/%Y')} {hour_12}:{dt.strftime('%M')} {ampm}"


def render_stock_embed(guild: discord.Guild) -> discord.Embed:
    """Tạo Embed kho hàng chuẩn phong cách Cookie Store • STOCK theo ảnh."""
    settings = get_guild_settings(guild.id)
    store_name = settings.get("store_name") or "Cookie Store"
    store_author = settings.get("store_author") or "made by ngocngann"

    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM store_stocks
            WHERE guild_id = ? AND (status = 'available' OR status = 'holding')
            ORDER BY category ASC, id ASC
            """,
            (guild.id,),
        ).fetchall()

    total_items = len(rows)
    embed = discord.Embed(
        title=f"📦 {store_name} • STOCK",
        color=0x57F287,  # Màu xanh lá vibrant chuẩn Store
        timestamp=datetime.now(VN_TZ),
    )

    now_vn = datetime.now(VN_TZ)
    time_str = format_vietnam_time_stock(now_vn)

    if not rows:
        embed.description = (
            "*(Hiện tại kho hàng đang trống hoặc đang cập nhật sản phẩm mới...)*\n\n"
            "💡 **Quản trị viên:** Dùng lệnh `>addstock <danh mục> <giá> <#kênh>` hoặc `>createacc` để thêm hàng vào kho!"
        )
        embed.set_footer(text=f"⚡ {store_name} • {store_author} • Còn 0 acc • {time_str}")
        return embed

    # Gom nhóm theo danh mục
    cat_map = defaultdict(list)
    for r in rows:
        cat_map[r["category"]].append(r)

    desc_lines = []
    for cat, items in cat_map.items():
        cat_upper = cat.upper()
        icon = "🎮 " if not any(cat_upper.startswith(e) for e in ["🎮", "📦", "💎", "⭐", "🔥", "⚡", "✨", "👑"]) else ""
        desc_lines.append(f"**{icon}{cat_upper} • {len(items)} acc**")

        for item in items:
            p_str = "0đ" if item["price"] <= 0 else format_vnd(item["price"])
            ch_id = item["channel_id"]
            ch_obj = guild.get_channel(ch_id) if ch_id else None

            # Ưu tiên hiển thị mention kênh thật dạng # channel-name
            if ch_obj:
                channel_display = ch_obj.mention
            elif item["item_channel"] and item["item_channel"].startswith("<#") and item["item_channel"].endswith(">"):
                raw_digits = re.sub(r"[^\d]", "", item["item_channel"])
                target_ch = guild.get_channel(int(raw_digits)) if raw_digits.isdigit() else None
                if target_ch:
                    channel_display = target_ch.mention
                else:
                    channel_display = f"# `{item['item_name'] or 'acc-mc'}`"
            elif item["item_channel"]:
                clean_name = item["item_channel"].replace("#", "").strip().lower()
                target_ch = discord.utils.get(guild.text_channels, name=clean_name)
                if target_ch:
                    channel_display = target_ch.mention
                else:
                    channel_display = f"# `{item['item_channel']}`"
            else:
                channel_display = f"# `{item['item_name']}`"

            if item["status"] == "holding":
                desc_lines.append(f"💎 `{p_str}` — {channel_display} *(⏳ Đang giữ chỗ)*")
            else:
                desc_lines.append(f"💎 `{p_str}` — {channel_display}")

        desc_lines.append("")

    embed.description = "\n".join(desc_lines)
    embed.set_footer(text=f"⚡ {store_name} • {store_author} • Còn {total_items} acc • {time_str}")
    return embed


async def refresh_persistent_stock_panel(guild: discord.Guild):
    """Cập nhật bảng Stock đã ghim ở kênh cấu hình theo thời gian thực."""
    settings = get_guild_settings(guild.id)
    ch_id = settings.get("stock_channel_id", 0)
    msg_id = settings.get("stock_message_id", 0)
    if ch_id and msg_id:
        ch = guild.get_channel(ch_id)
        if ch:
            try:
                msg = await ch.fetch_message(msg_id)
                embed = render_stock_embed(guild)
                await msg.edit(embed=embed, view=StockControlView())
            except Exception:
                pass


class AddStockModal(ui.Modal, title="➕ Thêm Sản Phẩm / Kênh Vào Kho Stock"):
    cat_input = ui.TextInput(
        label="Danh mục (VD: RÈ SỐC ACC MC)",
        placeholder="RÈ SỐC ACC MC / NETFLIX 4K / GEMINI...",
        default="RÈ SỐC ACC MC",
        required=True,
        max_length=60,
    )
    price_input = ui.TextInput(
        label="Đơn giá (VD: 165k hoặc 0)",
        placeholder="165k, 0, 50000...",
        default="165k",
        required=True,
        max_length=30,
    )
    item_input = ui.TextInput(
        label="Kênh hoặc Tên Acc (Tag #kênh hoặc nhập tên)",
        placeholder="VD: #✅-cape-hero hoặc acc-mc-01",
        required=True,
        max_length=80,
    )
    auto_create = ui.TextInput(
        label="Tự tạo kênh Discord mới nếu chưa có? (co / khong)",
        default="khong",
        required=False,
        max_length=10,
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ Chỉ Staff / Admin mới có quyền thêm hàng vào kho!", ephemeral=True)

        try:
            price = parse_smart_amount(self.price_input.value)
        except ValueError:
            return await interaction.response.send_message("❌ Định dạng giá không hợp lệ! Ví dụ: `165k`, `0`, `50000`...", ephemeral=True)

        guild = interaction.guild
        val = self.item_input.value.strip()
        ch_obj = None

        m_id = re.search(r"<#(\d+)>", val)
        if m_id:
            ch_obj = guild.get_channel(int(m_id.group(1)))
        elif val.isdigit():
            ch_obj = guild.get_channel(int(val))
        else:
            clean_name = val.replace("#", "").strip().lower()
            ch_obj = discord.utils.get(guild.text_channels, name=clean_name)

        should_create = self.auto_create.value.strip().lower() in ["co", "có", "yes", "y", "1"]
        if not ch_obj and should_create:
            clean_ch_name = re.sub(r"[\s#@:/\\]+", "-", val).strip("-")[:50].lower()
            if not clean_ch_name:
                clean_ch_name = f"acc-{random.randint(100,999)}"
            cat_obj = discord.utils.find(lambda c: "kho" in c.name.lower() or "stock" in c.name.lower(), guild.categories)
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
            }
            try:
                ch_obj = await guild.create_text_channel(name=clean_ch_name, category=cat_obj, overwrites=overwrites)
                info_embed = discord.Embed(
                    title=f"📦 THÔNG TIN TÀI KHOẢN: #{clean_ch_name}",
                    description=(
                        f"┃ ➡️ **Danh mục:** 🎮 `{self.cat_input.value.upper()}`\n"
                        f"┃ ➡️ **Đơn giá:** 💎 **`{format_vnd(price)}`**\n"
                        f"┃ ➡️ **Tình trạng:** ✅ *Sẵn sàng giao dịch*\n\n"
                        f"👉 Quý khách muốn mua hãy gõ `>createticket` hoặc bấm nút mua tại bảng `>stock`!"
                    ),
                    color=0x57F287,
                )
                await ch_obj.send(embed=info_embed)
            except Exception:
                pass

        ch_id = ch_obj.id if ch_obj else 0
        ch_name = ch_obj.name if ch_obj else val
        now_str = datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y")

        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO store_stocks (guild_id, category, price, item_name, item_channel, channel_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'available', ?)
                """,
                (guild.id, self.cat_input.value.strip(), price, ch_name, ch_name, ch_id, now_str),
            )
            conn.commit()

        await refresh_persistent_stock_panel(guild)
        await interaction.response.send_message(
            f"✅ Đã thêm **{ch_obj.mention if ch_obj else f'#{ch_name}'}** ({format_vnd(price)}) vào danh mục **{self.cat_input.value.upper()}**!",
            ephemeral=True,
        )


class HoldStockModal(ui.Modal, title="⏳ Giữ Chỗ Tài Khoản / Mặt Hàng"):
    target_input = ui.TextInput(
        label="Tên Kênh hoặc Tag Kênh cần giữ",
        placeholder="VD: #✅-cape-hero hoặc tên kênh",
        required=True,
        max_length=60,
    )
    minutes_input = ui.TextInput(
        label="Thời gian giữ chỗ (Số phút: 5 - 30)",
        default="15",
        required=True,
        max_length=5,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            mins = int(self.minutes_input.value.strip())
            mins = max(5, min(mins, 60))
        except ValueError:
            return await interaction.response.send_message("❌ Số phút giữ chỗ không hợp lệ!", ephemeral=True)

        val = self.target_input.value.strip()
        guild = interaction.guild
        ch_id = 0
        m_id = re.search(r"<#(\d+)>", val)
        if m_id:
            ch_id = int(m_id.group(1))
        elif val.isdigit():
            ch_id = int(val)
        else:
            clean = val.replace("#", "").strip().lower()
            ch = discord.utils.get(guild.text_channels, name=clean)
            if ch:
                ch_id = ch.id

        now_ts = int(time.time())
        until_ts = now_ts + (mins * 60)

        with get_db() as conn:
            if ch_id:
                row = conn.execute(
                    "SELECT * FROM store_stocks WHERE guild_id = ? AND channel_id = ? AND status = 'available'",
                    (guild.id, ch_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM store_stocks WHERE guild_id = ? AND (item_name LIKE ? OR item_channel LIKE ?) AND status = 'available'",
                    (guild.id, f"%{val}%", f"%{val}%"),
                ).fetchone()

            if not row:
                return await interaction.response.send_message(
                    "❌ Không tìm thấy món hàng còn trống khớp với yêu cầu!", ephemeral=True
                )

            conn.execute(
                "UPDATE store_stocks SET status = 'holding', hold_until = ?, holder_id = ? WHERE id = ?",
                (until_ts, interaction.user.id, row["id"]),
            )
            conn.commit()

        target_ch = guild.get_channel(row["channel_id"]) if row["channel_id"] else None
        if target_ch and not target_ch.name.startswith("⏳-"):
            try:
                await target_ch.edit(name=f"⏳-{target_ch.name.replace('✅-', '')}")
            except Exception:
                pass

        await refresh_persistent_stock_panel(guild)
        await interaction.response.send_message(
            f"⏳ Đã giữ chỗ thành công cho bạn trong vòng **{mins} phút**! Vui lòng tạo Ticket để thanh toán trước khi hết hạn.",
            ephemeral=True,
        )


class StockControlView(ui.View):
    """Persistent View cho bảng tồn kho >stock chuẩn Cookie Store (Đầy đủ chức năng tương tác)."""
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="🛒 Mua Ngay / Tạo Ticket",
        style=discord.ButtonStyle.success,
        custom_id="store:stock_buy_ticket",
        row=0,
    )
    async def buy_ticket(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(TicketCreateModal())

    @ui.button(
        label="🔄 Cập Nhật Kho",
        style=discord.ButtonStyle.secondary,
        custom_id="store:stock_refresh",
        row=0,
    )
    async def refresh_stock(self, interaction: discord.Interaction, button: ui.Button):
        embed = render_stock_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(
        label="💳 Xem VietQR",
        style=discord.ButtonStyle.primary,
        custom_id="store:stock_qr",
        row=0,
    )
    async def show_qr(self, interaction: discord.Interaction, button: ui.Button):
        settings = get_guild_settings(interaction.guild_id)
        qr_url = build_vietqr_url(
            settings["bank_code"], settings["account_no"], settings["account_name"], 0, f"MUA HANG {interaction.user.name}"
        )
        embed = discord.Embed(
            title="💳 THÔNG TIN THANH TOÁN STORE",
            description=(
                f"```text\n"
                f"Ngân hàng : {settings['bank_code']}\n"
                f"Số TK     : {settings['account_no']}\n"
                f"Chủ TK    : {settings['account_name']}\n"
                f"```"
            ),
            color=COLOR_CYAN,
        )
        embed.set_image(url=qr_url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(
        label="➕ Thêm Món Vào Kho",
        style=discord.ButtonStyle.success,
        custom_id="store:stock_add_btn",
        row=1,
    )
    async def add_stock_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("❌ Chỉ Staff / Admin mới có quyền thêm hàng vào kho!", ephemeral=True)
        await interaction.response.send_modal(AddStockModal())

    @ui.button(
        label="⏳ Giữ Chỗ Acc",
        style=discord.ButtonStyle.secondary,
        custom_id="store:stock_hold_btn",
        row=1,
    )
    async def hold_stock_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(HoldStockModal())


@tasks.loop(minutes=1)
async def auto_check_stock_holds():
    """Tự động kiểm tra và giải phóng các tài khoản giữ chỗ đã hết hạn."""
    now_ts = int(time.time())
    with get_db() as conn:
        expired = conn.execute(
            "SELECT * FROM store_stocks WHERE status = 'holding' AND hold_until > 0 AND hold_until <= ?",
            (now_ts,),
        ).fetchall()
        if expired:
            conn.execute(
                "UPDATE store_stocks SET status = 'available', hold_until = 0, holder_id = 0 WHERE status = 'holding' AND hold_until > 0 AND hold_until <= ?",
                (now_ts,),
            )
            conn.commit()

    for item in expired:
        guild = bot.get_guild(item["guild_id"])
        if guild:
            ch = guild.get_channel(item["channel_id"]) if item["channel_id"] else None
            if ch and ch.name.startswith("⏳-"):
                try:
                    await ch.edit(name=ch.name.replace("⏳-", ""))
                except Exception:
                    pass
            await refresh_persistent_stock_panel(guild)


# --- 6. HỆ THỐNG GIVEAWAY / PHÁT QUÀ TỰ ĐỘNG ---
class GiveawayView(ui.View):
    """Persistent View cho các sự kiện Giveaway."""
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="🎉 Tham Gia",
        style=discord.ButtonStyle.primary,
        custom_id="store:giveaway_enter",
    )
    async def enter_giveaway(self, interaction: discord.Interaction, button: ui.Button):
        msg_id = interaction.message.id
        with get_db() as conn:
            gw = conn.execute("SELECT * FROM giveaways WHERE message_id = ?", (msg_id,)).fetchone()
            if not gw:
                return await interaction.response.send_message("❌ Sự kiện Giveaway này không còn tồn tại!", ephemeral=True)
            if gw["is_ended"]:
                return await interaction.response.send_message("⏰ Sự kiện Giveaway này đã kết thúc!", ephemeral=True)

            already = conn.execute(
                "SELECT * FROM giveaway_entries WHERE message_id = ? AND user_id = ?",
                (msg_id, interaction.user.id),
            ).fetchone()

            if already:
                conn.execute(
                    "DELETE FROM giveaway_entries WHERE message_id = ? AND user_id = ?",
                    (msg_id, interaction.user.id),
                )
                conn.commit()
                cnt = conn.execute("SELECT COUNT(*) FROM giveaway_entries WHERE message_id = ?", (msg_id,)).fetchone()[0]
                await interaction.response.send_message(f"👋 Bạn đã hủy tham gia. (Hiện có {cnt} người tham gia)", ephemeral=True)
            else:
                conn.execute(
                    "INSERT INTO giveaway_entries (message_id, user_id) VALUES (?, ?)",
                    (msg_id, interaction.user.id),
                )
                conn.commit()
                cnt = conn.execute("SELECT COUNT(*) FROM giveaway_entries WHERE message_id = ?", (msg_id,)).fetchone()[0]
                await interaction.response.send_message(f"🎉 **Chúc mừng!** Bạn đã tham gia Giveaway! (Hiện có {cnt} người tham gia)", ephemeral=True)

        # Cập nhật số người tham gia trên embed
        embed = interaction.message.embeds[0]
        desc = embed.description or ""
        desc = re.sub(r"• \*\*Số người tham gia:\*\* `\d+`", f"• **Số người tham gia:** `{cnt}`", desc)
        embed.description = desc
        try:
            await interaction.message.edit(embed=embed)
        except Exception:
            pass


async def finish_giveaway(message_id: int):
    """Kết thúc giveaway, chọn người chiến thắng ngẫu nhiên và thông báo."""
    with get_db() as conn:
        gw = conn.execute("SELECT * FROM giveaways WHERE message_id = ?", (message_id,)).fetchone()
        if not gw or gw["is_ended"]:
            return
        conn.execute("UPDATE giveaways SET is_ended = 1 WHERE message_id = ?", (message_id,))
        entries = conn.execute("SELECT user_id FROM giveaway_entries WHERE message_id = ?", (message_id,)).fetchall()
        conn.commit()

    guild = bot.get_guild(gw["guild_id"])
    if not guild:
        return
    channel = guild.get_channel(gw["channel_id"])
    if not channel:
        return

    try:
        msg = await channel.fetch_message(message_id)
    except Exception:
        msg = None

    candidate_ids = [r["user_id"] for r in entries]
    winners_count = gw["winners_count"]

    if not candidate_ids:
        if msg:
            embed = msg.embeds[0]
            embed.title = "🎉 GIVEAWAY ĐÃ KẾT THÚC (KHÔNG CÓ NGƯỜI THAM GIA) 🎉"
            embed.color = COLOR_DANGER
            await msg.edit(embed=embed, view=None)
        await channel.send(f"⚠️ Giveaway **{gw['prize']}** đã kết thúc nhưng không có ai tham gia!")
        return

    num_picks = min(len(candidate_ids), winners_count)
    winner_ids = random.sample(candidate_ids, num_picks)
    winner_mentions = ", ".join([f"<@{uid}>" for uid in winner_ids])

    if msg:
        embed = msg.embeds[0]
        embed.title = "🎉 GIVEAWAY ĐÃ KẾT THÚC 🎉"
        embed.color = COLOR_GOLD
        embed.description += f"\n\n🏆 **NGƯỜI TRÚNG THƯỞNG:** {winner_mentions}\n• *Vui lòng tạo Ticket để nhận giải nhé!*"
        await msg.edit(embed=embed, view=None)

    win_embed = discord.Embed(
        title="🎊 CHÚC MỪNG NGƯỜI CHIẾN THẮNG GIVEAWAY! 🎊",
        description=(
            f"┃ ➡️ **Phần thưởng:** 🎁 **{gw['prize']}**\n"
            f"┃ ➡️ **Người trúng giải:** {winner_mentions}\n"
            f"┃ ➡️ **Tổ chức bởi:** <@{gw['host_id']}>\n\n"
            f"✨ Hãy tạo Ticket tại Server để được trao quà trong vòng 24h nhé!"
        ),
        color=COLOR_SUCCESS,
    )
    await channel.send(content=f"🔔 Chúc mừng {winner_mentions}!", embed=win_embed)


@tasks.loop(seconds=30)
async def auto_check_giveaways():
    """Quét và tự động kết thúc giveaway khi đến hạn."""
    now_ts = int(time.time())
    with get_db() as conn:
        rows = conn.execute(
            "SELECT message_id FROM giveaways WHERE is_ended = 0 AND end_time <= ?",
            (now_ts,),
        ).fetchall()

    for r in rows:
        await finish_giveaway(r["message_id"])


# --- 7. TIỆN ÍCH VÍ XU & ECONOMY ---
def get_user_balance(guild_id: int, user_id: int) -> int:
    with get_db() as conn:
        row = conn.execute(
            "SELECT balance FROM user_economy WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO user_economy (user_id, guild_id, balance) VALUES (?, ?, 0)",
                (user_id, guild_id),
            )
            conn.commit()
            return 0
        return row["balance"]


def update_user_balance(guild_id: int, user_id: int, delta: int):
    with get_db() as conn:
        get_user_balance(guild_id, user_id)
        conn.execute(
            "UPDATE user_economy SET balance = MAX(0, balance + ?) WHERE guild_id = ? AND user_id = ?",
            (delta, guild_id, user_id),
        )
        conn.commit()


# =============================================================================
# V. SỰ KIỆN BOT, AUTO INLINE CALCULATOR, ANTI-SPAM & AUTO LEGIT REACTION
# =============================================================================
@bot.event
async def on_ready():
    global webserver_started
    init_db()
    # Đăng ký Persistent Views để các nút bấm hoạt động xuyên suốt 24/7
    bot.add_view(SecretPasteView())
    bot.add_view(TicketControlView())
    bot.add_view(StorePriceListView())
    bot.add_view(LegitPanelView())
    bot.add_view(NotificationRoleView())
    bot.add_view(StockControlView())
    bot.add_view(GiveawayView())

    if not auto_revoke_expired_keys.is_running():
        auto_revoke_expired_keys.start()
    if not auto_check_giveaways.is_running():
        auto_check_giveaways.start()
    if not auto_check_stock_holds.is_running():
        auto_check_stock_holds.start()

    # Khởi chạy Webserver Keep-Alive & Webhook Ngân hàng (chỉ chạy 1 lần)
    if not webserver_started:
        webserver_started = True
        bot.loop.create_task(start_webserver())

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, name="Store 24/7 | >help | >banggia"
        )
    )
    print(f"✅ Bot đã sẵn sàng hoạt động: {bot.user} (ID: {bot.user.id})")


@bot.event
async def on_member_join(member: discord.Member):
    """Tự động cấp Role thành viên mới nếu server đã bật >autorole."""
    if member.bot:
        return
    settings = get_guild_settings(member.guild.id)
    if settings["autorole_id"]:
        role = member.guild.get_role(settings["autorole_id"])
        if role:
            try:
                await member.add_roles(role, reason="AutoRole khi vào Server")
            except Exception:
                pass


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    now_ts = time.time()
    content_raw = message.content.strip()
    content_lower = content_raw.lower()

    # 1. HỆ THỐNG ANTI-SPAM (Quá 5 tin nhắn / 4 giây)
    if not message.author.guild_permissions.manage_messages:
        user_times = spam_tracker[(message.guild.id, message.author.id)]
        user_times.append(now_ts)
        if len(user_times) >= 5 and (now_ts - user_times[0]) <= 4.0:
            user_times.clear()
            try:
                await message.channel.purge(
                    limit=5, check=lambda m: m.author.id == message.author.id
                )
            except Exception:
                pass
            warn_embed = discord.Embed(
                description=f"⚠️ {message.author.mention} **Cảnh báo Anti-Spam:** Vui lòng không nhắn quá nhanh (Tối đa 5 tin / 4 giây)!",
                color=COLOR_DANGER,
            )
            await message.channel.send(embed=warn_embed, delete_after=6)
            return

    # 2. TỰ ĐỘNG BẮT TIN NHẮN "+1 legit ..."
    if content_lower.startswith("+1 legit") or "+1 legit " in content_lower:
        seller_name = "Store Staff"
        if message.mentions:
            seller_name = message.mentions[0].display_name

        now_str = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO legit_feedbacks (guild_id, customer_id, seller_text, item_text, stars, comment, created_at)
                VALUES (?, ?, ?, ?, 5, ?, ?)
                """,
                (
                    message.guild.id,
                    message.author.id,
                    seller_name,
                    content_raw[:100],
                    content_raw,
                    now_str,
                ),
            )
            total_legit = conn.execute(
                "SELECT COUNT(*) FROM legit_feedbacks WHERE guild_id = ?",
                (message.guild.id,),
            ).fetchone()[0]
            conn.commit()

        settings = get_guild_settings(message.guild.id)
        legit_ch_id = settings.get("legit_channel_id", 0)
        legit_ch = message.guild.get_channel(legit_ch_id) if legit_ch_id else None

        fb_embed = discord.Embed(
            title=f"💎 ĐÁNH GIÁ UY TÍN MỚI (#{total_legit})",
            description=(
                f"┃ ➡️ **Khách hàng:** {message.author.mention}\n"
                f"┃ ➡️ **Người bán:** `{seller_name}`\n"
                f"┃ ➡️ **Đánh giá:** ⭐⭐⭐⭐⭐ (`5/5`)\n\n"
                f"💬 **Nội dung:**\n"
                f"```text\n{content_raw}\n```"
            ),
            color=COLOR_CYAN,
            timestamp=datetime.now(VN_TZ),
        )
        fb_embed.set_thumbnail(url=message.author.display_avatar.url)
        fb_embed.set_footer(text=f"Tổng số giao dịch uy tín: {total_legit} Legit")

        if legit_ch and message.channel.id == legit_ch.id:
            # Nhắn trực tiếp trong kênh Legit: xóa tin thô, gửi Embed và đẩy Menu xuống dưới cùng
            try:
                await message.delete()
            except Exception:
                pass
            posted = await legit_ch.send(embed=fb_embed)
            try:
                await posted.add_reaction("💖")
                await posted.add_reaction("💎")
            except Exception:
                pass
            await send_or_bump_legit_panel(message.guild, legit_ch)
        else:
            try:
                await message.add_reaction("💖")
                await message.add_reaction("💎")
            except Exception:
                pass
            if legit_ch:
                posted = await legit_ch.send(embed=fb_embed)
                try:
                    await posted.add_reaction("💖")
                    await posted.add_reaction("💎")
                except Exception:
                    pass
                await send_or_bump_legit_panel(message.guild, legit_ch)

    # 2.1 TỰ ĐỘNG GHIM LẠI MENU LEGIT XUỐNG DƯỚI CÙNG NẾU CÓ CHAT TRONG KÊNH FEEDBACK/LEGIT
    settings_legit = get_guild_settings(message.guild.id)
    if (
        settings_legit
        and settings_legit.get("legit_channel_id") == message.channel.id
        and not content_raw.startswith(">")
        and not is_legit_msg
    ):
        await send_or_bump_legit_panel(message.guild, message.channel)

    # 3. TÍNH TOÁN THÔNG MINH KHÔNG CẦN LỆNH (AUTO INLINE CALCULATOR)
    if not content_raw.startswith(">"):
        calc_res = safe_inline_calculate(content_raw)
        if calc_res is not None:
            await message.reply(
                f"🧮 **Kết quả:** `{content_raw}` = **`{calc_res}`**",
                mention_author=False,
            )
            return

        # Kiểm tra từ khóa FAQ tự động nếu trùng khớp chính xác
        with get_db() as conn:
            faq_row = conn.execute(
                "SELECT answer FROM faqs WHERE guild_id = ? AND keyword = ?",
                (message.guild.id, content_lower),
            ).fetchone()
            if faq_row:
                embed = discord.Embed(
                    title=f"💡 Giải đáp nhanh: {content_raw}",
                    description=faq_row["answer"],
                    color=COLOR_CYAN,
                )
                await message.reply(embed=embed, mention_author=False)
                return

    await bot.process_commands(message)


# =============================================================================
# VI. NHÓM LỆNH STORE, VIETQR, PASTE & BẢNG GIÁ
# =============================================================================
@bot.command(name="paste", aliases=["taoban"])
@commands.has_permissions(manage_messages=True)
async def cmd_paste(ctx: commands.Context):
    """Mở trình dán Token / Cookie / Link bí mật chống lộ & cắt xén."""
    try:
        await ctx.message.delete()
    except Exception:
        pass
    embed = discord.Embed(
        title="🔐 TRÌNH TẠO BẢNG DỮ LIỆU BẢO MẬT (TOKEN / COOKIE / ACC)",
        description=(
            "┃ ➡️ Bấm nút bên dưới để mở cửa sổ **Modal nhập liệu kín**.\n"
            "┃ ➡️ Dữ liệu sau khi gửi sẽ được ẩn an toàn, chỉ khách trong Ticket hoặc Admin mới bấm xem & copy được."
        ),
        color=COLOR_STORE,
    )
    await ctx.send(embed=embed, view=OpenPasteModalView(ctx.author.id), delete_after=60)


@bot.command(name="setupqr")
@commands.has_permissions(administrator=True)
async def cmd_setupqr(ctx: commands.Context, bank_code: str, account_no: str, *, account_name: str):
    """Cài đặt tài khoản ngân hàng VietQR: >setupqr <ngân hàng> <stk> <tên chủ tk>"""
    get_guild_settings(ctx.guild.id)
    with get_db() as conn:
        conn.execute(
            """
            UPDATE store_settings
            SET bank_code = ?, account_no = ?, account_name = ?
            WHERE guild_id = ?
            """,
            (bank_code.upper(), account_no, account_name.upper(), ctx.guild.id),
        )
        conn.commit()

    qr_url = build_vietqr_url(bank_code, account_no, account_name)
    embed = discord.Embed(
        title="✅ ĐÃ CẬP NHẬT CẤU HÌNH VIETQR STORE",
        description=(
            f"```text\n"
            f"Ngân hàng      : {bank_code.upper()}\n"
            f"Số tài khoản   : {account_no}\n"
            f"Chủ tài khoản  : {account_name.upper()}\n"
            f"```"
        ),
        color=COLOR_SUCCESS,
    )
    embed.set_thumbnail(url=qr_url)
    await ctx.reply(embed=embed)


@bot.command(name="qr")
async def cmd_qr(ctx: commands.Context, amount_str: str = "0", *, content: str = ""):
    """Tạo mã VietQR tự động theo số tiền & nội dung: >qr <số tiền> [nội dung]"""
    settings = get_guild_settings(ctx.guild.id)
    try:
        amount = parse_smart_amount(amount_str)
    except ValueError:
        return await ctx.reply(
            "❌ Định dạng số tiền không hợp lệ! Ví dụ đúng: `>qr 50k Mua Nitro` hoặc `>qr 1.5m`"
        )

    transfer_note = content.strip() or f"THANH TOAN {ctx.author.name.upper()}"
    qr_url = build_vietqr_url(
        settings["bank_code"], settings["account_no"], settings["account_name"], amount, transfer_note
    )

    embed = discord.Embed(
        title="💎 QUÉT MÃ VIETQR THANH TOÁN NHANH",
        description=(
            f"┃ ➡️ **Ngân hàng:** `{settings['bank_code']}`\n"
            f"┃ ➡️ **Số tài khoản:** `{settings['account_no']}`\n"
            f"┃ ➡️ **Chủ tài khoản:** `{settings['account_name']}`\n"
            f"┃ ➡️ **Số tiền:** ✨ **`{format_vnd(amount)}`**\n\n"
            f"📋 **Nội dung chuyển khoản (Tự động điền khi quét QR):**\n"
            f"```text\n{transfer_note}\n```"
        ),
        color=COLOR_CYAN,
        timestamp=datetime.now(VN_TZ),
    )
    embed.set_image(url=qr_url)
    embed.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name} • Quét bằng mọi App Ngân hàng & MoMo")
    await ctx.reply(embed=embed)


@bot.command(name="banggia")
async def cmd_banggia(ctx: commands.Context):
    """Hiển thị bảng giá dịch vụ chuyên nghiệp kèm nút Tạo Ticket & VietQR."""
    embed = discord.Embed(
        title="✨💎 BẢNG GIÁ DỊCH VỤ SỐ & TÀI KHOẢN PREMIUM 💎✨",
        description=(
            "Chào mừng quý khách đến với **Store Dịch Vụ Số Tự Động 24/7**.\n"
            "Cam kết **Bảo hành 1 đổi 1 Full thời hạn** – Giao hàng ngay trong 1 phút!\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=COLOR_CYAN,
    )
    embed.add_field(
        name="🤖 1. TÀI KHOẢN AI (GEMINI PRO / CLAUDE / CHATGPT)",
        value=(
            "┃ ➡️ **Gemini Advanced (2TB + AI Pro):**\n"
            "➔ `Add Family Chính Chủ`: **45.000đ / 1 Tháng** | **120.000đ / 3 Tháng**\n"
            "➔ `Acc Cấp Sẵn Riêng Tư`: **39.000đ / 1 Tháng**\n"
            "┃ ➡️ **Claude 3.5 Sonnet Pro / API Key:**\n"
            "➔ `Acc Cấp Mới Full BH`: **350.000đ / 1 Tháng**\n"
            "➔ `Credit API Key`: **Liên hệ theo hạn mức ($5 - $100)**\n"
            "• *Bảo hành: 1 đổi 1 suốt thời gian sử dụng.*"
        ),
        inline=False,
    )
    embed.add_field(
        name="🎮 2. GAME & GIẢI TRÍ (NETFLIX / YOUTUBE / SPOTIFY)",
        value=(
            "┃ ➡️ **Netflix Premium 4K Ultra HD:**\n"
            "➔ `1 Profile Riêng (Pin cố định)`: **65.000đ / 1 Tháng**\n"
            "┃ ➡️ **YouTube Premium + Music:**\n"
            "➔ `Nâng Chính Chủ (Add Family)`: **35.000đ / 1 Tháng** | **180.000đ / 6 Tháng**\n"
            "┃ ➡️ **Spotify Premium Cá Nhân:**\n"
            "➔ `Nâng Chính Chủ (Không mất Playlist)`: **40.000đ / 1 Tháng**"
        ),
        inline=False,
    )
    embed.add_field(
        name="🚀 3. DISCORD NITRO & BOOST SERVER",
        value=(
            "┃ ➡️ **Nitro Basic (1 Tháng):** `45.000đ` (Gift Link chính hãng)\n"
            "┃ ➡️ **Nitro Full Gaming (1 Tháng):** `115.000đ` (Login / Gift)\n"
            "┃ ➡️ **Boost Server 14x (1 Tháng / 3 Tháng):** `90.000đ` / `195.000đ`\n"
            "• *Bảo hành: Không thu hồi (No Revoke) 100%.*"
        ),
        inline=False,
    )
    embed.add_field(
        name="📱 4. MẠNG XÃ HỘI & THIẾT KẾ (CANVA / CAPCUT)",
        value=(
            "┃ ➡️ **CapCut Pro (Chính chủ / Cấp sẵn):** `35.000đ / 1 Tháng` | `190.000đ / 1 Năm`\n"
            "┃ ➡️ **Canva Pro Edu / Teams:** `49.000đ / Vĩnh viễn (BH 1 năm)`\n"
            "```text\n💡 Bấm nút [🪽 Tạo Ticket Mua Hàng] bên dưới để được nhân viên phục vụ ngay!\n```"
        ),
        inline=False,
    )
    embed.set_footer(text="Uy tín tạo thương hiệu • Hỗ trợ tự động 24/7")
    await ctx.send(embed=embed, view=StorePriceListView())


# =============================================================================
# VII. HỆ THỐNG TICKET & ĐÁNH GIÁ UY TÍN
# =============================================================================
@bot.command(name="createticket")
async def cmd_createticket(ctx: commands.Context, category_name: str = None, *, duration_name: str = "1 Tháng"):
    """
    Tạo bảng mở Ticket cho khách (nếu Admin không truyền tham số)
    hoặc mở trực tiếp kênh Ticket hỗ trợ ngay lập tức.
    """
    if not category_name:
        embed = discord.Embed(
            title="🪽🪽 TRUNG TÂM HỖ TRỢ & THUÊ ACC TỰ ĐỘNG 🪽🪽",
            description=(
                "Quý khách có nhu cầu **Mua tài khoản, Thuê dịch vụ AI/Game/Nitro** hoặc **Cần bảo hành**?\n\n"
                "┃ ➡️ **Bước 1:** Bấm vào nút **`[🪽 Tạo Ticket Mua Hàng / Thuê Acc]`** bên dưới.\n"
                "┃ ➡️ **Bước 2:** Điền mặt hàng và thời hạn muốn thuê.\n"
                "┃ ➡️ **Bước 3:** Bot sẽ mở phòng chat riêng tư 1-1 cùng mã VietQR tự động!"
            ),
            color=COLOR_CYAN,
        )
        embed.set_footer(text="Hệ thống Ticket tự động lưu lịch sử bảo vệ quyền lợi khách hàng")
        return await ctx.send(embed=embed, view=StorePriceListView())

    # Tạo kênh Ticket trực tiếp nếu người dùng gõ >createticket <danh mục> <thời hạn>
    guild = ctx.guild
    user = ctx.author
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
    }
    for role in guild.roles:
        if role.permissions.manage_messages or role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

    clean_username = re.sub(r"[^a-z0-9]", "", user.name.lower())[:12] or "khach"
    ticket_num = random.randint(1000, 9999)
    ticket_channel = await guild.create_text_channel(
        name=f"ticket-{clean_username}-{ticket_num}",
        overwrites=overwrites,
        topic=f"Ticket của {user.display_name} ({user.id}) | Mã: TICKET{ticket_num}",
    )

    embed = discord.Embed(
        title="🪽🪽 TICKET THUÊ ACC & DỊCH VỤ SỐ 🪽🪽",
        description=(
            f"┃ ➡️ **Khách hàng:** {user.mention} (`{user.id}`)\n"
            f"┃ ➡️ **Danh mục thuê:** ✨ `{category_name}`\n"
            f"┃ ➡️ **Thời hạn thuê:** 💎 `{duration_name}`\n"
            f"┃ ➡️ **Mã thanh toán tự động:**\n"
            f"```text\nTICKET{ticket_num}\n```\n"
            f"• **Trạng thái:** ⏳ *Đang chờ nhân viên tiếp nhận...*"
        ),
        color=COLOR_CYAN,
        timestamp=datetime.now(VN_TZ),
    )
    await ticket_channel.send(content=f"🔔 {user.mention}", embed=embed, view=TicketControlView())
    await ctx.reply(f"✅ Đã tạo Ticket thành công tại: {ticket_channel.mention}")


@bot.command(name="setuplegit")
@commands.has_permissions(manage_channels=True)
async def cmd_setuplegit(ctx: commands.Context, channel: discord.TextChannel = None):
    """
    Thiết lập bảng Đánh giá uy tín Chống Trôi:
    >setuplegit [#kênh] (mặc định là kênh hiện tại)
    """
    try:
        await ctx.message.delete()
    except Exception:
        pass

    target_channel = channel or ctx.channel
    await send_or_bump_legit_panel(ctx.guild, target_channel)

    if target_channel.id != ctx.channel.id:
        embed = discord.Embed(
            title="✅ ĐÃ THIẾT LẬP KÊNH LEGIT THÀNH CÔNG",
            description=(
                f"┃ ➡️ **Kênh đánh giá:** {target_channel.mention}\n"
                f"┃ ➡️ **Chế độ Chống Trôi:** `Bật (Sticky Auto-Bump)`\n"
                f"┃ ➡️ Bảng Menu Đánh Giá đã được gửi và sẽ luôn tự động đẩy xuống cuối kênh {target_channel.mention}!"
            ),
            color=COLOR_SUCCESS,
        )
        await ctx.send(embed=embed, delete_after=10)


@cmd_setuplegit.error
async def cmd_setuplegit_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("❌ Bạn cần quyền **Quản lý kênh (Manage Channels)** hoặc **Admin** để dùng lệnh này!")
    elif isinstance(error, commands.ChannelNotFound):
        await ctx.reply("❌ Không tìm thấy kênh được chỉ định! Ví dụ: `>setuplegit #feedback`")
    else:
        await ctx.reply(f"❌ Đã xảy ra lỗi: {error}")


# =============================================================================
# VIII. HỆ THỐNG KEY BẢN QUYỀN & CẤP ROLE CÓ THỜI HẠN
# =============================================================================
def generate_random_key() -> str:
    """Sinh mã ngẫu nhiên định dạng KEY-XXXX-YYYY-ZZZZ."""
    chars = string.ascii_uppercase + string.digits
    p1 = "".join(random.choices(chars, k=4))
    p2 = "".join(random.choices(chars, k=4))
    p3 = "".join(random.choices(chars, k=4))
    return f"KEY-{p1}-{p2}-{p3}"


@bot.command(name="genkey")
@commands.has_permissions(administrator=True)
async def cmd_genkey(ctx: commands.Context, role: discord.Role, days: int, amount: int = 1):
    """Tạo Key VIP cấp Role có thời hạn: >genkey <@role> <số ngày (0=vĩnh viễn)> [số lượng]"""
    amount = max(1, min(50, amount))
    keys_created = []

    with get_db() as conn:
        for _ in range(amount):
            k = generate_random_key()
            conn.execute(
                """
                INSERT INTO license_keys (key_code, guild_id, role_id, duration_days)
                VALUES (?, ?, ?, ?)
                """,
                (k, ctx.guild.id, role.id, days),
            )
            keys_created.append(k)
        conn.commit()

    dur_text = "Vĩnh viễn" if days <= 0 else f"{days} Ngày"
    keys_block = "\n".join(keys_created)
    embed = discord.Embed(
        title="🔑 ĐÃ KHỞI TẠO KEY BẢN QUYỀN VIP",
        description=(
            f"┃ ➡️ **Role cấp phát:** {role.mention}\n"
            f"┃ ➡️ **Thời hạn gói:** `{dur_text}`\n"
            f"┃ ➡️ **Số lượng:** `{amount} Key`\n\n"
            f"📋 **Danh sách mã Key (Dùng lệnh `>redeem <key>` để kích hoạt):**\n"
            f"```text\n{keys_block}\n```"
        ),
        color=COLOR_GOLD,
    )
    await ctx.reply(embed=embed)


@bot.command(name="redeem")
async def cmd_redeem(ctx: commands.Context, key_code: str):
    """Kích hoạt mã Key VIP và tự động nhận Role: >redeem <key>"""
    key_clean = key_code.strip().upper()
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM license_keys WHERE key_code = ? AND guild_id = ?",
            (key_clean, ctx.guild.id),
        ).fetchone()

        if not row:
            return await ctx.reply("❌ Mã Key không tồn tại hoặc không thuộc Server này!")
        if row["is_used"]:
            return await ctx.reply("❌ Mã Key này đã được sử dụng trước đó rồi!")

        role = ctx.guild.get_role(row["role_id"])
        if not role:
            return await ctx.reply("⚠️ Role liên kết với Key này không còn tồn tại trên Server!")

        days = row["duration_days"]
        now_dt = datetime.now(VN_TZ)
        if days > 0:
            exp_dt = now_dt + timedelta(days=days)
            exp_ts = int(exp_dt.timestamp())
            exp_str = exp_dt.strftime("%H:%M %d/%m/%Y")
        else:
            exp_ts = 0  # 0 = Vĩnh viễn
            exp_str = "Vĩnh viễn (Lifetime)"

        try:
            await ctx.author.add_roles(role, reason=f"Kích hoạt Key VIP: {key_clean}")
        except discord.Forbidden:
            return await ctx.reply("❌ Bot không đủ quyền cấp Role này (Hãy kéo Role của Bot lên cao hơn)!")

        conn.execute(
            "UPDATE license_keys SET is_used = 1, used_by = ?, used_at = ? WHERE key_code = ?",
            (ctx.author.id, now_dt.strftime("%H:%M %d/%m/%Y"), key_clean),
        )
        conn.execute(
            """
            INSERT INTO active_subscriptions (guild_id, user_id, role_id, key_code, expires_at, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (ctx.guild.id, ctx.author.id, role.id, key_clean, exp_ts),
        )
        conn.commit()

    embed = discord.Embed(
        title="✨ KÍCH HOẠT KEY BẢN QUYỀN THÀNH CÔNG!",
        description=(
            f"┃ ➡️ **Khách hàng:** {ctx.author.mention}\n"
            f"┃ ➡️ **Mã Key:** `{key_clean}`\n"
            f"┃ ➡️ **Role nhận được:** {role.mention}\n"
            f"┃ ➡️ **Ngày hết hạn:** 💎 `{exp_str}`"
        ),
        color=COLOR_SUCCESS,
    )
    await ctx.reply(embed=embed)
    try:
        await ctx.author.send(embed=embed)
    except Exception:
        pass


@tasks.loop(minutes=5)
async def auto_revoke_expired_keys():
    """Task chạy ngầm 5 phút/lần: Quét Database và tự động gỡ Role khi hết hạn."""
    now_ts = int(datetime.now(VN_TZ).timestamp())
    with get_db() as conn:
        expired_rows = conn.execute(
            """
            SELECT * FROM active_subscriptions
            WHERE is_active = 1 AND expires_at > 0 AND expires_at <= ?
            """,
            (now_ts,),
        ).fetchall()

        for sub in expired_rows:
            guild = bot.get_guild(sub["guild_id"])
            if guild:
                member = guild.get_member(sub["user_id"])
                role = guild.get_role(sub["role_id"])
                if member and role and role in member.roles:
                    try:
                        await member.remove_roles(role, reason="Hết hạn Key VIP tự động")
                    except Exception:
                        pass
                    try:
                        dm_embed = discord.Embed(
                            title="⏰ THÔNG BÁO HẾT HẠN GÓI VIP / KEY BẢN QUYỀN",
                            description=(
                                f"Chào {member.mention}, gói quyền lợi **{role.name}** (Key: `{sub['key_code']}`) "
                                f"tại **{guild.name}** của bạn đã hết hạn sử dụng.\n\n"
                                f"┃ ➡️ Hệ thống đã tự động thu hồi Role theo quy định.\n"
                                f"┃ ➡️ Vui lòng tạo Ticket tại Server để gia hạn và tiếp tục sử dụng dịch vụ nhé! 💖"
                            ),
                            color=COLOR_GOLD,
                        )
                        await member.send(embed=dm_embed)
                    except Exception:
                        pass

            conn.execute(
                "UPDATE active_subscriptions SET is_active = 0 WHERE id = ?",
                (sub["id"],),
            )
        conn.commit()


# =============================================================================
# IX. QUẢN LÝ SERVER, KIỂM DUYỆT & TIỆN ÍCH NÂNG CAO
# =============================================================================
@bot.command(name="addrole")
@commands.has_permissions(manage_roles=True)
async def cmd_addrole(ctx: commands.Context, member: discord.Member, role: discord.Role):
    """Cấp role cho thành viên: >addrole @user @role"""
    await member.add_roles(role, reason=f"Cấp bởi {ctx.author}")
    await ctx.reply(f"✅ Đã cấp role {role.mention} cho {member.mention}!")


@bot.command(name="removerole")
@commands.has_permissions(manage_roles=True)
async def cmd_removerole(ctx: commands.Context, member: discord.Member, role: discord.Role):
    """Gỡ role của thành viên: >removerole @user @role"""
    await member.remove_roles(role, reason=f"Gỡ bởi {ctx.author}")
    await ctx.reply(f"✅ Đã gỡ role {role.mention} khỏi {member.mention}!")


@bot.command(name="autorole")
@commands.has_permissions(administrator=True)
async def cmd_autorole(ctx: commands.Context, role: discord.Role = None):
    """Cài đặt tự động phát role khi có người mới vào Server: >autorole @role (hoặc bỏ trống để tắt)."""
    get_guild_settings(ctx.guild.id)
    role_id = role.id if role else 0
    with get_db() as conn:
        conn.execute(
            "UPDATE store_settings SET autorole_id = ? WHERE guild_id = ?",
            (role_id, ctx.guild.id),
        )
        conn.commit()
    if role:
        await ctx.reply(f"✅ Đã bật **AutoRole**: Thành viên mới vào sẽ tự động nhận {role.mention}!")
    else:
        await ctx.reply("🔕 Đã tắt tính năng **AutoRole**.")


@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def cmd_ban(ctx: commands.Context, member: discord.Member, *, reason: str = "Vi phạm nội quy Server"):
    """Cấm thành viên khỏi Server: >ban @user [lý do]"""
    await member.ban(reason=f"{ctx.author}: {reason}")
    await ctx.reply(f"🔨 Đã **Ban** `{member}` | Lý do: `{reason}`")


@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def cmd_unban(ctx: commands.Context, user_id: int, *, reason: str = "Được ân xá"):
    """Gỡ lệnh cấm theo ID: >unban <user_id> [lý do]"""
    user_obj = await bot.fetch_user(user_id)
    await ctx.guild.unban(user_obj, reason=f"{ctx.author}: {reason}")
    await ctx.reply(f"✅ Đã **Unban** `{user_obj}` (`{user_id}`)!")


@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def cmd_kick(ctx: commands.Context, member: discord.Member, *, reason: str = "Vi phạm nội quy"):
    """Đuổi thành viên khỏi Server: >kick @user [lý do]"""
    await member.kick(reason=f"{ctx.author}: {reason}")
    await ctx.reply(f"👢 Đã **Kick** `{member}` | Lý do: `{reason}`")


def parse_duration_to_timedelta(dur_str: str) -> timedelta:
    """Chuyển chuỗi 10m, 2h, 7d... sang timedelta (tối đa 28 ngày chuẩn Discord Timeout)."""
    m = re.match(r"^(\d+)(s|m|h|d)$", dur_str.strip().lower())
    if not m:
        return timedelta(minutes=10)
    val, unit = int(m.group(1)), m.group(2)
    if unit == "s":
        td = timedelta(seconds=val)
    elif unit == "m":
        td = timedelta(minutes=val)
    elif unit == "h":
        td = timedelta(hours=val)
    else:
        td = timedelta(days=val)
    return min(td, timedelta(days=28))


@bot.command(name="mute")
@commands.has_permissions(moderate_members=True)
async def cmd_mute(
    ctx: commands.Context,
    member: discord.Member,
    duration: str = "10m",
    *,
    reason: str = "Vi phạm quy tắc chat",
):
    """Timeout thành viên chính thức của Discord (từ 10m đến 28 ngày): >mute @user 1h [lý do]"""
    td = parse_duration_to_timedelta(duration)
    await member.timeout(td, reason=f"{ctx.author}: {reason}")
    await ctx.reply(
        f"🔇 Đã **Mute (Timeout)** {member.mention} trong `{duration}` | Lý do: `{reason}`"
    )


@bot.command(name="unmute")
@commands.has_permissions(moderate_members=True)
async def cmd_unmute(ctx: commands.Context, member: discord.Member):
    """Gỡ Timeout cho thành viên: >unmute @user"""
    await member.timeout(None, reason=f"Unmute bởi {ctx.author}")
    await ctx.reply(f"🔊 Đã gỡ **Mute** cho {member.mention}!")


@bot.command(name="warn")
@commands.has_permissions(manage_messages=True)
async def cmd_warn(ctx: commands.Context, member: discord.Member, *, reason: str = "Nhắc nhở vi phạm"):
    """Cảnh cáo thành viên và lưu vào Database: >warn @user [lý do]"""
    now_str = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO warnings (guild_id, user_id, moderator_id, reason, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ctx.guild.id, member.id, ctx.author.id, reason, now_str),
        )
        total = conn.execute(
            "SELECT COUNT(*) FROM warnings WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, member.id),
        ).fetchone()[0]
        conn.commit()

    embed = discord.Embed(
        title="⚠️ CẢNH CÁO VI PHẠM",
        description=(
            f"┃ ➡️ **Thành viên:** {member.mention}\n"
            f"┃ ➡️ **Người xử lý:** {ctx.author.mention}\n"
            f"┃ ➡️ **Lý do:** `{reason}`\n"
            f"┃ ➡️ **Tổng số lần cảnh cáo:** `{total} lần`"
        ),
        color=COLOR_DANGER,
    )
    await ctx.reply(embed=embed)


@bot.command(name="warnings")
async def cmd_warnings(ctx: commands.Context, member: discord.Member = None):
    """Xem lịch sử cảnh cáo của thành viên: >warnings [@user]"""
    target = member or ctx.author
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY id DESC LIMIT 15",
            (ctx.guild.id, target.id),
        ).fetchall()

    if not rows:
        return await ctx.reply(f"✅ {target.mention} chưa có bất kỳ cảnh cáo nào!")

    lines = [
        f"`#{idx+1}` [{r['created_at']}] - **Lý do:** {r['reason']} (Bởi <@{r['moderator_id']}>)"
        for idx, r in enumerate(rows)
    ]
    embed = discord.Embed(
        title=f"📋 LỊCH SỬ CẢNH CÁO: {target.display_name}",
        description="\n".join(lines),
        color=COLOR_GOLD,
    )
    await ctx.reply(embed=embed)


@bot.command(name="clear", aliases=["purge"])
@commands.has_permissions(manage_messages=True)
async def cmd_clear(ctx: commands.Context, amount: int = 10):
    """Dọn dẹp tin nhắn rác nhanh: >clear <số lượng>"""
    amount = max(1, min(200, amount))
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 Đã dọn dẹp **`{len(deleted)-1}`** tin nhắn!", delete_after=4)


@bot.command(name="lock")
@commands.has_permissions(manage_channels=True)
async def cmd_lock(ctx: commands.Context):
    """Khóa nhanh kênh chat hiện tại."""
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.reply("🔒 **Kênh chat đã được khóa bởi Quản trị viên!**")


@bot.command(name="unlock")
@commands.has_permissions(manage_channels=True)
async def cmd_unlock(ctx: commands.Context):
    """Mở khóa kênh chat hiện tại."""
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = None
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.reply("🔓 **Kênh chat đã được mở khóa!**")


@bot.command(name="steal")
@commands.has_permissions(manage_emojis=True)
async def cmd_steal(ctx: commands.Context, *, emojis_input: str = ""):
    """
    Trộm 1 hoặc NHIỀU Emoji (kể cả GIF) từ Server khác về Server mình cùng lúc:
    • Trộm nhiều Emoji: >steal <emoji1> <emoji2> <emoji3> ...
    • Trộm 1 Emoji đổi tên: >steal <emoji> [tên_mới]
    • Trộm từ tin nhắn trả lời: Reply vào tin nhắn có emoji rồi gõ `>steal`
    """
    raw_content = emojis_input.strip()

    # Nếu người dùng reply tin nhắn và gõ >steal mà không paste emoji
    if not raw_content and ctx.message.reference:
        try:
            ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            raw_content = ref_msg.content
        except Exception:
            pass

    if not raw_content:
        return await ctx.reply(
            "❌ Vui lòng gửi kèm ít nhất một Custom Emoji hoặc Reply vào tin nhắn chứa Emoji!\n"
            "• Ví dụ steal nhiều emoji: `>steal <:e1:...> <:e2:...> <:e3:...>`"
        )

    # Tìm tất cả emoji dạng <a:name:id> hoặc <:name:id>
    matches = re.findall(r"<(a?):([a-zA-Z0-9_]+):(\d+)>", raw_content)
    if not matches:
        return await ctx.reply(
            "❌ Không tìm thấy Custom Emoji nào hợp lệ!\n"
            "💡 *Lưu ý: Chỉ trộm được Custom Emoji của server Discord, không thể trộm emoji mặc định của hệ điều hành (😀, 👍, ...)*"
        )

    # Nếu chỉ có 1 emoji và có từ thứ 2 không phải emoji thì dùng làm custom name
    custom_name = None
    if len(matches) == 1:
        parts = raw_content.split()
        if len(parts) >= 2 and not parts[1].startswith("<"):
            custom_name = re.sub(r"[^a-zA-Z0-9_]", "", parts[1])[:32]

    # Giới hạn tối đa 25 emoji mỗi lần để tránh rate limit Discord
    if len(matches) > 25:
        matches = matches[:25]

    status_msg = await ctx.reply(f"⏳ Đang tiến hành trộm **{len(matches)}** Emoji về Server...")

    added = []
    failed = []

    async with aiohttp.ClientSession() as session:
        for is_anim, orig_name, emoji_id in matches:
            final_name = (custom_name if (len(matches) == 1 and custom_name) else orig_name)[:32]
            ext = "gif" if is_anim else "png"
            url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}"

            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        failed.append(f"`:{orig_name}:` (Không tải được ảnh)")
                        continue
                    img_bytes = await resp.read()

                new_emoji = await ctx.guild.create_custom_emoji(
                    name=final_name,
                    image=img_bytes,
                    reason=f"Steal bởi {ctx.author} ({ctx.author.id})",
                )
                added.append(f"{new_emoji} `:{new_emoji.name}:`")
                # Nghỉ nhẹ 0.3s giữa các emoji để tránh Discord Rate Limit
                await asyncio.sleep(0.3)
            except discord.HTTPException as e:
                err_text = str(e)
                if e.code == 30008:
                    failed.append(f"`:{orig_name}:` (Server đã hết slot chứa Emoji)")
                    break
                elif "already exists" in err_text.lower():
                    failed.append(f"`:{orig_name}:` (Tên đã tồn tại)")
                else:
                    failed.append(f"`:{orig_name}:` (Lỗi Discord: {e.text[:40]})")
            except Exception as e:
                failed.append(f"`:{orig_name}:` ({str(e)[:30]})")

    # Tạo Embed thông báo kết quả
    embed = discord.Embed(
        title="✨ KẾT QUẢ TRỘM EMOJI (BULK STEAL)",
        color=COLOR_SUCCESS if added else COLOR_DANGER,
        timestamp=datetime.now(VN_TZ),
    )
    if added:
        embed.add_field(
            name=f"✅ Thành Công ({len(added)}/{len(matches)}):",
            value="\n".join(added[:15]) + (f"\n*...và {len(added) - 15} emoji khác*" if len(added) > 15 else ""),
            inline=False,
        )
    if failed:
        embed.add_field(
            name=f"⚠️ Thất Bại ({len(failed)}):",
            value="\n".join(failed[:10]),
            inline=False,
        )
    embed.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name}")

    try:
        await status_msg.edit(content=None, embed=embed)
    except Exception:
        await ctx.send(embed=embed)


@cmd_steal.error
async def cmd_steal_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("❌ Bạn cần quyền **Quản lý biểu cảm (Manage Emojis & Stickers)** để dùng lệnh này!")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.reply("❌ Bot thiếu quyền **Quản lý biểu cảm (Manage Emojis & Stickers)** trên Server!")
    else:
        await ctx.reply(f"❌ Lỗi lệnh steal: {error}")


@bot.command(name="banner")
async def cmd_banner(ctx: commands.Context, member: discord.Member = None):
    """Lấy ảnh Banner của người dùng hoặc của Server: >banner [@user]"""
    target = member or ctx.author
    fetched_user = await bot.fetch_user(target.id)

    if fetched_user.banner:
        embed = discord.Embed(
            title=f"🖼️ BANNER CỦA {fetched_user.display_name.upper()}",
            color=COLOR_CYAN,
        )
        embed.set_image(url=fetched_user.banner.url)
        return await ctx.reply(embed=embed)

    if ctx.guild.banner:
        embed = discord.Embed(
            title=f"🖼️ BANNER SERVER: {ctx.guild.name.upper()}",
            description="*(Người dùng này không có Banner cá nhân, hiển thị Banner của Server)*",
            color=COLOR_CYAN,
        )
        embed.set_image(url=ctx.guild.banner.url)
        return await ctx.reply(embed=embed)

    await ctx.reply("❌ Người dùng này (và cả Server) hiện chưa cài đặt ảnh Banner!")


def _get_system_font(size: int, bold: bool = False):
    """Tìm font tiếng Việt có sẵn trên hệ thống Windows hoặc fallback."""
    font_candidates = [
        "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\segoeuib.ttf" if bold else "C:\\Windows\\Fonts\\segoeui.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for candidate in font_candidates:
        if os.path.exists(candidate):
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:
                pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


@bot.command(name="bannergen")
async def cmd_bannergen(ctx: commands.Context, *, text: str):
    """Tự động vẽ ảnh Banner thông báo sắc nét bằng thư viện Pillow: >bannergen <nội dung>"""
    width, height = 1000, 360
    img = Image.new("RGB", (width, height), color=(18, 20, 28))
    draw = ImageDraw.Draw(img)

    # Vẽ nền chuyển sắc (Gradient) & viền Cyan hiện đại
    for y in range(height):
        r = int(18 + (y / height) * 15)
        g = int(22 + (y / height) * 35)
        b = int(35 + (y / height) * 65)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Khung viền đôi sang trọng
    draw.rectangle([12, 12, width - 12, height - 12], outline=(0, 255, 255), width=3)
    draw.rectangle([22, 22, width - 22, height - 22], outline=(88, 101, 242), width=1)

    # Tải font chữ hỗ trợ Unicode
    font_title = _get_system_font(44, bold=True)
    font_sub = _get_system_font(24, bold=False)

    header_text = f"✦ {ctx.guild.name.upper()} OFFICIAL STORE ✦"
    draw.text((width // 2, 70), header_text, fill=(0, 255, 255), anchor="mm", font=font_sub)

    # Tự động ngắt dòng nếu nội dung dài
    words = text.upper().split()
    lines, cur = [], ""
    for w in words:
        if len(cur + " " + w) <= 28:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    final_body = "\n".join(lines[:3])

    draw.multiline_text(
        (width // 2, height // 2 + 15),
        final_body,
        fill=(255, 255, 255),
        anchor="mm",
        align="center",
        font=font_title,
        spacing=12,
    )
    draw.text(
        (width // 2, height - 45),
        "UY TÍN • TỰ ĐỘNG 24/7 • BẢO HÀNH 1 ĐỔI 1",
        fill=(241, 196, 15),
        anchor="mm",
        font=font_sub,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    await ctx.reply(
        content=f"✨ Banner thông báo của {ctx.author.mention} đã sẵn sàng!",
        file=discord.File(buf, filename="store_banner.png"),
    )


@bot.group(name="faq", invoke_without_command=True)
async def cmd_faq(ctx: commands.Context):
    """Quản lý hệ thống trả lời tự động FAQ: >faq add / list / del"""
    await ctx.reply(
        "📌 **Cú pháp FAQ:**\n"
        "• `>faq add <từ khóa> | <câu trả lời>`\n"
        "• `>faq list`\n"
        "• `>faq del <từ khóa>`"
    )


@cmd_faq.command(name="add")
@commands.has_permissions(manage_messages=True)
async def cmd_faq_add(ctx: commands.Context, *, content: str):
    if "|" not in content:
        return await ctx.reply("❌ Vui lòng ngăn cách từ khóa và câu trả lời bằng dấu `|`")
    kw, ans = [x.strip() for x in content.split("|", 1)]
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO faqs (guild_id, keyword, answer) VALUES (?, ?, ?)",
            (ctx.guild.id, kw.lower(), ans),
        )
        conn.commit()
    await ctx.reply(f"✅ Đã lưu FAQ cho từ khóa: `{kw.lower()}`")


@cmd_faq.command(name="list")
async def cmd_faq_list(ctx: commands.Context):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT keyword, answer FROM faqs WHERE guild_id = ?", (ctx.guild.id,)
        ).fetchall()
    if not rows:
        return await ctx.reply("📭 Server hiện chưa có FAQ nào.")
    desc = "\n".join([f"• **`{r['keyword']}`** ➔ {r['answer'][:80]}" for r in rows])
    embed = discord.Embed(title="📚 DANH SÁCH CÂU HỎI THƯỜNG GẶP (FAQ)", description=desc, color=COLOR_CYAN)
    await ctx.reply(embed=embed)


@cmd_faq.command(name="del")
@commands.has_permissions(manage_messages=True)
async def cmd_faq_del(ctx: commands.Context, *, keyword: str):
    with get_db() as conn:
        conn.execute(
            "DELETE FROM faqs WHERE guild_id = ? AND keyword = ?",
            (ctx.guild.id, keyword.strip().lower()),
        )
        conn.commit()
    await ctx.reply(f"🗑️ Đã xóa FAQ: `{keyword.strip().lower()}`")


@bot.command(name="ask")
async def cmd_ask(ctx: commands.Context, *, question: str):
    """Hỏi đáp thông minh tích hợp Gemini AI & dữ liệu Store: >ask <câu hỏi>"""
    if not GEMINI_API_KEY:
        return await ctx.reply(
            "🤖 **Trợ lý AI Store:** Admin chưa cấu hình `GEMINI_API_KEY` trong file cấu hình `.env`. "
            "Quý khách có thể gõ `>banggia` hoặc `>createticket` để được hỗ trợ ngay nhé!"
        )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    system_prompt = (
        "Bạn là trợ lý AI chuyên nghiệp của cửa hàng dịch vụ số Discord Store. "
        "Hãy trả lời ngắn gọn, lịch sự, nhiệt tình bằng tiếng Việt."
    )
    payload = {
        "contents": [{"parts": [{"text": f"{system_prompt}\n\nCâu hỏi khách hàng: {question}"}]}]
    }

    async with ctx.typing():
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    return await ctx.reply("⚠️ Kết nối Gemini AI đang bận, vui lòng thử lại sau giây lát!")
                data = await resp.json()
                try:
                    answer = data["candidates"][0]["content"]["parts"][0]["text"]
                except Exception:
                    answer = "Xin lỗi, mình chưa tìm được câu trả lời phù hợp."

    embed = discord.Embed(
        title="✨ TRỢ LÝ GEMINI AI - DISCORD STORE",
        description=answer[:3900],
        color=COLOR_CYAN,
    )
    embed.set_footer(text=f"Hỏi bởi {ctx.author.display_name}")
    await ctx.reply(embed=embed)


# =============================================================================
# X. CÁC TÍNH NĂNG NÂNG CẤP ĐỘC QUYỀN CHO STORE
# =============================================================================

# --- 1. KIỂM TRA LỪA ĐẢO / DANH SÁCH ĐEN (>checkscam, >addscam) ---
@bot.command(name="checkscam")
async def cmd_checkscam(ctx: commands.Context, target_id: str):
    """Tra cứu STK ngân hàng hoặc Discord ID có nằm trong danh sách Scammer không."""
    clean_id = target_id.strip().replace("<@", "").replace(">", "")
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM scam_blacklist WHERE target_id = ?", (clean_id,)
        ).fetchone()

    if row:
        embed = discord.Embed(
            title="🚨 CẢNH BÁO ĐỎ: PHÁT HIỆN ĐỐI TƯỢNG SCAM / LỪA ĐẢO!",
            description=(
                f"┃ ➡️ **STK / ID tra cứu:** `{clean_id}`\n"
                f"┃ ➡️ **Trạng thái:** ⛔ **NẰM TRONG DANH SÁCH ĐEN (BLACKLIST)**\n"
                f"┃ ➡️ **Bằng chứng / Lý do:** `{row['reason']}`\n"
                f"┃ ➡️ **Ngày ghi nhận:** `{row['created_at']}`\n\n"
                f"⚠️ **Khuyến cáo:** *Tuyệt đối KHÔNG giao dịch hoặc chuyển tiền cho số tài khoản/ID này!*"
            ),
            color=COLOR_DANGER,
        )
    else:
        embed = discord.Embed(
            title="🛡️ KẾT QUẢ KIỂM TRA AN TOÀN (CHECK SCAM)",
            description=(
                f"┃ ➡️ **STK / ID tra cứu:** `{clean_id}`\n"
                f"┃ ➡️ **Trạng thái:** ✅ **Chưa có ghi nhận lừa đảo trên hệ thống**\n\n"
                f"💡 *Lưu ý: Luôn giao dịch trực tiếp qua Ticket chính thức của Store để được bảo hiểm 100%.*"
            ),
            color=COLOR_SUCCESS,
        )
    await ctx.reply(embed=embed)


@bot.command(name="addscam")
@commands.has_permissions(administrator=True)
async def cmd_addscam(ctx: commands.Context, target_id: str, *, reason: str):
    """Thêm STK hoặc ID lừa đảo vào danh sách đen: >addscam <stk/id> <lý do>"""
    clean_id = target_id.strip().replace("<@", "").replace(">", "")
    now_str = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO scam_blacklist (target_id, reason, added_by, created_at) VALUES (?, ?, ?, ?)",
            (clean_id, reason, ctx.author.id, now_str),
        )
        conn.commit()
    await ctx.reply(f"🚨 Đã đưa `{clean_id}` vào **Danh sách đen Scammer** | Lý do: `{reason}`")


# --- 2. THỐNG KÊ DOANH THU & BÁO CÁO BÁN HÀNG (>done, >doanhthu) ---
@bot.command(name="done")
@commands.has_permissions(manage_messages=True)
async def cmd_done(ctx: commands.Context, customer: discord.Member, amount_str: str, *, item: str = "Dịch vụ Store"):
    """Nhân viên chốt đơn hoàn tất: >done @khách <số tiền> [mặt hàng]"""
    try:
        amount = parse_smart_amount(amount_str)
    except ValueError:
        return await ctx.reply("❌ Số tiền không hợp lệ! Ví dụ: `>done @khach 120k Gemini Pro 3 tháng`")

    now_dt = datetime.now(VN_TZ)
    now_str = now_dt.strftime("%H:%M %d/%m/%Y")
    day_str = now_dt.strftime("%Y-%m-%d")
    month_str = now_dt.strftime("%Y-%m")

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO sales_orders (guild_id, staff_id, customer_id, amount, item, created_at, day_str, month_str)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ctx.guild.id, ctx.author.id, customer.id, amount, item, now_str, day_str, month_str),
        )
        order_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()

    embed = discord.Embed(
        title=f"✅ HOÀN TẤT ĐƠN HÀNG #{order_id}",
        description=(
            f"┃ ➡️ **Khách hàng:** {customer.mention}\n"
            f"┃ ➡️ **Nhân viên hỗ trợ:** {ctx.author.mention}\n"
            f"┃ ➡️ **Sản phẩm:** ✨ `{item}`\n"
            f"┃ ➡️ **Doanh thu ghi nhận:** 💰 **`{format_vnd(amount)}`**\n\n"
            f"💖 *Cảm ơn quý khách! Đừng quên để lại đánh giá uy tín tại kênh Feedback nhé!*"
        ),
        color=COLOR_SUCCESS,
        timestamp=now_dt,
    )
    await ctx.reply(embed=embed)


@bot.command(name="doanhthu")
@commands.has_permissions(manage_guild=True)
async def cmd_doanhthu(ctx: commands.Context):
    """Xem báo cáo doanh thu Ngày / Tháng và Bảng xếp hạng nhân viên bán chạy nhất."""
    now_dt = datetime.now(VN_TZ)
    day_str = now_dt.strftime("%Y-%m-%d")
    month_str = now_dt.strftime("%Y-%m")

    with get_db() as conn:
        day_rev = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as s, COUNT(*) as c FROM sales_orders WHERE guild_id = ? AND day_str = ?",
            (ctx.guild.id, day_str),
        ).fetchone()
        month_rev = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as s, COUNT(*) as c FROM sales_orders WHERE guild_id = ? AND month_str = ?",
            (ctx.guild.id, month_str),
        ).fetchone()
        top_staff = conn.execute(
            """
            SELECT staff_id, SUM(amount) as total_amt, COUNT(*) as orders
            FROM sales_orders
            WHERE guild_id = ? AND month_str = ?
            GROUP BY staff_id
            ORDER BY total_amt DESC
            LIMIT 5
            """,
            (ctx.guild.id, month_str),
        ).fetchall()

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    if top_staff:
        lb_lines = [
            f"{medals[i]} <@{r['staff_id']}> ➔ **`{format_vnd(r['total_amt'])}`** (`{r['orders']} đơn`)"
            for i, r in enumerate(top_staff)
        ]
        lb_text = "\n".join(lb_lines)
    else:
        lb_text = "*Chưa có dữ liệu đơn hàng trong tháng này.*"

    embed = discord.Embed(
        title="📊 BÁO CÁO DOANH THU & BẢNG XẾP HẠNG STORE",
        description=(
            f"┃ ➡️ **Doanh thu Hôm nay (`{day_str}`):**\n"
            f"➔ 💰 **`{format_vnd(day_rev['s'])}`** ({day_rev['c']} đơn hàng)\n\n"
            f"┃ ➡️ **Doanh thu Tháng này (`{month_str}`):**\n"
            f"➔ 💎 **`{format_vnd(month_rev['s'])}`** ({month_rev['c']} đơn hàng)\n\n"
            f"🏆 **TOP NHÂN VIÊN BÁN CHẠY NHẤT THÁNG:**\n"
            f"{lb_text}"
        ),
        color=COLOR_GOLD,
        timestamp=now_dt,
    )
    await ctx.reply(embed=embed)


# --- 3. NÚT TỰ NHẬN THÔNG BÁO SALE / HÀNG MỚI VỀ (>setupnotify) ---
@bot.command(name="setupnotify")
@commands.has_permissions(administrator=True)
async def cmd_setupnotify(ctx: commands.Context, role: discord.Role):
    """Tạo bảng nút bấm cho khách tự nhận Role thông báo Sale / Hàng mới về."""
    get_guild_settings(ctx.guild.id)
    with get_db() as conn:
        conn.execute(
            "UPDATE store_settings SET notify_role_id = ? WHERE guild_id = ?",
            (role.id, ctx.guild.id),
        )
        conn.commit()

    embed = discord.Embed(
        title="🔔 ĐĂNG KÝ NHẬN THÔNG BÁO FLASH SALE & HÀNG MỚI VỀ",
        description=(
            f"Bấm vào nút bên dưới để nhận ngay Role {role.mention}!\n\n"
            f"┃ ➡️ **Quyền lợi:** Nhận thông báo sớm nhất khi Store có **Deal 0đ, Flash Sale giảm 50%** hoặc **Restock hàng hiếm**.\n"
            f"┃ ➡️ Bạn có thể bấm lại bất cứ lúc nào để bật/tắt thông báo."
        ),
        color=COLOR_CYAN,
    )
    await ctx.send(embed=embed, view=NotificationRoleView())


# --- 4. LỆNH TEST WEBHOOK CHECK BILL TỰ ĐỘNG (>testbill) ---
@bot.command(name="testbill")
@commands.has_permissions(administrator=True)
async def cmd_testbill(ctx: commands.Context, amount_str: str = "50k", *, transfer_content: str = ""):
    """Giả lập tín hiệu ting ting từ ngân hàng vào Ticket hiện tại để test."""
    try:
        amount = parse_smart_amount(amount_str)
    except ValueError:
        return await ctx.reply("❌ Định dạng số tiền không hợp lệ! Ví dụ: `>testbill 50k`")

    content_note = transfer_content or f"TICKET {ctx.channel.name}"
    embed = discord.Embed(
        title="✅ XÁC NHẬN THANH TOÁN TỰ ĐỘNG (AUTO BANK WEBHOOK)",
        description=(
            f"**✅ Đã nhận được {format_vnd(amount)}! Nhân viên sẽ bàn giao acc ngay cho bạn.**\n\n"
            f"```text\n"
            f"Số tiền nhận : {format_vnd(amount)}\n"
            f"Nội dung CK  : {content_note}\n"
            f"Thời gian    : {datetime.now(VN_TZ).strftime('%H:%M:%S %d/%m/%Y')}\n"
            f"```"
        ),
        color=COLOR_SUCCESS,
    )
    await ctx.send(embed=embed)


# =============================================================================
# X. TÍNH NĂNG TICKET V2, KHO STOCK, GIVEAWAY, ECONOMY & MENU TRỢ GIÚP
# =============================================================================

# --- 1. TÍNH NĂNG ĐỔI TÊN KÊNH TICKET V2 (>rename) ---
@bot.command(name="rename", aliases=["doiten", "renameticket", "ticketrename"])
async def cmd_rename(ctx: commands.Context, *, new_name: str = None):
    """
    Đổi tên kênh Ticket v2 hoặc phòng hỗ trợ hiện tại.
    Cú pháp: >rename <tên mới>
    Ví dụ: >rename ✅-cape-hero
           >rename cho-bank-50k
           >rename done-khach-vip
    """
    if not new_name:
        embed = discord.Embed(
            title="✏️ ĐỔI TÊN KÊNH TICKET V2",
            description=(
                "**Hướng dẫn đổi tên kênh nhanh chóng:**\n\n"
                "┃ ➡️ **Cách 1 (Lệnh chat):** Gõ `>rename <tên mới>` trực tiếp trong kênh này.\n"
                "• *Ví dụ 1:* `>rename ✅-cape-hero`\n"
                "• *Ví dụ 2:* `>rename cho-bank-50k`\n"
                "• *Ví dụ 3:* `>rename done-acc`\n\n"
                "┃ ➡️ **Cách 2 (Nút bấm):** Bấm nút **`[✏️ Đổi Tên Kênh]`** trong tin nhắn đầu kênh Ticket!"
            ),
            color=COLOR_CYAN,
        )
        embed.set_footer(text="Hỗ trợ đầy đủ Emoji ✅ ⏳ 💎 và định dạng tiếng Việt")
        return await ctx.reply(embed=embed)

    is_staff = ctx.author.guild_permissions.manage_messages or ctx.author.guild_permissions.administrator
    is_author = str(ctx.author.id) in (ctx.channel.topic or "")
    if not (is_staff or is_author):
        return await ctx.reply("❌ Bạn không có thẩm quyền đổi tên Ticket này (Cần quyền Staff hoặc Chủ Ticket)!")

    raw_val = new_name.strip().replace(" ", "-")
    clean = re.sub(r"[\s#@:/\\]+", "-", raw_val).strip("-")
    if not clean:
        clean = "ticket-updated"
    clean = clean[:100].lower()
    old_name = ctx.channel.name

    try:
        await ctx.channel.edit(name=clean, reason=f"Đổi tên bởi {ctx.author}")
        embed = discord.Embed(
            title="✏️ ĐỔI TÊN KÊNH THÀNH CÔNG",
            description=(
                f"┃ ➡️ **Kênh cũ:** `#{old_name}`\n"
                f"┃ ➡️ **Kênh mới:** **`#{clean}`**\n"
                f"┃ ➡️ **Người thực hiện:** {ctx.author.mention}"
            ),
            color=COLOR_SUCCESS,
            timestamp=datetime.now(VN_TZ),
        )
        await ctx.send(embed=embed)
    except discord.HTTPException as e:
        if getattr(e, "status", None) == 429:
            await ctx.reply(
                "⚠️ Discord giới hạn đổi tên kênh tối đa **2 lần trong vòng 10 phút**! Vui lòng chờ vài phút rồi thử lại nhé."
            )
        else:
            await ctx.reply(f"⚠️ Không thể đổi tên kênh lúc này: {e}")


# --- 2. HỆ THỐNG KHO HÀNG CHUẨN COOKIE STORE • STOCK (>stock, >setupstock, >createacc...) ---
@bot.command(name="setupstock", aliases=["ghimkho", "initstock"])
@commands.has_permissions(administrator=True)
async def cmd_setupstock(ctx: commands.Context, channel: discord.TextChannel = None):
    """
    Ghim bảng Kho Hàng tự động (Real-time Auto-Update) chuẩn Cookie Store • STOCK.
    Cú pháp: >setupstock [#kênh]
    Bảng này sẽ tự động cập nhật tức thì mỗi khi có thêm hàng, bán hàng, giữ chỗ!
    """
    target_ch = channel or ctx.channel
    embed = render_stock_embed(ctx.guild)
    msg = await target_ch.send(embed=embed, view=StockControlView())

    with get_db() as conn:
        conn.execute(
            "UPDATE store_settings SET stock_channel_id = ?, stock_message_id = ? WHERE guild_id = ?",
            (target_ch.id, msg.id, ctx.guild.id),
        )
        conn.commit()

    await ctx.reply(
        f"✅ Đã ghim bảng **Kho Hàng Tồn (STOCK)** tại {target_ch.mention}! Bảng sẽ tự động đồng bộ thời gian thực mỗi khi cập nhật kho."
    )


@bot.command(name="setstore", aliases=["doitenstore"])
@commands.has_permissions(administrator=True)
async def cmd_setstore(ctx: commands.Context, store_name: str, *, store_author: str = "made by ngocngann"):
    """
    Cài đặt Tên Cửa Hàng và Chữ ký tác giả hiển thị trên Bảng Stock.
    Ví dụ: >setstore "Cookie Store" "made by ngocngann"
    """
    get_guild_settings(ctx.guild.id)
    with get_db() as conn:
        conn.execute(
            "UPDATE store_settings SET store_name = ?, store_author = ? WHERE guild_id = ?",
            (store_name.strip(), store_author.strip(), ctx.guild.id),
        )
        conn.commit()

    await refresh_persistent_stock_panel(ctx.guild)
    await ctx.reply(
        f"✅ Đã cập nhật thông tin Store:\n"
        f"┃ ➡️ **Tên Store:** `{store_name.strip()}`\n"
        f"┃ ➡️ **Chữ ký Footer:** `{store_author.strip()}`\n"
        f"💡 Bảng `>stock` đã được cập nhật giao diện mới!"
    )


@bot.command(name="stock", aliases=["kho", "tonkho"])
async def cmd_stock(ctx: commands.Context):
    """Hiển thị bảng kho hàng sản phẩm có sẵn kèm nút mua nhanh và VietQR chuẩn Cookie Store."""
    embed = render_stock_embed(ctx.guild)
    await ctx.send(embed=embed, view=StockControlView())


@bot.command(name="createacc", aliases=["taokenhacc", "newacc"])
@commands.has_permissions(manage_messages=True)
async def cmd_createacc(ctx: commands.Context, category: str, price_str: str, *, channel_name: str):
    """
    Tự động tạo kênh Discord thật sự cho Account và đưa vào bảng Stock.
    Cú pháp: >createacc <danh_mục> <giá> <tên_kênh>
    Ví dụ: >createacc "RÈ SỐC ACC MC" 0 ✅-cape-hero
           >createacc "RÈ SỐC ACC MC" 165k acc-mc-fullmail
    """
    try:
        price = parse_smart_amount(price_str)
    except ValueError:
        return await ctx.reply("❌ Định dạng giá không hợp lệ! Ví dụ: `165k`, `0`, `50000`...")

    clean_ch_name = re.sub(r"[\s#@:/\\]+", "-", channel_name.strip()).strip("-")[:50].lower()
    if not clean_ch_name:
        clean_ch_name = f"acc-{random.randint(100, 999)}"

    guild = ctx.guild
    cat_obj = discord.utils.find(lambda c: "kho" in c.name.lower() or "stock" in c.name.lower() or "store" in c.name.lower(), guild.categories)
    if not cat_obj:
        try:
            cat_obj = await guild.create_category(name="📦 KHO HÀNG ACC")
        except Exception:
            cat_obj = None

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
    }

    try:
        new_ch = await guild.create_text_channel(
            name=clean_ch_name,
            category=cat_obj,
            overwrites=overwrites,
            topic=f"Mặt hàng {clean_ch_name} | Danh mục: {category.upper()} | Giá: {format_vnd(price)}",
        )
    except Exception as e:
        return await ctx.reply(f"❌ Không thể tạo kênh Discord mới: {e}")

    info_embed = discord.Embed(
        title=f"📦 THÔNG TIN TÀI KHOẢN: #{clean_ch_name}",
        description=(
            f"┃ ➡️ **Danh mục:** 🎮 `{category.upper()}`\n"
            f"┃ ➡️ **Đơn giá:** 💎 **`{format_vnd(price)}`**\n"
            f"┃ ➡️ **Chính sách:** ✅ Bảo hành 1 đổi 1 Full thời gian\n"
            f"┃ ➡️ **Trạng thái:** ✨ *Sẵn sàng giao dịch*\n\n"
            f"👉 Quý khách muốn mua hãy gõ `>createticket` hoặc bấm **`[🛒 Mua Ngay]`** tại bảng Stock!"
        ),
        color=0x57F287,
        timestamp=datetime.now(VN_TZ),
    )
    info_embed.set_footer(text="Hệ thống Store tự động • Cookie Store Style")
    await new_ch.send(embed=info_embed)

    now_str = datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y")
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO store_stocks (guild_id, category, price, item_name, item_channel, channel_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'available', ?)
            """,
            (guild.id, category.strip(), price, clean_ch_name, clean_ch_name, new_ch.id, now_str),
        )
        conn.commit()

    await refresh_persistent_stock_panel(guild)
    await ctx.reply(
        f"✨ Đã tạo thành công kênh {new_ch.mention} và thêm vào danh mục **{category.upper()}** với giá **{format_vnd(price)}**!"
    )


@bot.command(name="addstock", aliases=["themhang"])
@commands.has_permissions(manage_messages=True)
async def cmd_addstock(ctx: commands.Context, category: str, price_str: str, *, item_or_channel: str):
    """
    Thêm tài khoản / kênh vào kho hàng Store.
    Cú pháp: >addstock <danh_mục> <giá> <#kênh hoặc tên>
    Ví dụ: >addstock "RÈ SỐC ACC MC" 0 #✅-cape-hero
           >addstock "RÈ SỐC ACC MC" 165k acc-mc-fullmail
    """
    try:
        price = parse_smart_amount(price_str)
    except ValueError:
        return await ctx.reply("❌ Định dạng giá không hợp lệ! Ví dụ: `165k`, `0`, `50000`...")

    val = item_or_channel.strip()
    guild = ctx.guild
    ch_obj = None

    if ctx.message.channel_mentions:
        ch_obj = ctx.message.channel_mentions[0]
    else:
        m_id = re.search(r"<#(\d+)>", val)
        if m_id:
            ch_obj = guild.get_channel(int(m_id.group(1)))
        elif val.isdigit():
            ch_obj = guild.get_channel(int(val))
        else:
            clean_name = val.replace("#", "").strip().lower()
            ch_obj = discord.utils.get(guild.text_channels, name=clean_name)

    ch_id = ch_obj.id if ch_obj else 0
    ch_name = ch_obj.name if ch_obj else val
    now_str = datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y")

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO store_stocks (guild_id, category, price, item_name, item_channel, channel_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'available', ?)
            """,
            (guild.id, category.strip(), price, ch_name, ch_name, ch_id, now_str),
        )
        conn.commit()

    await refresh_persistent_stock_panel(guild)
    target_display = ch_obj.mention if ch_obj else f"`#{ch_name}`"
    embed = discord.Embed(
        title="📦 ĐÃ THÊM HÀNG VÀO KHO THÀNH CÔNG",
        description=(
            f"┃ ➡️ **Danh mục:** 🎮 `{category.strip().upper()}`\n"
            f"┃ ➡️ **Sản phẩm / Kênh:** {target_display}\n"
            f"┃ ➡️ **Giá bán:** 💎 **`{format_vnd(price)}`**\n"
            f"┃ ➡️ **Trạng thái:** ✅ *Sẵn sàng bán*\n\n"
            f"💡 Bảng `>stock` đã được cập nhật tự động!"
        ),
        color=COLOR_SUCCESS,
    )
    await ctx.reply(embed=embed)


@bot.command(name="syncstock", aliases=["dongbokho"])
@commands.has_permissions(manage_messages=True)
async def cmd_syncstock(ctx: commands.Context, category_name: str, price_str: str = "165k"):
    """
    Tự động quét tất cả các kênh trong một Category và thêm vào kho hàng.
    Cú pháp: >syncstock <tên_category> [đơn_giá]
    Ví dụ: >syncstock "KHO ACC MC" 165k
    """
    try:
        price = parse_smart_amount(price_str)
    except ValueError:
        price = 165000

    guild = ctx.guild
    cat_obj = discord.utils.find(lambda c: category_name.lower() in c.name.lower(), guild.categories)
    if not cat_obj:
        return await ctx.reply(f"❌ Không tìm thấy Category nào có tên chứa `{category_name}`!")

    added = 0
    now_str = datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y")
    with get_db() as conn:
        for ch in cat_obj.text_channels:
            exists = conn.execute("SELECT id FROM store_stocks WHERE guild_id = ? AND channel_id = ?", (guild.id, ch.id)).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO store_stocks (guild_id, category, price, item_name, item_channel, channel_id, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'available', ?)
                    """,
                    (guild.id, cat_obj.name.upper(), price, ch.name, ch.name, ch.id, now_str),
                )
                added += 1
        conn.commit()

    await refresh_persistent_stock_panel(guild)
    await ctx.reply(
        f"✅ Đã đồng bộ thành công **{added} kênh** từ Category **{cat_obj.name}** vào bảng Stock!"
    )


@bot.command(name="hold", aliases=["giucho"])
@commands.has_permissions(manage_messages=True)
async def cmd_hold(ctx: commands.Context, target: str, minutes: int = 15):
    """
    Giữ chỗ một tài khoản / kênh trong kho cho khách chuẩn bị chuyển khoản.
    Cú pháp: >hold <#kênh hoặc tên> [số_phút]
    Ví dụ: >hold #✅-cape-hero 15
    """
    mins = max(5, min(minutes, 60))
    guild = ctx.guild
    ch_id = 0

    if ctx.message.channel_mentions:
        ch_id = ctx.message.channel_mentions[0].id
    else:
        m_id = re.search(r"<#(\d+)>", target)
        if m_id:
            ch_id = int(m_id.group(1))
        elif target.isdigit():
            ch_id = int(target)
        else:
            clean = target.replace("#", "").strip().lower()
            ch = discord.utils.get(guild.text_channels, name=clean)
            if ch:
                ch_id = ch.id

    now_ts = int(time.time())
    until_ts = now_ts + (mins * 60)

    with get_db() as conn:
        if ch_id:
            row = conn.execute(
                "SELECT * FROM store_stocks WHERE guild_id = ? AND channel_id = ?",
                (guild.id, ch_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM store_stocks WHERE guild_id = ? AND (item_name LIKE ? OR item_channel LIKE ?)",
                (guild.id, f"%{target}%", f"%{target}%"),
            ).fetchone()

        if not row:
            return await ctx.reply("❌ Không tìm thấy món hàng nào khớp với yêu cầu trong kho!")

        conn.execute(
            "UPDATE store_stocks SET status = 'holding', hold_until = ?, holder_id = ? WHERE id = ?",
            (until_ts, ctx.author.id, row["id"]),
        )
        conn.commit()

    target_ch = guild.get_channel(row["channel_id"]) if row["channel_id"] else None
    if target_ch and not target_ch.name.startswith("⏳-"):
        try:
            await target_ch.edit(name=f"⏳-{target_ch.name.replace('✅-', '')}")
        except Exception:
            pass

    await refresh_persistent_stock_panel(guild)
    await ctx.reply(
        f"⏳ Đã đặt giữ chỗ **{target_ch.mention if target_ch else f'#{row['item_name']}'}** trong vòng **{mins} phút**!"
    )


@bot.command(name="unhold", aliases=["huygiucho"])
@commands.has_permissions(manage_messages=True)
async def cmd_unhold(ctx: commands.Context, *, target: str):
    """Hủy giữ chỗ và trả lại tài khoản về trạng thái sẵn sàng bán."""
    guild = ctx.guild
    ch_id = 0
    if ctx.message.channel_mentions:
        ch_id = ctx.message.channel_mentions[0].id
    else:
        m_id = re.search(r"<#(\d+)>", target)
        if m_id:
            ch_id = int(m_id.group(1))

    with get_db() as conn:
        if ch_id:
            row = conn.execute("SELECT * FROM store_stocks WHERE guild_id = ? AND channel_id = ?", (guild.id, ch_id)).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM store_stocks WHERE guild_id = ? AND (item_name LIKE ? OR item_channel LIKE ?)",
                (guild.id, f"%{target}%", f"%{target}%"),
            ).fetchone()

        if not row:
            return await ctx.reply("❌ Không tìm thấy món hàng này trong kho!")

        conn.execute("UPDATE store_stocks SET status = 'available', hold_until = 0, holder_id = 0 WHERE id = ?", (row["id"],))
        conn.commit()

    target_ch = guild.get_channel(row["channel_id"]) if row["channel_id"] else None
    if target_ch and target_ch.name.startswith("⏳-"):
        try:
            await target_ch.edit(name=target_ch.name.replace("⏳-", ""))
        except Exception:
            pass

    await refresh_persistent_stock_panel(guild)
    await ctx.reply(f"✅ Đã hủy giữ chỗ và trả **{target_ch.mention if target_ch else f'#{row['item_name']}'}** về kho hàng!")


@bot.command(name="sellstock", aliases=["daban", "chotkho"])
@commands.has_permissions(manage_messages=True)
async def cmd_sellstock(ctx: commands.Context, target: str, customer: discord.Member, amount_str: str = None):
    """
    Bán một món hàng trong kho: chốt đơn, cộng doanh thu và gỡ khỏi bảng Stock.
    Cú pháp: >sellstock <#kênh hoặc tên> @khách [tiền]
    """
    guild = ctx.guild
    ch_id = 0
    if ctx.message.channel_mentions:
        for ch in ctx.message.channel_mentions:
            if ch.id != ctx.channel.id or len(ctx.message.channel_mentions) == 1:
                ch_id = ch.id
                break

    with get_db() as conn:
        if ch_id:
            row = conn.execute("SELECT * FROM store_stocks WHERE guild_id = ? AND channel_id = ?", (guild.id, ch_id)).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM store_stocks WHERE guild_id = ? AND (item_name LIKE ? OR item_channel LIKE ?)",
                (guild.id, f"%{target}%", f"%{target}%"),
            ).fetchone()

        if not row:
            return await ctx.reply("❌ Không tìm thấy mặt hàng này trong kho!")

        price = parse_smart_amount(amount_str) if amount_str else row["price"]
        conn.execute("DELETE FROM store_stocks WHERE id = ?", (row["id"],))

        now = datetime.now(VN_TZ)
        conn.execute(
            """
            INSERT INTO store_revenues (guild_id, staff_id, customer_id, amount, note, timestamp, day_str, month_str)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                guild.id,
                ctx.author.id,
                customer.id,
                price,
                f"Bán kho: {row['item_name']}",
                now.isoformat(),
                now.strftime("%Y-%m-%d"),
                now.strftime("%Y-%m"),
            ),
        )
        conn.commit()

    target_ch = guild.get_channel(row["channel_id"]) if row["channel_id"] else None
    if target_ch:
        try:
            clean_name = target_ch.name.replace("⏳-", "").replace("✅-", "")
            await target_ch.edit(name=f"done-{clean_name}")
        except Exception:
            pass

    await refresh_persistent_stock_panel(guild)
    embed = discord.Embed(
        title="🎉 CHỐT ĐƠN HÀNG KHO THÀNH CÔNG! 🎉",
        description=(
            f"┃ ➡️ **Sản phẩm:** `{row['item_name']}` ({row['category']})\n"
            f"┃ ➡️ **Khách hàng:** {customer.mention}\n"
            f"┃ ➡️ **Nhân viên:** {ctx.author.mention}\n"
            f"┃ ➡️ **Doanh thu:** 💎 **`{format_vnd(price)}`**\n\n"
            f"✨ Mặt hàng đã được gỡ khỏi bảng Stock và cập nhật vào doanh thu tháng!"
        ),
        color=COLOR_SUCCESS,
        timestamp=now,
    )
    await ctx.send(embed=embed)


@bot.command(name="importstock", aliases=["nhaphang"])
@commands.has_permissions(manage_messages=True)
async def cmd_importstock(ctx: commands.Context, category: str, price_str: str, *, items_text: str):
    """
    Nhập nhiều tài khoản / mặt hàng cùng lúc vào kho (mỗi dòng 1 món).
    Cú pháp: >importstock <danh_mục> <giá> <danh sách>
    """
    try:
        price = parse_smart_amount(price_str)
    except ValueError:
        return await ctx.reply("❌ Định dạng giá không hợp lệ! Ví dụ: `165k`, `0`...")

    lines = [line.strip() for line in items_text.strip().splitlines() if line.strip()]
    if not lines:
        return await ctx.reply("❌ Vui lòng nhập ít nhất 1 dòng mặt hàng!")

    now_str = datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y")
    with get_db() as conn:
        for itm in lines:
            conn.execute(
                """
                INSERT INTO store_stocks (guild_id, category, price, item_name, item_channel, channel_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, 0, 'available', ?)
                """,
                (ctx.guild.id, category.strip(), price, itm, itm, now_str),
            )
        conn.commit()

    await refresh_persistent_stock_panel(ctx.guild)
    embed = discord.Embed(
        title="📦 NHẬP HÀNG HÀNG LOẠT THÀNH CÔNG",
        description=(
            f"┃ ➡️ **Danh mục:** 🎮 `{category.strip().upper()}`\n"
            f"┃ ➡️ **Số lượng nhập:** 💎 **`{len(lines)} acc/món`**\n"
            f"┃ ➡️ **Đơn giá mỗi món:** `{format_vnd(price)}`\n\n"
            f"💡 Bảng `>stock` đã được cập nhật tự động!"
        ),
        color=COLOR_SUCCESS,
    )
    await ctx.reply(embed=embed)


@bot.command(name="delstock", aliases=["xoahang"])
@commands.has_permissions(manage_messages=True)
async def cmd_delstock(ctx: commands.Context, *, item_or_id: str):
    """Xóa một món hàng khỏi kho theo ID hoặc tên sản phẩm."""
    with get_db() as conn:
        if item_or_id.isdigit():
            cur = conn.execute("DELETE FROM store_stocks WHERE guild_id = ? AND id = ?", (ctx.guild.id, int(item_or_id)))
        else:
            cur = conn.execute(
                "DELETE FROM store_stocks WHERE guild_id = ? AND (item_name LIKE ? OR item_channel LIKE ?)",
                (ctx.guild.id, f"%{item_or_id.strip()}%", f"%{item_or_id.strip()}%"),
            )
        conn.commit()
        cnt = cur.rowcount

    await refresh_persistent_stock_panel(ctx.guild)
    if cnt > 0:
        await ctx.reply(f"✅ Đã xóa **{cnt}** mặt hàng khớp với `{item_or_id}` khỏi kho!")
    else:
        await ctx.reply(f"⚠️ Không tìm thấy mặt hàng nào khớp với `{item_or_id}` trong kho.")


@bot.command(name="clearstock")
@commands.has_permissions(administrator=True)
async def cmd_clearstock(ctx: commands.Context, *, category: str = None):
    """Xóa toàn bộ kho hàng hoặc xóa theo danh mục (Admin)."""
    with get_db() as conn:
        if category:
            cur = conn.execute("DELETE FROM store_stocks WHERE guild_id = ? AND category LIKE ?", (ctx.guild.id, f"%{category.strip()}%"))
        else:
            cur = conn.execute("DELETE FROM store_stocks WHERE guild_id = ?", (ctx.guild.id,))
        conn.commit()
        cnt = cur.rowcount

    await refresh_persistent_stock_panel(ctx.guild)
    await ctx.reply(f"🗑️ Đã làm sạch **{cnt}** mặt hàng trong kho!")


# --- 3. HỆ THỐNG GIVEAWAY TỰ ĐỘNG (>gstart, >gend, >greroll) ---
def parse_time_duration(t_str: str) -> int:
    """Chuyển đổi chuỗi thời gian như 30s, 10m, 2h, 1d sang số giây."""
    m = re.match(r"^(\d+)([smhd])$", t_str.lower().strip())
    if not m:
        raise ValueError("Invalid duration format")
    val, unit = int(m.group(1)), m.group(2)
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return val * mult[unit]


@bot.command(name="gstart", aliases=["giveaway"])
@commands.has_permissions(manage_messages=True)
async def cmd_gstart(ctx: commands.Context, duration_str: str, winners_count: int, *, prize: str):
    """
    Tổ chức Giveaway phát quà / phát acc tự động.
    Cú pháp: >gstart <thời_gian> <số_giải> <phần_thưởng>
    Ví dụ: >gstart 10m 1 Acc Minecraft Full Mail
           >gstart 1h 2 Nitro Boost 1 Tháng
    """
    try:
        dur_sec = parse_time_duration(duration_str)
    except ValueError:
        return await ctx.reply("❌ Định dạng thời gian không hợp lệ! Dùng: `30s`, `10m`, `2h`, `1d`...")

    if winners_count <= 0 or winners_count > 50:
        return await ctx.reply("❌ Số người thắng phải từ 1 đến 50!")

    now_ts = int(time.time())
    end_ts = now_ts + dur_sec

    embed = discord.Embed(
        title="🎉 SỰ KIỆN PHÁT QUÀ (GIVEAWAY) 🎉",
        description=(
            f"┃ ➡️ **Phần thưởng:** 🎁 **{prize}**\n"
            f"┃ ➡️ **Số giải thưởng:** 🏆 `{winners_count} người`\n"
            f"┃ ➡️ **Tổ chức bởi:** {ctx.author.mention}\n"
            f"┃ ➡️ **Kết thúc lúc:** <t:{end_ts}:R> (<t:{end_ts}:f>)\n"
            f"• **Số người tham gia:** `0`\n\n"
            f"👉 *Bấm vào nút **`[🎉 Tham Gia]`** bên dưới để nhận cơ hội trúng giải!*"
        ),
        color=COLOR_PRIMARY,
        timestamp=datetime.now(VN_TZ),
    )
    embed.set_footer(text="Hệ thống Giveaway tự động • Store")

    msg = await ctx.send(embed=embed, view=GiveawayView())

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO giveaways (message_id, guild_id, channel_id, prize, winners_count, end_time, is_ended, host_id)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (msg.id, ctx.guild.id, ctx.channel.id, prize, winners_count, end_ts, ctx.author.id),
        )
        conn.commit()


@bot.command(name="gend")
@commands.has_permissions(manage_messages=True)
async def cmd_gend(ctx: commands.Context, message_id: int):
    """Kết thúc sớm một Giveaway đang diễn ra."""
    with get_db() as conn:
        gw = conn.execute("SELECT * FROM giveaways WHERE message_id = ?", (message_id,)).fetchone()
    if not gw:
        return await ctx.reply("❌ Không tìm thấy Giveaway với Message ID này!")
    if gw["is_ended"]:
        return await ctx.reply("⚠️ Giveaway này đã kết thúc trước đó rồi.")

    await finish_giveaway(message_id)
    await ctx.reply(f"✅ Đã kết thúc sớm Giveaway `{message_id}`!")


@bot.command(name="greroll")
@commands.has_permissions(manage_messages=True)
async def cmd_greroll(ctx: commands.Context, message_id: int):
    """Quay lại người thắng khác cho một Giveaway đã kết thúc."""
    with get_db() as conn:
        gw = conn.execute("SELECT * FROM giveaways WHERE message_id = ?", (message_id,)).fetchone()
        entries = conn.execute("SELECT user_id FROM giveaway_entries WHERE message_id = ?", (message_id,)).fetchall()

    if not gw:
        return await ctx.reply("❌ Không tìm thấy Giveaway này!")
    if not entries:
        return await ctx.reply("⚠️ Giveaway này không có ai tham gia để quay lại.")

    candidate_ids = [r["user_id"] for r in entries]
    winner_id = random.choice(candidate_ids)

    embed = discord.Embed(
        title="🎊 QUAY LẠI NGƯỜI CHIẾN THẮNG (REROLL) 🎊",
        description=(
            f"┃ ➡️ **Phần thưởng:** 🎁 **{gw['prize']}**\n"
            f"┃ ➡️ **Người trúng giải mới:** <@{winner_id}>\n\n"
            f"✨ Chúc mừng <@{winner_id}>! Hãy tạo Ticket để nhận giải nhé!"
        ),
        color=COLOR_GOLD,
    )
    await ctx.send(content=f"🔔 Reroll chúc mừng <@{winner_id}>!", embed=embed)


# --- 4. HỆ THỐNG VÍ XU & MINI-GAME STORE (>daily, >bal, >taixiu, >flip, >pay) ---
@bot.command(name="daily", aliases=["diemdanh"])
async def cmd_daily(ctx: commands.Context):
    """Điểm danh mỗi ngày nhận Xu mua sắm và chơi mini-game."""
    today_str = datetime.now(VN_TZ).strftime("%Y-%m-%d")
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM user_economy WHERE user_id = ? AND guild_id = ?",
            (ctx.author.id, ctx.guild.id),
        ).fetchone()

        if row and row["last_daily"] == today_str:
            return await ctx.reply("⏰ Hôm nay bạn đã nhận thưởng điểm danh rồi! Hãy quay lại vào ngày mai nhé.")

        reward = random.randint(10000, 50000)
        get_user_balance(ctx.guild.id, ctx.author.id)
        conn.execute(
            """
            UPDATE user_economy
            SET balance = balance + ?, last_daily = ?
            WHERE user_id = ? AND guild_id = ?
            """,
            (reward, today_str, ctx.author.id, ctx.guild.id),
        )
        conn.commit()
        new_bal = get_user_balance(ctx.guild.id, ctx.author.id)

    embed = discord.Embed(
        title="🎁 ĐIỂM DANH HÀNG NGÀY THÀNH CÔNG",
        description=(
            f"┃ ➡️ **Phần thưởng nhận được:** 💎 **`+{format_vnd(reward)}`**\n"
            f"┃ ➡️ **Số dư hiện tại:** 🪙 **`{format_vnd(new_bal)}`**\n\n"
            f"✨ Chúc bạn một ngày mua sắm vui vẻ tại Store!"
        ),
        color=COLOR_GOLD,
    )
    await ctx.reply(embed=embed)


@bot.command(name="bal", aliases=["balance", "vi", "tien", "coins"])
async def cmd_bal(ctx: commands.Context, member: discord.Member = None):
    """Kiểm tra số dư ví Xu của bạn hoặc người khác."""
    target = member or ctx.author
    bal = get_user_balance(ctx.guild.id, target.id)

    embed = discord.Embed(
        title=f"🪙 VÍ TIỀN XU CỦA {target.display_name.upper()}",
        description=(
            f"┃ ➡️ **Chủ tài khoản:** {target.mention}\n"
            f"┃ ➡️ **Số dư khả dụng:** 💎 **`{format_vnd(bal)}`**\n\n"
            f"💡 Dùng lệnh `>daily` điểm danh mỗi ngày hoặc chơi `>taixiu`, `>flip`!"
        ),
        color=COLOR_GOLD,
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.reply(embed=embed)


@bot.command(name="taixiu", aliases=["tx"])
async def cmd_taixiu(ctx: commands.Context, choice: str, bet_str: str):
    """
    Chơi mini-game Tài Xỉu 3 xúc xắc.
    Cú pháp: >taixiu <tai/xiu> <tiền_cược>
    Ví dụ: >taixiu tai 10k
           >taixiu xiu 50000
    """
    choice_clean = choice.lower().strip()
    if choice_clean not in ["tai", "tài", "t", "xiu", "xỉu", "x"]:
        return await ctx.reply("❌ Lựa chọn không hợp lệ! Vui lòng chọn `tai` hoặc `xiu`.")
    is_tai = choice_clean in ["tai", "tài", "t"]

    try:
        bet = parse_smart_amount(bet_str)
    except ValueError:
        return await ctx.reply("❌ Định dạng số tiền cược không hợp lệ! Ví dụ: `10k`, `50k`...")

    if bet < 1000:
        return await ctx.reply("❌ Tiền cược tối thiểu là 1,000đ!")

    cur_bal = get_user_balance(ctx.guild.id, ctx.author.id)
    if cur_bal < bet:
        return await ctx.reply(f"❌ Bạn không đủ Xu! Số dư hiện tại: **`{format_vnd(cur_bal)}`**")

    # Lắc 3 xúc xắc
    d1, d2, d3 = random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)
    total = d1 + d2 + d3
    dice_str = f"`[{d1}]` `[{d2}]` `[{d3}]`"
    win = False

    # 3-10: Xỉu, 11-18: Tài (Bộ ba đồng nhất 111 hoặc 666 là nhà cái thắng)
    if d1 == d2 == d3:
        result_name = f"BỘ BA ĐỒNG NHẤT ({total})"
        win = False
    elif total >= 11:
        result_name = f"TÀI ({total})"
        win = is_tai
    else:
        result_name = f"XỈU ({total})"
        win = not is_tai

    if win:
        update_user_balance(ctx.guild.id, ctx.author.id, bet)
        res_color = COLOR_SUCCESS
        res_title = "🎉 BẠN ĐÃ THẮNG CƯỢC TÀI XỈU! 🎉"
        diff_str = f"➕ **`+{format_vnd(bet)}`**"
    else:
        update_user_balance(ctx.guild.id, ctx.author.id, -bet)
        res_color = COLOR_DANGER
        res_title = "💸 BẠN ĐÃ THUA CƯỢC TÀI XỈU!"
        diff_str = f"➖ **`-{format_vnd(bet)}`**"

    new_bal = get_user_balance(ctx.guild.id, ctx.author.id)
    embed = discord.Embed(
        title=res_title,
        description=(
            f"🎲 **Xúc xắc:** {dice_str} ➔ **{result_name}**\n"
            f"┃ ➡️ **Bạn chọn:** `{'TÀI' if is_tai else 'XỈU'}` | **Cược:** `{format_vnd(bet)}`\n"
            f"┃ ➡️ **Kết quả:** {diff_str}\n"
            f"┃ ➡️ **Số dư mới:** 💎 **`{format_vnd(new_bal)}`**"
        ),
        color=res_color,
    )
    await ctx.reply(embed=embed)


@bot.command(name="flip", aliases=["tungxu", "cf"])
async def cmd_flip(ctx: commands.Context, choice: str, bet_str: str):
    """
    Mini-game Tung Đồng Xu (Sấp / Ngửa).
    Cú pháp: >flip <ngua/sap> <tiền_cược>
    """
    c = choice.lower().strip()
    if c not in ["ngua", "ngửa", "n", "sap", "sấp", "s"]:
        return await ctx.reply("❌ Vui lòng chọn `ngua` hoặc `sap`!")
    pick_ngua = c in ["ngua", "ngửa", "n"]

    try:
        bet = parse_smart_amount(bet_str)
    except ValueError:
        return await ctx.reply("❌ Định dạng số tiền không hợp lệ! Ví dụ: `10k`, `20000`...")

    if bet < 1000:
        return await ctx.reply("❌ Tiền cược tối thiểu là 1,000đ!")

    bal = get_user_balance(ctx.guild.id, ctx.author.id)
    if bal < bet:
        return await ctx.reply(f"❌ Bạn không đủ Xu! Số dư: **`{format_vnd(bal)}`**")

    outcome_ngua = random.choice([True, False])
    outcome_str = "NGỬA 🟡" if outcome_ngua else "SẤP ⚪"
    win = (pick_ngua == outcome_ngua)

    if win:
        update_user_balance(ctx.guild.id, ctx.author.id, bet)
        res_color = COLOR_SUCCESS
        res_text = f"🎉 **Chiến thắng!** Nhận được: `+{format_vnd(bet)}`"
    else:
        update_user_balance(ctx.guild.id, ctx.author.id, -bet)
        res_color = COLOR_DANGER
        res_text = f"💸 **Thua cuộc!** Mất: `-{format_vnd(bet)}`"

    new_bal = get_user_balance(ctx.guild.id, ctx.author.id)
    embed = discord.Embed(
        title="🪙 KẾT QUẢ TUNG ĐỒNG XU 🪙",
        description=(
            f"Đồng xu quay và dừng lại ở: **{outcome_str}**\n\n"
            f"{res_text}\n"
            f"┃ ➡️ **Số dư hiện tại:** 💎 **`{format_vnd(new_bal)}`**"
        ),
        color=res_color,
    )
    await ctx.reply(embed=embed)


@bot.command(name="pay", aliases=["chuyentien"])
async def cmd_pay(ctx: commands.Context, receiver: discord.Member, amount_str: str):
    """Chuyển Xu cho thành viên khác trong Server."""
    if receiver.id == ctx.author.id:
        return await ctx.reply("❌ Bạn không thể tự chuyển Xu cho chính mình!")
    if receiver.bot:
        return await ctx.reply("❌ Không thể chuyển Xu cho Bot!")

    try:
        amount = parse_smart_amount(amount_str)
    except ValueError:
        return await ctx.reply("❌ Số tiền không hợp lệ!")

    if amount < 1000:
        return await ctx.reply("❌ Số tiền chuyển tối thiểu là 1,000đ!")

    bal = get_user_balance(ctx.guild.id, ctx.author.id)
    if bal < amount:
        return await ctx.reply(f"❌ Bạn không đủ Xu để chuyển! Số dư: `{format_vnd(bal)}`")

    update_user_balance(ctx.guild.id, ctx.author.id, -amount)
    update_user_balance(ctx.guild.id, receiver.id, amount)

    embed = discord.Embed(
        title="💸 CHUYỂN TIỀN THÀNH CÔNG",
        description=(
            f"┃ ➡️ **Người chuyển:** {ctx.author.mention}\n"
            f"┃ ➡️ **Người nhận:** {receiver.mention}\n"
            f"┃ ➡️ **Số tiền chuyển:** 💎 **`{format_vnd(amount)}`**\n"
            f"┃ ➡️ **Số dư còn lại:** `{format_vnd(bal - amount)}`"
        ),
        color=COLOR_SUCCESS,
        timestamp=datetime.now(VN_TZ),
    )
    await ctx.send(embed=embed)


@bot.command(name="congtien")
@commands.has_permissions(administrator=True)
async def cmd_congtien(ctx: commands.Context, member: discord.Member, amount_str: str):
    """Cộng hoặc trừ Xu cho thành viên (Chỉ Admin)."""
    try:
        amount = parse_smart_amount(amount_str)
    except ValueError:
        return await ctx.reply("❌ Định dạng số tiền không hợp lệ!")

    update_user_balance(ctx.guild.id, member.id, amount)
    new_bal = get_user_balance(ctx.guild.id, member.id)
    await ctx.reply(f"✅ Đã cộng/trừ **{format_vnd(amount)}** cho {member.mention}. Số dư mới: **`{format_vnd(new_bal)}`**")


# --- 5. HỒ SƠ KHÁCH HÀNG VIP, THÔNG TIN SERVER & THÔNG BÁO ---
@bot.command(name="profile", aliases=["hoso", "me"])
async def cmd_profile(ctx: commands.Context, member: discord.Member = None):
    """Xem hồ sơ khách hàng VIP, tổng chi tiêu tại Store và số Xu."""
    target = member or ctx.author
    with get_db() as conn:
        spent_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as s, COUNT(*) as c FROM store_revenues WHERE guild_id = ? AND customer_id = ?",
            (ctx.guild.id, target.id),
        ).fetchone()

    coins = get_user_balance(ctx.guild.id, target.id)
    spent = spent_row["s"] if spent_row else 0
    orders = spent_row["c"] if spent_row else 0

    if spent >= 5000000:
        vip_rank = "💎 KIM CƯƠNG VIP"
    elif spent >= 1000000:
        vip_rank = "🥇 VÀNG VIP"
    elif spent >= 200000:
        vip_rank = "🥈 BẠC THÂN THIẾT"
    else:
        vip_rank = "🥉 THÀNH VIÊN MỚI"

    embed = discord.Embed(
        title=f"👑 THẺ HỒ SƠ KHÁCH HÀNG: {target.display_name.upper()}",
        description=(
            f"┃ ➡️ **Khách hàng:** {target.mention} (`{target.id}`)\n"
            f"┃ ➡️ **Hạng thành viên:** **{vip_rank}**\n"
            f"┃ ➡️ **Tổng tiền đã mua:** 💎 **`{format_vnd(spent)}`**\n"
            f"┃ ➡️ **Số đơn hàng đã chốt:** 📦 **`{orders} đơn`**\n"
            f"┃ ➡️ **Ví Xu Store:** 🪙 **`{format_vnd(coins)}`**\n"
            f"┃ ➡️ **Ngày tham gia:** `{target.joined_at.astimezone(VN_TZ).strftime('%d/%m/%Y') if target.joined_at else 'N/A'}`"
        ),
        color=COLOR_GOLD,
        timestamp=datetime.now(VN_TZ),
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.set_footer(text="Hệ thống Khách Hàng Thân Thiết Store")
    await ctx.reply(embed=embed)


@bot.command(name="serverinfo", aliases=["thongtinserver"])
async def cmd_serverinfo(ctx: commands.Context):
    """Xem tổng quan thông tin và trạng thái Server."""
    g = ctx.guild
    embed = discord.Embed(
        title=f"🏰 THÔNG TIN MÁY CHỦ: {g.name.upper()}",
        description=(
            f"┃ ➡️ **Chủ Server:** {g.owner.mention if g.owner else 'N/A'}\n"
            f"┃ ➡️ **ID Server:** `{g.id}`\n"
            f"┃ ➡️ **Tổng thành viên:** 👥 **`{g.member_count}`**\n"
            f"┃ ➡️ **Kênh văn bản & Thoại:** 💬 **`{len(g.text_channels)} text / {len(g.voice_channels)} voice`**\n"
            f"┃ ➡️ **Tổng số Role:** 🛡️ **`{len(g.roles)}`**\n"
            f"┃ ➡️ **Cấp độ Boost:** 🚀 **`Level {g.premium_tier}`** ({g.premium_subscription_count} Boosts)\n"
            f"┃ ➡️ **Ngày tạo Server:** `{g.created_at.astimezone(VN_TZ).strftime('%d/%m/%Y %H:%M')}`"
        ),
        color=COLOR_CYAN,
        timestamp=datetime.now(VN_TZ),
    )
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    await ctx.reply(embed=embed)


@bot.command(name="announce", aliases=["thongbao"])
@commands.has_permissions(administrator=True)
async def cmd_announce(ctx: commands.Context, channel: discord.TextChannel, *, content_text: str):
    """Đăng thông báo chính thức chuẩn giao diện Store vào kênh chỉ định."""
    embed = discord.Embed(
        title=f"📢 THÔNG BÁO TỪ BAN QUẢN TRỊ {ctx.guild.name.upper()}",
        description=content_text,
        color=COLOR_CYAN,
        timestamp=datetime.now(VN_TZ),
    )
    embed.set_footer(text=f"Đăng bởi {ctx.author.display_name} • Store Announcement", icon_url=ctx.author.display_avatar.url)
    await channel.send(embed=embed)
    await ctx.reply(f"✅ Đã gửi thông báo đến kênh {channel.mention} thành công!")


# --- 6. MENU TRỢ GIÚP TỔNG HỢP (>help) ---
@bot.command(name="help")
async def cmd_help(ctx: commands.Context):
    """Hiển thị toàn bộ danh sách lệnh của Bot Store."""
    embed = discord.Embed(
        title="✨ HỆ THỐNG LỆNH BOT STORE & QUẢN LÝ SERVER ✨",
        description="Tiền tố lệnh (Prefix): **`>`** | Hỗ trợ **Tính toán tự động** khi gõ phép tính trực tiếp vào chat!",
        color=COLOR_CYAN,
    )
    embed.add_field(
        name="🛒 1. Store, Bán Hàng & Quản Lý Kho Stock",
        value=(
            "`>stock` : Xem bảng tồn kho Cookie Store có sẵn\n"
            "`>setupstock [#kênh]` : Ghim bảng Stock tự động cập nhật 24/7\n"
            "`>createacc <dục> <giá> <kênh>` : Tự tạo kênh thật đưa vào kho\n"
            "`>addstock <dục> <giá> <#kênh>` : Thêm kênh hoặc acc vào kho\n"
            "`>syncstock <category> [giá]` : Đồng bộ cả Category vào kho\n"
            "`>hold <#kênh> [phút]` / `>unhold` : Đặt/hủy giữ chỗ acc\n"
            "`>sellstock <#kênh> @khách` : Chốt bán acc & gỡ khỏi kho\n"
            "`>setstore <tên> [tác_giả]` : Đổi tên Store & chữ ký footer\n"
            "`>importstock` / `>delstock` / `>clearstock` : Quản lý kho\n"
            "`>banggia` / `>qr` / `>done` / `>doanhthu` : Bán hàng & Doanh thu"
        ),
        inline=False,
    )
    embed.add_field(
        name="🪽 2. Ticket v2 & Đánh Giá Uy Tín (Legit)",
        value=(
            "`>rename <tên mới>` : Đổi tên kênh Ticket v2 (có emoji)\n"
            "`>createticket` : Mở bảng đăng ký thuê acc / mua dịch vụ\n"
            "`>setuplegit` : Ghim bảng menu đánh giá uy tín chống trôi\n"
            "`>setupnotify @role` : Tạo nút tự nhận thông báo Flash Sale\n"
            "`>checkscam <stk/id>` / `>addscam` : Tra cứu & thêm lừa đảo"
        ),
        inline=False,
    )
    embed.add_field(
        name="🎉 3. Giveaway & Quà Tặng Tự Động",
        value=(
            "`>gstart <tg> <số_giải> <quà>` : Tạo sự kiện Giveaway (VD: `>gstart 10m 1 Nitro`)\n"
            "`>gend <id>` : Kết thúc sớm Giveaway\n"
            "`>greroll <id>` : Quay lại người trúng thưởng mới"
        ),
        inline=False,
    )
    embed.add_field(
        name="🪙 4. Ví Xu & Mini-Game Giải Trí",
        value=(
            "`>daily` : Điểm danh hàng ngày nhận 10.000đ - 50.000đ Xu\n"
            "`>bal [@user]` : Kiểm tra số dư ví Xu\n"
            "`>taixiu <tai/xiu> <tiền>` : Chơi Tài Xỉu 3 xúc xắc\n"
            "`>flip <ngua/sap> <tiền>` : Tung đồng xu may mắn\n"
            "`>pay @user <tiền>` : Chuyển Xu cho thành viên khác\n"
            "`>profile [@user]` : Thẻ thành viên VIP & tổng chi tiêu"
        ),
        inline=False,
    )
    embed.add_field(
        name="🛡️ 5. Quản Lý Server & Tiện Ích",
        value=(
            "`>genkey` / `>redeem` : Hệ thống tạo & nhập Key VIP\n"
            "`>addrole` / `>removerole` / `>autorole`\n"
            "`>ban` / `>unban` / `>kick` / `>mute` / `>unmute`\n"
            "`>warn` / `>warnings` / `>clear` / `>lock` / `>unlock`\n"
            "`>steal <emoji...>` : Cướp nhiều Emoji cùng lúc (tối đa 25)\n"
            "`>serverinfo` / `>announce <#kênh> <nội dung>`\n"
            "`>banner` / `>bannergen <chữ>` / `>faq` / `>ask <Gemini AI>`"
        ),
        inline=False,
    )
    embed.set_footer(text="Bot hoạt động 24/7 • Thiết kế chuẩn UI/UX Store Discord")
@bot.event
async def on_command_error(ctx: commands.Context, error):
    """Xử lý lỗi lệnh tập trung, thông báo thân thiện cho người dùng."""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingPermissions):
        perms = ", ".join(error.missing_permissions)
        await ctx.reply(f"❌ Bạn không đủ quyền để dùng lệnh này! (Yêu cầu quyền: `{perms}`)")
    elif isinstance(error, commands.BotMissingPermissions):
        perms = ", ".join(error.missing_permissions)
        await ctx.reply(f"❌ Bot thiếu quyền thực thi trên Server! (Yêu cầu quyền: `{perms}`)")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(f"❌ Thiếu tham số bắt buộc `{error.param.name}`! Hãy xem `>help` để biết cú pháp chuẩn.")
    elif isinstance(error, commands.BadArgument):
        await ctx.reply(f"❌ Tham số truyền vào không hợp lệ: {error}")
    else:
        if ctx.command and ctx.command.has_error_handler():
            return
        print(f"⚠️ Lỗi lệnh [{ctx.command}]: {error}")


# =============================================================================
# XI. WEBSERVER KEEP-ALIVE 24/7 & CỔNG WEBHOOK NGÂN HÀNG (SEPAY / CASSO)
# =============================================================================
async def handle_health(request: web.Request):
    """Route trang chủ giúp UptimeRobot / Render / Railway giữ bot sống 24/7."""
    return web.Response(
        text="✅ Discord Store Bot is running 24/7! Webhook endpoint: POST /webhook/bank",
        status=200,
    )


async def handle_bank_webhook(request: web.Request):
    """
    Cổng nhận Webhook tự động từ SePay hoặc Casso khi khách quét mã VietQR.
    Tự động tìm kênh Ticket khớp với mã `TICKETxxxx` trong nội dung chuyển khoản và báo ting ting!
    """
    if WEBHOOK_SECRET:
        auth_header = request.headers.get("Authorization", "")
        if WEBHOOK_SECRET not in auth_header:
            return web.json_response({"success": False, "error": "Unauthorized"}, status=401)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)

    # Tương thích cấu trúc JSON của cả SePay (transferAmount, content) và Casso (data list)
    transactions = []
    if "transferAmount" in data:
        transactions.append(
            {"amount": int(data.get("transferAmount", 0)), "content": str(data.get("content", ""))}
        )
    elif isinstance(data.get("data"), list):
        for item in data["data"]:
            transactions.append(
                {"amount": int(item.get("amount", 0)), "content": str(item.get("description", ""))}
            )

    for tx in transactions:
        amt = tx["amount"]
        desc = tx["content"]
        if amt <= 0:
            continue

        # Tìm mã TICKETxxxx trong nội dung chuyển khoản
        m = re.search(r"TICKET\s*(\d{4})", desc.upper())
        target_code = m.group(1) if m else None

        for guild in bot.guilds:
            for ch in guild.text_channels:
                if target_code and ch.name.endswith(f"-{target_code}"):
                    embed = discord.Embed(
                        title="✅ THANH TOÁN THÀNH CÔNG (AUTO CHECK BILL)",
                        description=(
                            f"**✅ Đã nhận được {format_vnd(amt)}! Nhân viên sẽ bàn giao acc ngay cho bạn.**\n\n"
                            f"```text\n"
                            f"Số tiền nhận : {format_vnd(amt)}\n"
                            f"Nội dung CK  : {desc}\n"
                            f"Thời gian    : {datetime.now(VN_TZ).strftime('%H:%M:%S %d/%m/%Y')}\n"
                            f"```"
                        ),
                        color=COLOR_SUCCESS,
                    )
                    try:
                        await ch.send(embed=embed)
                    except Exception:
                        pass

    return web.json_response({"success": True})


async def start_webserver():
    """Khởi chạy aiohttp Web Server ngầm cùng Event Loop của Bot."""
    try:
        app = web.Application()
        app.router.add_get("/", handle_health)
        app.router.add_post("/webhook/bank", handle_bank_webhook)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        print(f"🌐 Keep-Alive & Bank Webhook Server đang lắng nghe tại cổng {PORT}")
    except Exception as e:
        print(f"⚠️ Không thể khởi chạy Web Server tại cổng {PORT}: {e}")


# =============================================================================
# XII. KHỞI CHẠY CHƯƠNG TRÌNH
# =============================================================================
if __name__ == "__main__":
    init_db()
    if not TOKEN or TOKEN == "THAY_TOKEN_BOT_CUA_BAN_VAO_DAY":
        print("❌ Lỗi: Chưa cung cấp DISCORD_TOKEN trong file .env hoặc biến môi trường!")
        exit(1)
    try:
        bot.run(TOKEN)
    except discord.errors.PrivilegedIntentsRequired:
        print("\n" + "="*70)
        print("❌ LỖI: Bot chưa được bật 'Privileged Gateway Intents' trên Discord Developer Portal!")
        print("Vui lòng truy cập: https://discord.com/developers/applications")
        print("Chọn Bot -> Tab 'Bot' -> Kéo xuống phần 'Privileged Gateway Intents':")
        print("  [x] PRESENCE INTENT")
        print("  [x] SERVER MEMBERS INTENT")
        print("  [x] MESSAGE CONTENT INTENT")
        print("Bật cả 3 tùy chọn trên rồi lưu lại (Save Changes), sau đó khởi động lại Bot!")
        print("="*70 + "\n")
    except discord.errors.LoginFailure:
        print("❌ Lỗi: Token Discord không chính xác hoặc đã bị reset!")
    except Exception as e:
        print(f"❌ Lỗi khởi chạy Bot: {e}")
