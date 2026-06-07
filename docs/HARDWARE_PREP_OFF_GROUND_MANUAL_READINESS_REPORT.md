# Hardware Prep Off-Ground Manual Readiness Report

## Scope

Bu rapor gercek donanim testi degildir.

Bu rapor yalnizca off-ground fiziksel test oncesi manuel hazirlik kontrolunu kayit altina almak icin kullanilir. Bu rapor herhangi bir seri porta baglanmaz, robota komut gondermez ve `dry_run=false` calistirma izni vermez.

## Current Gate Status

- Baseline: PASS
- Dry-run: PASS
- Socket loopback: PASS
- Real serial loopback: PENDING
- Off-ground test: NOT RUN

## Manual Checklist

- [ ] Robot off-ground konumda
- [ ] Tekerlekler bosa donebiliyor
- [ ] Kalem/cizim mekanizmasi pasif
- [ ] Acil durdurma hazir
- [ ] Test alani bos
- [ ] Insan eli motorlara yakin degil
- [ ] `SERIAL_PORT` manuel dogrulandi
- [ ] `EXECUTE_SERIAL_ADMIN_TOKEN` set edildi
- [ ] `EXECUTE_SERIAL_ALLOW_REMOTE` kapali
- [ ] Kucuk test plani secildi: `LINE 0 0 100 0`
- [ ] Analyze `collision_mode="error"` temiz
- [ ] Dry-run `trace_id` kaydedildi
- [ ] Dry-run `commands_sha256` kaydedildi
- [ ] `preflight_summary` temiz
- [ ] Operator manuel onay verdi

## Required Values To Fill

- Test date:
- Operator:
- `SERIAL_PORT`:
- `SERIAL_BAUD`:
- `EXECUTE_SERIAL_ADMIN_TOKEN` present: yes/no
- `EXECUTE_SERIAL_ALLOW_REMOTE`: false/true
- `trace_id`:
- `commands_sha256`:
- `preflight_summary`:
- firmware version/commit if known:

## Go / No-Go Decision

- GO ancak tum checklist maddeleri tamamlandiysa verilebilir.
- Herhangi bir madde eksikse NO-GO.

## Safety Warning

Socket loopback PASS, gercek serial transport PASS anlamina gelmez. Ilk off-ground test gercek serial/firmware sinirini ilk kez dogrulayacaktir.

Bu rapor tek basina canli test izni degildir. Canli test ancak manuel checklist tamamlanir, operator acik onay verir ve guvenlik kosullari fiziksel olarak hazirlanirsa degerlendirilebilir.

## Final Status

NO-GO UNTIL MANUAL CHECKLIST COMPLETED
