# Hardware Prep Off-Ground Test Plan

## Scope

Bu plan gercek cizim testi degildir.

Bu plan, robot bagli ama zeminden kaldirilmis/off-ground durumda yapilacak dusuk riskli ilk baglanti ve davranis testini tarif eder. Amac, robot zeminde serbest hareket etmeden once serial/firmware/motor sinirinin guvenli sekilde gozlenmesidir.

Bu plan tam donanim hazirligi veya tam cizim izni vermez. Ilk fiziksel test yalniz cok kisa komut, dusuk hiz, pasif kalem ve insan gozetimi ile yapilabilir.

## Current Readiness State

- Baseline: PASS
- Dry-run: PASS
- Socket loopback: PASS
- Real serial COM loopback: PENDING
- Firmware/robot physical test: NOT YET PERFORMED

Durum yorumu:

- Socket loopback PASS, serial protokol mantigini ve host tarafindaki `BEGIN` / payload / `END` / `DONE` / `ERR` / `STATUS` / `STOP` akislarini driver-free sekilde dogrular.
- Socket loopback PASS, gercek COM/USB serial transport katmaninin dogrulandigi anlamina gelmez.
- Gercek COM/USB serial transport hala dogrulanmadi.
- Bu nedenle Asama 3 yapilacaksa ekstra guvenlik sartlariyla ve off-ground yapilmalidir.

## Why Off-Ground

Robot zeminde serbest hareket ettirilmeden once motor ve serial davranisinin kontrollu sekilde gozlenmesi gerekir. Off-ground testte tekerlekler bosa donebilir, beklenmeyen hizlanma veya yon hatasi zeminde kacis hareketine donusmeden fark edilir.

Off-ground testin amaci:

- `SERIAL_PORT` / firmware haberlesmesinin acilip acilmadigini gormek.
- Firmware tarafinin beklenen protokol cevabini verip vermedigini gormek.
- Motorlarin dusuk hizda beklenen yone kisa tepki verip vermedigini gormek.
- Timeout, `ERR`, surekli hareket veya beklenmeyen yon risklerini zeminde serbest hareket olmadan yakalamak.

## Preconditions

Asagidaki kosullar saglanmadan off-ground test baslatilmamalidir:

- Robot zeminden kaldirilmis/off-ground olmali.
- Tekerlekler bosa donebilmeli.
- Kalem/cizim mekanizmasi pasif olmali.
- Acil durdurma hazir olmali.
- Batarya/guc baglantisi guvenli olmali.
- Test alaninda insan eli motorlara, tekerleklere veya hareketli mekanizmaya yakin olmamali.
- `SERIAL_PORT` manuel dogrulanmali.
- `EXECUTE_SERIAL_ADMIN_TOKEN` set edilmeli.
- `EXECUTE_SERIAL_ALLOW_REMOTE` kapali olmali.
- Ilk test sadece cok kisa komut olmali.
- Once dry-run sonucu alinmis olmali.
- `trace_id`, `commands_sha256`, `preflight_summary` kaydedilmis olmali.
- Analyze sonucu `blocked=false` olmali.
- Collision veya wall-crossing bulgusu olmamali.
- Operator testi fiziksel olarak izlemeli.

## Forbidden Actions

Asagidaki aksiyonlar yasaktir:

- Buyuk plan calistirma.
- Ilk denemede zeminde hareket.
- Yuksek hiz.
- Remote execution.
- Token olmadan canli serial.
- `blocked` analyze sonucu ile canli gonderim.
- Collision veya wall-crossing uyarisi varken canli gonderim.
- Kalem aktifken ilk test.
- Insan gozetimi olmadan test.
- Acil durdurma hazir degilken test.
- `SERIAL_PORT` dogrulanmadan test.
- Socket loopback PASS sonucunu full hardware readiness gibi yorumlama.

## Minimal Test Plan

1. Yazilim baseline tekrar kontrol edilir.
2. Kucuk plan hazirlanir:

```text
LINE 0 0 100 0
```

3. `/api/compile_plan` calisir.
4. `/api/analyze` `collision_mode="error"` ile temiz sonuc alinir.
5. `/api/execute_serial` `dry_run=true` ile `trace_id`, `commands_sha256` ve `preflight_summary` alinir.
6. `SERIAL_PORT` manuel dogrulanir.
7. Robot off-ground konuma alinir.
8. Kalem/cizim mekanizmasi pasif birakilir.
9. `dry_run=false` yalniz bu kosullar saglanirsa ve kullanici acikca manuel onay verirse yapilabilir.
10. Ilk canli test sonrasi motor davranisi, loglar ve cevaplar kaydedilir.

## Pass Criteria

Off-ground test yalniz asagidaki kosullarin tamami saglanirsa PASS kabul edilir:

- Port aciliyor.
- Robot/firmware beklenen cevap veriyor.
- `DONE` veya beklenen protokol cevabi aliniyor.
- Motorlar dusuk hizda beklenen yonde kisa tepki veriyor.
- `ERR` yok.
- Timeout yok.
- Beklenmeyen surekli hareket yok.
- Acil durdurma gerekmeden test tamamlanıyor.
- Log ve trace kayitlari saklaniyor.

## Fail Criteria

Asagidakilerden biri olursa test FAIL kabul edilir ve bir sonraki asamaya gecilmez:

- Port acilamiyor.
- Timeout.
- `ERR`.
- Beklenmeyen motor yonu.
- Surekli hareket.
- Robot off-ground degilken hareket denemesi.
- Acil durdurma ihtiyaci.
- Log/trace kaydi yok.
- Analyze blocked, collision veya wall-crossing bulgusu.
- Operator fiziksel gozetimi yok.

## Required Logs

Asagidaki kayitlar saklanmalidir:

- `commands_text`
- `trace_id`
- `commands_sha256`
- `preflight_summary`
- `execute_serial` response
- Serial logs
- Test tarihi
- Kullanilan `SERIAL_PORT`
- Firmware versiyonu veya commit bilgisi varsa
- Operator gozlem notu
- PASS/FAIL karari ve sebebi

## Final Gate

Socket loopback PASS tek basina full hardware readiness degildir.

Socket loopback, host tarafindaki protokol mantigini driver-free sekilde dogrular. Off-ground test ise gercek serial/firmware sinirini ilk kez guvenli sekilde dogrulamak icindir.

Off-ground test PASS olmadan zeminde hareket, kalem aktif cizim veya tam plan testi yapilmamalidir.
