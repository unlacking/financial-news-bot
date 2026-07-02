print("Check")

from datetime import datetime, timezone, timedelta
import feedparser
import json
import email.utils

def tu_dong_lay_tin_tai_chinh():
    # 1. Cấu hình các nguồn RSS và tham số (Chỉ giữ lại VnEconomy và VnExpress)
    cac_nguon_rss = {
        "VnEconomy": "https://vneconomy.vn/tai-chinh-ngan-hang.rss",
        "VietStock": "https://vietstock.vn/tai-chinh.rss",
        "CafeF": "https://cafef.vn/thi-truong-chung-khoan.rss"
    }
    tin_tuc = []
    cac_link_da_lay = set()  # Tập hợp giúp kiểm tra và loại bỏ tin trùng lặp hiệu quả (O(1))
    so_luong_tin_muon_lay = 5  # Số lượng tin tối đa muốn lấy cho MỖI nguồn
    mui_gio_vn = timezone(timedelta(hours=7))
    hom_nay_vn = datetime.now(mui_gio_vn).date()

    print("Bắt đầu tự động lấy tin tài chính...")

    # 2. Vòng lặp quét qua từng nguồn RSS trong cấu hình
    for ten_nguon, rss_url in cac_nguon_rss.items():
        feed = feedparser.parse(rss_url, agent="Mozilla/5.0")
        
        # Kiểm tra an toàn xem feed có dữ liệu không
        if not getattr(feed, 'entries', None):
            print(f"⚠ Cảnh báo: Không kết nối được hoặc link RSS {ten_nguon} bị lỗi/không có dữ liệu!")
            continue

        so_luong_tin_hien_tai = 0
        for entry in feed.entries: 
            # Dừng lại nếu đã lấy đủ số lượng tin yêu cầu cho nguồn này
            if so_luong_tin_hien_tai >= so_luong_tin_muon_lay:
                break

            # Lấy an toàn link và published_raw bằng getattr đề phòng RSS khuyết thiếu trường
            link_bai_bao = getattr(entry, 'link', '').strip()
            published_raw = getattr(entry, 'published', getattr(entry, 'pubDate', None))

            # Nếu bài viết không có link (dữ liệu rác), bỏ qua luôn
            if not link_bai_bao:
                continue

            try:
                # Nếu không có ngày đăng, ta coi như không hợp lệ để lọc theo ngày hôm nay
                if not published_raw:
                    raise ValueError
                thoi_gian_bai_bao = email.utils.parsedate_to_datetime(published_raw)
                thoi_gian_bai_bao_vn = thoi_gian_bai_bao.astimezone(mui_gio_vn)
                ngay_xuat_ban_vn = thoi_gian_bai_bao_vn.date()
            except (ValueError, TypeError):
                # Không crash chương trình khi gặp bài báo lỗi định dạng ngày tháng
                continue

            # ĐIỀU KIỆN: Phải là tin hôm nay VÀ link bài viết chưa từng được lấy
            if ngay_xuat_ban_vn == hom_nay_vn and link_bai_bao not in cac_link_da_lay:
                summary_clean = getattr(entry, 'summary', '')
                
                # Xử lý cắt chuỗi HTML thừa từ RSS một lần duy nhất
                if "/>" in summary_clean:
                    summary_clean = summary_clean.split("/>")[-1].replace("</a>", "").strip()
                elif "</a>" in summary_clean:
                    summary_clean = summary_clean.split("</a>")[-1].strip()
                
                tin_tuc.append({
                    "source": ten_nguon,
                    "title": getattr(entry, 'title', 'Không rõ tiêu đề'),
                    "link": link_bai_bao,
                    "published": ngay_xuat_ban_vn.isoformat(), # Chuyển thành String "YYYY-MM-DD" để an toàn cho JSON
                    "summary": summary_clean
                })
                
                cac_link_da_lay.add(link_bai_bao) # Đánh dấu bài viết này đã lấy vào tập hợp set()
                so_luong_tin_hien_tai += 1
                
    return tin_tuc

# --- "NGƯỜI GÁC CỔNG" __name__ = "__main__" ---
if __name__ == "__main__":
    danh_sach_tin_tuc = tu_dong_lay_tin_tai_chinh()

    # Kiểm tra an toàn trước khi in
    if danh_sach_tin_tuc:
        with open("tin_tuc_cuoi_ngay.json", "w", encoding="utf-8") as f:
            json.dump(danh_sach_tin_tuc, f, ensure_ascii=False, indent=4)
        print("Đã lưu sản phẩm cuối ngày vào file: tin_tuc_cuoi_ngay.json")

        print(f"\nĐã thu thập được tổng cộng {len(danh_sach_tin_tuc)} tin mới.\n")
        print("================ DANH SÁCH TIN TỨC ================")
        
        for index, bai_tin in enumerate(danh_sach_tin_tuc, start=1):
            print(f"[{index}] Nguồn: {bai_tin['source']}")
            print(f"Tiêu đề: {bai_tin['title']}")
            print(f"Ngày đăng: {bai_tin['published']}")
            print(f"Tóm tắt: {bai_tin['summary']}")
            print(f"Link: {bai_tin['link']}")
            print("-" * 50) 
            
    else:
        print("\nKhông có tin tức nào mới trong ngày hôm nay.")