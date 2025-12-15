import httpx
import time
import sys
import json

# CẤU HÌNH
API_BASE = "http://localhost:8000/api/v1"
# URL này là localhost của container (chính nó), vì API gọi lại chính API test
CALLBACK_URL = "http://localhost:8000/api/v1/test/mock-moodle-callback"

def run_test():
    print("🚀 BẮT ĐẦU KIỂM THỬ HỆ THỐNG CHẤM ĐIỂM AI...")
    
    # 1. Chuẩn bị dữ liệu giả lập
    payload = {
        "callback_url": CALLBACK_URL,
        "request_id": "TEST_AUTO_001",
        "assignment_content": "Giải thích khái niệm Encapsulation (Đóng gói) trong OOP.",
        "student_submission_text": "Đóng gói là việc gom dữ liệu và hàm vào trong class, đồng thời che giấu dữ liệu bằng access modifier như private.",
        "grading_criteria": "Chấm điểm dựa trên độ chính xác và ngắn gọn.",
        "max_score": 10.0
    }

    # 2. Gửi Request chấm bài
    print(f"\n1️⃣  Gửi bài làm lên API ({payload['request_id']})...")
    try:
        # Lưu ý: Dùng data=... cho form-data
        response = httpx.post(f"{API_BASE}/grading/async-batch", data=payload, timeout=10.0)
        
        if response.status_code == 202:
            print("✅ Gửi thành công! Server đã nhận việc.")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Gửi thất bại: {response.status_code} - {response.text}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Lỗi kết nối: {e}")
        sys.exit(1)

    # 3. Vòng lặp chờ kết quả (Polling)
    print("\n2️⃣  Đang chờ AI xử lý (Polling)...")
    req_id = payload["request_id"]
    max_retries = 20  # Chờ tối đa 40s (20 lần x 2s)
    
    for i in range(max_retries):
        try:
            # Gọi vào API check-result để xem có dữ liệu chưa
            check_resp = httpx.get(f"{API_BASE}/test/check-result/{req_id}")
            result = check_resp.json()
            
            if result["status"] == "done":
                print(f"\n🎉 ĐÃ CÓ KẾT QUẢ SAU {i*2} GIÂY!")
                ai_data = result["data"]
                
                # In báo cáo
                print("="*50)
                print(f"📌 Trạng thái: {ai_data.get('status')}")
                print(f"🏆 Điểm số:   {ai_data.get('score')}")
                print(f"📝 Nhận xét:  {ai_data.get('feedback')}")
                
                if ai_data.get('error_message'):
                    print(f"⚠️ Lỗi AI:    {ai_data.get('error_message')}")
                print("="*50)
                return # Test thành công
                
            else:
                # Chưa xong, đợi tiếp
                sys.stdout.write(".")
                sys.stdout.flush()
                time.sleep(2)
                
        except Exception as e:
            print(f"\n❌ Lỗi khi kiểm tra: {e}")
            break

    print("\n\n❌ HẾT GIỜ (TIMEOUT): AI chưa phản hồi sau 40s.")
    print("👉 Hãy kiểm tra log docker xem có lỗi gì không: docker logs -f ai_engine_api")

if __name__ == "__main__":
    run_test()