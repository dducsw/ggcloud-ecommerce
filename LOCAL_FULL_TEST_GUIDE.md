# Huong Dan Chay Local Hoan Toan (Khong Can Cloud)

Tai lieu nay huong dan ban test toan bo phan local truoc, theo tung lenh cu the tren Windows PowerShell.

## 1) Muc tieu local test

Khi chua tao cloud, ban van test duoc cac phan quan trong nhat:

- Source: PostgreSQL + datagen co ghi du lieu lien tuc hay khong
- CDC: Debezium co bat thay doi va day message len Kafka hay khong
- Message quality: schema/table/op trong CDC payload co dung hay khong
- San sang cho cloud: xac nhan du lieu vao on dinh truoc khi chay Pub/Sub, Dataflow, BigQuery

Luu y quan trong:

- Phan Router chinh thuc trong src/dataflow/beam_router.py can Pub/Sub + BigQuery + GCS (cloud).
- Tai lieu nay giup ban kiem thu local 100% cho Source + CDC + chat luong message truoc.

## 2) Yeu cau cai dat

Can co san:

- Docker Desktop
- Python 3.10+
- PowerShell 5.1 hoac 7+

Kiem tra nhanh:

```powershell
docker --version
python --version
```

## 3) Chuan bi workspace

Mo PowerShell tai thu muc repo:

```powershell
cd C:\252\ggcloud-ecommerce
```

Tao virtual env va cai package:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Neu ban gap loi policy khi activate:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 4) Xoa state cu de test sach

Neu truoc do da chay, nen reset nhanh:

```powershell
docker compose -f docker-compose.yaml down -v
```

## 5) Chay Step 1 local (Source + CDC)

### Cach nhanh (khuyen dung)

Script nay se:

- Start postgres-source, kafka, debezium-cdc, datagen
- Doi Debezium REST san sang
- Tu dong register connector

```powershell
.\infra\cdc\run_step1_local.ps1
```

### Cach tay (neu muon quan sat tung buoc)

```powershell
docker compose -f docker-compose.yaml up -d postgres-source kafka debezium-cdc datagen
python src/cdc/register_debezium_connector.py --connect-url http://localhost:8083 --config-path infra/cdc/connectors/debezium-connector.json
```

## 6) Kiem tra health tung thanh phan

### 6.1 Kiem tra container

```powershell
docker compose -f docker-compose.yaml ps
```

Ky vong: postgres-source, kafka, debezium-cdc, datagen deu Up.

### 6.2 Kiem tra Debezium connector status

```powershell
Invoke-RestMethod http://localhost:8083/connectors/thelook-postgres-source/status | ConvertTo-Json -Depth 10
```

Ky vong:

- connector.state = RUNNING
- tasks[0].state = RUNNING

### 6.3 Kiem tra datagen co dang ghi du lieu

```powershell
docker compose -f docker-compose.yaml logs --tail 100 datagen
```

Ky vong: log co cac dong ghi users/orders/order_items/events.

## 7) Kiem tra PostgreSQL local

Vao psql trong container:

```powershell
docker exec -it postgres-source psql -U db_user -d thelook_db
```

Chay cac cau lenh sau trong psql:

```sql
\dn
\dt demo.*
select count(*) as users_count from demo.users;
select count(*) as products_count from demo.products;
select count(*) as dist_centers_count from demo.distribution_centers;
select count(*) as orders_count from demo.orders;
select count(*) as order_items_count from demo.order_items;
select count(*) as events_count from demo.events;
```

Thoat psql:

```sql
\q
```

Ky vong:

- Co schema demo
- Co table demo.users, demo.products, demo.distribution_centers, demo.orders, demo.order_items, demo.events
- So dong tang dan theo thoi gian (orders/events)

## 8) Kiem tra Kafka topic CDC

### 8.1 Liet ke topic

```powershell
docker exec ggcloud_kafka bash -lc "kafka-topics.sh --bootstrap-server kafka:9092 --list"
```

Ky vong co cac topic dang:

- thelook.demo.users
- thelook.demo.products
- thelook.demo.distribution_centers
- thelook.demo.orders
- thelook.demo.order_items
- thelook.demo.events

### 8.2 Doc thu message tu topic events

```powershell
docker exec ggcloud_kafka bash -lc "kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic thelook.demo.events --from-beginning --max-messages 5"
```

Ky vong message JSON co cac truong payload, source, op, before/after.

## 9) Kiem tra chat luong CDC message (local)

### 9.1 Lay sample message ve file

```powershell
New-Item -ItemType Directory -Force .local_check | Out-Null
docker exec ggcloud_kafka bash -lc "kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic thelook.demo.events --from-beginning --max-messages 200" > .local_check\cdc_events_sample.jsonl
```

### 9.2 Dem op type va table trong sample

```powershell
python -c "import json,collections,pathlib; p=pathlib.Path('.local_check/cdc_events_sample.jsonl'); c_op=collections.Counter(); c_tbl=collections.Counter();
for line in p.read_text(encoding='utf-8', errors='ignore').splitlines():
    line=line.strip();
    if not line: continue
    try:
        obj=json.loads(line)
        payload=obj.get('payload',{})
        src=payload.get('source',{})
        c_op.update([payload.get('op','unknown')])
        c_tbl.update([src.get('table','unknown')])
    except Exception:
        pass
print('op_counter =', dict(c_op)); print('table_counter =', dict(c_tbl))"
```

Ky vong:

- op_counter co c/u/r (va co the co d)
- table_counter co events (va cac table khac o topic khac)

## 10) Tieu chi PASS local truoc cloud

Local duoc xem la on khi:

1. Tat ca container Step 1 deu Up
2. Debezium connector va task deu RUNNING
3. Table trong demo schema co du lieu
4. Kafka topic CDC co message lien tuc
5. Message CDC parse duoc payload/source/op

Neu 5 dieu tren dat, ban da san sang sang buoc cloud (Pub/Sub, Dataflow, BigQuery, dbt, dashboard).

## 11) Lenh dung va don dep

Dung he thong:

```powershell
docker compose -f docker-compose.yaml down
```

Dung va xoa luon volume (reset du lieu ve 0):

```powershell
docker compose -f docker-compose.yaml down -v
```

## 12) Loi thuong gap va cach xu ly

### Debezium task FAILED

- Kiem tra log:

```powershell
docker compose -f docker-compose.yaml logs --tail 200 debezium-cdc
```

- Kiem tra Postgres da bat logical replication (compose da set san).

### Khong co topic thelook.demo.*

- Kiem tra connector co RUNNING
- Kiem tra datagen co dang ghi du lieu vao DB

### Datagen loi ket noi DB

- Kiem tra postgres-source da healthy:

```powershell
docker compose -f docker-compose.yaml ps
```

### Muon test lai tu dau

- Chay:

```powershell
docker compose -f docker-compose.yaml down -v
.\infra\cdc\run_step1_local.ps1
```

---

Neu ban muon, buoc tiep theo minh co the tao them 1 script PowerShell duy nhat (local_smoke.ps1) de tu dong chay tat ca check o tren va in PASS/FAIL tung muc.
