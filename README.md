# Scintigraphy Enhancer (3D Slicer Extension)

**Scintigraphy Enhancer** là một module mở rộng (extension) dành cho [3D Slicer](https://www.slicer.org/), được thiết kế chuyên biệt cho việc tiền xử lý và cải thiện hiển thị các ảnh y học hạt nhân, PET, và SPECT. 

Extension này cung cấp giao diện trực quan và các công cụ tối ưu để bác sĩ và các nhà nghiên cứu dễ dàng thay đổi mức hiển thị, giảm nhiễu và làm rõ tổn thương trên ảnh.

## Tính Năng Chính (Features)

*   **Chỉnh sửa Window / Level Nhanh:** Công cụ điều chỉnh slider độ sáng (Level) và độ tương phản (Window) trực quan.
*   **Bản Đồ Màu (Color LUT):** Tích hợp sẵn các preset màu phổ biến cho PET/SPECT (như Grey, PET-DICOM) với tính năng đảo ngược bảng màu (Invert LUT) chỉ bằng một click.
*   **Lọc Ngưỡng Hiển Thị (Thresholding):** Loại bỏ các dải tín hiệu không mong muốn bằng cách điều chỉnh cận trên (cận dưới được giữ nguyên ở mức cơ bản 0), tạo cảm giác mượt mà và tập trung như các công cụ xem SUV Max chuyên dụng.
*   **Giảm Nhiễu (Bilateral Smoothing):** Tích hợp bộ lọc Bilateral giúp loại bỏ nhiễu ảnh hiệu quả trong khi vẫn giữ nguyên độ sắc nét vùng biên của các tổn thương (Gợi ý Sigma: 0.8-1.5 cho PET, 1.2-2.0 cho SPECT).
*   **Tự Động Tối Ưu (Auto-Adjust):**
    *   **Thiết lập PET-DICOM nhanh:** Đưa hình ảnh về chuẩn hiển thị màu PET ngay lập tức.
    *   **Tự chỉnh nâng cao (Otsu + Percentile):** Thuật toán tự động tìm ngưỡng Otsu và dải phần trăm (Percentile 2-99.5) để tối ưu hóa Window/Level và Threshold mà không cần tinh chỉnh thủ công.
*   **Khôi Phục Trạng Thái (Reset):** Nút hoàn tác giúp người dùng quay ngay về trạng thái nguyên bản của ảnh nếu quá trình chỉnh sửa không như ý muốn.

## Khuyến Nghị Sử Dụng Dành Cho Bác Sĩ

1.  Dùng **"Thiết lập PET-DICOM nhanh"** cho thao tác thường quy (tự động đổi LUT chuẩn và đảo màu).
2.  Nếu cần tinh chỉnh máy tính hỗ trợ, mở mục **Nâng cao** và chọn **"Tự chỉnh WL/Threshold"**.
3.  Sử dụng bộ lọc giảm nhiễu với mức thiết lập Sigma khuyến cáo tuỳ vào loại ảnh (PET hoặc SPECT).
4.  Khi cần bắt đầu lại, chỉ cần bấm **"Khôi phục"**.

## Cách Chạy Extention (Hướng Dẫn Cài Đặt)

1. Mở 3D Slicer, nhấn tổ hợp phím `Ctrl + F` để tìm kiếm và mở công cụ **Extension Wizard**.
2. Nhấn vào mục **Select Extension**, trỏ tới thư mục chứa code của extention `ScintigraphyEnhancer`.
3. Khởi động lại phần mềm (**Restart Slicer**).
4. Sau khi Slicer mở lại, nhấn `Ctrl + F` và tìm **ScintigraphyEnhancer** hoặc chọn trực tiếp tên module này từ thanh công cụ (Modules toolbar) để truy cập và sử dụng.

