# Baseline VisA PCB4 do Giang chạy

Tham khảo hướng train/inference của [RoyalB26/AIoT_H261](https://github.com/RoyalB26/AIoT_H261/tree/dbb9e89f3b6feef215f82732cf91407103948510). Các script tại đây là adapter cho lần chạy riêng, không phải checkpoint do Bảo cung cấp. Không có thí nghiệm cải thiện sau baseline ngày 22/10/2026.

## Môi trường đã thử

Python 3.11.9; torch 2.6.0+cu124; torchvision 0.21.0+cu124; anomalib 2.2.0; lightning 2.5.5; torchmetrics 1.8.2; RTX 4060. Cần các dependency tương ứng và trọng số pretrained ResNet18. Lần đầu fit có thể tải backbone, chưa xác minh đóng gói offline đầy đủ. Không cần token Hugging Face cho lần tải công khai đã thực hiện.

## Dữ liệu và chạy

Lấy VisA từ [nguồn chính thức Amazon Science](https://github.com/amazon-science/spot-diff), đọc điều kiện dataset trước khi sử dụng/phân phối. Không có ảnh dataset trong Git.

`prepare_visa_pcb4.py` mặc định đọc `D:/Downloads/VisA_20220922.tar`, chỉ giải nén pcb4 và split_csv/1cls.csv vào `D:/Project/aiot-model/datasets/visa`; giữ nguyên nhãn mask. Kiểm tra đường dẫn và checksum file có sẵn, không ghi đè file khác nội dung. Đổi các hằng ARCHIVE/DEST nếu dùng đường dẫn khác.

```powershell
& "D:\Project\aiot-model\.venv\Scripts\python.exe" .\bao-model\prepare_visa_pcb4.py
& "D:\Project\aiot-model\.venv\Scripts\python.exe" .\bao-model\train_visa_pcb4.py
```

Script train hỗ trợ `--root` để đổi gốc `D:/Project/aiot-model`. Dùng split chính thức: 904 normal train, 101 normal test, 100 anomaly test. Seed 42 tách 100 normal từ train để calibration; fit 804 ảnh. ResNet18 layer2/layer3, ảnh 256×256, chuẩn hóa ImageNet một lần; bank tối đa 2.000 patch lấy mẫu ngẫu nhiên bằng priority. Không phải greedy coreset PatchCore chuẩn.

Ngưỡng là quantile 99% higher trên calibration normal; không dùng test chọn ngưỡng. Các quyết định sau khi đã xem baseline test phải phân biệt thăm dò với đánh giá độc lập.

## Đầu ra

Mỗi lần tạo `runs/visa-pcb4-<timestamp>` riêng, gồm model.pt, threshold.json, manifest.json, calibration.json, test-predictions.json và results.json. Chỉ coi hoàn tất khi có COMPLETE và results.json. model.pt lưu state_dict/config/bank của PatchcoreModel, không phải Lightning .ckpt cho predictor cũ.

Kết quả baseline và manifest được lưu tại [Report/evidence](../Report/evidence). SHA256 checkpoint trong verification-summary.json giúp nhận diện file đã chạy; checkpoint không được commit. Tự chạy lại có thể khác chút theo thiết bị/phiên bản; seed không bảo đảm giống bit trên mọi máy. Khi nối demo, sửa RUN trong model_service.py trỏ đúng run cùng checkpoint/ngưỡng, không chọn tùy tiện checkpoint mới nhất.

## Kết quả và hạn chế

AUROC 94,11%, precision 100%, recall 31%, F1 47,33%; TP/TN/FP/FN = 31/101/0/69. Các số không chứng minh hệ thống đủ tin cậy để chọn sản phẩm tốt. Không có pixel metric; mask gốc chứa giá trị 0–7, cần chuyển `mask > 0` nếu đánh giá bất thường nhị phân sau này. Không so trực tiếp GPU latency của lần này với CPU benchmark của Bảo.
