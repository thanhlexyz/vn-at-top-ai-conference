---
title: "Ứng viên"
layout: "candidates"
draft: true
---

Danh sách ứng viên đang chờ rà soát hoặc xác nhận trước khi đưa vào bảng xếp hạng chính thức.
Một giảng viên chỉ xuất hiện trên trang công khai khi mục tương ứng trong `backend/roster.csv` được đặt `approved = yes`.
Để thêm ứng viên từ danh sách dưới đây, chạy lệnh `python find_candidates.py --add "Tên"` trong thư mục `backend/`, sau đó điền thông tin vị trí (`rank`), năm về nước (`vn_since`), mã hồ sơ OpenReview và đặt `approved` thành `yes`.
Những trường hợp đã xác nhận không phải là giảng viên đại học tại Việt Nam được lưu tại trang [Không theo dõi](../not-tracked/).
*(Trang nháp này chỉ hiển thị trong môi trường phát triển cục bộ qua lệnh `make run` và không đưa vào bản xuất bản chính thức).*