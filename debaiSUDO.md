# ĐỀ BÀI DỰ ÁN CUỐI KÌ SUDO CODE 2026 - VÒNG 1

**Harness Agent hỗ trợ Call Center E-commerce (Telesale)**
*Ngữ cảnh liên tục qua nhiều phiên & nhiều kênh - Tự đánh giá và cải tiến theo thời gian*

---

## A. BỐI CẢNH & CASE STUDY

Phần lớn đơn hàng online giá trị trung bình cao tại Việt Nam không chốt được trên web/app mà phải qua cuộc gọi tư vấn. Mỗi telesale gọi $80-150 \text{ cuộc/ngày}$ và một khách thường cần nhiều lần chạm mới quyết định. Vấn đề: hầu hết hệ thống call center được thiết kế stateless – kết thúc cuộc gọi là mất ngữ cảnh.

### Case 1 - Khách gọi lại nhưng hệ thống coi như người lạ (bài toán lõi)
Chị Hoa được tư vấn 9 phút mua máy lọc không khí: phòng 25m², có trẻ nhỏ, ngân sách 5tr, chốt model X giá 4.890.000đ, khuyến mãi tới cuối tuần. Chị nói "để hỏi ông xã rồi gọi lại". Hai ngày sau chị gọi lại, rơi vào nhân viên khác – kịch bản lặp lại từ đầu: "Dạ chị quan tâm sản phẩm nào ạ? Nhà mình bao nhiêu m²? Ngân sách khoảng nhiêu ạ?". Nhân viên mới tư vấn model Y, báo giá 5.200.000đ vì không biết khuyến mãi cũ. Chị Hoa mất niềm tin: "Sao mỗi người nói một kiểu vậy em?"
*   **Hệ quả:** đơn lẽ ra chốt sau 2 cuộc thì mất 5-10 cuộc - chi phí phục vụ/đơn tăng 3-5 lần; 40-60% thời lượng cuộc gọi bị đốt để thu thập lại thông tin đã có; khách bỏ đi sau cuộc thứ 3.
*   **Thiếu:** bộ nhớ dài hạn theo khách hàng vượt ranh giới phiên + cơ chế nhận diện khách gọi lại và tái nạp ngữ cảnh.

### Case 2 - Ngữ cảnh phân mảnh đa kênh: mỗi kênh biết một nửa sự thật
Anh Tuấn nhắn Fanpage hỏi giày, được báo sale 690k. Anh inbox Zalo OA hỏi đổi size, nhân viên khác trả lời. Anh xem livestream rồi gọi hotline. Nhân viên hotline không thấy gì cả, báo giá niêm yết 790k. "Ủa bên em nhắn Facebook báo anh 690k mà?" – nhân viên không xác minh được, hoặc chấp nhận đại dù chương trình đã hết.
*   **Hệ quả:** báo giá/chính sách không nhất quán giữa các kênh → khiếu nại, mất uy tín; khách lặp lại nhu cầu 3-4 lần - nhân viên phải mở song song 4-5 tab trong lúc đang nói chuyện với khách.
*   **Thiếu:** hồ sơ ngữ cảnh hợp nhất theo danh tính khách hàng (nhận diện qua SĐT / Zalo ID / FB ID) + cơ chế giải quyết mâu thuẫn giữa các nguồn.

### Case 3 - Bàn giao mù: giữa AI và người, giữa ca này và ca kia
Voicebot lọc lead nói chuyện 4 phút, khai thác được: khách mua cho mẹ bị tiểu đường, quan tâm sản phẩm A nhưng lo tương tác thuốc. Khách hỏi câu ngoài phạm vi → chuyển máy. Nhân viên nhận máy: "Dạ em nghe, mình cần hỗ trợ gì ạ?" – 4 phút khai thác bốc hơi. Trải nghiệm chuyển máy thành trải nghiệm tệ nhất hành trình, tệ hơn cả không có bot. Tương tự khi: ca sáng hẹn "chiều gọi lại" nhưng chiều là ca khác trực; nhân viên phụ trách nghỉ việc; khách gọi đổi size địa chỉ nhưng không ai biết trạng thái đơn.
*   **Hệ quả:** hài lòng sau chuyển máy thấp hẳn - người thật phải nghe lại 5-10 phút ghi âm, hoặc bỏ qua luôn; đơn COD bị hoàn vì không ai chủ động xác nhận lại.
*   **Thiếu:** bản tóm tắt bàn giao (handoff brief) có cấu trúc + bộ nhớ chia sẻ giữa các agent, cả AI lẫn người.

### Case 4 - Kịch bản đóng băng: không học được gì từ hàng nghìn cuộc gọi
Trung tâm 40 nhân viên, ~4.000 cuộc/ngày, QA chỉ nghe ngẫu nhiên ~2%. Call script do trưởng nhóm viết 8 tháng trước, cập nhật bằng cảm tính. Cùng một phản đối "đắt quá em ơi", có người chốt được 40%, có người 8% nhưng không ai biết cách nào hiệu quả hơn vì không có dữ liệu đối chiếu giữa cách xử lý và kết quả chốt đơn. Câu khách hay hỏi ("đang cho con bú dùng được không?") không có trong kịch bản – mỗi người trả lời một kiểu. Khuyến mãi hết hạn vẫn được báo suốt 2 tuần.
*   **Hệ quả:** hệ thống hôm nay và 6 tháng trước giống hệt nhau về chất lượng; 98% tín hiệu chất lượng bị bỏ phí - rủi ro cam kết sai không được phát hiện.
*   **Thiếu:** cơ chế đánh giá tự động chấm 100% cuộc gọi + vòng lặp cải tiến biến kết quả chốt đơn thành cập nhật cho kịch bản, tài liệu và bộ nhớ.

---

## B. ĐỀ BÀI

**Xây dựng Harness Agent hỗ trợ Call Center bán hàng online (Telesale) có khả năng duy trì ngữ cảnh liên tục qua nhiều phiên & nhiều kênh, tự đánh giá và cải tiến theo thời gian.**

1.  **Xử lý dữ liệu hội thoại tiếng Việt:** giọng nói (file ghi âm cuộc gọi) và văn bản (chat, teencode, viết tắt) → ngữ cảnh có cấu trúc, truy vấn được.
2.  **Duy trì bộ nhớ khách hàng xuyên phiên:** khách gọi lại thì nhận diện được, nạp đúng ngữ cảnh cũ, mở đầu bằng xác nhận tiếp nối thay vì hỏi lại từ đầu.
3.  **Thiết kế agent harness:** vòng lặp nhận thức → truy hồi → lập kế hoạch → gọi tool → quan sát → ghi nhớ, có guardrail và fallback.
4.  **Đo lường được chính mình:** bộ đánh giá tự động, chứng minh bằng số rằng hệ thống tốt hơn baseline không-có-bộ-nhớ.
5.  **Cải tiến từ feedback mà không huấn luyện lại mô hình:** cập nhật tài liệu, bộ nhớ, ngân hàng ví dụ, kịch bản xử lý phản đối.

**Định hướng chấm điểm:** Toàn bộ mô hình đều dùng bản có sẵn. Điểm đến từ cách nhóm thiết kế dữ liệu, kiến trúc, cách đo đạc và cách cải tiến. *Một hệ thống chạy ở chế độ chat text, dùng model nhỏ, nhưng có bộ nhớ hoạt động đúng và có số liệu chứng minh sẽ được điểm cao hơn một hệ thống voice hào nhoáng mà không đo được gì.*

*(Các thuật ngữ in nghiêng trong đề như harness, guardrail, RAG, MCP, A2A, baseline... và công thức tính từng chỉ số đều được giải thích chi tiết ở Phụ lục cuối đề).*

---

## C. YÊU CẦU CỤ THỂ

**Hai mức độ hoàn thành:**
*   **M1 Cơ bản - bắt buộc.** Làm đủ M1 là đã đạt yêu cầu vòng 1.
*   **M2 Nâng cao - khuyến khích.** Làm được sẽ nổi bật rõ so với mặt bằng. Chỉ làm M2 khi M1 đã chạy ổn định.
*(Ngoài hai mức trên, mục G có danh sách tính năng cộng điểm thưởng dành cho nhóm còn dư thời gian).*

### C.1. Dữ liệu & xử lý tiếng Việt

| Hạng mục dataset | M1 | M2 |
| :--- | :--- | :--- |
| Số cuộc hội thoại (dạng transcript) | $\ge120$ | $\ge250$ |
| Trong đó có audio (thu thật hoặc sinh bằng TTS) | $\ge40$ cuộc / $\ge1$ giờ | $\ge100$ / $\ge3$ giờ |
| Khách hàng đa phiên ($\ge2$ cuộc gọi cùng 1 khách) | $\ge30$ khách | $\ge60$ (có khách $\ge3$ phiên) |
| Khách có cả cuộc gọi + chat (đa kênh) | $\ge10$ khách | $\ge30$ khách |
| Ngành hàng - giọng vùng miền | 1 ngành - 2 miền | 3 ngành - 3 miền |
| Audio có nhiễu (đường phố, sóng yếu) | | $\ge20\%$ |
| Catalog sản phẩm + chính sách (giá, KM, đổi trả, ship) | > 30 SKU | > 100 SKU |

*   **Điều kiện tiên quyết:** dataset các nhóm sẽ tự đi tìm, ưu tiên nguồn tiếng Việt và phải có nhóm khách đa phiên – đây là trọng tâm bài toán, dataset chỉ gồm các cuộc gọi rời rạc sẽ không chấm được.
*   **Được phép sinh toàn bộ dữ liệu bằng LLM đóng vai + TTS** – đây là cách làm hoàn toàn chấp nhận được, không bị trừ điểm.
*   **Nghiêm cấm dùng ghi âm khách hàng thật chưa ẩn danh.**
*   **Persona cần có:**
    *   **M1:** khách do dự cần hỏi người nhà - khách so giá - khách đã mua gọi lại đổi size/khiếu nại.
    *   **M2 thêm:** khách hỏi nhiều không mua - khách gọi lần 3 đã hết kiên nhẫn.

**Pipeline xử lý:**

| Hạng Mục | M1 Cơ bản | M2 Nâng cao |
| :--- | :--- | :--- |
| **Voice** | dùng ASR tiếng Việt có sẵn (Whisper / PhoWhisper - không cần train) để chuyển file ghi âm thành text; báo cáo WER/CER trên $\ge20$ file. <br>chuẩn hóa số bắt buộc: "bốn triệu tám trăm chín mươi" $\rightarrow$ 4.890.000, "hai trăm bốn chín k" $\rightarrow$ 249.000, số điện thoại, ngày hẹn gọi lại. | Tách người nói (diarization) agent/khách sửa lỗi ASR bằng từ điển tên sản phẩm ("Xiao Mi" $\rightarrow$ Xiaomi, "sai z eo" $\rightarrow$ size L); xử lý audio nhiễu - xử lý theo luồng (streaming). |
| **Text** | chuẩn hóa teencode / viết tắt / không dấu ("sp nay co ship cod k a") và code-switching Việt-Anh (size, ship, sale, order, inbox). | |
| **Trích xuất có cấu trúc** | intent - sản phẩm quan tâm, size/màu, mức giá đã báo, thời điểm hẹn gọi lại, người ra quyết định ("để hỏi chồng") - kết quả cuộc gọi (chốt / hẹn lại / từ chối). | thêm: loại phản đối + cách xử lý; sentiment; cam kết đã hứa với khách. |
| **PII** | che số điện thoại / CCCD / địa chỉ khi lưu log và khi gửi ra model ngoài (regex là đủ). | tokenization để nghiệp vụ vẫn dùng được + xóa toàn bộ dữ liệu 1 khách theo yêu cầu. |

**Thiết kế lớp bộ nhớ (phần quan trọng nhất của mục này):**

| Mức | Tầng | Nội dung / ví dụ |
| :--- | :--- | :--- |
| **M1** | Working | Ngữ cảnh lượt thoại hiện tại: khách vừa nói gì, đang chờ xác nhận gì |
| | Episodic | Tóm tắt từng cuộc gọi: "Cuộc 1 (12/03): tư vấn model X, báo 4.89tr, khách hẹn hỏi chồng" |
| | Profile | Sự thật bền vững về khách: phòng 25m², có con nhỏ, ngân sách ~5tr |
| | Semantic/KB | Giá, tồn kho, khuyến mãi còn hiệu lực, chính sách đổi trả (dùng RAG) |

*   **M1:** Phải xử lý được: ghi gì / không ghi gì (tránh nhồi rác vào bộ nhớ) và khách đổi ý ("thôi anh lấy màu trắng" - thông tin cũ phải bị vô hiệu, không được để hai giá trị mâu thuẫn cùng tồn tại).
*   **M2:** Thêm: hết hạn theo thời gian (khuyến mãi cũ, ý định mua đã nguội) - truy vết nguồn gốc mỗi mẫu ký ức (đến từ cuộc gọi nào) - chống đầu độc bộ nhớ khi khách cung cấp thông tin sai.

### C.2. Harness Agent (trọng tâm)

*(Agent Harness - Vòng lặp mỗi lượt thoại: Perceive $\rightarrow$ Resolve Identity $\rightarrow$ Retrieve $\rightarrow$ Plan $\rightarrow$ Guardrail $\rightarrow$ Act $\rightarrow$ Observe $\rightarrow$ Persist)*

| Hạng Mục | M1 Cơ bản | M2 Nâng cao |
| :--- | :--- | :--- |
| **Session Continuity** <br>*(tính năng bắt buộc số 1)* | 1. Nhận diện khách gọi lại qua số điện thoại.<br>2. Sinh "Call Brief" nạp cho agent ngay trước khi bắt máy: khách là ai, đã gọi mấy lần - sản phẩm đã tư vấn + giá / khuyến mãi đã báo - rào cản còn tồn đọng ("chờ hỏi chồng") - hành động đề xuất tiếp theo.<br>3. Mở đầu bằng xác nhận tiếp nối: "Dạ em chào chị Hoa, hôm 12/03 bên em có tư vấn chị mẫu máy lọc X cho phòng 25m² giá ưu đãi 4.890.000đ. Chị đã trao đổi với anh nhà chưa ạ, hay còn băn khoăn điểm nào để em hỗ trợ thêm?"<br>4. Không hỏi lại thông tin đã có – nếu cần xác minh thì phải là câu hỏi xác nhận, không phải câu hỏi mở. | Phát hiện khuyến mãi đã hết hạn / hàng đã hết và xử lý khéo, không báo lại giá cũ; xử lý khách gọi từ số lạ. |
| **Tích hợp công cụ** <br>*(agent gọi được $\ge3$ tool)* | `crm.get_customer`, `catalog.search` + `inventory.check`, `order.create`. Quan trọng nhất: giá phải lấy từ tool, agent không được tự bịa giá hay khuyến mãi. (mock có schema rõ ràng là đủ, không cần hệ thống thật) | `pricing.get_quote` (chỉ trả KM còn hiệu lực), `order.status/update`, `schedule.callback`. |
| **Phải trình bày và bảo vệ được** | Đưa gì vào prompt và cắt gì khi ngữ cảnh dài; khi nào cần gọi tool và khi nào không; xử lý lỗi (tool timeout, ASR trả ra rác, LLM trả sai định dạng – hệ thống nói gì với khách lúc đó?) - khi nào chuyển cho người thật và bàn giao kèm thông tin gì. | Xử lý khách ngắt lời (barge-in); nén/tóm tắt ngữ cảnh khi vượt cửa sổ token. |

**Chế độ hoạt động & hiệu năng:**

| Chỉ tiêu | M1 | M2 |
| :--- | :--- | :--- |
| Chế độ vận hành | Chat text + xử lý file ghi âm offline | Voice gần real-time |
| Thời gian nạp Call Brief | $\le5$ giây | $\le3$ giây |
| Thời gian phản hồi mỗi lượt (p95) | Chat: TTFT $p95\le3$ giây; Total Latency $p95\le8$ giây. | Voice: TTFA $p95\le2.5$ giây |
| Số phiên đồng thời (demo) | 1 | $\ge2$ |

*Lưu ý quan trọng:* M1 không yêu cầu voicebot nói chuyện real-time. Chế độ chat text + đọc file ghi âm là đủ để chứng minh toàn bộ ý tưởng về bộ nhớ và harness. Đừng dồn cả 4 tuần vào việc ghép voice pipeline rồi không còn thời gian làm phần bộ nhớ và đánh giá.

### C.3. Áp dụng MCP hoặc A2A (chọn ít nhất một, giải thích lý do chọn)

*   **Hướng 1 - MCP (Model Context Protocol):** đóng gói hệ thống nghiệp vụ thành MCP server thay vì hard-code trong agent.
    *   **M1:** Xây $\ge2$ MCP server, trong đó bắt buộc có `mcp-memory` (đọc/ghi bộ nhớ khách hàng) - đây là server thú vị nhất của bài này. Server còn lại tự chọn: `mcp-catalog` hoặc `mcp-crm`.
    *   **M2:** Thêm `mcp-order`, `mcp-knowledge` (RAG chính sách/FAQ), phân quyền theo tool (tool nào được ghi dữ liệu).
*   **Hướng 2 - A2A / Multi-agent:** nhiều agent chuyên biệt phối hợp với nhau.

| Mức | Agent | Trách nhiệm |
| :--- | :--- | :--- |
| | Orchestrator / Router | Điều phối, quyết định agent nào xử lý lượt thoại này |
| **M1** | Context & Memory Agent | Nhận diện khách, dựng Call Brief, quyết định ghi gì vào bộ nhớ |
| | Sales Advisor Agent | Tư vấn sản phẩm dựa trên profile khách |
| **M2** | Policy & Compliance Agent | Chặn bịa giá / cam kết sai chính sách / lộ thông tin cá nhân |
| | QA/Evaluator Agent | Chấm điểm cuộc gọi theo rubric (mục C.4) |

*Yêu cầu chung:* các agent phải thật sự chia sẻ trạng thái và chuyển giao nhiệm vụ cho nhau, không phải một chuỗi prompt gọi tuần tự rồi đặt tên cho oai. Nhóm phải chỉ ra được ít nhất một tình huống cụ thể mà tách agent giúp hệ thống tốt hơn.

### C.4. Đánh giá hệ thống (trọng tâm)

Phải có script đánh giá chạy được bằng một lệnh và in ra bảng chỉ số – không chấp nhận số liệu chép tay trong slide. Công thức tính từng chỉ số xem Phụ lục A; mẫu định dạng kịch bản test xem Phụ lục B.

**Bộ test:**
*   **M1:** $\ge20$ kịch bản đa phiên (mỗi kịch bản gồm 2-3 cuộc gọi liên tiếp cùng 1 khách, có kỳ vọng rõ ràng ở từng cuộc) + $\ge5$ kịch bản khó, chọn trong: khách đổi ý giữa chừng; khách đưa thông tin mâu thuẫn với phiên trước; khách đòi áp khuyến mãi đã hết hạn - khách hỏi thông tin không có trong tài liệu (agent phải nói không biết, không được bịa).
*   **M2:** $\ge40$ kịch bản + agent đóng vai khách hàng (customer simulator) để chạy đánh giá tự động lặp lại được, có mức kiên nhẫn giảm dần mỗi lần bị hỏi lại.

**Chỉ số bắt buộc M1** (chỉ 5 con số, nhưng phải đo đúng):

| Chỉ số | Ý nghĩa |
| :--- | :--- |
| **Repeat-Question Rate ★** | % câu hỏi lặp lại thông tin hệ thống đã biết – KPI số 1 của đề bài |
| **Context Carryover Rate** | % thông tin quan trọng từ phiên trước được dùng đúng ở phiên sau |
| **Task Success Rate** | % kịch bản đạt được mục tiêu đề ra |
| **Hallucination Rate** | % phát ngôn bịa thông tin giá / khuyến mãi / chính sách |
| **WER/CER** | Độ chính xác ASR, kèm độ chính xác riêng cho số tiền và số điện thoại |

*   **M2 Thêm:** Calls-to-Close; Tool-Call Accuracy; Recall@k của phần RAG; độ trễ $p50/p95$ - chi phí ước tính mỗi cuộc gọi.
*   **M1 Baseline bắt buộc:** phải chạy song song một phiên bản không có bộ nhớ (mỗi cuộc gọi độc lập, giống hệ thống call center hiện tại) trên cùng bộ test, và trình bày bảng so sánh chênh lệch. Không có baseline thì mọi con số đều vô nghĩa.
*   **Ngưỡng kỳ vọng:** Repeat-Question Rate giảm $\ge40\%$ so với baseline; Task Success Rate $\ge70\%$; Hallucination Rate về giá $\le5\%$.
*   **M2 Dùng LLM để chấm điểm (LLM-as-a-judge):** phải có rubric rõ ràng (không chấm kiểu "cho điểm 1-10" chung chung) và đối chiếu với người: nhóm tự chấm tay $\ge20$ mẫu, báo cáo tỷ lệ đồng thuận với LLM.

### C.5. Cơ chế cải tiến theo thời gian

*   **Ràng buộc:** KHÔNG được huấn luyện lại / fine-tune mô hình. Mọi cải tiến phải đến từ dữ liệu, bộ nhớ, prompt/kịch bản và cách điều phối. Ràng buộc này có chủ đích: buộc nhóm giải bài toán bằng thiết kế hệ thống, không phải bằng GPU.
*   **Nguồn feedback:** M1 thu ít nhất 2 trong số: kết quả cuộc gọi (chốt / hẹn lại / từ chối); điểm chấm tự động từ bộ đánh giá; nút like/dislike của nhân viên trên từng gợi ý mà hệ thống đưa ra; việc khách phải nhắc lại thông tin.
*   **Cơ chế cải tiến:** M1 hiện thực ít nhất 1, M2 ít nhất 2:
    1.  *(M1)* **Knowledge Gap Loop** (dễ nhất, nên chọn đầu tiên): câu hỏi agent không trả lời được sẽ tự động ghi lại thành danh sách thiếu sót → bổ sung vào tài liệu → tự động thêm vào bộ test để lần sau không tái phạm.
    2.  *(M1)* **Exemplar Bank** – cuộc gọi chốt đơn thành công được lưu thành ví dụ mẫu, lần sau gặp tình huống tương tự thì lấy ra làm few-shot.
    3.  *(M2)* **Reflection** - sau mỗi cuộc gọi, agent tự viết "bài học rút ra" có cấu trúc, được kiểm tra rồi mới ghi vào bộ nhớ.
    4.  *(M2)* **A/B test kịch bản** - chạy song song 2 biến thể cách xử lý phản đối, so sánh tỷ lệ chốt, giữ cái tốt hơn.
*   **M1 Chứng minh bằng số:** chạy hệ thống ở vòng 0, thu feedback, áp dụng cải tiến, chạy lại vòng 1 trên cùng một bộ test giữ nguyên, và trình bày chênh lệch. Chỉ cần 2 vòng là đủ.
*   **M2:** 3 vòng trở lên + phân tích trường hợp cải tiến gây hại.
*   **M1 An toàn:** thay đổi nào cần người duyệt trước khi áp dụng? Chống việc hệ thống học nhầm rằng "hứa đại cho khách chốt đơn" là chiến lược tốt - cơ chế quay lui khi chỉ số tụt.

### C.6. Sản phẩm & Demo

| Hạng Mục | M1 Cơ bản | M2 Nâng cao |
| :--- | :--- | :--- |
| **Giao diện** | Web đơn giản là đủ, không cần đẹp, khung hội thoại. Call Brief hiện ra khi khách gọi lại. Dòng thời gian bộ nhớ của khách (đã tương tác gì, khi nào). | Thêm: gợi ý câu trả lời cho nhân viên (chế độ copilot). Cảnh báo khi agent sắp cam kết sai. Dashboard hiển thị các chỉ số ở C.4. |
| **Kịch bản demo chạy trực tiếp** | **Cuộc 1:** khách liên hệ lần đầu, được tư vấn, có báo giá + khuyến mãi, hẹn "để hỏi người nhà".<br>**Cuộc 2** (vài ngày sau, cùng khách): hệ thống nhận diện khách, nạp Call Brief, mở đầu bằng xác nhận tiếp nối, không hỏi lại bất kỳ thông tin nào đã có, và chốt đơn. | **Cuộc 3:** khách gọi lại sau khi đã đặt hàng để đổi size / hỏi vận đơn – hệ thống biết đơn nào và cập nhật bộ nhớ tương ứng. |

*Kèm theo: chạy script đánh giá trực tiếp để cho thấy con số so với baseline.*

---

## D. RÀNG BUỘC

*   Không cần huấn luyện mô hình. Dùng model có sẵn (local hoặc API). Điểm đến từ thiết kế dữ liệu, kiến trúc, đánh giá và cải tiến – không đến từ điểm benchmark của model.
*   ASR phải chạy được local (Whisper bản nhỏ chạy được trên laptop hoặc Google Colab miễn phí). LLM được phép dùng API để nhóm không bị chặn bởi phần cứng. Chạy được toàn bộ LLM local là điểm thưởng, không bắt buộc.
*   Không dùng ghi âm khách hàng thật chưa ẩn danh và chưa có sự đồng ý → vi phạm là loại.
*   Toàn bộ trải nghiệm bằng tiếng Việt tự nhiên, đúng ngữ điệu bán hàng Việt Nam (dạ/vâng/ạ, xưng hô anh/chị/em theo ngữ cảnh).
*   Mã nguồn chạy được theo hướng dẫn trong README.
*   Agent không được giả vờ là người thật nếu khách hỏi trực tiếp.

**Ba lỗi khiến nhóm mất điểm nhiều nhất:**
1.  Dồn 3 tuần vào ghép voice real-time rồi không kịp làm bộ nhớ và đánh giá - M1 không cần voice;
2.  Để đến tuần cuối mới làm phần đánh giá, dẫn tới không có baseline và không có số liệu;
3.  Dataset toàn cuộc gọi rời rạc, không có khách đa phiên, nên không demo được đúng bài toán.

---

## E. GỢI Ý CÔNG NGHỆ & LỘ TRÌNH

*   **Combo gợi ý cho nhóm mới bắt đầu** (chạy được nhanh, ít rủi ro): `faster-whisper` (ASR) + LLM qua API + `ChromaDB` (bộ nhớ & RAG) + `LangGraph` hoặc tự viết vòng lặp bằng Python thuần + `FastAPI` + giao diện `Streamlit`. Tự viết vòng lặp harness bằng Python thuần hoàn toàn được chấp nhận và thường dễ giải thích khi phản biện hơn là dùng framework.
*   **ASR tiếng Việt:** PhoWhisper / Whisper / faster-whisper / wav2vec2-vi
*   **TTS tiếng Việt (để sinh dataset):** edge-tts (miễn phí, dễ nhất) / viXTTS / F5-TTS-Vietnamese
*   **Tách người nói:** Silero VAD / pyannote.audio
*   **LLM:** API (Claude, GPT, Gemini); local: Qwen, Llama, Gemma, Vistral, PhoGPT - chạy bằng Ollama/vLLM.
*   **Embedding tiếng Việt:** bge-m3 / multilingual-e5 / Vietnamese-SBERT
*   **Bộ nhớ / Vector DB:** ChromaDB / Qdrant / pgvector / SQLite (cho profile). Memo, Zep (framework có sẵn).
*   **Agent orchestration:** LangGraph / CrewAI / AutoGen / Pydantic AI - hoặc Python thuần.
*   **MCP:** Anthropic MCP SDK / FastMCP
*   **Đánh giá:** RAGAS / DeepEval / promptfoo / Langfuse (theo dõi) - hoặc tự viết script chấm.
*   **Backend / Frontend:** FastAPI / Streamlit (nhanh nhất) / Next.js/React

**Lộ trình gợi ý 4 tuần bám theo thứ tự này để không bị vỡ tiến độ:**
*   **Tuần 1:** sinh dataset (ưu tiên làm nhóm khách đa phiên trước) - dựng pipeline ASR + chuẩn hóa số - thiết kế schema bộ nhớ.
*   **Tuần 2:** vòng lặp harness + 3 tool mock + Session Continuity & Call Brief – đây là trái tim của bài, xong sớm sẽ nhàn.
*   **Tuần 3:** bộ test + script đánh giá + chạy baseline không-bộ-nhớ - đo số lần đầu tiên.
*   **Tuần 4:** 1 cơ chế cải tiến + đo lại vòng 2 - giao diện - quay demo - viết báo cáo.

---

## F. SẢN PHẨM NỘP

| Hạng mục | Yêu cầu |
| :--- | :--- |
| **Mã nguồn** | Repo có README, hướng dẫn cài đặt và chạy, script khởi tạo dữ liệu |
| **Dataset** | Bộ dữ liệu + mô tả ngắn: cách sinh, phân bố, hạn chế, cách xử lý thông tin cá nhân |
| **Tài liệu kiến trúc** | Sơ đồ hệ thống & vòng lặp harness - thiết kế bộ nhớ - danh sách tool - các quyết định thiết kế và lý do |
| **Báo cáo đánh giá** | Bảng chỉ số, so sánh với baseline không-bộ-nhớ, kết quả trước/sau khi cải tiến, phân tích $\ge10$ trường hợp hệ thống làm sai |
| **Video demo** | 5-8 phút, bắt buộc có kịch bản 2 cuộc gọi ở mục C.6 |
| **Website** | Phải có những tính năng bắt buộc |
| **Slide** | Tối đa 15 slide |

---

## G. TIÊU CHÍ ĐÁNH GIÁ VÒNG 1

| # | Tiêu chí | Mô tả | Hệ số |
| :--- | :--- | :--- | :--- |
| 1 | **Dữ liệu & xử lý tiếng Việt** | Dataset đủ và hợp lý, đặc biệt là nhóm khách đa phiên; chất lượng ASR và chuẩn hóa số tiền/SĐT; chất lượng trích xuất thông tin có cấu trúc; xử lý thông tin cá nhân | 12% |
| 2<br>3 | **Kiến trúc & Harness Agent**<br>**Áp dụng MCP / A2A** | Session Continuity: nhận diện khách gọi lại + Call Brief + không hỏi lại (bắt buộc) - thiết kế bộ nhớ phân tầng, xử lý khách đổi ý. Vòng lặp harness rõ ràng, có kiểm soát: guardrail chống bịa giá, fallback khi lỗi. Độ phù hợp của kiến trúc với bài toán - chất lượng tích hợp tool (đúng schema, xử lý lỗi) - giải thích thuyết phục lý do chọn. Nếu multi-agent: các agent có phối hợp thật sự không. | 22%<br>15% |
| 4 | **Đánh giá hệ thống** | Script đánh giá chạy được, tái lập được - bộ test đa phiên + ca khó đủ 5 chỉ số M1; có baseline không-bộ-nhớ để so sánh - phân tích lỗi nghiêm túc | 15% |
| 5<br>6 | **Cơ chế cải tiến**<br>**Trải nghiệm & demo** | Vòng lặp feedback hoạt động thật - chứng minh cải thiện bằng số qua 2 vòng trên cùng bộ test; có kiểm soát của con người trước khi áp dụng thay đổi. Giao diện dùng được cho telesale thật; hội thoại tiếng Việt tự nhiên; demo thuyết phục; ước lượng tác động kinh doanh; tính sáng tạo ngoài yêu cầu | 13%<br>13% |
| 7 | **Khả năng mở rộng & chi phí** | Kiến trúc mở rộng được theo số khách hàng - ước tính chi phí mỗi cuộc gọi; khả năng thêm ngành hàng/kênh mới | 5% |
| 8 | **Trình bày & phản biện** | Trình bày rõ ràng, logic, trung thực về hạn chế - trả lời phản biện chính xác | 5% |
| | | **TỔNG** | **100%** |

**Điểm thưởng (tối đa +5%) – chỉ tính khi phần M1 đã hoàn chỉnh:**
*   Voicebot nói chuyện real-time mượt, có xử lý khách ngắt lời.
*   Nhận diện khách qua giọng nói (voiceprint) khi gọi từ số lạ; xử lý được ca hai người dùng chung một số điện thoại.
*   Chạy được toàn bộ hệ thống (kể cả LLM) trên máy local với phần cứng phổ thông.
*   Tối ưu kịch bản/prompt tự động (DSPy, TextGrad, GEPA hoặc tự viết vòng lặp); ablation chỉ ra cơ chế cải tiến nào thực sự tạo khác biệt.
*   Tầng bộ nhớ Playbook: tự đúc kết cách xử lý phản đối hiệu quả theo từng persona.
*   Phát hiện realtime khi nhân viên cam kết sai chính sách và cảnh báo ngay trong cuộc gọi. Dự đoán xác suất chốt đơn và đề xuất thời điểm gọi lại tối ưu; phát hiện drift khi phân phối câu hỏi thay đổi. Kết nối MCP server có sẵn ngoài đời (Google Calendar cho lịch gọi lại, Google Sheets/Notion cho bảng giá).

**Điểm trừ nặng:**
*   Không có Session Continuity (khách gọi lại vẫn bị hỏi từ đầu) → mất phần lớn hạng mục 2.
*   Không có baseline so sánh → mất phần lớn hạng mục 4.
*   Số liệu báo cáo không tái lập được bằng code → coi như không có số liệu.
*   Dùng dữ liệu khách hàng thật trái phép → loại.

---

## PHỤ LỤC A - CÁCH TÍNH CÁC CHỈ SỐ BẮT BUỘC

Phần này quy định cách tính thống nhất để ban giám khảo so sánh được giữa các nhóm. Nhóm nào tính khác phải nêu rõ và giải thích lý do trong báo cáo.

### A.1. Repeat-Question Rate (RQR) – tỷ lệ hỏi lại – KPI số 1
*   **Đo cái gì:** agent có đang hỏi khách những điều mà hệ thống đã biết từ trước cuộc gọi hay không. Đây là con số phản ánh trực tiếp nỗi đau ở Case 1.
*   `RQR = (Số câu hỏi thừa) / (Tổng số câu hỏi agent đặt ra) × 100%`
*   **Thế nào là "câu hỏi thừa":** mỗi câu hỏi của agent được gán về một slot thông tin (ngân sách, diện tích phòng, size, màu, địa chỉ, sản phẩm quan tâm...). Nếu slot đó đã có giá trị hợp lệ trong bộ nhớ trước khi cuộc gọi bắt đầu thì câu hỏi đó bị tính là thừa.
*   **Ba trường hợp KHÔNG tính là thừa:**
    1.  Câu xác nhận: "Dạ chị vẫn lấy size L đúng không ạ?" Đây là hành vi đúng, được khuyến khích. Chỉ câu hỏi mở ("Chị mặc size mấy ạ?") mới bị tính.
    2.  Thông tin đã hết hạn theo quy tắc TTL nhóm tự định nghĩa (ví dụ địa chỉ giao hàng quá 6 tháng thì hỏi lại là hợp lý).
    3.  Thông tin thực sự mới, chưa từng xuất hiện ở phiên trước.
*   **Cách gán nhãn tự động:** trong file kịch bản test, khai báo sẵn trường `must_not_ask` liệt kê các slot mà agent không được hỏi lại (xem Phụ lục B). Script đánh giá chỉ cần đối chiếu câu hỏi của agent với danh sách này – không cần chấm tay.
*   **Ví dụ tính:** ở cuộc gọi thứ 2, agent đặt 6 câu hỏi, trong đó 3 câu hỏi lại về diện tích phòng, ngân sách, và có trẻ nhỏ hay không; cả 3 slot này đều đã có trong profile. $\rightarrow RQR = 3/6 = 50\%$.
*   **So với baseline:** đề yêu cầu giảm $\ge 40\%$, hiểu là giảm tương đối:
    `Mức giảm = (RQR_baseline - RQR_hệ_thống) / RQR_baseline × 100%`
    Ví dụ: baseline 83%, hệ thống 50% $\rightarrow (83-50)/83 = 39.8\%$ → CHƯA đạt ngưỡng 40%.

### A.2. Context Carryover Rate (CCR) – tỷ lệ mang ngữ cảnh sang phiên sau
*   **Đo cái gì:** ngược với RQR. RQR phạt việc hỏi thừa; CCR thưởng việc dùng đúng thông tin cũ. Cần cả hai vì một agent im lặng không hỏi gì cũng đạt $RQR=0\%$ nhưng vô dụng.
*   `CCR = (Số fact được sử dụng đúng) / (Số fact bắt buộc mang sang) × 100%`
*   **Cách xác định:** mỗi kịch bản test khai báo trước danh sách `must_carry_over` - những thông tin bắt buộc phải được mang sang phiên sau. Thế nào là "sử dụng đúng": fact đó xuất hiện ở đúng chỗ có ý nghĩa – trong lời thoại của agent, hoặc trong tham số của một lệnh gọi tool. Mỗi fact chỉ tính tối đa 1 lần.
*   *Cảnh báo khi thiết kế chỉ số này:* đừng để agent "cày điểm" bằng cách đọc vẹt toàn bộ thông tin cũ vào câu chào. Nhóm nên bổ sung quy tắc chấm: fact chỉ được tính khi nó phục vụ đúng mục đích ở lượt thoại đó.

### A.3. Task Success Rate (TSR) – tỷ lệ hoàn thành nhiệm vụ
*   `TSR = (Số kịch bản đạt) / (Tổng số kịch bản) × 100%`
*   **Quan trọng - chấm nhị phân bằng assertion, không chấm cảm tính.** Mỗi kịch bản khai báo trước điều kiện thành công dưới dạng kiểm tra được bằng code, ví dụ: Agent đã gọi `order.create` với đúng SKU, đúng size, đúng giá đã cam kết ở phiên trước. Hoặc (ca khó): agent không gọi tool nào và trả lời rằng mình không có thông tin.
*   Nếu điều kiện thành công phụ thuộc vào chất lượng lời thoại (khó assert), nhóm dùng LLM-as-a-judge với rubric - nhưng phải nêu rõ kịch bản nào chấm bằng assertion, kịch bản nào chấm bằng judge.

### A.4. Hallucination Rate (HR) – tỷ lệ bịa thông tin
*   Đơn vị đếm là "claim", không phải lượt thoại. Một claim kiểm chứng được là bất kỳ phát ngôn nào của agent khẳng định một dữ kiện có thể đối chiếu với nguồn sự thật.
*   `HR = (Số claim sai) / (Tổng số claim kiểm chứng được) × 100%`
*   Ví dụ: agent nói "Dạ máy này giá 4.890.000đ, đang có khuyến mãi tặng bộ lọc, giao trong 2 ngày ạ" $\rightarrow 3$ claim. Nếu catalog ghi giá 5.200.000đ và khuyến mãi đã hết hạn $\rightarrow 2$ claim sai. Riêng lượt này $HR = 2/3$.

### A.5. WER/CER và độ chính xác thực thể
*   **WER (Word Error Rate)** – tỷ lệ lỗi ở mức từ, tính bằng khoảng cách chỉnh sửa giữa câu ASR nhận ra và câu đúng (ground truth):
    $WER = (S + D + I) / N \times 100\%$
    ($S$ = số từ bị thay sai; $D$ = số từ bị thiếu; $I$ = số từ bị thêm thừa; $N$ = tổng số từ trong câu đúng).
*   **CER (Character Error Rate)** - công thức tương tự nhưng đếm trên ký tự. Nên báo cáo cả hai vì WER rất nhạy với lỗi dấu thanh. Chuẩn hóa trước khi tính - phải nêu rõ trong báo cáo đã chuẩn hóa những gì.
*   **Entity Accuracy** quan trọng hơn WER trong bài này:
    `Entity Accuracy = (Số thực thể trích xuất đúng hoàn toàn) / (Tổng số thực thể) × 100%`
    Áp dụng cho số điện thoại và số tiền, so khớp chính xác tuyệt đối (exact match) sau khi chuẩn hóa.

### A.6. Bảng so sánh bắt buộc trong báo cáo

| Chỉ số | Baseline (không bộ nhớ) | Hệ thống của nhóm | Chênh lệch |
| :--- | :--- | :--- | :--- |
| Repeat-Question Rate | | | giảm ...% |
| Context Carryover Rate | | | |
| Task Success Rate | | | |
| Hallucination Rate (giá & KM) | | | |
| Số lượt thoại trung bình / kịch bản | | | |

*Baseline và hệ thống phải chạy trên cùng bộ test, cùng model, cùng tham số – chỉ khác duy nhất ở việc có nạp bộ nhớ phiên trước hay không.*

---

## PHỤ LỤC B - MẪU ĐỊNH DẠNG KỊCH BẢN TEST

Đây là gợi ý định dạng, nhóm được tự thiết kế lại. Điểm mấu chốt: mọi thứ dùng để chấm điểm đều phải khai báo trước trong file, để script đánh giá tự chấm được mà không cần người ngồi nghe.

```json
{
  "scenario_id": "SC-07",
  "persona": "khach_do_du_hoi_nguoi_nha",
  "customer_phone": "0982xxxxxx",
  "call_1": {
    "customer_goal": "hoi may loc khong khi cho phong 25m2, ngan sach 5tr",
    "facts_established": {
      "room_area_m2": 25,
      "has_children": true,
      "budget_vnd": 5000000,
      "product_advised": "SKU-AP-X",
      "price_quoted_vnd": 4890000,
      "promo_code": "GIFT-FILTER",
      "promo_expiry": "2026-03-16",
      "blocker": "can hoi chong"
    },
    "expected_outcome": "hen_goi_lai"
  },
  "call_2": {
    "days_later": 2,
    "must_carry_over": [ // dùng để tính Context Carryover Rate
      "product_advised", "price_quoted_vnd", "room_area_m2", "blocker"
    ],
    "must_not_ask": [ // dùng để tính Repeat-Question Rate
      "room_area_m2", "budget_vnd", "has_children", "product_advised"
    ],
    "success_if": { // dùng để tính Task Success Rate
      "tool_called": "order.create",
      "args_match": { "sku": "SKU-AP-X", "price_vnd": 4890000}
    },
    "ground_truth_facts": { // dùng để tính Hallucination Rate
      "price_vnd": 4890000,
      "promo_active": true,
      "in_stock": true,
      "delivery_days": 2
    }
  }
}
```

*Vì sao nên làm file test trước khi code agent:* khi bộ test đã định nghĩa rõ "không được hỏi lại cái gì" và "thành công nghĩa là gì", việc thiết kế bộ nhớ và harness trở nên rõ ràng hơn hẳn. Đây cũng là lý do lộ trình đặt phần đánh giá ở tuần 3 chứ không phải tuần cuối.

---

## PHỤ LỤC C - GIẢI THÍCH THUẬT NGỮ

### C.1. Thuật ngữ AI / kỹ thuật

| Thuật ngữ | Giải thích |
| :--- | :--- |
| **Agent** | Chương trình dùng LLM để tự quyết định hành động: đọc ngữ cảnh → chọn việc cần làm → gọi công cụ → xem kết quả → làm tiếp, lặp cho đến khi xong nhiệm vụ. |
| **Harness** | Phần "khung xương" bao quanh LLM: code điều khiển vòng lặp, quản lý ngữ cảnh đưa vào prompt, gọi tool, bắt lỗi, áp guardrail, ghi nhớ. LLM là bộ não; harness là toàn bộ phần còn lại. |
| **Tool/Function calling** | Cơ chế cho LLM gọi hàm do lập trình viên định nghĩa (tra tồn kho, tạo đơn) thay vì tự bịa câu trả lời. |
| **Guardrail** | Lớp kiểm tra chặn agent làm điều không được phép - ở bài này là: không báo giá không có trong catalog, không hứa chính sách sai, không đọc thông tin cá nhân của khách khác. |
| **Fallback** | Phương án dự phòng khi có sự cố (tool lỗi, ASR trả rác): agent nói gì với khách thay vì đứng im. |
| **Baseline** | Phiên bản đối chứng đơn giản để so sánh. Ở đề này là hệ thống không có bộ nhớ. |
| **RAG** | Retrieval-Augmented Generation. Tìm các đoạn tài liệu liên quan rồi đưa vào prompt để LLM trả lời dựa trên đó. |
| **Embedding/ Vector DB** | Embedding biến đoạn text thành dãy số; Vector DB lưu và tìm nhanh các đoạn có ý nghĩa gần nhất. |
| **Recall@k** | Trong k đoạn tài liệu lấy ra, có bao nhiêu phần trăm trường hợp chứa được đoạn đúng cần thiết. |
| **Working/Episodic/Profile memory** | Ba tầng bộ nhớ: working = ngữ cảnh lượt thoại hiện tại; episodic = tóm tắt từng cuộc gọi; profile = sự thật bền vững về khách. |
| **TTL/decay** | Thời hạn sống của một mẫu ký ức. |
| **Memory poisoning** | Bộ nhớ bị ghi nhầm thông tin sai và agent luôn hành xử dựa trên dữ kiện sai đó. |
| **Identity resolution** | Xác định các định danh khác nhau (SĐT, Zalo ID, FB ID) thực chất là cùng một người. |
| **Session / phiên** | Một lần tương tác trọn vẹn (một cuộc gọi, một đoạn chat). Bài toán lõi là giữ ngữ cảnh xuyên phiên. |
| **Call Brief** | Bản tóm tắt ngắn về khách được nạp cho agent ngay trước khi bắt máy. |
| **ASR/TTS/VAD/ Diarization** | ASR: giọng nói $\rightarrow$ text. TTS: text $\rightarrow$ giọng nói. VAD: phát hiện tiếng nói. Diarization: tách người nói. |
| **ITN** | Inverse Text Normalization - chuyển chữ viết ra thành ký hiệu chuẩn: "bốn triệu tám" $\rightarrow$ 4.800.000. |
| **WER/CER** | Tỷ lệ lỗi ASR ở mức từ / mức ký tự. |
| **Hallucination** | LLM nói ra thông tin nghe hợp lý nhưng sai sự thật (nguy hiểm nhất là bịa giá/khuyến mãi). |
| **Few-shot/Exemplar** | Đưa vài ví dụ mẫu vào prompt để LLM bắt chước cách làm. |
| **LLM-as-a-judge / Rubric / Golden set / Customer simulator** | Dùng LLM chấm điểm theo bảng tiêu chí định sẵn (Rubric). Golden set: Bộ test chuẩn. Customer simulator: Agent đóng vai khách hàng. |
| **Ablation** | Tắt bớt từng thành phần rồi đo lại để biết thành phần nào thực sự tạo ra cải thiện. |
| **Drift** | Phân phối dữ liệu thực tế thay đổi theo thời gian khiến hệ thống dần kém đi. |
| **Human-in-the-loop** | Có người duyệt trước khi hệ thống tự áp dụng thay đổi. |
| **MCP** | Model Context Protocol - chuẩn chung để agent kết nối tới nguồn dữ liệu và công cụ. |
| **A2A/Multi-agent** | Kiến trúc nhiều agent chuyên biệt cùng xử lý một nhiệm vụ. |
| **PII** | Personally Identifiable Information - thông tin định danh cá nhân (họ tên, SĐT, CCCD). |
| **$p50/p95$** | Phân vị độ trễ. $p95 = 95\%$ số lượt phản hồi nhanh hơn con số này. |

### C.2. Thuật ngữ nghiệp vụ call center / bán hàng

| Thuật ngữ | Giải thích |
| :--- | :--- |
| **Telesale** | Bán hàng qua điện thoại – nhân viên gọi ra hoặc nhận cuộc gọi đến để tư vấn và chốt đơn. |
| **Lead** | Khách hàng tiềm năng đã để lại thông tin liên hệ nhưng chưa mua. |
| **Chốt đơn** | Thuyết phục được khách đồng ý mua và tạo được đơn hàng. |
| **Objection (phản đối)** | Lý do khách viện ra để chưa mua: "đắt quá", "để hỏi vợ đã". |
| **Call script/Playbook** | Kịch bản hội thoại mẫu mà nhân viên bám theo. |
| **Upsell/Cross-sell** | Bán phiên bản cao cấp hơn / bán thêm sản phẩm đi kèm. |
| **Escalate (chuyển máy)** | Chuyển cuộc gọi lên nhân viên có thẩm quyền hoặc từ bot sang người thật. |
| **Handoff brief** | Bản tóm tắt bàn giao khi chuyển máy. |
| **AHT** | Average Handling Time - thời lượng trung bình xử lý một cuộc gọi. |
| **Calls-to-Close** | Số cuộc gọi trung bình cần để chốt được một đơn. |
| **Conversion rate** | Tỷ lệ khách được tư vấn thực sự mua hàng. |
| **CSAT** | Customer Satisfaction - điểm hài lòng khách chấm. |
| **QA (call center)** | Bộ phận nghe lại ghi âm để chấm chất lượng. |
| **COD** | Cash on Delivery - thanh toán khi nhận hàng. |
| **Hoàn hàng** | Khách từ chối nhận, hàng bị trả về – shop chịu phí ship 2 chiều. |
| **SKU** | Mã định danh một phiên bản sản phẩm cụ thể. |
| **Hotline/OA/Fanpage** | Các kênh khách liên hệ. |
| **Pending queue** | Hàng đợi các khách đã tư vấn nhưng chưa chốt, cần gọi lại. |

*Hết đề*