# Cursor / PowerShell Terminalde Backend ve Frontend

Cursor terminali PowerShell kullandığı için script kısıtı (`npm`, venv `Activate.ps1`) hata verebilir. İki yol:

---

## 1) Bir kez izin ver (önerilen)

PowerShell’de **bir kez** şunu çalıştır (Cursor terminalinde de olur):

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Sorulursa `Y` de. Bundan sonra:

**Backend:**
```powershell
cd webapp\backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt   # sadece ilk sefer
uvicorn app.main:app --reload --port 8000
```

**Frontend** (yeni terminal sekmesi):
```powershell
cd webapp\frontend
npm install   # sadece ilk sefer
npm run dev
```

---

## 2) İzin vermeden (script kullanmadan)

ExecutionPolicy değiştirmek istemezsen, Cursor terminalinde doğrudan şunları kullan:

**Backend** (venv’i “aktif etmeden” doğrudan venv Python’u):
```powershell
cd webapp\backend
# İlk sefer: venv yoksa oluştur ve paket kur
if (-not (Test-Path .venv)) { python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt }
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

**Frontend** (`npm` yerine `npm.cmd` — script değil, CMD betiği):
```powershell
cd webapp\frontend
npm.cmd install   # sadece ilk sefer
npm.cmd run dev
```

---

Özet: İzin verirsen her gün kullandığın `npm` ve `uvicorn` komutları aynen çalışır; vermezsen backend için `.\webapp\backend\.venv\Scripts\python.exe -m uvicorn ...`, frontend için `npm.cmd` kullan.
