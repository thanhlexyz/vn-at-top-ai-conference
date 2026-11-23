---
title: "Giới thiệu"
toc: true
---

**Vietnam AIRankings** là dự án mã nguồn mở định hướng dữ liệu (open-source, data-driven), nhằm theo dõi và thống kê các công bố khoa học của đội ngũ giảng viên tại các trường đại học ở Việt Nam tại các hội nghị quốc tế hàng đầu về trí tuệ nhân tạo (AI).

Trong ngành khoa học máy tính, các hội nghị chuyên ngành hàng đầu (top-tier conferences) là nơi công bố những nghiên cứu mới nhất và có sức ảnh hưởng học thuật lớn nhất. Bằng việc theo dõi dữ liệu từ năm 2020 đến nay tại 10 hội nghị hàng đầu thuộc bốn phân ngành cốt lõi (AI, Machine Learning, Computer Vision và NLP), dự án hướng tới cung cấp một góc nhìn khách quan, minh bạch và toàn diện về năng lực nghiên cứu AI tại các trường đại học ở Việt Nam.

## Phạm vi và Thu thập Dữ liệu

### Hội nghị theo dõi
Dự án theo dõi 10 hội nghị hàng đầu từ năm 2020, được phân chia thành 4 lĩnh vực theo chuẩn của [CSRankings](https://csrankings.org/): **AI** (AAAI, IJCAI), **ML** (ICLR, NeurIPS, ICML), **CV** (CVPR, ICCV năm lẻ, ECCV năm chẵn) và **NLP** (ACL, EMNLP).

Về loại hình bài báo, hệ thống chỉ thống kê các công trình chính thức dạng Long Papers tại Main Track. Những bài báo ngắn (Short papers), bài workshop, position papers, Datasets & Benchmarks track, journal track, blog posts và Tiny Papers không tính vào số liệu chính mà được thống kê riêng ở mục "Ngoài Main Track". Các bài báo thuộc phân nhánh *Findings* được xếp cùng nhóm với các bài không vào Main Track và hiển thị cùng các bài workshop.

### Đối tượng thống kê
Đối tượng được theo dõi là các giảng viên, phó giáo sư và giáo sư người Việt Nam hiện có vị trí công tác chính thức tại một trường đại học ở Việt Nam. Danh sách bao gồm cả ngạch Giảng viên, bởi chức danh Phó Giáo sư và Giáo sư tại Việt Nam do Hội đồng Giáo sư Nhà nước công nhận với quy trình đặc thù so với hệ thống tenure-track quốc tế, trong khi nhiều giảng viên trẻ hiện đã chủ trì phòng thí nghiệm và trực tiếp hướng dẫn nghiên cứu sinh tương đương vị trí Assistant hoặc Associate Professor ở nước ngoài.

Ngược lại, sinh viên, giảng viên nước ngoài cùng các nghiên cứu viên làm việc thuần túy tại doanh nghiệp hoặc viện nghiên cứu độc lập không nằm trong phạm vi thống kê của dự án. Danh sách nhân sự này được rà soát và đối chiếu thủ công, trong đó một giảng viên chỉ xuất hiện trên bảng xếp hạng sau khi đã được xác thực thông tin và có ít nhất một bài nộp được ghi nhận tại 10 hội nghị.

Về mốc thời gian và đơn vị công tác, công trình nghiên cứu bắt đầu được tính từ năm giảng viên chính thức về làm việc tại một trường đại học ở Việt Nam. Một bài báo được nhận chỉ được ghi nhận nếu bản in PDF chính thức có ghi rõ tên trường đại học tại Việt Nam của giảng viên. Những bài báo chỉ ghi tên doanh nghiệp hoặc viện nghiên cứu bên ngoài mà không có tên trường đại học đi kèm sẽ không được tính vào bảng xếp hạng.

### Kỷ yếu chính thức và OpenReview
Dự án thu thập danh sách bài được nhận từ cổng thông tin và kỷ yếu chính thức của từng hội nghị (chi tiết xem bảng bên dưới).

{{< coverage >}}

† Danh sách chính thức của hội nghị không in đơn vị công tác, do đó đơn vị của tác giả được đối chiếu thủ công từ trang đầu bản in PDF. Những bài chưa thể xác định đầy đủ đơn vị của từng tác giả sẽ tạm thời chưa đưa vào các chỉ số phân tích hợp tác.
‡ Danh sách sơ bộ do hội nghị công bố trước ngày diễn ra chính thức và đang tiếp tục được cập nhật.

### Đối chiếu tác giả và Bài báo chưa chính thức
Đối với dữ liệu OpenReview, các bài báo được khớp chính xác thông qua Profile ID cá nhân. Đối với kỷ yếu hội nghị, hệ thống đối chiếu theo tên tác giả và tự động ghi nhận nếu đơn vị công tác in trên bài trùng khớp với trường đại học của giảng viên. Trong trường hợp bài báo ghi nhận một cơ quan khác tại Việt Nam hoặc danh sách hội nghị thiếu thông tin đơn vị (`†`), chúng tôi sẽ kiểm tra thủ công từng bản PDF. Nếu bài báo chỉ ghi đơn vị ở nước ngoài, tác giả được xác định là người khác trùng tên.

Khi danh sách chính thức từ hội nghị chưa được phát hành đầy đủ{{< provisional >}}, những công trình được công bố trên trang cá nhân hoặc trang của phòng lab sẽ được ghi nhận tạm thời dưới dạng `+N` kèm nhãn "chưa chính thức" cho đến khi kỷ yếu và dữ liệu OpenReview xuất bản hoàn tất.

## Phương pháp Tính điểm

### Điểm giảng viên
Mỗi bài báo được nhận có tổng điểm là 1,0, chia đều cho số tác giả của bài (`1 / N`). Điểm của giảng viên là tổng điểm phân đoạn từ các bài báo hợp lệ theo mô hình của [CSRankings](https://csrankings.org/).

### Điểm trường
Điểm của các giảng viên thuộc trường được cộng riêng theo từng lĩnh vực (AI, ML, CV, NLP). Điểm chung cuộc của trường là trung bình nhân (geometric mean) của `(Điểm lĩnh vực + 1)` trên cả 4 lĩnh vực (căn bậc 4 của tích). Việc cộng 1 giúp một lĩnh vực chưa có bài không kéo tổng điểm về 0, đồng thời khuyến khích sự phát triển đồng đều giữa các phân ngành.

### Vai trò tác giả và Hướng dẫn sinh viên
Trang thông tin của từng trường và giảng viên cung cấp thêm hai biểu đồ lọc riêng các bài báo mà trường hoặc giảng viên giữ vị trí **tác giả đầu (first author)** hoặc chiếm **đa số (>50%) số tác giả**. Đối với các bạn sinh viên và nghiên cứu sinh đang tìm kiếm giáo sư hướng dẫn (advisor), đây là một chỉ dấu rất đáng quan tâm: tỷ lệ bài báo có tác giả đầu hoặc đa số tác giả cùng trường cao thường phản ánh giảng viên dành nhiều thời gian làm việc và trực tiếp hướng dẫn sinh viên trong phòng lab của mình. Ngược lại, nếu tỷ lệ này thấp, điều đó thường cho thấy giảng viên dành nhiều thời gian hơn cho các dự án hợp tác đối ngoại với các nhóm nghiên cứu bên ngoài.

## Dữ liệu Bài nộp và Ước tính Tỷ lệ

### Mức độ công khai dữ liệu phản biện
Chính sách công khai dữ liệu phản biện giữa các hội nghị có sự khác biệt lớn:

| Hội nghị | Bài được nhận | Bài bị từ chối và tự rút |
|:---|:---|:---|
| **ICLR** | Công khai | Công khai toàn bộ bài nộp |
| **NeurIPS** | Công khai | Chỉ công khai khi tác giả tự nguyện chia sẻ |
| **ACL, EMNLP, CVPR** | Công khai | Không công khai (ngoại trừ các bài xuất bản ở Findings track) |
| **ICML, ICCV, ECCV, AAAI, IJCAI** | Công khai | Hoàn toàn bảo mật |

Các hội nghị như ACL, EMNLP hay CVPR không công khai bài bị từ chối, nhưng các bài được công bố ở Findings track cho biết bài đó không được nhận vào Main Track (dù vẫn không thể biết được toàn bộ các bài bị từ chối khác). Do đó, vì chỉ riêng ICLR công khai đầy đủ số liệu bài nộp và bài bị từ chối, một giảng viên nộp bài thường xuyên tại ICLR sẽ có số lượng bài bị từ chối hiển thị nhiều hơn so với người không nộp ICLR. Trên hệ thống, số bài **Bị từ chối** có ghi nhận bao gồm các bài bị từ chối sau phản biện, bài tác giả tự rút, bài bị loại sơ bộ (desk-rejected) và bài chuyển sang Findings. Số bài **Đã nộp** được tính bằng tổng số bài được nhận và số bài bị từ chối được ghi nhận.

### Ước tính bài nộp tại các hội nghị bảo mật thông tin
Để biểu đồ theo năm trên trang cá nhân phản ánh cân bằng hơn, hệ thống ước tính số bài không được nhận ở các hội nghị bảo mật thông tin dựa trên chính lịch sử nộp bài ICLR của giảng viên đó thông qua kỹ thuật làm mịn Laplace:

{{< ratio-eq >}}

Chẳng hạn, với 9 bài nộp ICLR và 1 bài được nhận, tỷ lệ là `(9 + 1) / (1 + 1) = 5`, tức mỗi bài được nhận ở hội nghị khác được ước tính tương ứng với 5 lượt nộp (mặc định bằng 1 nếu giảng viên chưa từng nộp ICLR). Việc cộng 1 giúp mẫu số luôn khác 0 và giữ ước lượng ổn định khi số bài còn ít. Đây là phép ước tính thống kê theo lượt nộp: một bài bị từ chối ở hội nghị này rồi được nhận ở hội nghị sau được tính là hai lượt thử.

Đáng chú ý, phép ước tính này chỉ áp dụng cho những hội nghị chắc chắn có bài nộp dựa trên minh chứng là có ít nhất một bài được nhận. Chẳng hạn, nếu một giảng viên có 1 bài được nhận tại AAAI và có lịch sử nộp bài tại ICLR, hệ thống mới ngoại suy số lượt nộp tại AAAI. Nếu giảng viên không có bài nào được nhận tại AAAI, hệ thống hoàn toàn không ước tính lượt nộp nào cho hội nghị đó vì không có căn cứ xác định họ có nộp bài hay không.

{{% ai-only %}}
## Thử nghiệm: Quét Văn bản AI

Mỗi bài báo có PDF công khai hiển thị hai chỉ số thử nghiệm từ mô hình mở [MELD](https://huggingface.co/anon-review-meld-2026/meld) (v8, giấy phép MIT, ~1 tỷ tham số), chạy cục bộ trên phần văn bản chính trích xuất bằng `pdftotext` (từ tóm tắt đến trước tài liệu tham khảo/lời cảm ơn, lược bỏ các khối dưới 15 từ và các bài dưới 300 từ):

- **% câu AI:** Tỷ lệ câu trong phần nội dung chính (từ 8 token trở lên) có điểm vượt ngưỡng 1% dương tính giả được hiệu chỉnh trên văn bản thông thường.
- **p_AI:** Điểm xác suất toàn văn bản (0–100%), tính từ trung bình 25% token có điểm cao nhất.

**Lưu ý khi đọc:** Đây là ước lượng thống kê về mặt văn bản, không phải kết luận về tác giả hay chất lượng khoa học. Do việc dùng LLM để biên tập và trau chuốt tiếng Anh đã trở nên phổ biến, `p_AI` của hầu hết bài báo năm 2025–2026 đều gần 100%, vì vậy chỉ số `% câu AI` mang tính tham khảo tốt hơn. Công thức toán, bảng biểu, mã nguồn và mức độ biên tập cũng có thể làm thay đổi chỉ số.
{{% /ai-only %}}

## Thông tin Dự án và Lời cảm ơn

Dự án này do **Lê Thành** ([thanhle.xyz](http://thanhle.xyz)) lên ý tưởng, thiết kế và quản lý nội dung, được xây dựng với sự trợ giúp của [Claude](https://www.anthropic.com/claude) và biên tập, hoàn thiện văn phong với sự hỗ trợ của [Gemini](https://gemini.google.com/). Tôi thực hiện trang web này từ sự tò mò cá nhân, với hy vọng đóng góp một nguồn tham khảo minh bạch, hữu ích cho cộng đồng học thuật và những ai quan tâm đến nghiên cứu AI tại Việt Nam.

Toàn bộ mã nguồn và dữ liệu được công khai tại [GitHub](https://github.com/thanhlexyz/vn-at-top-ai-conference). Nếu thấy trang hữu ích, bạn có thể tặng dự án một ngôi sao ⭐ trên GitHub, hoặc gửi thông tin bổ sung, đính chính qua trang [Góp ý](../feedback/). Lượt truy cập được thống kê bằng [GoatCounter](https://www.goatcounter.com/) (không dùng cookie và không lưu dữ liệu cá nhân).

**Lời cảm ơn:**
- **TS. [Võ Sỹ Nam](https://vingen.vinbigdata.org/teams/vo-sy-nam/):** Đã góp ý và gợi ý tách số liệu trên trang [Hội nghị](../venues/) thành giai đoạn trước và từ năm 2026 để thấy rõ bước chuyển của nghiên cứu AI.
- **GS. [Huỳnh Thị Thanh Bình](../professors/huynh-thi-thanh-binh/):** Đã góp ý mở rộng theo dõi thêm EMNLP, ICCV, ECCV, AAAI, IJCAI và phân nhóm theo chuẩn CSRankings.
- **GS. [ThanhVu Nguyen](https://tvn.roars.dev/):** Tác giả của bộ công cụ đã truyền cảm hứng cho dự án này:
  - [CS Picks](https://cspicks.roars.dev/) — so sánh giảng viên và trường đại học ngành Khoa học Máy tính tại Mỹ theo hướng nghiên cứu và tài trợ NSF.
  - [CS Conferences](https://cspicks.roars.dev/csconfs.html) — tra cứu thời gian và hạn nộp bài của các hội nghị khoa học máy tính.
  - [VietProfs](https://vietprofs.roars.dev/) — danh bạ giáo sư và giảng viên người Việt trên toàn thế giới.
