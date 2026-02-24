# PlanDraw Frontend

## PowerShell'de "running scripts is disabled" hatası

Windows'ta `npm` aslında `npm.ps1` çalıştırmaya çalışıyor ve script kısıtı yüzünden hata veriyor.

### Yol 1: CMD kullan (önerilen)

**CMD** (cmd.exe) aç:

```cmd
cd C:\Users\ahmet\OneDrive\Desktop\NewBot\webapp\frontend
npm install
npm run dev
```

CMD'de `npm` komutu `npm.cmd` kullanır, script izni gerekmez.

### Yol 2: run.bat

**run.bat** dosyasına çift tıkla. İlk seferde `npm install`, sonra `npm run dev` çalışır.

### Yol 3: PowerShell script iznini aç (bir kez)

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Sonra PowerShell'de normal şekilde `npm install` ve `npm run dev` çalışır.
