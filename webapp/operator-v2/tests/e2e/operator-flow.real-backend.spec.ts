import { expect, test } from "@playwright/test";

test.skip(
  process.env.OPERATOR_REAL_BACKEND !== "1",
  "Gerçek backend modu yalnızca OPERATOR_REAL_BACKEND=1 ile çalışır.",
);

test("gerçek backend ile plan yukle -> hizala -> kontrol et -> calistir -> sonuclar", async ({ page }) => {
  await page.goto("/plan-yukle");

  await test.step("Plan Yükle", async () => {
    await page.getByRole("button", { name: "Manuel plan metni" }).click();
    await page.getByLabel("Plan metni").fill("LINE 0 0 100 0\nLINE 100 0 100 80\nLINE 100 80 0 80\nLINE 0 80 0 0");
    await page.getByRole("button", { name: "Girdiyi hazırla" }).click();
    await expect(page.getByText(/Çalıştırılabilir girdi üretildi|Çalıştırılabilir girdi/).first()).toBeVisible();
  });

  await test.step("Hizala", async () => {
    await page.getByRole("link", { name: /Hizala/ }).click();
    await page.getByRole("button", { name: "Hizalamayı doğrula" }).click();
    await expect(page.getByText(/Hizalama doğrulandı|Hizalama çıktısı uyarı verdi/).first()).toBeVisible();
  });

  await test.step("Kontrol Et", async () => {
    await page.getByRole("link", { name: /Kontrol Et/ }).click();
    await page.getByRole("button", { name: "Kontrolü çalıştır" }).click();
    await expect(page.getByText(/Kontrol tamamlandı|engelleyici bulgular var/).first()).toBeVisible();
  });

  await test.step("Çalıştır (dry-run)", async () => {
    await page.getByRole("link", { name: /Çalıştır/ }).click();
    await page.getByRole("button", { name: "Ön kontrol çalıştır" }).click();
    await expect(page.getByText(/Ön kontrol|Serial|dry_run|tamamlandı/i).first()).toBeVisible();
  });

  await test.step("Sonuçlar", async () => {
    await page.getByRole("link", { name: /Sonuçlar/ }).click();
    await page.getByRole("button", { name: "Çıktıyı hazırla" }).click();
    await expect(page.getByText(/robot_export|gcode|Çıktı hazır|Çıktı üretildi/).first()).toBeVisible();
  });
});
