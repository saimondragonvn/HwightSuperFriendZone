# 🤖 HwightSuperFriendZone - Discord Store & Server Automation Bot

Bot Discord chuyên nghiệp dành cho Quản lý Server & Tự động hóa Store (Phong cách Cookie Store / Dịch vụ số uy tín).

---

## 🌟 Tính Năng Nổi Bật

1. **Thanh Toán & Hóa Đơn Tự Động (VietQR & Webhook):**
   - Tạo mã QR thanh toán nhanh ngân hàng Việt Nam theo số tiền và nội dung (`>qr 50k`, `>setupqr`).
   - Cổng Webhook ngầm tiếp nhận biến động số dư từ **SePay** hoặc **Casso**, tự động gửi thông báo bill ting ting vào đúng phòng Ticket của khách.
   - Lệnh test giả lập bill (`>testbill 50k`).

2. **Hệ Thống Dán Dữ Liệu Bảo Mật (>paste / >taoban):**
   - Giao diện Modal nhập Token, Cookie, Account, Link riêng tư chống lộ trên kênh chat chung.
   - Nút bấm `[📋 Xem Đầy Đủ / Copy]` mã hóa bản xem trước, chỉ người mua trong Ticket hoặc Quản trị viên mới xem được.

3. **Hệ Thống Ticket Thuê Acc & Bán Hàng Chuyên Nghiệp:**
   - Tạo phòng chat riêng tư 1-1 hỗ trợ khách hàng kèm mã Ticket tự động.
   - 4 Nút thao tác nhanh: `Claim Ticket`, `Đóng Ticket`, `Xem STK / VietQR`, `Hướng Dẫn Bảo Mật`.
   - Khi đóng Ticket, bot tự động trích xuất toàn bộ lịch sử trò chuyện thành file **HTML Transcript** và lưu trữ về kênh `#ticket-logs`.

4. **Hệ Thống Đánh Giá Uy Tín (Legit / Feedback):**
   - Đánh giá qua nút bấm Modal hoặc gõ cú pháp chat `+1 legit ...`.
   - Bot tự động thả reaction 💖 và 💎, lưu trữ số lượt uy tín vào Database.
   - Thống kê tổng số Legit và điểm trung bình (`>setuplegit`).

5. **Hệ Thống Key VIP Bản Quyền (Auto-Revoke Role):**
   - Tạo mã Key cấp Role có thời hạn hoặc vĩnh viễn (`>genkey @Role 30 5`).
   - Khách nhập lệnh `>redeem <KEY>` để tự nhận Role.
   - Task chạy ngầm quét Database mỗi 5 phút: tự động gỡ Role khi hết hạn và nhắn tin riêng (DM) nhắc khách gia hạn.

6. **Máy Tính Cây Cú Pháp An Toàn (Auto Inline Calculator):**
   - Gõ trực tiếp phép tính vào khung chat (VD: `50k * 3`, `1.5m - 200k`, `100k / 2`), Bot tự động tính toán mà không cần gõ lệnh.
   - Sử dụng thư viện `ast` của Python, an toàn tuyệt đối chống tấn công injection (DoS).

7. **Quản Lý Server & Tiện Ích Đỉnh Cao:**
   - Moderation: `>ban`, `>unban`, `>kick`, `>mute` (Timeout), `>unmute`, `>warn`, `>warnings`, `>clear`, `>lock`, `>unlock`.
   - AutoRole: Tự động phát Role cho thành viên mới (`>autorole @role`).
   - Role Thông báo: Nút bấm tự nhận/hủy Role thông báo Flash Sale (`>setupnotify @role`).
   - Tạo ảnh Banner sắc nét bằng Pillow (`>bannergen <nội dung>`).
   - Trộm Emoji (`>steal <emoji> [tên]`).
   - Trợ lý AI trả lời FAQ tích hợp Google Gemini AI (`>ask <câu hỏi>`).
   - Tra cứu lừa đảo / Blacklist Scammer (`>checkscam`, `>addscam`).
   - Quản lý doanh thu nhân viên (`>done`, `>doanhthu`).

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Bot

### 1. Yêu cầu hệ thống
- Python 3.10 trở lên (Đã tích hợp sẵn môi trường ảo `.venv` với Python 3.12).
- Kết nối Internet.

### 2. Cài đặt Privileged Gateway Intents (BẮT BUỘC TRÊN DISCORD)
Trước khi chạy bot, bạn **bắt buộc** phải kích hoạt các quyền Intents sau trên Discord Developer Portal:
1. Truy cập [Discord Developer Portal](https://discord.com/developers/applications).
2. Chọn ứng dụng Bot của bạn (`ID: 1560301422178738216`).
3. Vào mục **Bot** ở thanh menu bên trái.
4. Kéo xuống phần **Privileged Gateway Intents** và gạt bật cả 3 mục:
   - ✅ **Presence Intent**
   - ✅ **Server Members Intent**
   - ✅ **Message Content Intent**
5. Bấm **Save Changes**.

### 3. Mời Bot vào Server của bạn
Dùng đường link OAuth2 sau (đã gán quyền Administrator):
```
https://discord.com/oauth2/authorize?client_id=1560301422178738216&permissions=8&scope=bot%20applications.commands
```

### 4. Cấu hình file `.env`
File `.env` nằm tại thư mục gốc của bot:
```env
DISCORD_TOKEN=your_bot_token_here
BOT_ID=your_bot_id_here
PORT=8080
GEMINI_API_KEY=your_gemini_api_key_here
WEBHOOK_SECRET=your_webhook_secret_here
```
*(Nếu muốn dùng tính năng `>ask`, hãy điền thêm `GEMINI_API_KEY` từ [Google AI Studio](https://aistudio.google.com/)).*

### 5. Khởi chạy Bot
Chỉ cần nhấp đúp chuột vào file:
```
run_bot.bat
```
Hoặc chạy lệnh trong terminal:
```powershell
.\.venv\Scripts\python.exe bot.py
```

---

## 📋 Danh Sách Lệnh (Prefix: `>`)

### 🛒 1. Store, Bảng Giá & VietQR
| Lệnh | Mô tả |
| :--- | :--- |
| `>banggia` | Xem bảng giá dịch vụ số & nút tạo Ticket, VietQR |
| `>qr <tiền> [nội dung]` | Tạo mã VietQR theo số tiền (VD: `>qr 50k Nitro`) |
| `>setupqr <bank> <stk> <tên>` | Cài đặt thông tin tài khoản ngân hàng của Store |
| `>paste` hoặc `>taoban` | Mở Modal dán Cookie/Token bảo mật |
| `>done @khách <tiền> [mặt hàng]` | Chốt đơn hàng & cộng doanh thu cho nhân viên |
| `>doanhthu` | Xem báo cáo doanh thu Ngày/Tháng & BXH nhân viên |

### 🪽 2. Ticket v2 & Đánh Giá Uy Tín (Chống Trôi)
| Lệnh | Mô tả |
| :--- | :--- |
| `>rename <tên mới>` (hoặc `>doiten`) | Đổi tên kênh Ticket v2 (hỗ trợ Emoji `✅`, `⏳`, `💎` như `✅-cape-hero`) |
| `>createticket` | Mở bảng tạo Ticket mua hàng / thuê acc |
| `>setuplegit [#kênh]` | Mở bảng đánh giá uy tín **Chống Trôi 100%** (Tự động ghim xuống tin nhắn cuối) |
| `>checkscam <stk/id>` | Tra cứu STK ngân hàng hoặc Discord ID lừa đảo |
| `>addscam <stk/id> <lý do>` | Thêm đối tượng vào danh sách đen Scammer |
| `>setupnotify @role` | Tạo bảng cho khách tự nhận Role thông báo Flash Sale |

### 📦 3. Quản Lý Kho Hàng Chuẩn Cookie Store • STOCK (Tự Tạo & Đồng Bộ Kênh)
| Lệnh | Mô tả |
| :--- | :--- |
| `>setupstock [#kênh]` | Ghim bảng Stock **Tự Động Cập Nhật Real-Time 24/7** (khớp 100% ảnh Cookie Store) |
| `>createacc <danh_mục> <giá> <tên_kênh>` | **Tự động tạo kênh Discord thật** (ví dụ `#✅-cape-hero`), set quyền, gửi embed và đưa vào kho |
| `>addstock <danh_mục> <giá> <#kênh hoặc tên>` | Thêm kênh có sẵn hoặc acc vào kho (VD: `>addstock "RÈ SỐC ACC MC" 0 #✅-cape-hero`) |
| `>syncstock <tên_category> [đơn_giá]` | Tự động quét toàn bộ kênh trong một Category và thêm vào bảng Stock |
| `>hold <#kênh hoặc tên> [số_phút]` | Đặt giữ chỗ acc cho khách (đổi tên kênh thành `⏳-[tên]` và cập nhật bảng Stock) |
| `>unhold <#kênh hoặc tên>` | Hủy giữ chỗ và trả lại tài khoản về trạng thái sẵn sàng bán |
| `>sellstock <#kênh> @khách [tiền]` | Chốt bán acc trong kho, cộng doanh thu, đổi tên thành `done-[tên]` và gỡ khỏi kho |
| `>setstore <tên_store> [chữ_ký]` | Tùy chỉnh tên cửa hàng & chữ ký footer (VD: `>setstore "Cookie Store" "made by ngocngann"`) |
| `>importstock <danh_mục> <giá> <ds>` | Nhập hàng hàng loạt vào kho (mỗi dòng 1 sản phẩm) |
| `>delstock <id_hoặc_tên>` | Xóa mặt hàng khỏi kho theo ID hoặc tên sản phẩm |
| `>clearstock [danh_mục]` | Xóa sạch toàn bộ kho hàng hoặc xóa theo danh mục (Admin) |

### 🎉 4. Sự Kiện Giveaway Phát Quà Tự Động
| Lệnh | Mô tả |
| :--- | :--- |
| `>gstart <tg> <số_giải> <quà>` | Tổ chức Giveaway tự động (VD: `>gstart 10m 1 Nitro 1 Tháng`) |
| `>gend <message_id>` | Kết thúc sớm Giveaway đang diễn ra |
| `>greroll <message_id>` | Quay lại người trúng thưởng mới cho Giveaway đã kết thúc |

### 🪙 5. Hệ Thống Ví Xu, Cửa Hàng Đổi Thưởng & Bảng Xếp Hạng
| Lệnh | Mô tả |
| :--- | :--- |
| `>top [xu/daigia/legit]` | Bảng Xếp Hạng Top Server Real-Time (Top Xu, Top Đại Gia chi tiêu, Top Uy Tín Legit) kèm 3 nút bấm tương tác |
| `>shop` (hoặc `>cuahang`) | Mở Cửa Hàng Đổi Thưởng: Đổi Role VIP hoặc Key bản quyền tự động bằng Xu tích lũy kèm Select Menu mua nhanh |
| `>buy <id>` (hoặc `>mua`) | Mua / đổi thưởng vật phẩm trong Shop bằng ID (VD: `>buy 1`) |
| `>addshopitem <loại> <giá> <tên> [role/ngày] [kho]` | Thêm mặt hàng Role VIP / Key / Quà tặng vào Shop Đổi Thưởng (Chỉ Admin) |
| `>delshopitem <id>` | Xóa mặt hàng khỏi Shop theo ID (Chỉ Admin) |
| `>clearshop` | Xóa sạch toàn bộ mặt hàng trong Shop Đổi Thưởng (Chỉ Admin) |
| `>daily` | Điểm danh mỗi ngày nhận ngẫu nhiên 10.000đ - 50.000đ Xu |
| `>bal [@user]` | Kiểm tra số dư ví Xu của bạn hoặc người khác |
| `>taixiu <tai/xiu> <tiền>` | Chơi mini-game Tài Xỉu 3 xúc xắc (VD: `>taixiu tai 10k`) |
| `>flip <ngua/sap> <tiền>` | Mini-game Tung Đồng Xu may mắn |
| `>pay @user <tiền>` | Chuyển Xu cho thành viên khác trong Server |
| `>congtien @user <tiền>` | Cộng hoặc trừ Xu cho thành viên (Chỉ Admin) |

### 🚀 6. Hệ Thống Cấp Độ, XP & Thông Báo Thăng Cấp (Ping Kênh)
| Lệnh | Mô tả |
| :--- | :--- |
| `>rank [@user]` | Thẻ hồ sơ cấp độ, thanh tiến độ XP, thứ hạng hoạt động và tổng tin nhắn |
| `>toplevel` | Bảng Xếp Hạng Top 10 thành viên hoạt động nhiều nhất Server theo Level |
| `>setlevelupchannel <#kênh/none>` | **Cài đặt kênh thông báo & PING thành viên khi thăng cấp** (Chỉ Admin) |
| `>addlevelrole <level> [tên hoặc @Role]` | Gán Role thưởng khi lên cấp (Hỗ trợ **Tự Động Tạo Role mới** trên Discord nếu chưa có) (Chỉ Admin) |
| `>dellevelrole <level>` | Xóa Role phần thưởng của mốc cấp độ (Chỉ Admin) |
| `>levelroles` | Xem danh sách toàn bộ Role thưởng theo Level của Server |

### 💎 7. Hệ Thống Mốc Chi Tiêu & Nâng Cấp Role VIP Tự Động (Tự Tạo Role & Mốc 50k, 100k)
| Lệnh | Mô tả |
| :--- | :--- |
| `>+<tiền> to @user` (hoặc `+<tiền> @user`) | ⚡ **Cú pháp nhanh:** Cộng tiền chi tiêu và **tự động phân biệt & gán đúng Role VIP** (VD: `>+100k to @player`) |
| `>addspent @user <tiền> [món]` | Lệnh cộng chi tiêu tích lũy cho khách hàng (Staff/Admin) |
| `>setupviproles` (hoặc `>taorolevip`) | ⚡ **1-Click Tự Động Tạo Trọn Bộ Role VIP** trên Discord (50k, 100k, 200k, 500k, 1M, 2M, 5M) kèm màu sắc & hoist chuẩn |
| `>setviptier <tiền> [tên_role hoặc @Role]` | Thiết lập mốc chi tiêu VIP (**Tự động tạo Role mới** nếu chỉ nhập số tiền / tên, VD: `>setviptier 50k` hoặc `>setviptier 100k`) |
| `>viptiers` | Xem bảng các mốc tiền chi tiêu yêu cầu và Role VIP được nhận |
| `>delviptier <id>` | Xóa mốc chi tiêu VIP theo ID (Chỉ Admin) |
| `>spent [@user]` | Xem tổng tiền đã mua hàng tại Store, số đơn đã chốt và tiến độ lên mốc VIP kế tiếp |
| `>syncvip [@user/all]` | Quét lại cơ sở dữ liệu và tự động trao bổ sung Role VIP cho người đủ mốc (Chỉ Admin) |

### 👑 8. Hồ Sơ Khách Hàng VIP & Quản Trị Server
| Lệnh | Mô tả |
| :--- | :--- |
| `>profile [@user]` | Thẻ hồ sơ thành viên VIP: tổng tiền đã chi, tiến độ mốc VIP, số đơn hàng và Xu |
| `>serverinfo` | Xem tổng quan thông tin, cấp độ Boost và trạng thái Server |
| `>announce <#kênh> <nội dung>` | Đăng thông báo Store chính thức vào kênh chỉ định |
| `>genkey @Role <ngày> [số lượng]` | Tạo Key VIP cấp Role có thời hạn (0 = vĩnh viễn) |
| `>redeem <mã key>` | Khách nhập Key để tự động kích hoạt nhận Role |
| `>autorole @role` | Bật/tắt tự động cấp role cho thành viên mới |
| `>addrole @user @role` | Cấp role cho thành viên |
| `>removerole @user @role` | Gỡ role của thành viên |
| `>ban @user [lý do]` | Cấm thành viên |
| `>unban <user_id> [lý do]` | Gỡ lệnh cấm thành viên |
| `>kick @user [lý do]` | Đuổi thành viên |
| `>mute @user <thời gian> [lý do]` | Timeout thành viên (VD: `10m`, `1h`, `7d`) |
| `>unmute @user` | Gỡ Timeout |
| `>warn @user [lý do]` | Cảnh cáo thành viên |
| `>warnings [@user]` | Xem lịch sử các lần cảnh cáo |
| `>clear <số lượng>` | Dọn dẹp tin nhắn rác nhanh |
| `>lock` / `>unlock` | Khóa / Mở khóa kênh chat hiện tại |
| `>steal <emoji1> [emoji2]...` | Trộm 1 hoặc NHIỀU Emoji/GIF cùng lúc (hoặc reply tin nhắn) |
| `>banner [@user]` | Lấy ảnh banner của user hoặc server |
| `>bannergen <nội dung>` | Tạo ảnh banner thông báo sắc nét bằng Pillow |
| `>faq add / list / del` | Thiết lập câu hỏi - trả lời tự động |
| `>ask <câu hỏi>` | Trợ lý thông minh hỏi đáp Gemini AI |
