export const tr = {
  brand: {
    name: "LayoutBot",
    commandCenter: "Command Center",
    operatorPanel: "LayoutBot Operatör Paneli",
    tagline: "İnşaat Planı Çizen Otonom Mobil Robot",
    hero: "CAD'den Robota Çizim Hattı",
    subtitle:
      "DXF planını yükle, pen-safe komutlara dönüştür ve robota güvenli şekilde aktar.",
  },
  rail: {
    sistem: "Sistem",
    plan: "Plan",
    derleme: "Derleme",
    simulasyon: "Simülasyon",
    robot: "Robot Kontrol",
    loglar: "Loglar",
  },
  header: {
    backend: "Backend",
    robot: "Robot",
    activeMode: "Aktif Mod",
    lastUpdate: "Son güncelleme",
    stop: "STOP",
    stopHint: "Fiziksel acil stop'un yerini tutmaz.",
  },
  modes: {
    idle: "Beklemede",
    dryRun: "Dry-run",
    simulation: "Simülasyon",
    live: "Canlı",
  },
  pipeline: {
    title: "Görev Akışı",
    upload: "Plan Yükle",
    analyze: "Analiz Et",
    compile: "Pen-Safe Derle",
    simulate: "Simüle Et",
    send: "Robota Gönder",
    status: {
      waiting: "Bekliyor",
      ready: "Hazır",
      success: "Başarılı",
      error: "Hata",
    },
  },
  preview: {
    title: "Plan Önizleme",
    waiting: "DXF plan bekleniyor",
    hint: "Yüklenen yol verisi burada görselleştirilir.",
    scale: "Ölçek",
    points: "Nokta",
  },
  telemetry: {
    title: "Robot Telemetrisi",
    backend: "Backend",
    firmware: "Firmware",
    serial: "Serial",
    penSafe: "Pen-safe",
    stopReady: "STOP",
    motors: "Motor çıkışları",
    pen: "Kalem",
    unknown: "Bilinmiyor",
    waiting: "Bekleniyor",
    offline: "Bağlantı yok",
    online: "Aktif",
    disabled: "Devre dışı",
    ready: "Hazır",
    closed: "Kapalı",
    live: "Canlı",
    verified: "Doğrulandı",
    unverified: "Doğrulanmadı",
    penUp: "Yukarı",
    penDown: "Aşağı",
    motorNote: "Donanım doğrulaması yapılana kadar devre dışıdır.",
  },
  stream: {
    title: "Komut Akışı",
    empty: "Komut akışı boş — plan derlendikten sonra görünür.",
    activity: "Olay günlüğü",
  },
  control: {
    title: "Güvenlik Katmanı",
    compile: "Planı Derle",
    dryRun: "Dry-run Çalıştır",
    simulate: "Simülasyonu Başlat",
    live: "Canlı Robota Gönder",
    stop: "Robotu Durdur (Canlı STOP)",
    stopNote: "Yazılımsal STOP komutudur. Fiziksel acil stop'un yerini tutmaz.",
    simStop: "Simülasyonu Durdur",
    upload: "DXF / JSON Seç",
    penSafeNote: "Kopuk çizgiler arasında kalem otomatik kaldırılır.",
    liveNote: "Canlı mod fiziksel test ve operatör gözetimi gerektirir.",
    liveConfirmTitle: "Canlı gönderim onayı",
    liveConfirmBody:
      "Komutlar seri porta gönderilecek. Ortamın hazır olduğundan ve fiziksel acil stop'un erişilebilir olduğundan emin olun.",
    liveConfirmAction: "Canlı Gönder",
    cancel: "İptal",
    busy: "İşlem sürüyor…",
    needsPlan: "Önce plan yükleyin ve derleyin.",
  },
  safety: {
    banner:
      "Güvenlik Katmanı: Canlı çalıştırma yalnızca hazır ortamda ve operatör gözetiminde yapılmalıdır.",
  },
  errors: {
    backendOffline: "Backend bağlantısı yok — npm run dev:v3 ile sunucuyu başlatın.",
    unsupportedFile: "Desteklenmeyen dosya. DXF veya JSON plan seçin.",
    importFailed: "Plan içe aktarılamadı.",
    noCommands: "Derleme sonucu komut üretmedi.",
  },
} as const;

export type MissionSection = keyof typeof tr.rail;

export type StepStatus = "waiting" | "ready" | "success" | "error";

export type ActiveMode = "idle" | "dryRun" | "simulation" | "live";
