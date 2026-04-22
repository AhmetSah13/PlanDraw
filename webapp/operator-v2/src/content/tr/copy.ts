export const TR_COPY = {
  uygulama: {
    urunTipi: "Operatör odaklı çalışma alanı",
    urunAdi: "PlanDraw Operatör V2",
    urunAciklamasi:
      "Plan yükleme, hizalama, kontrol, çalıştırma ve sonuç adımlarını tek operatör akışında sade ve güvenli biçimde yönetir.",
    durumEtiketi: "Durum",
    kurulumDurumu: "Sistem hazır",
    anaAkisEtiketi: "Ana akış"
  },
  asamalar: {
    planYukle: {
      sira: "1",
      baslik: "Plan Yükle",
      yol: "/plan-yukle",
      aciklama:
        "İlk hedef geçerli plan kaynağını alıp operatöre net bir hazır olma durumu sunmaktır."
    },
    hizala: {
      sira: "2",
      baslik: "Hizala",
      yol: "/hizala",
      aciklama: "Saha referansları ve plan eşleşmesi için bu adım burada kurulacak."
    },
    kontrolEt: {
      sira: "3",
      baslik: "Kontrol Et",
      yol: "/kontrol-et",
      aciklama: "Analiz, risk doğrulaması ve hazır olma durumu bu adımda toplanacak."
    },
    calistir: {
      sira: "4",
      baslik: "Çalıştır",
      yol: "/calistir",
      aciklama: "Simülasyon ve canlı gönderim ayrımı bu adımda net şekilde kurulacak."
    },
    sonuclar: {
      sira: "5",
      baslik: "Sonuçlar",
      yol: "/sonuclar",
      aciklama: "Görev özeti, çıktı kayıtları ve bir sonraki önerilen adım burada gösterilecek."
    }
  },
  durumlar: {
    hazir: "Hazır",
    engelli: "Engelli",
    bekliyor: "Bekliyor",
    calisiyor: "Çalışıyor",
    tamamlandi: "Tamamlandı",
    hata: "Hata",
    dikkat: "Dikkat"
  },
  butonlar: {
    hazirlikKaydiOlustur: "Hazırlık kaydını oluştur",
    girdiyiHazirla: "Girdiyi hazırla",
    tekrarDene: "Tekrar dene",
    devamEt: "Devam et",
    geriDon: "Geri dön",
    kaydet: "Kaydet",
    kapat: "Kapat",
    dosyaSec: "Dosya seç",
    farkliKaynakSec: "Farklı kaynak seç",
    simulasyonuBaslat: "Simülasyonu başlat",
    simulasyonuYenidenBaslat: "Simülasyonu yeniden başlat",
    yenidenBaglan: "Yeniden bağlan",
    isiDurdur: "İşi durdur",
    onKontrolCalistir: "Ön kontrol çalıştır",
    canliCalistir: "Canlı gönderimi başlat",
    hizalamayiDogrula: "Hizalamayı doğrula",
    kontroluCalistir: "Kontrolü çalıştır",
    ciktiyiHazirla: "Çıktıyı hazırla"
  },
  geriBildirim: {
    basari: {
      hazirlikKaydiOlustu: "Hazırlık kaydı oluşturuldu.",
      kurulumHazir: "Uygulama çalışmaya hazır.",
      planHazir:
        "Çalıştırılabilir girdi üretildi. Sıradaki adım olarak Hizala ekranına geçebilirsiniz."
    },
    bos: {
      hazirlikYok: "Henüz hazırlık kaydı yok.",
      sonucYok: "Henüz gösterilecek sonuç yok.",
      dosyaYok: "Henüz dosya seçilmedi.",
      planMetniYok: "Henüz manuel plan metni girilmedi."
    },
    hata: {
      genel: "Bir sorun oluştu. Lütfen yeniden deneyin.",
      akisaAitVeriYok: "Akış verisi henüz alınamadı.",
      planMetniKisa: "En az 8 karakterlik bir plan metni girin.",
      planMetniUzun: "Plan metni 240 karakteri geçmemeli.",
      dosyaSecilmedi: "Devam etmek için önce uygun dosyayı seçin.",
      manuelPlanBos: "Devam etmek için manuel plan metnini girin.",
      komutUretilemedi:
        "Sistem çalıştırılabilir girdi üretemedi. Kaynağı kontrol edip yeniden deneyin."
    },
    dikkat: {
      kurulumDevam:
        "Bu aşamada teknik detaylar ikinci katmanda gösterilir. Öncelik operatör karar akışıdır.",
      teknikDetaylarIkinciKatman:
        "Teknik özet ve API uç noktası bilgileri bu ekranın ikincil katmanında gösterilir."
    }
  },
  ortak: {
    hazirOlmaDurumu: "Hazır olma durumu",
    kurulumDurumu: "Kurulum durumu",
    iskeletEkran: "İskelet ekran",
    siradakiAdim: "Sıradaki adım",
    turkceMetinAltyapisiHazir: "Türkçe metin altyapısı hazır",
    teknikDetaylar: "Teknik detaylar",
    endpointBilgisi: "API uç noktası",
    kabulEdilenFormatlar: "Kabul edilen formatlar",
    yuklemeDurumu: "Yükleme durumu",
    basariOzeti: "Başarı özeti",
    hataOzeti: "Hata özeti",
    calistirilabilirGirdi: "Çalıştırılabilir girdi",
    sonrakiAdim: "Sonraki adım",
    teknikAkis: "Teknik olay akışı",
    sonMesaj: "Son mesaj",
    riskSeviyesi: "Risk seviyesi",
    jobKimligi: "İş kimliği",
    komutSayisi: "Komut sayısı",
    notlar: "Notlar"
  },
  ekranlar: {
    planYukle: {
      ustBaslik: "Plan Yükle",
      ustAciklama:
        "DXF, DWG, JSON veya manuel plan metnini tek akışta yükleyin. Sistem çalıştırılabilir girdi üretip üretmediğini açıkça göstersin.",
      kaynakBasligi: "Plan kaynağı seçin",
      kaynakAciklamasi:
        "Önce tek bir kaynak türü seçin. Ardından girdiyi hazırlayıp sistemin komut üretip üretmediğini doğrulayın.",
      anaPanelBasligi: "Kaynağı hazırlayın",
      anaPanelAciklamasi:
        "Bu alandaki işlem tamamlandığında sistem bir sonraki adıma geçmeye hazır olup olmadığını net biçimde gösterecek.",
      manuelBaslik: "Manuel plan metni",
      manuelAciklama:
        "Bu yöntem doğrudan plan satırlarıyla çalışır. Teknik format ayrıntıları yalnızca ikincil detay alanında gösterilir.",
      metinEtiketi: "Plan metni",
      metinYerTutucu: "Örn. LINE 0 0 100 0",
      dropzoneBaslik: "Dosyanızı bırakın veya seçin",
      dropzoneAciklama:
        "Sürükle bırak desteklenir. Seçtiğiniz dosya doğrudan ilgili backend endpoint’ine gönderilir.",
      dosyaHazir: "Dosya hazır",
      dosyaBekliyor: "Dosya bekleniyor",
      manuelHazir: "Plan metni hazır",
      manuelBekliyor: "Plan metni bekleniyor",
      siradakiAdimHazir:
        "Plan girdisi hazır. Hizala ekranına geçip saha referans eşleşmesini başlatın.",
      siradakiAdimBekliyor:
        "Önce tek bir kaynak seçip Girdiyi hazırla butonuyla çalıştırılabilir girdi üretin.",
      teknikKartAciklamasi:
        "Bu bölüm kullanıcıya ilk bakışta gösterilmesi gerekmeyen teknik çıktıları toplar.",
      kaynaklar: {
        dxf: {
          etiket: "DXF dosyası",
          aciklama: "Mimari çizim için önerilen kaynak.",
          formatBilgisi: ".dxf"
        },
        dwg: {
          etiket: "DWG dosyası",
          aciklama: "DWG içeriği arka planda dönüştürülerek işlenir.",
          formatBilgisi: ".dwg"
        },
        json: {
          etiket: "JSON plan dosyası",
          aciklama: "Normalize plan sözleşmesine uygun JSON kaynağı.",
          formatBilgisi: ".json"
        },
        manuel: {
          etiket: "Manuel plan metni",
          aciklama: "Düz plan satırlarını doğrudan girin.",
          formatBilgisi: "Düz metin"
        }
      }
    },
    hizala: {
      ustBaslik: "Hizala",
      ustAciklama:
        "Saha referanslarını girin ve plan duvarlarını gerçek hizalama servisiyle doğrulayın. Ekran tek iş yapar: hizalamanın çalıştırmaya hazır olup olmadığını açıkça göstermek.",
      anaPanelBasligi: "Hizalama girişi",
      kontrolNoktalariBasligi: "Kontrol noktalarını girin",
      kontrolNoktalariAciklama:
        "Her satırda CAD noktası ile saha karşılığını verin. Ana aksiyon yalnızca hizalama doğrulamasıdır.",
      toleransEtiketi: "İzin verilen en yüksek residual (m)",
      duvarSayisi: "Kullanılan duvar sayısı",
      noktaEtiketi: (sira: number) => `Kontrol noktası ${sira}`,
      cadX: "CAD X",
      cadY: "CAD Y",
      sahaX: "Saha X",
      sahaY: "Saha Y",
      onizlemeBaslik: "Hizalama öncesi görünüm",
      sonucBaslik: "Hizalama sonrası görünüm",
      residualOrtalama: "Residual ortalama",
      residualMaksimum: "Residual maksimum",
      donusAcisi: "Dönüş açısı (deg)",
      kaymaBilgisi: "Kayma (tx / ty)",
      sonrakiAdimHazir:
        "Hizalama doğrulandı. Şimdi Kontrol Et ekranında risk analizini çalıştırın.",
      sonrakiAdimBekliyor:
        "Önce kontrol noktalarını girip hizalamayı doğrulayın. Bu adım tamamlanmadan saha eşleşmesi güvenceye alınmaz.",
      mesajlar: {
        planHazirDegil:
          "Duvar verisi hazır değil. Önce Plan Yükle ekranında çalıştırılabilir girdi üretin.",
        bekleyenHizalama:
          "Hizalama henüz çalıştırılmadı. Kontrol noktalarını girip doğrulamayı başlatın.",
        toleransGecersiz: "Geçerli bir tolerans değeri girin.",
        hizalamaHazir:
          "Hizalama doğrulandı. Residual tolerans içinde ve sonraki adıma geçilebilir.",
        hizalamaRiskli:
          "Hizalama çıktısı uyarı verdi. Residual veya nedenler nedeniyle operatör kontrolü gerekiyor.",
        onIzlemeBekliyor: "Henüz hizalama önizlemesi yok.",
        sonucBekliyor: "Henüz hizalama sonucu yok."
      }
    },
    kontrolEt: {
      ustBaslik: "Kontrol Et",
      ustAciklama:
        "Komut metnini gerçek analiz servisiyle doğrulayın. Bu ekran tek iş yapar: planın riskli olup olmadığını açıkça göstermek.",
      anaPanelBasligi: "Analiz akışı",
      ozetBaslik: "Çalıştırma öncesi kontrol",
      ozetAciklama:
        "Bu adım `/api/analyze` çağrısıyla sözdizimi ve çarpışma risklerini toplar; sonuç tek karar cümlesiyle sunulur.",
      komutDurumu: "Komut metni durumu",
      moveSayisi: "Hareket sayısı",
      carpismaSayisi: "Çarpışma sayısı",
      kontrolSonucu: "Kontrol özeti",
      tahminiSure: "Tahmini süre",
      yolUzunlugu: "Yol uzunluğu",
      azalmaOrani: "Azalma oranı",
      duvarTemasi: "Duvar teması",
      bulguBaslik: "Bulgu listesi",
      unrolledKomutlar: "Açılmış komut metni",
      pathNoktasi: "Yol noktası",
      tekAnaIs:
        "Bu ekranda tek ana iş vardır: kontrolü çalıştırmak ve sonucu görmek.",
      sonrakiAdimHazir:
        "Risk analizi temiz. Şimdi Çalıştır ekranında simülasyon veya ön kontrol akışına geçebilirsiniz.",
      sonrakiAdimBekliyor:
        "Önce kontrolü çalıştırın. Operatör hazır değilse nedenini bu ekran söylemelidir.",
      mesajlar: {
        planHazirDegil:
          "Hazır komut metni bulunmuyor. Önce Plan Yükle ekranında girdi üretin.",
        kontrolBekliyor:
          "Kontrol henüz çalıştırılmadı. Ana aksiyon ile gerçek analiz sonucunu alın.",
        kontrolHazir:
          "Kontrol tamamlandı. Engelleyici hata bulunmadı ve akış çalıştırmaya hazır.",
        kontrolEngelli:
          "Kontrol tamamlandı ancak engelleyici bulgular var. Risk çözülmeden bir sonraki adıma geçmeyin.",
        bulguYok: "Parser veya analiz bulgusu yok."
      }
    },
    calistir: {
      ustBaslik: "Çalıştır",
      ustAciklama:
        "Simülasyon ile canlı gönderimi ayrı akışlarda yönetin. Operatör ilk bakışta hazır olup olmadığını, aktif işin hangi durumda olduğunu ve sıradaki güvenli adımı net görsün.",
      durumKartBasligi: "Ana durum",
      akisSecimBasligi: "Çalıştırma akışı",
      akisSecimAciklamasi:
        "Önce hangi akışla ilerleyeceğinizi seçin. Simülasyon güvenli gözlem içindir; canlı gönderim donanıma etki edebilir.",
      simulasyonBaslik: "Simülasyon",
      simulasyonAciklama:
        "Komut metnini `/api/jobs` ile job olarak başlatır, ilerlemeyi `/api/jobs/{id}/stream` üzerinden izler ve gerekirse `/api/jobs/{id}/stop` ile durdurur.",
      canliBaslik: "Canlı gönderim",
      canliAciklama:
        "Bu akış `/api/execute_serial` üzerinden gerçek gönderim yapabilir. Riskli aksiyon açıkça işaretlenir ve onay olmadan canlı komut gönderilmez.",
      onKontrolBaslik: "Ön kontrol",
      onKontrolAciklama:
        "Canlı hatta çıkmadan önce aynı komut metnini güvenli özet akışıyla doğrular. Donanıma gönderim yapmaz.",
      riskRozeti: "Riskli aksiyon",
      guvenliRozet: "Güvenli akış",
      canliOnayEtiketi: "Canlı gönderimin donanıma etki edebileceğini anlıyorum.",
      canliOnayAciklamasi:
        "Bu onay verilmeden canlı gönderim başlatılamaz. Ön kontrol her zaman onaysız çalıştırılabilir.",
      planOzetiBaslik: "Hazır girdi özeti",
      planOzetiAciklama:
        "Çalıştır ekranı yalnızca Plan Yükle adımında üretilen aktif komut metniyle çalışır. Backend kontratı değiştirilmez.",
      sonrakiAdimHazir:
        "Simülasyonla akışı doğrulayın veya ön kontrol çalıştırın. Canlı gönderime yalnızca sonuçlar netleştiğinde geçin.",
      sonrakiAdimEngelli:
        "Önce Plan Yükle ekranında çalıştırılabilir girdi üretin. Bu ekran hazır komut olmadan işlem başlatmaz.",
      mesajlar: {
        planHazirDegil:
          "Hazır komut metni bulunmuyor. Önce Plan Yükle ekranında çalıştırılabilir girdi üretin.",
        planHazir: (girdiAdi: string) =>
          `${girdiAdi} kaynağından üretilen komut metni hazır. Simülasyon veya canlı gönderim seçebilirsiniz.`,
        planHazirVarsayilan:
          "Komut metni hazır. Önce simülasyonla doğrulama yapmanız önerilir.",
        simulasyonBaslatiliyor: "Simülasyon job kaydı açılıyor.",
        simulasyonIzleniyor: "Simülasyon başladı. Akış canlı olarak izleniyor.",
        simulasyonAkisiSuruyor: "Simülasyon sürüyor. Son olay ana durum kartına yansıtılıyor.",
        simulasyonTamamlandi:
          "Simülasyon tamamlandı. Sonuçları gözden geçirip isterseniz canlı gönderime geçebilirsiniz.",
        simulasyonHata:
          "Simülasyon akışında beklenmeyen bir sorun oluştu. Yeniden bağlanabilir veya yeniden başlatabilirsiniz.",
        baglantiKoptu:
          "Akış bağlantısı şu an kararsız. İş devam ediyor olabilir; yeniden bağlanabilirsiniz.",
        yenidenBaglaniyor: "Aktif işe yeniden bağlanılıyor.",
        durduruluyor: "Aktif iş güvenli biçimde durduruluyor.",
        isDurduruldu: "İş durduruldu. İsterseniz aynı komutla yeniden başlayabilirsiniz.",
        jobBulunamadi:
          "İş artık aktif listede görünmüyor. Bu durum kırmızı hata yerine yaşam döngüsü bilgisi olarak gösterildi.",
        onKontrolBaslatiliyor: "Ön kontrol çalıştırılıyor.",
        canliCalistirmaBaslatiliyor: "Canlı gönderim başlatılıyor.",
        canliCalistirmaEngelli:
          "Canlı gönderim için önce risk onayını verin veya aktif simülasyonu durdurun.",
        aktifSimulasyonVar:
          "Aktif simülasyon sürerken canlı gönderim başlatılamaz. Önce işi durdurun veya tamamlanmasını bekleyin."
      },
      kartlar: {
        simulasyonDurumu: "Simülasyon durumu",
        canliDurumu: "Canlı gönderim durumu",
        siradakiAdim: "Sıradaki güvenli adım",
        teknikDetaylar: "Teknik stream detayları"
      },
      teknik: {
        jobKaydi: "Job kaydı",
        stream: "Stream bağlantısı",
        stop: "Durdurma isteği",
        serial: "Canlı gönderim",
        sonOlay: "Son olay"
      }
    },
    sonuclar: {
      ustBaslik: "Sonuçlar",
      ustAciklama:
        "Gerçek durum akışından gelen özetleri toplayın ve çıktı üretin. Bu ekran tek iş yapar: operatöre kullanılabilir sonuç vermek.",
      anaPanelBasligi: "Çıktı akışı",
      ciktiHazirlamaBasligi: "Operasyon çıktısını üretin",
      ciktiHazirlamaAciklama:
        "Bu adım `/api/export` çağrısıyla gerçek çıktı içeriği oluşturur. Önce biçimi seçin, sonra tek ana butonla çıktıyı hazırlayın.",
      formatBasligi: "Çıktı biçimi",
      robotFormat: "Robot çıktısı",
      gcodeFormat: "GCode lite",
      akisOzetiBaslik: "Akış özeti",
      ciktiOzetiBaslik: "Çıktı özeti",
      icerikOnizlemeBaslik: "İçerik önizleme",
      okunanStateBasligi: "Okunan durum kaynakları",
      planKaynagi: "Plan kaynağı",
      hizalamaOzeti: "Hizalama özeti",
      kontrolOzeti: "Kontrol özeti",
      calistirmaOzeti: "Çalıştır özeti",
      dosyaAdi: "Dosya adı",
      ciktiDurumu: "Çıktı durumu",
      exportMoveSayisi: "Çıktı hareket sayısı",
      tekAnaIs:
        "Bu ekranda tek ana iş vardır: seçilen biçimde gerçek çıktıyı hazırlamak.",
      stateKalemi: (etiket: string, varMi: boolean) =>
        `${etiket}: ${varMi ? "okundu" : "henüz yok"}`,
      mesajlar: {
        planHazirDegil:
          "Hazır komut metni olmadan çıktı üretilemez. Önce Plan Yükle ekranına dönün.",
        ciktiBekliyor:
          "Henüz çıktı üretilmedi. Biçimi seçip çıktıyı hazırlayın.",
        ciktiHazir:
          "Çıktı hazır. Dosya özeti ve içerik önizlemesi aşağıda sunuldu.",
        ciktiUyarili:
          "Çıktı üretildi ancak backend engelli uyarısı döndürdü. İçeriği ve bulguları dikkatle gözden geçirin.",
        onizlemeYok: "Henüz içerik önizlemesi yok."
      }
    },
    placeholder: {
      kartBasligi: "Bu ekran için temel alan ayrıldı",
      kartAciklamasi:
        "Bu ekran henüz backend çağrısı bağlanmamış başlangıç alanıdır. Amaç, yeni uygulamanın ayrı kökte ve net katmanlarla ayağa kalktığını doğrulamaktır."
    }
  }
} as const;
