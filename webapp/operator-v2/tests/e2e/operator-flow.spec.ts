import { expect, test } from "@playwright/test";

test("operatör akışı hizala, kontrol et, çalıştır ve sonuçlar ekranlarında gerçek akışları kullanır", async ({
  page,
}) => {
  await page.route("**/api/compile_plan", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        commands_text: "LINE 0 0 100 0\nLINE 100 0 100 100",
        plan_text: "LINE 0 0 100 0\nLINE 100 0 100 100",
        walls: [
          [0, 0, 10, 0],
          [10, 0, 10, 10],
        ],
        raw_path_points: [
          [0, 0],
          [10, 0],
          [10, 10],
        ],
        warnings: [],
        recommended_step_size: 0.25,
      }),
    });
  });

  await page.route("**/api/alignment/rigid_2d", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        alignment: {
          transform_type: "rigid_2d",
          point_count: 3,
          residual_mean_m: 0.01,
          residual_max_m: 0.02,
          tolerance_m: 0.05,
          blocked: false,
          transform: {
            theta_rad: 0,
            theta_deg: 0,
            tx_m: 0.1,
            ty_m: 0.2,
          },
          reasons: [],
          notes: ["Hizalama doğrulandı."],
        },
        pre_svg: "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 60'><rect width='100' height='60' fill='#edf4fb'/><text x='12' y='35'>Önce</text></svg>",
        post_svg: "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 60'><rect width='100' height='60' fill='#eef9f2'/><text x='12' y='35'>Sonra</text></svg>",
      }),
    });
  });

  await page.route("**/api/analyze", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        blocked: false,
        commands_unrolled: "MOVE 0 0\nMOVE 10 10",
        parser: [],
        analysis: [],
        stats: {
          move_count: 2,
          estimated_time: 12.5,
          path_length: 22.4,
          reduction_ratio: 0.15,
          collision_count: 0,
          wall_touch_count: 0,
          path_points: [
            [0, 0],
            [10, 10],
          ],
        },
      }),
    });
  });

  await page.route("**/api/execute_serial", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "completed",
        message: "Ön kontrol tamamlandı.",
        command_count: 2,
        artifact_paths: ["out/preview.txt"],
        notes: ["Donanıma gönderim yapılmadı."],
      }),
    });
  });

  await page.route("**/api/export", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        blocked: false,
        filename: "robot_export.robot_v1.txt",
        content: "MOVE 0 0\nMOVE 10 10",
        parser_diags: [],
        analysis_diags: [],
        stats: {
          move_count: 2,
          estimated_time: 12.5,
          path_length: 22.4,
        },
      }),
    });
  });

  await page.goto("/plan-yukle");
  await page.getByRole("button", { name: "Manuel plan metni" }).click();
  await page.getByLabel("Plan metni").fill("LINE 0 0 100 0\nLINE 100 0 100 100");
  await page.getByRole("button", { name: "Girdiyi hazırla" }).click();
  await expect(
    page.getByText("Plan girdisi hazır. Hizala ekranına geçip saha referans eşleşmesini başlatın."),
  ).toBeVisible();
  await expect(page.getByTestId("plan-preview-canvas")).toBeVisible();

  await page.getByRole("link", { name: /Hizala/ }).click();
  await page.getByRole("button", { name: "Hizalamayı doğrula" }).click();
  await expect(
    page.getByText("Hizalama doğrulandı. Residual tolerans içinde ve sonraki adıma geçilebilir."),
  ).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  const hizalaCanvas = page.getByTestId("alignment-overlay-canvas");
  await expect(hizalaCanvas).toBeVisible();
  await hizalaCanvas.hover();
  const hizalaScrollStart = await page.evaluate(() => window.scrollY);
  await page.mouse.wheel(0, 700);
  const hizalaScrollAfterCanvas = await page.evaluate(() => window.scrollY);
  expect(Math.abs(hizalaScrollAfterCanvas - hizalaScrollStart)).toBeLessThan(2);

  await page.getByRole("link", { name: /Kontrol Et/ }).click();
  await page.getByRole("button", { name: "Kontrolü çalıştır" }).click();
  await expect(
    page.getByText("Kontrol tamamlandı. Engelleyici hata bulunmadı ve akış çalıştırmaya hazır."),
  ).toBeVisible();

  await page.getByRole("link", { name: /Çalıştır/ }).click();
  await expect(page.getByTestId("simulation-canvas")).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  const simCanvas = page.getByTestId("simulation-canvas");
  await simCanvas.hover();
  const calistirScrollStart = await page.evaluate(() => window.scrollY);
  await page.mouse.wheel(0, 700);
  const calistirScrollAfterCanvas = await page.evaluate(() => window.scrollY);
  expect(Math.abs(calistirScrollAfterCanvas - calistirScrollStart)).toBeLessThan(2);
  await page.getByRole("button", { name: "Oynat" }).click();
  await expect.poll(async () => Number(await page.getByTestId("simulation-progress").getAttribute("value"))).toBeGreaterThan(0);
  await page.getByRole("button", { name: "Ön kontrol çalıştır" }).click();
  await expect(page.getByText("Ön kontrol tamamlandı.").first()).toBeVisible();

  await page.getByRole("link", { name: /Sonuçlar/ }).click();
  await page.getByRole("button", { name: "Çıktıyı hazırla" }).click();
  await expect(page.getByText("robot_export.robot_v1.txt")).toBeVisible();
  await page.getByText("İçerik önizleme").click();
  await expect(page.getByText("MOVE 10 10")).toBeVisible();
});
