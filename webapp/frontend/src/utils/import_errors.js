/**
 * Backend'den gelen import hata metnini kullanıcıya anlaşılır hale getirir.
 * Not: Bu fonksiyon UI'dan bağımsız, saf bir yardımcıdır.
 */
export function formatImportError(backendError, isNetworkError) {
  if (isNetworkError) {
    return "Backend'e ulaşılamadı. Backend çalışıyor mu? (http://127.0.0.1:8000)";
  }
  if (!backendError || typeof backendError !== "string") return "İçe aktarma hatası.";
  const e = backendError.toLowerCase();
  if (
    e.includes("entity") ||
    e.includes("entities") ||
    e.includes("binary") ||
    e.includes("utf-8") ||
    e.includes("utf8") ||
    e.includes("ascii") ||
    e.includes("dxf") ||
    e.includes("dwg")
  ) {
    return (
      "Dosya formatı veya içerik uygun değil. DXF/DWG okunamadı veya segment üretilemedi. Detay: " +
      backendError
    );
  }
  if (
    e.includes("çizilebilir") ||
    e.includes("segment") ||
    e.includes("nokta üretmedi") ||
    e.includes("normalizasyon")
  ) {
    return (
      "Plan çizilemiyor: " +
      backendError +
      " (step_size artırın veya daha az katman seçin)"
    );
  }
  if (e.includes("max_bounds_size") || e.includes("max_bounds")) {
    return (
      "Plan çizim alanı çok büyük. Öneri: recenter açın veya daha az katman seçin. Detay: " +
      backendError
    );
  }
  if (e.includes("max_moves") || e.includes("max_path") || e.includes("max_total_time")) {
    return (
      "Plan çok detaylı veya uzun. Öneri: step_size değerini artırın veya daha az katman seçin. Detay: " +
      backendError
    );
  }
  if (e.includes("dosya boyutu") || e.includes("çok büyük") || e.includes("payload")) {
    return "Dosya boyutu çok büyük. Daha küçük bir plan deneyin veya katmanları azaltın. Detay: " + backendError;
  }
  return backendError;
}

