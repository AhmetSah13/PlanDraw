# Hardware Prep Runbook

Bu dokuman PlanDraw / NewBot projesinde yazilim tarafindan donanim hazirlik asamasina guvenli gecis icin kullanilir.

## 1. Amac

Bu asama "gercek robota tam cizim yaptirma" asamasi degildir.

Bu asamanin amaci, yazilim zincirinin donanim entegrasyonuna hazirlik icin guvenli, izlenebilir ve kademeli sekilde dogrulanmasidir. Gercek robot hareketi ancak yazilim baseline, dry-run, loopback ve kontrollu fiziksel test adimlari basariyla tamamlandiktan sonra denenmelidir.

Bu runbook, operatorun ve gelistirme ekibinin ayni guvenlik siralarini takip etmesini saglar. Her asamada baslamadan once gerekenler, basari kriterleri, hata halinde durus noktasi ve saklanacak kanitlar acikca belirtilir.

## 2. Mevcut Yazilim Durumu

Son Hardware Readiness Blocking Fix sonucu: READY FOR HARDWARE PREP.

Bilinen dogrulama durumu:

- Backend test sonucu: `201 passed, 87 deselected`
- Frontend `build`, `lint`, `test`, `e2e` sonuclari gecti.
- `verify:backend-live` gercek backend uzerinde dry-run/simulasyon akisini dogruladi.
- `e2e:real` gercek backend ile operator akisini dogruladi.
- `/api/execute_serial` backend tarafinda preflight gate eklendi.
- Canli gonderim oncesinde final `collision_mode="error"` analizi var.
- `dry_run=true` akisi korunuyor.
- Canli seri gonderim icin `trace_id`, `commands_sha256` ve `preflight_summary` response seviyesinde izlenebilir.

Bu durum, yazilimin donanim hazirligina gecmek icin temel engelleri kapattigini gosterir. Bu durum, robotun dogrudan tam plan cizimine hazir oldugu anlamina gelmez.

## 3. Donanima Gecmeden Once Zorunlu Guvenlik Kurallari

- `EXECUTE_SERIAL_ADMIN_TOKEN` kullanilmali.
- `EXECUTE_SERIAL_ALLOW_REMOTE` kapali kalmali.
- `dry_run=false` yalniz kontrollu testlerde kullanilmali.
- `SERIAL_PORT` acikca set edilmeli.
- `SERIAL_BAUD` test ortamindaki firmware/protokol beklentisine gore dogrulanmali.
- Acil durdurma fiziksel olarak hazir olmali.
- Robot ilk testte zeminde tam serbest hareket ettirilmemeli.
- Ilk fiziksel testte robot kaldirilmis veya off-ground durumda olmali.
- Ilk fiziksel testte motor hizi dusuk olmali.
- Ilk fiziksel testte kalem/cizim mekanizmasi pasif olmali.
- Analiz `blocked` donuyorsa canli serial denenmemeli.
- Collision warning veya error varsa canli serial denenmemeli.
- Dry-run sonucu ve artifact incelenmeden canli test denenmemeli.

## 4. Asamali Gecis Plani

### Asama 0: Yazilim Baseline Dogrulama

Amac:

Yazilim tarafinin mevcut guvenlik ve regresyon kapilarindan gectigini dogrulamak.

Calistirilacaklar:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests
```

```powershell
cd webapp/operator-v2
npm run build
npm run lint
npm run test
npm run e2e
npm run verify:backend-live
npm run e2e:real
```

Baslamadan once gerekenler:

- Backend sanal ortam hazir olmali.
- Operator V2 bagimliliklari kurulu olmali.
- Gercek backend lokal standart portta calisabilir durumda olmali.
- Gercek seri port veya robot baglantisi kullanilmamali.

Basarili sayilmasi icin gerekenler:

- Backend testleri basarisiz olmamali.
- Frontend build/lint/test/e2e basarisiz olmamali.
- `verify:backend-live` mock disi backend akisini tamamlamali.
- `e2e:real` browser uzerinden gercek backend akisini tamamlamali.

Basarisizlik halinde:

- Donanim hazirlik asamasina gecme.
- Ilk hata veren komutun logunu sakla.
- Kod veya ortam sorunu ayrilana kadar fiziksel test planlama.

Saklanacak log/artifact:

- Backend pytest cikti ozeti.
- Frontend build/lint/test/e2e cikti ozeti.
- `verify:backend-live` cikti ozeti.
- `e2e:real` cikti ozeti.

### Asama 1: Dry-run Serial Dogrulama

Amac:

`/api/execute_serial` hattinin fiziksel robota komut gondermeden canonical command, preflight ve artifact izlenebilirligini dogrulamak.

Kontrol edilecekler:

- `/api/execute_serial` yalniz `dry_run=true` ile cagrilmali.
- Response icinde `trace_id` bulunmali.
- Response icinde `commands_sha256` bulunmali.
- Response icinde `preflight_summary` bulunmali.
- Dry-run artifact dosyalari beklenen komut metniyle uyumlu olmali.

Baslamadan once gerekenler:

- Asama 0 basariyla tamamlanmis olmali.
- Plan, hizalama ve kontrol et adimlari temiz gecmis olmali.
- Collision veya blocked durumu olmamali.
- Gercek seri port kullanilmamali.

Basarili sayilmasi icin gerekenler:

- `dry_run=true` response basarili olmali.
- `trace_id` kaydedilmeli.
- `commands_sha256` kaydedilmeli.
- `preflight_summary` temiz olmali.
- Artifact icerigi beklenen canonical command ciktisiyla uyumlu olmali.

Basarisizlik halinde:

- Canli serial denenmemeli.
- Response ve artifact farklari incelenmeli.
- Parser, analyze veya command serialization uyumsuzlugu varsa once yazilimda kapatilmali.

Saklanacak log/artifact:

- `/api/execute_serial` dry-run response.
- `trace_id`.
- `commands_sha256`.
- `preflight_summary`.
- Dry-run command artifact dosyasi.
- Dry-run summary artifact dosyasi.

### Asama 2: Serial Loopback Testi

Amac:

Gercek robot bagli olmadan serial protokolun frame, response ve timeout davranisini dogrulamak.

Kontrol edilecekler:

- Loopback veya sanal COM kullanilmali.
- Gercek robot bagli olmamali.
- BEGIN/END frame yapisi dogrulanmali.
- DONE/ERR/timeout davranisi dogrulanmali.
- Payload beklenen canonical command ciktisiyla eslesmeli.

Baslamadan once gerekenler:

- Asama 1 basariyla tamamlanmis olmali.
- Kullanilacak loopback/sanal COM ortami belirlenmis olmali.
- `SERIAL_PORT` yalniz loopback/sanal COM portunu gostermeli.
- `SERIAL_BAUD` hedef protokol beklentisine gore set edilmeli.
- Admin token set edilmeli.
- Remote execution kapali olmali.

Basarili sayilmasi icin gerekenler:

- Frame baslangic ve bitis yapisi beklenen formatta olmali.
- DONE cevabi dogru islenmeli.
- ERR cevabi guvenli hata olarak raporlanmali.
- Timeout durumunda islem basarisiz ve anlasilir sekilde kapanmali.
- Payload hash veya metin olarak dry-run artifact ile izlenebilir olmali.

Basarisizlik halinde:

- Gercek robot baglanmamali.
- Serial framing, baud, timeout ve protokol uyumsuzluklari ayrica giderilmeli.
- Hata tekrar uretilebilir hale getirilmeden bir sonraki asamaya gecilmemeli.

Saklanacak log/artifact:

- Loopback serial logu.
- Gonderilen payload.
- Alinan DONE/ERR/timeout cevabi.
- Iliskili `trace_id`.
- Iliskili `commands_sha256`.

### Asama 3: Robot Bagli Ama Guvenli Fiziksel Test

Amac:

Robot bagliyken motor/serial hattinin en dusuk riskli fiziksel kosullarda temel tepki verdigini dogrulamak.

Kontrol edilecekler:

- Robot kaldirilmis veya off-ground durumda olmali.
- Motorlar dusuk hizda calistirilmali.
- Kalem veya cizim mekanizmasi pasif olmali.
- Sadece cok kisa tek cizgi komutu denenmeli.
- Acil durdurma fiziksel olarak hazir olmali.

Baslamadan once gerekenler:

- Asama 2 basariyla tamamlanmis olmali.
- Robot cevresi bos olmali.
- Operator fiziksel olarak robotu gozlemliyor olmali.
- Admin token set edilmeli.
- Remote execution kapali olmali.
- `SERIAL_PORT` gercek robot portu olarak dogrulanmali.
- `SERIAL_BAUD` firmware tarafiyla dogrulanmali.

Basarili sayilmasi icin gerekenler:

- Robot beklenen kisa tepkiyi verir.
- Beklenmeyen hizlanma, takilma veya surekli hareket olmaz.
- Stop/iptal davranisi guvenli calisir.
- Loglar komut ve tepki arasinda izlenebilir kalir.

Basarisizlik halinde:

- Test hemen durdurulmali.
- Robot enerjisi guvenli sekilde kesilmeli.
- Canli serial tekrar denenmemeli.
- Serial log, backend response ve firmware cevabi birlikte incelenmeli.

Saklanacak log/artifact:

- Canli test response.
- `trace_id`.
- `commands_sha256`.
- `preflight_summary`.
- Serial log.
- Operator gozlem notu.

### Asama 4: Dusuk Hizli Gercek Hareket Testi

Amac:

Robotun zeminde kucuk ve kontrollu bir hareketi dusuk hizda guvenli tamamladigini dogrulamak.

Kontrol edilecekler:

- Kucuk alan kullanilmali.
- Tek kisa path secilmeli.
- Acil durdurma hazir olmali.
- Insan gozetimi olmali.
- Robot cevresi bos olmali.

Baslamadan once gerekenler:

- Asama 3 problemsiz tamamlanmis olmali.
- Zemin uygun ve engelsiz olmali.
- Plan once dry-run ve loopback ile dogrulanmis olmali.
- Collision ve blocked durumu olmamali.

Basarili sayilmasi icin gerekenler:

- Robot beklenen dusuk hizli hareketi tamamlar.
- Hareket rotasi beklenen path ile uyumlu olur.
- Acil durdurma erisilebilir kalir.
- Komut, response ve fiziksel davranis arasinda izlenebilirlik korunur.

Basarisizlik halinde:

- Test durdurulmali.
- Ayni plan tekrar denenmemeli.
- Kinematik, hiz, firmware ve serial loglari incelenmeli.
- Gerekirse Asama 2 veya Asama 3'e geri donulmeli.

Saklanacak log/artifact:

- Dry-run artifact.
- Loopback log.
- Canli response.
- Serial log.
- Operator gozlem notu.

### Asama 5: Ilk Basit Cizim Testi

Amac:

Minimum plan ile cizim mekanizmasinin ve hareketin birlikte calistigini dogrulamak.

Kontrol edilecekler:

- Kare veya tek cizgi gibi minimum plan kullanilmali.
- Buyuk mimari plan kullanilmamali.
- Once dry-run yapilmali.
- Sonra loopback yapilmali.
- En son canli test yapilmali.

Baslamadan once gerekenler:

- Asama 4 basariyla tamamlanmis olmali.
- Cizim mekanizmasi guvenli ve dusuk riskli ayarda olmali.
- Plan analizde temiz olmali.
- Collision warning veya error olmamali.

Basarili sayilmasi icin gerekenler:

- Robot minimum cizimi beklenen sekilde tamamlar.
- Cizim olcegi, yonu ve path sirasi kabul edilebilir olur.
- Stop ve hata davranislari halen guvenli kalir.
- Komut hash, preflight ve artifact kayitlari saklanir.

Basarisizlik halinde:

- Buyuk plan testine gecilmemeli.
- Cizim mekanizmasi, hiz, kalibrasyon ve path generation tekrar incelenmeli.
- Asama 4'e geri donulmeli.

Saklanacak log/artifact:

- Kullanilan minimum plan.
- Dry-run artifact.
- Loopback log.
- Canli response.
- Cizim sonucu fotografi veya operator notu.

### Asama 6: Tam Plan Cizim Testi

Amac:

Onceki tum asamalar problemsiz gectikten sonra daha kapsamli plan cizimini kontrollu sekilde denemek.

Kontrol edilecekler:

- Sadece onceki asamalar problemsiz gectiyse yapilir.
- Plan once dry-run ile dogrulanir.
- Plan once loopback ile dogrulanir.
- Plan collision/error olmadan gecmelidir.
- Operator test boyunca robotu izlemelidir.

Baslamadan once gerekenler:

- Asama 0-5 basariyla tamamlanmis olmali.
- Tum log ve artifact kayitlari tutarli olmali.
- Robot fiziksel olarak stabil davranmis olmali.
- Acil durdurma hazir olmali.

Basarili sayilmasi icin gerekenler:

- Tam plan beklenen sinirlar icinde tamamlanir.
- Robotta beklenmeyen hizlanma, sapma veya takilma olmaz.
- Cizim sonucu kabul edilebilir olur.
- Loglar sonradan denetlenebilir durumdadir.

Basarisizlik halinde:

- Tam plan tekrar denenmemeli.
- Son basarili asamaya geri donulmeli.
- Hata komut, serial, firmware veya mekanik kaynakli olarak ayrilmali.

Saklanacak log/artifact:

- Tam plan input dosyasi.
- Analyze response.
- Dry-run artifact.
- Loopback log.
- Canli response.
- Serial log.
- Operator gozlem notu.

## 5. Her Asama Icin Genel Giris/Cikis Kriterleri

Her asamada baslamadan once:

- Onceki asama basariyla tamamlanmis olmali.
- Kullanilacak plan veya komut kapsami minimum tutulmali.
- Operator sorumlusu belirlenmis olmali.
- Log/artifact saklama yeri belirlenmis olmali.
- Hata halinde durma karari onceden net olmali.

Her asamada basarili sayilmasi icin:

- Beklenen response veya fiziksel davranis elde edilmeli.
- Hata, blocked, collision veya timeout olmamali.
- `trace_id`, `commands_sha256` ve ilgili preflight/artifact bilgisi saklanmali.
- Sonuc tekrar denetlenebilir olmali.

Basarisizlik halinde:

- Bir sonraki asamaya gecilmemeli.
- Test tekrar edilmeden once kok neden ayrilmali.
- Gerekirse son basarili asamaya geri donulmeli.
- Hata loglari silinmemeli.

Saklanacak kanitlar:

- Terminal komut ciktisi.
- Backend response.
- Serial log.
- Dry-run artifact.
- Loopback log.
- Operator gozlem notu.
- Kullanilan plan veya command text.

## 6. Minimum Test Komutlari

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests
```

Frontend:

```powershell
cd webapp/operator-v2
npm run build
npm run lint
npm run test
npm run e2e
npm run verify:backend-live
npm run e2e:real
```

## 7. Donanim Oncesi Kesinlikle Yapilmamasi Gerekenler

- Ilk denemede buyuk plan cizme.
- Ilk denemede yuksek hiz kullanma.
- Token olmadan canli serial acma.
- Remote execution acma.
- Analiz `blocked` iken serial gonderme.
- Collision warning veya error varken canli gonderme.
- Dry-run sonucu incelenmeden canli deneme yapma.
- Loopback dogrulamasi yapmadan robot baglama.
- Robot cevresi bos degilken test yapma.
- Acil durdurma hazir degilken test yapma.
- `SERIAL_PORT` dogrulanmadan canli serial deneme.
- `SERIAL_BAUD` dogrulanmadan canli serial deneme.

## 8. Operator Checklist'i

Gercek testten once asagidaki maddeler tek tek isaretlenmelidir:

- [ ] Backend testleri gecti.
- [ ] Frontend build gecti.
- [ ] Frontend lint gecti.
- [ ] Frontend unit testleri gecti.
- [ ] Frontend E2E gecti.
- [ ] `verify:backend-live` gecti.
- [ ] `e2e:real` gecti.
- [ ] Dry-run basarili.
- [ ] `trace_id` kaydedildi.
- [ ] `commands_sha256` kaydedildi.
- [ ] `preflight_summary` temiz.
- [ ] Dry-run artifact incelendi.
- [ ] Loopback testi basarili.
- [ ] `SERIAL_PORT` dogrulandi.
- [ ] `SERIAL_BAUD` dogrulandi.
- [ ] `EXECUTE_SERIAL_ADMIN_TOKEN` set edildi.
- [ ] Remote execution kapali.
- [ ] Acil durdurma hazir.
- [ ] Robot cevresi bos.
- [ ] Robot ilk fiziksel test icin kaldirilmis veya off-ground.
- [ ] Dusuk hiz secildi.
- [ ] Kalem/cizim mekanizmasi ilk test icin pasif.
- [ ] Ilk test kisa komut.
- [ ] Operator test boyunca robotu gozlemleyecek.

## 9. Final Oneri

Bu dokuman gercek donanima dogrudan gecis izni degildir. Bu dokuman kontrollu hardware prep surecinin guvenli uygulanmasi icindir.

Donanima gecis, yalnizca bu runbook'taki asamalar sirayla tamamlandiginda ve her asamanin kanitlari saklandiginda degerlendirilmelidir. Bir asama basarisiz olursa bir sonraki asamaya gecilmemeli, hata kok nedeni kapatilmali ve son basarili asamadan tekrar baslanmalidir.
