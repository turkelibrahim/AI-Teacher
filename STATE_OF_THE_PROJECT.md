# CANLI ÖĞRETMEN AI - PROJE DURUM RAPORU

**Son Güncelleme:** 16 Ağustos 2026
**Bulunulan Aşama:** Phase 7 Tamamlandı. Gelecek adımlar (Phase 8+) için hazır.

Bu belge, projeye yeni dahil olan kullanıcıların veya AI ajanlarının projenin şu anki durumunu, mimarisini ve nelerin tamamlandığını hızlıca anlaması için hazırlanmıştır.

---

## 🏗️ Mimari ve Teknoloji Yığını
Proje, çok kiracılı (multi-tenant) ve ölçeklenebilir bir RAG (Retrieval-Augmented Generation) altyapısı üzerine inşa edilmektedir.

* **Backend:** FastAPI (Python 3.11), SQLAlchemy, PostgreSQL (pgvector ile)
* **Asenkron İşlemler:** Celery & Redis
* **Nesne Depolama:** MinIO (AWS S3 uyumlu)
* **Altyapı:** Docker & Docker Compose
* **Gömülü Vektörler (Embeddings):** Sentence-Transformers (`paraphrase-multilingual-MiniLM-L12-v2`), CPU üzerinde çalışacak şekilde izole edilmiştir.

---

## ✅ Tamamlanan Aşamalar (Phases 0-5)

### PHASE 0: FOUNDATION (Altyapı) - `[TAMAMLANDI]`
- Docker Compose ile API, PostgreSQL, Redis, Celery Worker ve MinIO servisleri ayağa kaldırıldı.
- Alembic ile veritabanı migrasyon yapısı kuruldu.
- Temel CI/CD ve test altyapısı (`pytest`, `pytest-asyncio`) entegre edildi.

### PHASE 1: IDENTITY & TENANCY (Kimlik ve Kiracı Yönetimi) - `[TAMAMLANDI]`
- Kullanıcı doğrulama (JWT, Argon2 hashing) yapısı kuruldu.
- Çoklu kiracı (Multi-tenancy) modeli oluşturuldu. Her kullanıcının bir organizasyona (Organization) ait olması sağlandı.
- Organizasyonlar arası kesin veri izolasyonu (Tenant Isolation) veritabanı seviyesinde garanti altına alındı.

### PHASE 2: RBAC & ORG MANAGEMENT (Rol ve Yetki Yönetimi) - `[TAMAMLANDI]`
- Organizasyon içi Yetki ve Rol tabanlı erişim kontrolü (Role-Based Access Control) kuruldu.
- OWNER, ADMIN, INSTRUCTOR ve MEMBER rolleri oluşturularak yetki sınırları çizildi.

### PHASE 3: RESOURCE UPLOAD (Kaynak Yükleme) - `[TAMAMLANDI]`
- Kullanıcıların MinIO üzerinden güvenli ve izole bir şekilde dosya yükleyebilmesi sağlandı.
- Dosya boyutu, format validasyonları ve organizasyon izolasyon testleri başarıyla tamamlandı.

### PHASE 4: DOCUMENT INGESTION (Belge İşleme) - `[TAMAMLANDI]`
- Yüklenen belgelerin (PDF, DOCX, TXT vb.) arka planda Celery worker'ları tarafından indirilip düz metne çevrilmesi işlemi yapıldı.
- Belge sınırları (sayfa/slayt/bölüm) korunarak veri tabanına işlendi.

### PHASE 5: RAG FOUNDATION (Chunking & Embeddings) - `[TAMAMLANDI]`
- İşlenen metinlerin semantik olarak anlamlı parçalara bölünmesi (Chunking) işlemi tamamlandı (`SemanticChunker`). Token sınırları strict olarak 112 (max) ve 96 (target) olarak ayarlandı.
- CPU tabanlı `LocalEmbeddingProvider` kullanılarak, metin parçalarının vektörleri (`paraphrase-multilingual-MiniLM-L12-v2`) çıkarıldı.
- Çıkarılan bu vektörler PostgreSQL üzerinde `pgvector` eklentisi kullanılarak indekslendi.
- API üzerinden kiracı yalıtımlı, vektörel semantik arama (`POST /api/v1/organizations/{org_id}/retrieval/search`) uç noktası geliştirildi ve entegrasyon testlerinden geçti.
- Gelecekteki LLM süreçleri (Phase 6) için ana RTX GPU'nun VRAM'i tamamen boş ve hazır bırakıldı (Embedding'ler sadece CPU'da çalışıyor).

---

### PHASE 6: LLM & LESSON ENGINE - `[TAMAMLANDI]`
- Soyut LLM sağlayıcı arayüzü (`BaseLLMProvider`) ve OpenAI uyumlu (`OpenAICompatibleProvider`) API istemcisi geliştirildi.
- Lesson (Ders) ve LessonMessage (Ders Mesajları) için veritabanı modelleri oluşturuldu ve çoklu kiracı (multi-tenant) veri yalıtımı sağlandı.
- Önceden oluşturulan Phase 2 (Yetkilendirme) ve Phase 5 (Vektörel Arama/RAG) sistemleri `LessonService` içinde orkestre edildi.
- Sistem prompt'u oluşturucu modülü (`prompt.py`) ile vektörel arama sonuçları ve sohbet geçmişi LLM'ye iletilecek şekilde bağlandı.
- Test senaryoları yazılarak tam yalıtımlı çalıştığı (`docker compose exec api pytest`) doğrulandı.

---

### PHASE 7: WEBSOCKETS/SSE & FRONTEND - `[TAMAMLANDI]`
- Backend tarafında Lesson Service için `stream_message_and_generate_response` metodu ile Server-Sent Events (SSE) altyapısı kuruldu.
- Next.js (React) kullanılarak uygulamanın temel önyüzü (Frontend) geliştirildi (`apps/web`).
- Login (`/login`), Organizasyon Seçimi (`/organizations`), Ders Listesi (`/lessons`) ekranları tamamlandı.
- Ders içi gerçek zamanlı sohbet (Chat UI - `/lessons/[id]`) ekranı yapıldı; StreamingResponse entegre edildi.
- **RAG UI (Belge Yükleme):** Chat ekranına 📎 butonu eklenerek kullanıcıların ders anında doğrudan PDF/TXT yüklemesi ve arka plan Celery işçisi üzerinden RAG (vektörleştirme) sürecinin tetiklenmesi sağlandı.

### PHASE 8: AI SERVING & AVATAR (Local ML Models) - `[YAPIM AŞAMASINDA]`
- Kullanıcının isteği doğrultusunda **tamamen yerel (local)** optimizasyon ve güvenlik hedeflenmiştir.
- **RAG Katı Kurallar (Anti-Hallucination):** `prompt.py` içindeki sistem mesajı katılaştırılarak, LLM'nin sadece belgelerden cevap vermesi, genel kültür bilgisiyle dışarı çıkması (veya kod üretmesi) engellendi.
- **Video Avatar Mimari Altyapısı:** `apps/api/app/modules/avatar/service.py` ve Docker Compose içerisine `avatar-worker` taslağı eklendi. (NVIDIA GPU pass-through ile local TTS / Wav2Lip için hazır hale getirildi).
- **Not (Sıradaki Adım):** Projeyi devralan kişi, `avatar-worker` içerisindeki ML modellerini (Bark, SadTalker vb.) indirip bağlamalı veya alternatif ses/görüntü çözümleri (cloud dahil) uygulamalıdır.

## 💡 Notlar ve Uyarılar
- `.env` dosyasında `LLM_BASE_URL="http://host.docker.internal:11434/v1"` ve `LLM_MODEL_NAME="qwen2.5:3b"` olarak ayarlanmıştır. Çalıştırmak için Docker'ın host'a erişebilmesi ve Ollama'da modelin inmiş olması gerekir.
- Herhangi bir aşamaya geri dönüp değişiklik yapmadan önce mevcut testleri (`docker compose exec api pytest`) çalıştırdığınızdan emin olun.
- Veritabanı model değişikliklerinde mutlaka Alembic migrasyonlarını oluşturun.
- Uygulama çalışırken `docker compose up -d` komutuyla tüm container'ları (web ve api dahil) ayakta tutabilirsiniz. Worker container'ı `Celery` görevlerini işlemek (RAG vektorizasyonu) için kritiktir.
- Veritabanı model değişikliklerinde mutlaka Alembic migrasyonlarını (`alembic revision --autogenerate -m "..."`) oluşturun.
- Uygulama çalışırken `docker compose up -d` komutuyla tüm container'ları ayakta tutabilirsiniz. Worker container'ı `Celery` görevlerini işlemek için kritiktir.
