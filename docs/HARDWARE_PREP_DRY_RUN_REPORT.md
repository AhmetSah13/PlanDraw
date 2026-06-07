# Hardware Prep Dry-Run Report

## Date

2026-05-05

## Scope

Bu rapor yalnizca Asama 1 dry-run serial dogrulamasini kapsar.

Bu rapor gercek donanim testi degildir. Gercek seri port kullanilmadi, `dry_run=false` calistirilmadi ve robota komut gonderilmedi.

Resmi urun hatti kapsaminda dogrulanan alanlar:

- `backend/`
- `webapp/operator-v2/`

Legacy kabul edilen ve dokunulmayan alanlar:

- `webapp/frontend/`
- `webapp/backend/`

## Test Plan

Kullanilan minimum guvenli manuel plan:

```text
LINE 0 0 100 0
```

Bu plan tek kisa cizgiden olusur. Buyuk DXF/DWG, karmasik mimari plan veya gercek robot hareketi kullanilmadi.

## Pipeline Steps

Guncel backend guvenli yerel modda `127.0.0.1:8001` uzerinde calistirildi. `SERIAL_PORT` canli donanim baglantisi icin set edilmedi ve `EXECUTE_SERIAL_ALLOW_REMOTE=false` olarak tutuldu.

Calistirilan endpoint zinciri:

1. `POST /api/compile_plan`
2. `POST /api/analyze`
3. `POST /api/execute_serial` with `dry_run=true`

`/api/compile_plan` request ozeti:

```json
{
  "plan_text": "LINE 0 0 100 0",
  "step_size": 5.0,
  "speed": 120.0,
  "world_scale": 1.0
}
```

`/api/analyze` request ozeti:

```json
{
  "collision_mode": "error",
  "walls": []
}
```

`/api/execute_serial` request ozeti:

```json
{
  "dry_run": true,
  "walls": [],
  "preflight": "api/analyze sonucu"
}
```

## Analyze Result

Analyze sonucu temizdir.

| Alan | Sonuc |
| --- | --- |
| `blocked` | `false` |
| Parser diagnostic sayisi | `0` |
| Analysis diagnostic sayisi | `0` |
| Collision count | `0` |
| Wall proper cross count | `0` |
| Path length | `100.0` |
| Estimated duration | `null` |

Compile sonucu canonical komut metni `SPEED 120.0`, `PEN DOWN`, 0-100 arasinda 5 birimlik `MOVE` adimlari ve `PEN UP` ile olustu.

## Dry-Run Serial Result

`/api/execute_serial` yalniz `dry_run=true` ile calisti.

| Alan | Sonuc |
| --- | --- |
| Status | `dry_run` |
| Command count | `24` |
| `trace_id` | `7c90dd9f33d4` |
| `commands_sha256` | `a2b9e364bd748f00aa64fac4eb147de008f5d95f09026a9168e81702ce6e7050` |
| `preflight_summary.required` | `false` |
| `preflight_summary.commands_sha256` | `a2b9e364bd748f00aa64fac4eb147de008f5d95f09026a9168e81702ce6e7050` |
| Driver status | `null` |

Response mesaji dry-run oldugunu ve driver cagrilmadigini bildirdi. Artifact summary icinde `dry_run=true` ve `driver_kind="dry_run"` dogrulandi.

Dry-run sirasinda olusan artifact ozeti:

- Commands artifact: `backend/reports/execution_job/execute_serial_7c90dd9f33d4_commands.dsl.txt`
- Summary artifact: `backend/reports/execution_job/execute_serial_7c90dd9f33d4_summary.json`

Artifact icerigi dogrulama sirasinda incelendi ve rapora islendikten sonra repo degisikligini dokumantasyonla sinirli tutmak icin gecici dosyalar temizlendi.

## Safety Confirmation

- `dry_run=false` calistirilmadi.
- Gercek seri port kullanilmadi.
- `SERIAL_PORT` canli baglanti icin kullanilmadi.
- Firmware degistirilmedi.
- Robota komut gonderilmedi.
- Remote execution acilmadi.
- Legacy klasorlere dokunulmadi.
- `webapp/frontend/` altinda islem yapilmadi.
- `webapp/backend/` altinda islem yapilmadi.

## Final Verdict

DRY_RUN PASS

## Recommended Next Step

Asama 2: Serial loopback testi
