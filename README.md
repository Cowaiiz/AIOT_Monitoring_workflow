# Industrial AI Monitoring Framework

Demo kiểm tra bất thường ảnh PCB4: **ảnh → AI → Node-RED → cảnh báo → web nội bộ**.

## Bắt đầu từ đây

| Bạn muốn… | Mở |
|---|---|
| Đọc báo cáo tiến độ gửi thầy | [Báo cáo tổng hợp](reports/BAO_CAO_TIEN_DO.md) |
| Chạy giao diện Inspect và workflow | [Hướng dẫn demo](demo/README.md) |
| Chuẩn bị dữ liệu hoặc chạy baseline | [Hướng dẫn mô hình](model/TRAINING_README.md) |
| Đối chiếu số liệu và kiểm thử | [Bằng chứng kết quả](reports/evidence/verification-summary.json) |
| Xem giai đoạn dùng dữ liệu giả lập | [Demo HTTP cũ](legacy/http-mock/README.md) |

## Cấu trúc repo

| Thư mục | Nội dung |
|---|---|
| `demo/` | Web Inspect, dịch vụ inference, SQLite, flow Node-RED, script deploy và kiểm thử |
| `model/` | Chuẩn bị VisA PCB4, train baseline và hướng dẫn môi trường |
| `reports/` | Báo cáo tiếng Việt, manifest chia tập và kết quả thực đo |
| `legacy/http-mock/` | Mã và kết quả demo giả lập trước khi nối AI thật |

## Chạy demo

Cần chuẩn bị môi trường Python, dataset và checkpoint theo [hướng dẫn mô hình](model/TRAINING_README.md). Repo không chứa dataset, trọng số, môi trường `.venv`, cache hoặc database vận hành. Script hiện sử dụng các đường dẫn Windows của môi trường đã thử; đọc [điều kiện chạy](demo/README.md#điều-kiện-chạy) khi dùng máy khác.

Giữ Node-RED chạy ở cổng 1880. Từ thư mục gốc repo:

```powershell
& "D:\Project\aiot-model\.venv\Scripts\python.exe" .\demo\start_demo.py
```

Sau khi terminal báo hoàn tất kiểm tra, mở http://localhost:1880/giang-pcb4/v1/demo . Giữ dịch vụ model chạy.

Chỉ cập nhật giao diện khi cả hai dịch vụ đang chạy:

```powershell
& "D:\Project\aiot-model\.venv\Scripts\python.exe" .\demo\update_ui.py
```

**Lưu ý khi đang dùng bản cũ:** lần sắp xếp repo này không di chuyển dịch vụ hoặc database trên máy đang chạy. Bạn vẫn dùng được các lệnh cũ trong thư mục dự án hiện tại. Nếu chuyển sang bản checkout mới, đọc [hướng dẫn chuyển thư mục](demo/README.md#chuyển-từ-cấu-trúc-cũ) trước khi chạy, để giữ database và tránh mở trùng dịch vụ.

## Trạng thái thực tế

- Đã chạy AI thật trên VisA PCB4, tích hợp HTTP, lưu SQLite và deploy giao diện Inspect.
- Baseline do Giang tự chạy: **Image AUROC 94,11%, recall 31%**, bỏ sót 69/100 ảnh lỗi ở ngưỡng hiện tại. Chưa có lần cải thiện mô hình; chưa dùng để kết luận sản phẩm tốt.
- Script HTTP và cập nhật UI đã kiểm chứng thành công. Kiểm thử đầy đủ UI mới và restart tiến trình thực còn chưa hoàn tất.
- Tham khảo [repo của Bảo](https://github.com/RoyalB26/AIoT_H261). Không dùng checkpoint Bảo bàn giao và không nhận benchmark của Bảo là kết quả tái lập của Giang.
- Source trên GitHub không công khai dịch vụ localhost. Chưa có camera, MQTT hoặc cảm biến thật.

Số liệu, phân công, giới hạn và mốc công việc tiếp theo được trình bày trong [báo cáo tiến độ](reports/BAO_CAO_TIEN_DO.md).
