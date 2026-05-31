# Ứng dụng đồ thị (CTRR)

Tài liệu này giải thích **công dụng của các hàm / lớp** trong `graph_algorithms.py` dùng cho **hai bài toán** đã triển khai:

1. **Đường đi ngắn nhất** (từ đỉnh `s` đến đỉnh `t`): Dijkstra và Bellman–Ford.  
2. **Luồng cực đại** trên mạng có dung lượng cạnh: **Ford–Fulkerson** với chọn đường tăng luồng bằng **BFS** (thường gọi là **Edmonds–Karp**).

Trên cạnh, ký hiệu **w** trong giao diện là **trọng số** khi chạy bài toán đường đi, và là **dung lượng** khi chạy bài toán luồng.

---

## Lưu trữ đồ thị: lớp `WeightedDiGraph`

Đây là mô hình dữ liệu chung: **đồ thị có hướng**, mỗi cạnh `u → v` gắn một số thực `w` (float).

| Phương thức | Công dụng |
|-------------|-----------|
| `add_vertex(u)` | Thêm đỉnh `u` (nếu chưa có). Đỉnh cô lập vẫn tồn tại trong đồ thị. |
| `add_edge(u, v, w)` | Thêm cạnh có hướng từ `u` đến `v` với trọng số/dung lượng `w`. Tự thêm hai đỉnh nếu cần. |
| `remove_edge(u, v)` | Xóa **một** cạnh `u → v` đầu tiên trong danh sách kề của `u`. Trả về `True` nếu đã xóa được. |
| `remove_vertex(u)` | Xóa đỉnh `u` và mọi cạnh đi vào / đi ra `u`. |
| `vertices()` | Danh sách các đỉnh hiện có. |
| `edges()` | Danh sách bộ ba `(u, v, w)` — mọi cạnh. |
| `neighbors(u)` | Các cặp `(v, w)` kề ra từ `u`. |
| `copy()` | Sao chép đồ thị (dùng khi cần thử thuật toán mà không làm thay đổi bản gốc). |

Cả hai bài toán đều nhận một `WeightedDiGraph` làm đầu vào.

---

## Bài toán 1: Đường đi ngắn nhất

Mục tiêu: tìm đường đi từ `s` đến `t` sao cho **tổng trọng số các cạnh** trên đường đi là nhỏ nhất.

### `_reconstruct_path(pred, s, t)` (hàm nội bộ)

- **Công dụng:** Từ mảng **đỉnh cha** `pred` (mỗi đỉnh lưu đỉnh liền trước trên đường đi từ `s`), dựng lại **chuỗi đỉnh** trên đường đi từ `s` tới `t`.  
- **Dùng cho:** Cả Dijkstra và Bellman–Ford sau khi đã tính xong `pred` và biết `t` tới được.  
- **Trả về:** `list` các đỉnh theo thứ tự `s → … → t`, hoặc `None` nếu không dựng được đường hợp lệ.

### `dijkstra(graph, s, t)`

- **Bài toán:** Đường đi ngắn nhất khi **mọi trọng số cạnh không âm**.  
- **Ý tưởng:** Mở rộng theo đỉnh có **khoảng cách tạm thời nhỏ nhất** (hàng đợi ưu tiên — `heapq`). Mỗi cạnh chỉ “thư giãn” khi đã cố định khoảng cách tới `u`.  
- **Tham số:** `graph`, đỉnh nguồn `s`, đỉnh đích `t`.  
- **Trả về:** `(path, dist)`  
  - `path`: danh sách đỉnh trên đường đi ngắn nhất, hoặc `None` nếu không có đường từ `s` đến `t`.  
  - `dist`: tổng trọng số tương ứng; nếu không tới được thì `inf`.  
- **Lưu ý:** Nếu có cạnh **âm**, hàm ném `ValueError` — đó là giả định của thuật toán Dijkstra.

### `bellman_ford(graph, s, t)`

- **Bài toán:** Đường đi ngắn nhất khi **cho phép trọng số âm**, nhưng cần phát hiện **chu trình trọng số âm** (làm bài toán không xác định được nếu chu trình đó tới được từ `s`).  
- **Ý tưởng:** Lặp tối đa `|V|-1` vòng, mỗi vòng duyệt **mọi cạnh** và cập nhật khoảng cách (thư giãn). Sau đó kiểm tra thêm một lần nữa: nếu vẫn còn cạnh làm giảm khoảng cách thì có **chu trình âm**.  
- **Trả về:** `(path, dist, message)`  
  - Nếu ổn định và `t` tới được: `path` là đường đi, `dist` là độ dài, `message` thường là `"OK"`.  
  - Nếu có chu trình âm từ `s`: `path = None`, `dist = inf`, `message` giải thích.  
  - Nếu không có đường tới `t`: `path = None`, kèm thông báo tương ứng.

---

## Bài toán 2: Luồng cực đại (Ford–Fulkerson / Edmonds–Karp)

Mục tiêu: Cho mạng có hướng, mỗi cạnh có **dung lượng** (không âm), một **nguồn** `source` và **đích** `sink`, tìm **giá trị luồng lớn nhất** từ nguồn tới đích thỏa cân bằng luồng tại mỗi đỉnh trung gian và không vượt quá dung lượng cạnh.

Trong code, trọng số `w` trên cạnh của `WeightedDiGraph` được hiểu là **dung lượng** khi gọi hàm luồng bên dưới.

### `edmonds_karp_capacity(residual, source, sink, vertices)`

- **Công dụng:** Lõi của **Ford–Fulkerson**: lặp lại việc tìm **đường tăng luồng** trên **mạng thặng dư** (`residual`), mỗi lần đẩy thêm một lượng luồng bằng **bottleneck** của đường đó.  
- **Cách chọn đường tăng luồng:** **BFS** trên mạng thặng dư → đó chính là biến thể **Edmonds–Karp** (đường tăng luồng ngắn nhất theo số cạnh).  
- **Tham số `residual`:** Từ điển `(u, v) →` dung lượng thặng dư còn lại theo hướng `u → v`. Hàm **sửa trực tiếp** từ điển này (giảm dung lượng theo chiều thuận, tăng chiều ngược).  
- **Trả về:** Một số thực — **tổng luồng** đã gửi từ `source` đến `sink`.  
- **Ghi chú:** Người dùng ứng dụng thường **không gọi trực tiếp** hàm này mà gọi `max_flow_from_graph` (bên dưới) để khỏi tự dựng mạng thặng dư.

### `max_flow_from_graph(graph, source, sink)`

- **Công dụng:** Bọc toàn bộ quy trình cho **bài toán luồng** trên `WeightedDiGraph`:  
  1. Gom dung lượng các cạnh song song `u → v` (nếu có nhiều cạnh) vào một ma trận thặng dư ban đầu.  
  2. Gọi `edmonds_karp_capacity` để tính **luồng cực đại**.  
  3. Suy ra **luồng trên từng cạnh gốc** bằng công thức: dung lượng ban đầu − dung lượng thặng dư còn lại theo chiều cạnh gốc.  
- **Trả về:** `(total, flow_dict, message)`  
  - `total`: giá trị luồng cực đại.  
  - `flow_dict`: các cặp `((u, v), f)` với `f > 0` — luồng thực tế qua cạnh `u → v` trong mạng gốc.  
  - `message`: `"OK"` hoặc thông báo lỗi (ví dụ thiếu đỉnh, dung lượng âm).

---

## Liên kết với `main.py`

Giao diện (`GraphApp`) giữ một `WeightedDiGraph`, khi bạn bấm:

- **Dijkstra** / **Bellman–Ford:** gọi `dijkstra` hoặc `bellman_ford` với `s`, `t` nhập trên form, rồi tô đậm đường đi trên hình.  
- **Luồng cực đại:** gọi `max_flow_from_graph` với nguồn/đích tương ứng, rồi hiển thị nhãn cạnh dạng luồng/dung lượng.

Phần **vẽ và lưu hình** dùng `networkx` + `matplotlib`, không thay thế các hàm thuật toán trên.

---

## Chạy chương trình

```bash
pip install -r requirements.txt
python main.py
```

---

## Tóm tắt nhanh

| Hàm / lớp | Bài toán | Vai trò chính |
|-----------|----------|----------------|
| `WeightedDiGraph` | Cả hai | Lưu đồ thị có hướng và `w` trên cạnh. |
| `_reconstruct_path` | Đường đi ngắn nhất | Dựng đường đi từ mảng đỉnh cha. |
| `dijkstra` | Đường đi ngắn nhất | Trọng số không âm, nhanh với heap. |
| `bellman_ford` | Đường đi ngắn nhất | Cho phép trọng số âm, phát hiện chu trình âm. |
| `edmonds_karp_capacity` | Luồng cực đại | Ford–Fulkerson + BFS trên mạng thặng dư. |
| `max_flow_from_graph` | Luồng cực đại | Chuẩn bị dữ liệu từ đồ thị và trả về luồng theo cạnh. |
