# Inspect: demo ảnh PCB4 và Node-RED

Trạng thái 22/10/2026: model thật đã nối HTTP, SQLite và UI Inspect đã deploy. Nguồn/HTML khớp deploy và cảnh báo giữ nguyên theo script. Các thao tác UI trước đợt thiết kế lại đã được người dùng thử; chưa có kiểm thử browser tự động cho toàn bộ UI Inspect mới. Xem [báo cáo tiến độ](../Report/BAO_CAO_TIEN_DO.md).

## Thành phần

- `model_service.py`: nạp model.pt cục bộ, suy luận, heatmap/overlay; bind 127.0.0.1:1891.
- `storage.py`: SQLite, transaction, fingerprint, cảnh báo/ACK, backup/migration.
- `index.html`: kéo thả ảnh, đối chiếu heatmap, kết quả, tìm/lọc/phân trang và xác nhận cảnh báo.
- `build_flow.py`, `flow.json`: nguồn sinh và flow import; tab `giang_pcb4_real_v1`, 5 route `/giang-pcb4/v1`.
- `start_demo.py`: backup, khởi động dịch vụ, deploy riêng tab theo revision, kiểm tra HTTP.
- `update_ui.py`: chỉ cập nhật function phục vụ UI, không dừng model.
- `test_storage.py`: 7 nhóm unit test; `check_local.py`: đối chiếu score 3 ảnh với baseline.

## Điều kiện chạy

Đây là snapshot môi trường Windows đã thử, chưa phải bộ cài đa nền tảng. Cần Node-RED ở cổng 1880, môi trường Python đã cài torch/torchvision/anomalib tương thích, dataset PCB4 và checkpoint. Xem [hướng dẫn mô hình](../bao-model/TRAINING_README.md). Dataset và checkpoint không có trong Git.

Mã hiện tham chiếu `D:/Project/aiot-model/runs/visa-pcb4-20261022-213717` trong model_service.py, dataset dưới `D:/Project/aiot-model/datasets/visa`. Sửa đường dẫn RUN/dataset nếu dùng máy hoặc lần train khác. `check_local.py` và phần kiểm chứng startup dùng test-predictions.json cùng run. Không trộn checkpoint với ngưỡng/manifest của một lần chạy khác.

Sau khi chuẩn bị môi trường, mở terminal riêng chạy `node-red.cmd`, rồi chạy từ thư mục repo:

```powershell
& "D:\Project\aiot-model\.venv\Scripts\python.exe" .\pcb4-demo\start_demo.py
```

Chờ `http_passed: true`, mở http://localhost:1880/giang-pcb4/v1/demo . Giữ terminal model mở. Nếu cổng đã dùng, không mở instance thứ hai. Script không tự tắt dịch vụ khác hoặc thay cấu hình bảo mật.

Chỉ cập nhật UI khi Node-RED và model đang chạy:

```powershell
& "D:\Project\aiot-model\.venv\Scripts\python.exe" .\pcb4-demo\update_ui.py
```

Đợi UI UPDATED và tải lại trang. Mã build là nguồn chính để lần build sau giữ đúng UI; không chỉnh flow import riêng rồi bỏ quên source.

## Cách thử

Trong `pcb4/Data/Images`: Normal/0011.JPG dưới ngưỡng; Anomaly/009.JPG tạo cảnh báo; Anomaly/000.JPG là lỗi bị bỏ sót. Nút Phân tích tạo bản ghi mới; Gửi lại giữ ID/timestamp/ảnh. Retry không thêm cảnh báo, ACK lặp không đổi thời gian đầu tiên. Chọn model/threshold khác có thể thay kết quả mong đợi, cần cập nhật baseline kiểm chứng một cách có căn cứ.

```powershell
python .\pcb4-demo\test_storage.py
& "D:\Project\aiot-model\.venv\Scripts\python.exe" .\pcb4-demo\check_local.py
```

Các file JSON đi kèm là kết quả đã chọn từ phiên chạy, không tự thay thế test trên máy mới. Startup tạo bản ghi verify_ và tự ACK cảnh báo kiểm thử. Kết quả mở lại DB đã được thử; bài dừng/khởi động lại tiến trình thật còn chưa hoàn tất.

## Lưu trữ và giới hạn

SQLite nằm ở `pcb4-demo/data/workflow.sqlite3`. Tối đa 20.000 cảnh báo/100.000 bản ghi, không tự xóa khi đầy. ACK không giải phóng dung lượng. Giữ file DB và backup; không đưa database hoạt động lên Git hoặc đồng bộ nhiều máy cùng ghi. Không có nút archive/restore. Khi nâng v1 RAM lên v2, giữ Node-RED chạy để lấy cảnh báo cũ trước redeploy; legacy ID thiếu fingerprint trả lỗi riêng khi retry.

AI chỉ thử PCB4; recall baseline 31%, chưa dùng để kết luận sản phẩm tốt. Heatmap không phải nhãn lỗi chính xác. Ngưỡng gốc đọc threshold.json, score quy đổi s/(s+t), ngưỡng 0,5; không phải xác suất. Chỉ dùng một người/một ảnh mỗi lần trong demo. Chưa có camera, MQTT, cảm biến, workflow thứ hai hoặc bộ cài offline được kiểm chứng.
