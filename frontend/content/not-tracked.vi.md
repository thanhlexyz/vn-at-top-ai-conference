---
title: "Không theo dõi"
layout: "not-tracked"
draft: true
---

Những trường hợp đã xác nhận không phải là giảng viên hay nhà nghiên cứu tại các trường đại học ở Việt Nam, do đó không thuộc phạm vi theo dõi của trang.
Mục "Kiểm tra thủ công" là các mục trong `backend/data/csv/roster.csv` có `approved = no`, kèm lý do ghi rõ trong cột `notes`. Mục "Không thuộc trường đại học" gồm các tác giả có bài báo chỉ ghi đơn vị doanh nghiệp hoặc viện nghiên cứu, và mục "Chỉ có bài NeurIPS 2026" là các tác giả chưa thể đối chiếu hồ sơ trên OpenReview. Cả hai nhóm này đều không xuất hiện trên trang [Ứng viên](../candidates/).
*(Trang nháp này chỉ hiển thị trong môi trường phát triển cục bộ qua lệnh `make run` và không đưa vào bản xuất bản chính thức).*