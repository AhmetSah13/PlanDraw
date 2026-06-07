# Hardware Prep Off-Ground Checklist

Bu checklist, robot bagli ama off-ground ilk guvenli fiziksel testten once manuel olarak doldurulmalidir.

- [ ] Baseline PASS kontrol edildi.
- [ ] Dry-run PASS kontrol edildi.
- [ ] Socket loopback PASS kontrol edildi.
- [ ] Real serial COM loopback durumunun PENDING oldugu biliniyor.
- [ ] `SERIAL_PORT` manuel dogrulandi.
- [ ] `EXECUTE_SERIAL_ADMIN_TOKEN` set edildi.
- [ ] `EXECUTE_SERIAL_ALLOW_REMOTE` kapali.
- [ ] Robot off-ground.
- [ ] Tekerlekler bosa donebiliyor.
- [ ] Kalem/cizim mekanizmasi pasif.
- [ ] Acil durdurma hazir.
- [ ] Batarya/guc baglantisi guvenli.
- [ ] Test alaninda insan eli motorlara yakin degil.
- [ ] Test plani kucuk: `LINE 0 0 100 0`.
- [ ] `/api/analyze` `collision_mode="error"` ile temiz.
- [ ] Analyze sonucu `blocked=false`.
- [ ] Collision veya wall-crossing bulgusu yok.
- [ ] Dry-run `trace_id` kaydedildi.
- [ ] Dry-run `commands_sha256` kaydedildi.
- [ ] Dry-run `preflight_summary` kaydedildi.
- [ ] Operator manuel onay verdi.
- [ ] Test boyunca operator fiziksel gozetim yapacak.

Bu checklist tamamlanmadan `dry_run=false` canli serial testine gecilmemelidir.
