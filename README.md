```markdown
# مستند کامل پیاده‑سازی پایپ‌لاین **Kafka → Logstash → Elasticsearch → Kibana**

> نوشته شده از زبان یک **دیتا انجینیر جونیور** و بر اساس تجربه‌ی واقعی که در طول همین چت پشت سر گذاشتم 😊

---

## فهرست مطالب
1. [معرفی کلی پروژه](#معرفی-کلی-پروژه)  
2. [ساختار پوشه‌ها](#ساختار-پوشهها)  
3. [جزئیات هر مؤلفه](#جزئیات-هر-مؤلفه)  
   - Producer (Python)  
   - Kafka & Zookeeper  
   - Logstash  
   - Elasticsearch  
   - Kibana  
4. [مراحل اجرا](#مراحل-اجرا)  
5. [چالش‌ها و باگ‌ها + راهکارها](#چالشها-و-باگها--راهکارها)  
6. [کارهای آینده](#کارهای-آینده)  

---

## معرفی کلی پروژه
هدف این بود که یک پایپ‌لاین **End‑to‑End** بسازم که:

1. **داده‌ی خام و به‑هم ریخته** (unstructured JSON) را با یک اسکریپت Python به **Kafka** بفرستم.  
2. با **Logstash** داده را تمیز و نرمال (id → integer، timestamp یکنواخت، حذف فیلد اضافه، خالی به null …) کنم.  
3. خروجی تمیز را در **Elasticsearch** ایندکس **`test_pipeline`** ذخیره کنم.  
4. در **Kibana** بتوانم همان اسناد را ببینم و اسکرین‑شات بگیرم.

---

## ساختار پوشه‌ها
```
.
├── data/                  # فایل نمونه‌ی خام
│   └── sample.json
├── docker-compose.yml
├── logstash/
│   └── pipeline/
│       └── logstash.conf
├── python_producer/
│   ├── requirements.txt
│   ├── Dockerfile.producer
│   └── producer.py
└── README.md              # همین فایل
```

---

## جزئیات هر مؤلفه

### 1 – Producer (Python)

| فایل  | توضیح |
|-------|-------|
| `producer.py` | داده را از `data/sample.json` می‌خواند، هر رکورد را به‌صورت JSON در Kafka topic به نام **`test_pipeline`** می‌فرستد. |
| `Dockerfile.producer` | ایمیج کم‌حجم **python:3.9‑slim**، نصب `kafka-python` از روی `requirements.txt` و اجرای اسکریپت. |
| Mounts | با volume ها، هم اسکریپت و هم فایل JSON داخل کانتینر در `/app` قرار می‌گیرند. |

### 2 – Kafka & Zookeeper
از ایمیج‌های رسمی **Confluent Platform 7.0.1** استفاده کردم.  
تنها نکته‌ی مهم ست کردن `KAFKA_ADVERTISED_LISTENERS` روی `kafka:9092` بود تا سایر سرویس‌ها داخل شبکه‌ی Docker بتوانند وصل شوند.

### 3 – Logstash
فایل `logstash.conf` سه بخش دارد:

```conf
input  { kafka { ... } }

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

### 4 – Elasticsearch
ایمیج **`docker.elastic.co/elasticsearch:7.17.9`** در حالت single‑node با ۵۱۲ MB RAM.  
ایندکس هدفمان ( `test_pipeline` ) را Logstash به‑صورت اتوماتیک ایجاد می‌کند.

### 5 – Kibana
ورژن متناظر ۷٫۱۷٫۹؛ فقط `ELASTICSEARCH_HOSTS` را روی `http://elasticsearch:9200` گذاشتم.

---

## مراحل اجرا

```bash
# 1. کل سرویس‌ها را بساز و اجرا کن
docker-compose up --build

# 2. در ترمینال جداگانه؛ برای اطمینان، producer را دوباره اجرا کن
docker-compose run --rm producer

# 3. لاگ‌ها را ببین
docker-compose logs -f logstash elasticsearch
```

سپس در مرورگر:  
`http://localhost:5601` ←  **Explore on my own** ←  **Discover** ← ایجاد index pattern به نام `test_pipeline*` و انتخاب فیلد زمان `timestamp`.

---

## چالش‌ها و باگ‌ها + راهکارها
| چالش | شرح اتفاق | راهکاری که اجرا کردم |
|------|-----------|----------------------|
| **Dockerfile.producer پیدا نشد** | در اولین `docker-compose up` خطای `failed to read dockerfile: Dockerfile.producer` گرفتم. | فایل Dockerfile.producer را ساختم و در `docker-compose.yml` مسیر `dockerfile:` را ست کردم. |
| **ندیدن ایندکس در Kibana** | Kibana می‌گفت «Name must match one or more indices». | فهمیدم داده اصلاً وارد ES نشده؛ با `curl _cat/indices` چک کردم → ایندکس نبود. لاگ Logstash را بررسی کردم، producer را دوباره اجرا کردم تا پیام‌ها بعد از آماده‑شدن Kafka ارسال شوند. |
| **No results in Discover** | حتی بعد از ایندکس، Discover خالی بود. | تایم‑پیکر Kibana روی **Last 15 minutes** بود ولی داده‌ی من برای 2025‑01‑31 بود! بازه‌ی زمانی را روی **Last 90 days** گذاشتم. |
| **جای‌گذاری sample.json** | ابتدا volume را اشتباه mount کرده بودم و فایل داخل کانتینر نبود. | Volume `./data:/app/data:ro` را به سرویس producer اضافه کردم و با `ls /app/data` چک کردم. |
| **ترتیب بالا آمدن سرویس‌ها** | producer زودتر از Kafka بالا می‌آمد و پیام‌ها را drop می‌کرد. | `depends_on` کافی نبود؛ بعد از بالا آمدن همه سرویس‌ها، producer را دستی اجرا کردم (`docker-compose run --rm producer`). |
| **خطای تاریخ در Logstash** | فرمت `2025/01/31 12:34:56` پارس نمی‌شد. | قبل از فیلتر `date` یک `gsub` نوشتم که `/` را به `-` بدل کند؛ سپس الگوی `"yyyy-MM-dd HH:mm:ss"` را اضافه کردم. |
| **Null کردن name خالی** | `full_name` ممکن بود فقط space باشد. | با یک فیلتر Ruby، استریپ کردم و اگر خالی بود `nil` ست کردم. |

---

## کارهای آینده
* تعریف **Index Template** تا mapping دقیق (id → long، active → boolean) قبل از ingest ست شود.  
* اضافه‌کردن **Filebeat** برای ingest فایل‌های لاگ واقعی.  
* ساخت داشبورد Kibana با visualisationهای از پیش آماده.

---

> ممنون که مستند من را می‌خوانید؛ اگر سوال یا پیشنهادی دارید خوشحال می‌شوم بدانم! 🙂
```