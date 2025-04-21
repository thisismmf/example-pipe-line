
# مستند اجرایی پایپ‌لاین `Kafka → Logstash → Elasticsearch → Kibana`



---

## فهرست مطالب
1. [معرفی پروژه](#معرفی-پروژه)  
2. [ساختار دایرکتوری‌ها](#ساختار-دایرکتوریها)  
3. [جزئیات سرویس‌ها](#جزئیات-سرویسها)  
4. [مراحل اجرای پایپ‌لاین](#مراحل-اجرای-پایپ‌لاین)  
5. [چالش‌ها و رفع باگ‌ها](#چالشها-و-رفع-باگها)  
6. [بهبودهای آینده](#بهبودهای-آینده)

---

## معرفی پروژه
هدف این بود که دادهٔ خام (JSON نامنظم) با یک اسکریپت Python به `Kafka` ارسال شود، توسط `Logstash` پاک‌سازی و نرمال گردد و در نهایت در ایندکسی به نام `test_pipeline` داخل `Elasticsearch` ذخیره شود؛ سپس داده در `Kibana` قابل مشاهده و تحلیل باشد.

---

## ساختار دایرکتوری‌ها<a id="ساختار-دایرکتوریها"></a>

```
.
├── data/
│   └── sample.json
├── docker-compose.yml
├── logstash/
│   └── pipeline/
│       └── logstash.conf
├── python_producer/
│   ├── requirements.txt
│   ├── Dockerfile.producer
│   └── producer.py
└── README.md 
```

---

## جزئیات سرویس‌ها<a id="جزئیات-سرویسها"></a>

### 1. Producer (Python)

| فایل | توضیح |
|------|-------|
| `producer.py` | رکوردهای `sample.json` را خوانده و در تاپیک `test_pipeline` منتشر می‌کند.  |
| `Dockerfile.producer` | بر پایهٔ ‌ایمیج `python:3.9-slim` پکیج‌های موردنیاز (`kafka-python`) را نصب می‌کند. |
| Volume‑ها | دایرکتوری کد و فایل JSON در مسیر `/app` کانتینر مونت می‌شوند. |

### 2. Kafka & Zookeeper
از ایمیج‌های رسمی Confluent (`cp-kafka:7.0.1`, `cp-zookeeper:7.0.1`) استفاده شده.  
نکتهٔ کلیدی: مقداردهی متغیر `KAFKA_ADVERTISED_LISTENERS` با `PLAINTEXT://kafka:9092` برای دسترسی سایر سرویس‌های داکری.

### 3. Logstash
`logstash.conf` شامل:

```
input { kafka { topics => ["test_pipeline"] codec => "json" ... } }

filter {
  mutate { rename => { "full_name" => "name" } remove_field => ["extra_field"] }
  mutate { convert => { "id" => "integer" } }
  mutate { gsub => ["timestamp","/","-"] }
  date   { match => ["timestamp","yyyy-MM-dd HH:mm:ss","ISO8601"] timezone => "UTC" }
  mutate { convert => { "active" => "boolean" } }
  ruby   { code => "event.get('name').strip!; event.set('name', nil) if event.get('name').empty?" }
}

output { elasticsearch { index => "test_pipeline" } stdout { codec => rubydebug } }
```

### 4. Elasticsearch
ایمیج `elasticsearch:7.17.9` در حالت تک‌نود (`single-node`) و حافظه ۵۱۲ MB.

### 5. Kibana
ایمیج متناظر `kibana:7.17.9`؛ متغیر `ELASTICSEARCH_HOSTS` روی `http://elasticsearch:9200`.

---

## مراحل اجرای پایپ‌لاین<a id="مراحل-اجرای-پایپ‌لاین"></a>

```bash
# ساخت و بالا آوردن تمام سرویس‌ها
docker-compose up --build

# در ترمینال دیگر، در صورت نیاز producer را مجدداً اجرا میکنیم
docker-compose run --rm producer
```

1. پس از بالا آمدن، در مرورگر به `http://localhost:5601` رفتم.  
2. گزینهٔ **Explore on my own** را زدم.  
3. در **Discover**، یک Index Pattern با نام `test_pipeline*` ساختم و فیلد زمان را `timestamp` انتخاب کردم.  
4. بازهٔ زمانی (Date Picker) را از **Last 15 minutes** به مثلا **Last 90 days**  تغییر دادم.  
5. اسناد تمیز شده را دیدم و اسکرین‌شات گرفتم و به شرح زیر است.
![اسکرین شات کیبانا](<Screenshot 2025-04-21 at 4.35.28 PM.png>)

---

## چالش‌ها و رفع باگ‌ها<a id="چالشها-و-رفع-باگها"></a>

| چالش | شرح | راهکار |
|------|-----|--------|
| **نداشتن `Dockerfile.producer`** | ارور *failed to read dockerfile* در build اولیه. | فایل `Dockerfile.producer` را اضافه و مسیر آن را در `docker-compose.yml` مشخص کردم. |
| **Index دیده نمی‌شد** | Kibana پیغام *Name must match one or more indices* می‌داد. | با `curl localhost:9200/_cat/indices` فهمیدم ایندکسی ایجاد نشده؛ Producer را بعد از آماده‌شدن Kafka و Logstash دوباره اجرا کردم. |
| **Discover خالی بود** | پیام *No results match your search criteria* دیده می‌شد. | Date Picker به ۱۵ دقیقه اخیر محدود بود؛ بازهٔ زمانی را گسترش دادم. |
| **عدمِ mount شدن `sample.json`** | Producer نمی‌توانست فایل را پیدا کند. | volume `./data:/app/data:ro` را اضافه و با `ls` داخل کانتینر کنترل کردم. |
| **Producer زودتر از Kafka اجرا شد** | پیام‌ها drop شدند. | `depends_on` کافی نبود؛ producer را دستی با `docker-compose run --rm producer` اجرا کردم. |
| **خطای Date Parse** | فرمت `2025/01/31 12:34:56` توسط فیلتر `date` پارس نمی‌شد. | قبل از آن با `gsub` اسلش‌ها را به دش تبدیل کردم و الگوی `yyyy-MM-dd HH:mm:ss` را اضافه نمودم. |
| **خالی‌ماندن فیلد `name`** | مقدار فقط whitespace بود. | با Ruby filter فضای خالی را trim و اگر خالی ماند به `null` تبدیل کردم. |
---