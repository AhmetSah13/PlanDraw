# PlanDraw Backend

## PowerShell'de "running scripts is disabled" hatası

Windows'ta venv aktif etmek için script çalıştırma izni gerekir. İki yol:

### Yol 1: CMD kullan (önerilen)

PowerShell yerine **CMD** (cmd.exe) aç:

```cmd
cd C:\Users\ahmet\OneDrive\Desktop\NewBot\webapp\backend
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Veya tek tıkla: **run.bat** dosyasına çift tıkla (önce venv yoksa oluşturur, sonra sunucuyu başlatır).

### Yol 2: PowerShell script iznini aç (bir kez)

PowerShell’i **Yönetici olarak** açıp:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Sonra normal şekilde:

```powershell
cd webapp\backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Venv olmadan (sistem Python ile)

Venv kullanmak istemezsen, proje kökünde (NewBot) sistem Python ile:

```cmd
cd C:\Users\ahmet\OneDrive\Desktop\NewBot
pip install fastapi uvicorn pydantic
cd webapp\backend
uvicorn app.main:app --reload --port 8000
```

(Bu durumda `commands` ve `scenario_analysis` proje kökünden import edilir; uvicorn’u **proje kökünden** çalıştır: `cd C:\Users\ahmet\OneDrive\Desktop\NewBot` sonra `uvicorn webapp.backend.app.main:app --reload --port 8000`.)
