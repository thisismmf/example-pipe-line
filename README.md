مستند اجرایی پایپ‌لاین Kafka → Logstash → Elasticsearch → Kibana

فهرست مطالب

معرفی پروژه

ساختار دایرکتوری‌ها

جزئیات سرویس‌ها

مراحل اجرای پایپ‌لاین

چالش‌ها و رفع باگ‌ها

بهبودهای آینده

معرفی پروژه

هدف این بود که دادهٔ خام (JSON نامنظم) با یک اسکریپت Python به Kafka ارسال شود، توسط Logstash پاک‌سازی و نرمال گردد و در نهایت در ایندکسی به نام test_pipeline داخل Elasticsearch ذخیره شود؛ سپس داده در Kibana قابل مشاهده و تحلیل باشد.

ساختار دایرکتوری‌ها

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
└── README.md   ← همین فایل

جزئیات سرویس‌ها

1. Producer (Python)

فایل

توضیح

producer.py

رکوردهای sample.json را خوانده و در تاپیک test_pipeline منتشر می‌کند.

Dockerfile.producer

بر پایهٔ ‌ایمیج python:3.9-slim پکیج‌های موردنیاز (kafka-python) را نصب می‌کند.

Volume‑ها

دایرکتوری کد و فایل JSON در مسیر /app کانتینر مونت می‌شوند.

2. Kafka & Zookeeper

از ایمیج‌های رسمی Confluent (cp-kafka:7.0.1, cp-zookeeper:7.0.1) استفاده شده.نکتهٔ کلیدی: مقداردهی متغیر KAFKA_ADVERTISED_LISTENERS با PLAINTEXT://kafka:9092 برای دسترسی سایر سرویس‌های داکری.

3. Logstash

logstash.conf شامل:

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

4. Elasticsearch

ایمیج elasticsearch:7.17.9 در حالت تک‌نود (single-node) و حافظه ۵۱۲ MB.

5. Kibana

ایمیج متناظر kibana:7.17.9؛ متغیر ELASTICSEARCH_HOSTS روی http://elasticsearch:9200.

مراحل اجرای پایپ‌لاین

# ساخت و بالا آوردن تمام سرویس‌ها
docker-compose up --build

# در ترمینال دیگر، در صورت نیاز producer را مجدداً اجرا کن
docker-compose run --rm producer

پس از بالا آمدن، در مرورگر به http://localhost:5601 برو.

گزینهٔ Explore on my own را بزن.

در Discover، یک Index Pattern با نام test_pipeline* بساز و فیلد زمان را timestamp انتخاب کن.

بازهٔ زمانی (Date Picker) را از Last 15 minutes به مثلا Last 90 days یا رنج دستی شامل تاریخ داده‌ها تغییر بده.

اسناد تمیز شده را می‌بینی؛ اسکرین‌شات بگیر و در مخزن ذخیره کن.

چالش‌ها و رفع باگ‌ها

چالش

شرح

راهکار

نداشتن Dockerfile.producer

ارور failed to read dockerfile در build اولیه.

فایل Dockerfile.producer را اضافه و مسیر آن را در docker-compose.yml مشخص کردم.

Index دیده نمی‌شد

Kibana پیغام Name must match one or more indices می‌داد.

با curl localhost:9200/_cat/indices فهمیدم ایندکسی ایجاد نشده؛ Producer را بعد از آماده‌شدن Kafka و Logstash دوباره اجرا کردم.

Discover خالی بود

پیام No results match your search criteria دیده می‌شد.

Date Picker به ۱۵ دقیقه اخیر محدود بود؛ بازهٔ زمانی را گسترش دادم.

عدمِ mount شدن sample.json

Producer نمی‌توانست فایل را پیدا کند.

volume ./data:/app/data:ro را اضافه و با ls داخل کانتینر کنترل کردم.

Producer زودتر از Kafka اجرا شد

پیام‌ها drop شدند.

depends_on کافی نبود؛ producer را دستی با docker-compose run --rm producer اجرا کردم.

خطای Date Parse

فرمت 2025/01/31 12:34:56 توسط فیلتر date پارس نمی‌شد.

قبل از آن با gsub اسلش‌ها را به دش تبدیل کردم و الگوی yyyy-MM-dd HH:mm:ss را اضافه نمودم.

خالی‌ماندن فیلد name

مقدار فقط whitespace بود.

با Ruby filter فضای خالی را trim و اگر خالی ماند به null تبدیل کردم.

بهبودهای آینده

تعریف Index Template برای نوع‌دهی دقیق فیلدها قبل از ingest.

اضافه‌کردن Filebeat جهت خواندن فایل‌لاگ‌های واقعی.

ساخت داشبوردهای آماده در Kibana برای مانیتورینگ بهتر.


