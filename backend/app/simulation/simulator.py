from __future__ import annotations

import csv
import math
import random
from typing import Dict, List, Tuple, Optional

import pygame

from app.core.plan_module import Plan, load_plan_from_file
from app.pathing.path_generator import PathGenerator
from app.execution.commands import Command, MoveCommand, Diagnostic, parse_commands, serialize_commands
from app.execution.compiler import compile_path_to_commands
from app.execution.executor import CommandExecutor
from app.analysis.scenario_analysis import analyze_commands, export_commands, ScenarioLimits, ScenarioStats


# --- Gürültü / drift parametreleri ---

# Başlık (heading) drift'i: saniyede derece cinsinden sapma hızı.
DRIFT_DEG_PER_SEC: float = 1.0

# Konum gürültüsü: saniyede biriken standart sapma (world unit / sqrt(saniye)).
# Her karede kullanılan gürültü, bu değerin dt'nin karekökü ile çarpılmasıyla hesaplanır.
POSITION_NOISE_STD_PER_SEC: float = 2.0


class WorldToScreenTransform:
    """Dünya (plan) koordinatlarını ekran koordinatlarına çevirir."""

    def __init__(
        self,
        world_bounds: Tuple[float, float, float, float],
        screen_width: int,
        screen_height: int,
        margin: int = 50,
    ) -> None:
        min_x, min_y, max_x, max_y = world_bounds

        # Boş veya tek noktalı durumlar için güvenlik
        if max_x - min_x == 0:
            max_x = min_x + 1.0
        if max_y - min_y == 0:
            max_y = min_y + 1.0

        world_width = max_x - min_x
        world_height = max_y - min_y

        usable_width = max(1, screen_width - 2 * margin)
        usable_height = max(1, screen_height - 2 * margin)

        scale_x = usable_width / world_width
        scale_y = usable_height / world_height

        self.scale = min(scale_x, scale_y)
        self.min_x = min_x
        self.min_y = min_y
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.margin = margin

    def world_to_screen(self, x: float, y: float) -> Tuple[int, int]:
        """
        Dünya koordinatlarını (x, y) pygame ekran koordinatlarına dönüştürür.

        Y ekseni, matematiksel sisteme göre yukarı pozitif olduğu varsayılarak
        ekran koordinatlarında ters çevrilir (pygame'de aşağı pozitif).
        """
        sx = self.margin + (x - self.min_x) * self.scale
        sy = self.screen_height - self.margin - (y - self.min_y) * self.scale
        return int(round(sx)), int(round(sy))


class RobotSimulator:
    """Basit 2B duvar ve yol simülatörü."""

    def __init__(
        self,
        screen_width: int = 900,
        screen_height: int = 700,
        world_speed: float = 120.0,
        step_size: float = 5.0,
    ) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.world_speed = world_speed
        self.step_size = step_size

        # --- World koordinat standardı ---
        # PathGenerator çıktısı "raw" kabul edilir -> world'e çevrilir.
        # commands.txt içindeki MOVE değerleri varsayılan olarak world kabul edilir.
        self.world_scale: float = 1.0
        self.world_offset: Tuple[float, float] = (0.0, 0.0)
        # commands.txt içindeki MOVE değerleri hangi birimde?
        # True: commands.txt world birimindedir (önerilen ve default)
        # False: commands.txt raw birimdedir -> world'e çevrilir
        self.commands_are_world: bool = True

        # Son parse işleminden gelen diagnostics listesi (ERROR/WARN)
        self.parser_diagnostics: List[Diagnostic] = []
        # Safety Gate / senaryo analizi diagnostics (bounds, limit, kalite)
        self.analysis_diagnostics: List[Diagnostic] = []
        # Son analiz çıktısı (I dump ve bounds için)
        self._last_scenario_stats: Optional[ScenarioStats] = None
        # Run Gate: Parser veya Analysis ERROR varsa True (simülasyon çalışmasın)
        self.scenario_blocked: bool = False
        # Komut dosyası header metadata (# name:, # units:, ...)
        self.scenario_metadata: Dict[str, str] = {}

        self.plan: Plan = load_plan_from_file("plan.txt")
        path_generator = PathGenerator(self.plan, step_size=self.step_size)
        raw_path: List[Tuple[float, float]] = path_generator.generate_path()
        self.path: List[Tuple[float, float]] = self._to_world_path(raw_path)

        # Komut akışını oluştur ya da mevcut dosyadan yükle.
        self.commands: List[Command] = self._load_or_generate_commands()
        self.executor: CommandExecutor = CommandExecutor(self.commands)

        self.transform = self._create_transform()

        # İdeal (hatasız) yol üzerindeki konum (executor çıktısı)
        self.ideal_position: Optional[List[float]] = None
        # Gerçek (drift/gürültü uygulanmış) robot konumu
        self.robot_position: Optional[List[float]] = None

        # Çizilen iz (gerçek robot konumu üzerinden)
        self.trace: List[Tuple[float, float]] = []

        # Simülasyon durumu
        self.paused: bool = False
        self.finished: bool = False

        # Drift / gürültü durumları
        self.drift_enabled: bool = False
        self.noise_enabled: bool = False
        self.heading_drift_deg: float = 0.0

        # Hata metrikleri
        self.error_instantaneous: float = 0.0
        self.error_mean: float = 0.0
        self.error_max: float = 0.0
        self._error_sum: float = 0.0
        self._error_count: int = 0

        # Simülasyon zamanı ve kayıt edilen örnekler
        self.sim_time: float = 0.0
        # time_seconds, ideal_x, ideal_y, real_x, real_y, error, pen_state
        self.samples: List[Tuple[float, float, float, float, float, float, str]] = []

        self._reset_simulation_state()

    def _to_world_point(self, x: float, y: float) -> Tuple[float, float]:
        """Raw plan biriminden world birimine çevirir."""
        ox, oy = self.world_offset
        return (float(x) * self.world_scale + ox, float(y) * self.world_scale + oy)

    def _to_world_path(self, path: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Raw path listesini world path listesine çevirir."""
        return [self._to_world_point(x, y) for (x, y) in path]

    def _compute_world_bounds(self) -> Tuple[float, float, float, float]:
        """Plan, yol ve komutlardan dünya sınırlarını hesaplar."""
        xs: List[float] = []
        ys: List[float] = []

        for wall in self.plan:
            x1, y1 = self._to_world_point(wall.x1, wall.y1)
            x2, y2 = self._to_world_point(wall.x2, wall.y2)
            xs.extend([x1, x2])
            ys.extend([y1, y2])

        for x, y in self.path:
            xs.append(x)
            ys.append(y)

        # Komutların bounds'unu dry-run ile al (MOVE_REL dahil)
        start_point = self._get_start_point_from_commands()
        if start_point is None and self.path:
            start_point = self.path[0]
        if start_point is None and self.commands:
            start_point = (0.0, 0.0)
        if start_point is not None and self.commands:
            limits_override, md_diags = self._limits_from_metadata()
            stats, analysis_diags = analyze_commands(
                self.commands, start=start_point, limits=limits_override
            )
            self.analysis_diagnostics = list(md_diags) + list(analysis_diags)
            self._last_scenario_stats = stats
            cminx, cminy, cmaxx, cmaxy = stats.bounds
            xs.extend([cminx, cmaxx])
            ys.extend([cminy, cmaxy])
        else:
            self.analysis_diagnostics = []
            self._last_scenario_stats = None

        # Run Gate: herhangi bir ERROR varsa senaryo bloklu
        pe = sum(1 for d in self.parser_diagnostics if d.severity == "ERROR")
        ae = sum(1 for d in self.analysis_diagnostics if d.severity == "ERROR")
        self.scenario_blocked = (pe > 0 or ae > 0)
        if self.scenario_blocked:
            self.paused = True

        if not xs or not ys:
            # Tamamen boş ise varsayılan küçük bir alan kullan
            return 0.0, 0.0, 100.0, 100.0

        return min(xs), min(ys), max(xs), max(ys)

    def _create_transform(self) -> WorldToScreenTransform:
        """Dünya -> ekran dönüşümünü oluşturur."""
        bounds = self._compute_world_bounds()
        return WorldToScreenTransform(bounds, self.screen_width, self.screen_height)

    def _reset_metrics_and_drift(self) -> None:
        """Hata metriklerini ve drift birikimini sıfırlar."""
        self.heading_drift_deg = 0.0
        self.error_instantaneous = 0.0
        self.error_mean = 0.0
        self.error_max = 0.0
        self._error_sum = 0.0
        self._error_count = 0
        self.sim_time = 0.0
        self.samples = []

    def _parse_commands_file_content(self, metin: str) -> Tuple[Dict[str, str], str]:
        """
        Dosya içeriğinden baştaki # key: value metadata satırlarını ayırır.
        Döner: (metadata_dict, body) — body parse_commands'a verilir.
        """
        metadata: Dict[str, str] = {}
        lines = metin.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if not stripped.startswith("#"):
                break
            # # key: value formatı
            rest = stripped[1:].strip()
            if ":" in rest:
                k, _, v = rest.partition(":")
                key = k.strip()
                val = v.strip()
                if key and not key.startswith(" "):
                    metadata[key] = val
            i += 1
        body = "\n".join(lines[i:])
        return metadata, body

    def _commands_to_world_if_needed(self, commands: List[Command]) -> List[Command]:
        """
        commands.txt içindeki MOVE komutlarını gerekirse raw'dan world birimine çevirir.
        """
        if self.commands_are_world:
            return commands

        converted: List[Command] = []
        for cmd in commands:
            if isinstance(cmd, MoveCommand):
                wx, wy = self._to_world_point(cmd.x, cmd.y)
                converted.append(MoveCommand(x=wx, y=wy))
            else:
                converted.append(cmd)
        return converted

    def _load_or_generate_commands(self, path: str = "commands.txt") -> List[Command]:
        """
        Başlangıçta komutları dosyadan yükler; dosya yoksa path'ten üretip kaydeder.
        Dosyada # key: value header varsa scenario_metadata'ya alınır.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                metin = f.read()
            self.scenario_metadata, body = self._parse_commands_file_content(metin)
            units = (self.scenario_metadata.get("units", "WORLD") or "WORLD").strip().upper()
            unknown_units_warn = None
            if units == "WORLD":
                self.commands_are_world = True
            elif units == "RAW":
                self.commands_are_world = False
            else:
                self.commands_are_world = True
                unknown_units_warn = Diagnostic(severity="WARN", line=0, message=f"Bilinmeyen units: {units!r} (WORLD varsayıldı)", text="")
            komutlar, diags = parse_commands(body, strict=False)
            self.parser_diagnostics = list(diags)
            if unknown_units_warn is not None:
                self.parser_diagnostics.append(unknown_units_warn)
            komutlar = self._commands_to_world_if_needed(komutlar)
            if komutlar:
                return komutlar
        except FileNotFoundError:
            komutlar = []
            self.scenario_metadata = {}
        except OSError as e:
            self.parser_diagnostics = [
                Diagnostic(
                    severity="ERROR",
                    line=0,
                    message=f"commands.txt okunamadı: {e}",
                    text="",
                ),
            ]
            komutlar = []
            self.scenario_metadata = {}

        # Dosya yoksa veya boşsa path'ten komut üret
        komutlar = compile_path_to_commands(self.path, speed=self.world_speed)
        self.scenario_metadata = {
            "units": "WORLD",
            "created": __import__("datetime").datetime.now().strftime("%Y-%m-%d"),
        }
        units = (self.scenario_metadata.get("units", "WORLD") or "WORLD").strip().upper()
        if units == "WORLD":
            self.commands_are_world = True
        elif units == "RAW":
            self.commands_are_world = False
        else:
            self.commands_are_world = True
            self.parser_diagnostics.append(
                Diagnostic(severity="WARN", line=0, message=f"Bilinmeyen units: {units!r} (WORLD varsayıldı)", text="")
            )
        self._save_commands_to_file(komutlar, path)
        return komutlar

    def _save_commands_to_file(
        self,
        commands: Optional[List[Command]] = None,
        path: str = "commands.txt",
    ) -> None:
        """Verilen komut listesini (veya mevcut commands'i) dosyaya yazar. Header metadata varsa üste eklenir."""
        if commands is None:
            commands = self.commands
        try:
            with open(path, "w", encoding="utf-8") as f:
                meta = getattr(self, "scenario_metadata", {})
                for key in ("name", "units", "max_time", "max_path", "created"):
                    if key in meta and meta[key]:
                        f.write(f"# {key}: {meta[key]}\n")
                f.write(serialize_commands(commands))
        except OSError:
            pass

    def _reload_commands_from_file(self, path: str = "commands.txt") -> None:
        """
        commands.txt dosyasını tekrar yükler ve simülasyonu baştan başlatır.
        Dosya okunamaz veya boşsa mevcut komutlar korunur.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                metin = f.read()
            self.scenario_metadata, body = self._parse_commands_file_content(metin)
            units = (self.scenario_metadata.get("units", "WORLD") or "WORLD").strip().upper()
            unknown_units_warn = None
            if units == "WORLD":
                self.commands_are_world = True
            elif units == "RAW":
                self.commands_are_world = False
            else:
                self.commands_are_world = True
                unknown_units_warn = Diagnostic(severity="WARN", line=0, message=f"Bilinmeyen units: {units!r} (WORLD varsayıldı)", text="")
            komutlar, diags = parse_commands(body, strict=False)
            self.parser_diagnostics = list(diags)
            if unknown_units_warn is not None:
                self.parser_diagnostics.append(unknown_units_warn)
            komutlar = self._commands_to_world_if_needed(komutlar)
            if not komutlar:
                return
        except FileNotFoundError:
            return
        except OSError as e:
            self.parser_diagnostics = [
                Diagnostic(
                    severity="ERROR",
                    line=0,
                    message=f"commands.txt okunamadı: {e}",
                    text="",
                ),
            ]
            return
        self.commands = komutlar
        # Komutlara göre dünya sınırları değişebileceği için transform'u yenile
        self.transform = self._create_transform()
        self._reset_simulation_state()

    def _limits_from_metadata(self) -> Tuple[ScenarioLimits, List[Diagnostic]]:
        """
        scenario_metadata içinden limit override üretir.
        Parse edilemeyen alanları WARN olarak döndürür.
        """
        diags: List[Diagnostic] = []
        md = getattr(self, "scenario_metadata", {}) or {}

        def get_float(key: str) -> Optional[float]:
            if key not in md:
                return None
            try:
                return float(str(md[key]).strip())
            except ValueError:
                diags.append(
                    Diagnostic(
                        severity="WARN",
                        line=0,
                        message=f"Metadata parse edilemedi: {key}={md[key]!r}",
                        text="",
                    )
                )
                return None

        def get_int(key: str) -> Optional[int]:
            if key not in md:
                return None
            try:
                return int(str(md[key]).strip())
            except ValueError:
                diags.append(
                    Diagnostic(
                        severity="WARN",
                        line=0,
                        message=f"Metadata parse edilemedi: {key}={md[key]!r}",
                        text="",
                    )
                )
                return None

        base = ScenarioLimits()
        max_time = get_float("max_time")
        max_path = get_float("max_path")
        max_moves = get_int("max_moves")
        max_bounds = get_float("max_bounds")
        max_abs = get_float("max_abs_coord")

        override = ScenarioLimits(
            max_total_time=max_time if max_time is not None else base.max_total_time,
            max_path_length=max_path if max_path is not None else base.max_path_length,
            max_moves=max_moves if max_moves is not None else base.max_moves,
            max_bounds_size=max_bounds if max_bounds is not None else base.max_bounds_size,
            max_abs_coord=max_abs if max_abs is not None else base.max_abs_coord,
        )
        return override, diags

    def _get_start_point_from_commands(self) -> Optional[Tuple[float, float]]:
        """Komut listesindeki ilk MOVE komutunun (x, y) hedefini döndürür."""
        for cmd in self.commands:
            if isinstance(cmd, MoveCommand):
                return float(cmd.x), float(cmd.y)
        return None

    def _reset_simulation_state(self) -> None:
        """Robotun konumunu, izi ve metrikleri sıfırlar."""
        self._reset_metrics_and_drift()

        # Komut yürütücüyü baştan kur
        self.executor = CommandExecutor(self.commands)

        # Başlangıç noktası: komutlardaki ilk MOVE, yoksa path[0], yoksa (0,0)
        start_point = self._get_start_point_from_commands()
        if start_point is None and self.path:
            start_point = (float(self.path[0][0]), float(self.path[0][1]))
        if start_point is None and self.commands:
            start_point = (0.0, 0.0)

        if start_point is not None:
            sx, sy = start_point
            self.ideal_position = [sx, sy]
            self.robot_position = [sx, sy]
            self.trace = [(sx, sy)]
            self.finished = False
        else:
            self.ideal_position = None
            self.robot_position = None
            self.trace = []
            self.finished = True

    def reset(self) -> None:
        """Dışarıdan çağrılan reset; sadece durumu sıfırlar."""
        self._reset_simulation_state()

    def clear_trace(self) -> None:
        """Sadece izi temizler, robot konumu aynı kalır."""
        if self.robot_position is not None:
            self.trace = [(self.robot_position[0], self.robot_position[1])]
        else:
            self.trace = []

    def toggle_pen(self) -> None:
        """Kalem durumunu manuel olarak değiştirir (executor iç durumunu ezerek)."""
        if self.executor is not None:
            self.executor.pen_down = not self.executor.pen_down

    def _apply_motion_model(
        self,
        ideal_dx: float,
        ideal_dy: float,
        dt: float,
    ) -> Tuple[float, float]:
        """
        İdeal hareket vektörüne drift ve gürültü uygular.

        Dönen değer, gerçek robot konumuna eklenecek (dx, dy) vektörüdür.
        """
        dx = ideal_dx
        dy = ideal_dy

        # Hareket yoksa drift/gürültü uygulamaya gerek yok
        uzunluk = math.hypot(dx, dy)
        if uzunluk < 1e-9:
            return 0.0, 0.0

        # Yön vektörü
        yon_x = dx / uzunluk
        yon_y = dy / uzunluk

        # Başlık drift'i: yön vektörünü yavaşça döndür
        if self.drift_enabled:
            self.heading_drift_deg += DRIFT_DEG_PER_SEC * dt
            aci_rad = math.radians(self.heading_drift_deg)
            cos_a = math.cos(aci_rad)
            sin_a = math.sin(aci_rad)
            # 2B rotasyon
            drifted_x = yon_x * cos_a - yon_y * sin_a
            drifted_y = yon_x * sin_a + yon_y * cos_a
        else:
            drifted_x = yon_x
            drifted_y = yon_y

        # Drift uygulanmış hareket (gürültü öncesi)
        hareket_dx = drifted_x * uzunluk
        hareket_dy = drifted_y * uzunluk

        # Konumsal gürültü (Gauss)
        if self.noise_enabled and dt > 0.0:
            std = POSITION_NOISE_STD_PER_SEC * math.sqrt(dt)
            noise_dx = random.gauss(0.0, std)
            noise_dy = random.gauss(0.0, std)
        else:
            noise_dx = 0.0
            noise_dy = 0.0

        return hareket_dx + noise_dx, hareket_dy + noise_dy

    def _update_error_metrics(self) -> None:
        """Anlık, ortalama ve maksimum hata değerlerini günceller."""
        if self.robot_position is None or self.ideal_position is None:
            self.error_instantaneous = 0.0
            return

        rx, ry = self.robot_position
        ix, iy = self.ideal_position

        # Anlık hata: ideal konum ile gerçek konum arasındaki mesafe
        hata = math.hypot(rx - ix, ry - iy)
        self.error_instantaneous = hata

        self._error_sum += hata
        self._error_count += 1
        self.error_mean = self._error_sum / self._error_count

        if hata > self.error_max:
            self.error_max = hata

    def _log_sample_if_needed(self) -> None:
        """Simülasyon çalışırken bir örnek satırı kaydeder."""
        if self.paused or self.finished:
            return
        if self.robot_position is None or self.ideal_position is None:
            return

        kalem_durumu = "DOWN" if self.executor is not None and self.executor.pen_down else "UP"

        self.samples.append(
            (
                self.sim_time,
                self.ideal_position[0],
                self.ideal_position[1],
                self.robot_position[0],
                self.robot_position[1],
                self.error_instantaneous,
                kalem_durumu,
            ),
        )

    def _save_metrics_to_csv(self, filename: str = "run_metrics.csv") -> None:
        """Kayıtlı örnekleri CSV dosyasına yazar."""
        try:
            with open(filename, "w", newline="", encoding="utf-8") as dosya:
                yazici = csv.writer(dosya)
                yazici.writerow(
                    [
                        "time_seconds",
                        "ideal_x",
                        "ideal_y",
                        "real_x",
                        "real_y",
                        "error",
                        "pen_state",
                    ],
                )
                for (
                    zaman,
                    ideal_x,
                    ideal_y,
                    gercek_x,
                    gercek_y,
                    hata,
                    kalem_durumu,
                ) in self.samples:
                    yazici.writerow(
                        [
                            f"{zaman:.4f}",
                            f"{ideal_x:.4f}",
                            f"{ideal_y:.4f}",
                            f"{gercek_x:.4f}",
                            f"{gercek_y:.4f}",
                            f"{hata:.4f}",
                            kalem_durumu,
                        ],
                    )
        except OSError:
            # Dosyaya yazma hatası durumunda simülasyonu bozmamak için sessizce geç
            pass

    def _update_robot(self, dt: float) -> None:
        """Robotun konumunu delta zamana göre günceller."""
        if self.paused or self.finished:
            return

        if self.ideal_position is None or self.robot_position is None:
            # Hareket edecek yol yok
            self.finished = True
            return

        onceki_bitti_durumu = self.executor.finished

        # Simülasyon zamanını ilerlet
        self.sim_time += dt

        # Executor'den ideal hareketi al
        eski_ideal_x, eski_ideal_y = self.ideal_position
        (yeni_ideal_x, yeni_ideal_y), _ = self.executor.update(dt, (eski_ideal_x, eski_ideal_y))
        self.ideal_position = [yeni_ideal_x, yeni_ideal_y]

        ideal_dx = yeni_ideal_x - eski_ideal_x
        ideal_dy = yeni_ideal_y - eski_ideal_y

        # İdeal hareketi drift/gürültü ile bozan gerçek hareketi hesapla
        gercek_dx, gercek_dy = self._apply_motion_model(ideal_dx, ideal_dy, dt)

        # Gerçek robot konumunu güncelle
        self.robot_position[0] += gercek_dx
        self.robot_position[1] += gercek_dy

        # Kalem aşağıysa izi güncelle
        if self.executor.pen_down and (abs(gercek_dx) > 1e-6 or abs(gercek_dy) > 1e-6):
            self.trace.append((self.robot_position[0], self.robot_position[1]))

        # Hata metriklerini güncelle ve örnek kaydet
        self._update_error_metrics()
        self._log_sample_if_needed()

        # Komutlar tamamlandıysa, metrikleri otomatik kaydet
        if not onceki_bitti_durumu and self.executor.finished:
            self.finished = True
            self._save_metrics_to_csv()

    def _draw_walls(self, surface: pygame.Surface) -> None:
        """Plana göre duvarları çizer."""
        color = (200, 200, 200)
        for wall in self.plan:
            x1, y1 = self._to_world_point(wall.x1, wall.y1)
            x2, y2 = self._to_world_point(wall.x2, wall.y2)
            start = self.transform.world_to_screen(x1, y1)
            end = self.transform.world_to_screen(x2, y2)
            pygame.draw.line(surface, color, start, end, width=1)

    def _draw_ideal_path(self, surface: pygame.Surface) -> None:
        """İdeal (hatasız) yolu ince bir poligon çizgisi olarak çizer."""
        if len(self.path) < 2:
            return

        color = (120, 120, 255)  # İzden ve duvardan farklı bir renk
        points = [self.transform.world_to_screen(x, y) for x, y in self.path]
        pygame.draw.lines(surface, color, False, points, width=1)

    def _draw_trace(self, surface: pygame.Surface) -> None:
        """Robotun geçtiği izleri çizer."""
        if len(self.trace) < 2:
            return

        color = (0, 180, 255)
        points = [self.transform.world_to_screen(x, y) for x, y in self.trace]
        pygame.draw.lines(surface, color, False, points, width=2)

    def _draw_robot(self, surface: pygame.Surface) -> None:
        """Robotu (dolu daire) çizer."""
        if self.robot_position is None:
            return

        color = (255, 80, 80)
        sx, sy = self.transform.world_to_screen(
            self.robot_position[0],
            self.robot_position[1],
        )
        # Ekrana göre sabit bir yarıçap
        radius = 6
        pygame.draw.circle(surface, color, (sx, sy), radius)

    def _draw_info_text(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        """Durum bilgisi ve kontrolleri gösterir."""
        beyaz = (240, 240, 240)
        gri = (180, 180, 180)

        durum = "DURAKLATILDI" if self.paused else ("BİTTİ" if self.finished else "ÇALIŞIYOR")
        satirlar = [
            f"Durum: {durum}",
            "Kontroller: SPACE | R=Reset | C=İz | D/N=Drift/Gürültü | P=Kalem | S=CSV | O=Kaydet | L=Yükle | I=Dump | E=Export (robot) | ESC",
        ]
        if getattr(self, "scenario_blocked", False):
            satirlar.append("BLOCKED: Senaryo güvenli değil (Parser veya Analysis ERROR) — çalıştırma kilitli.")
        name = (getattr(self, "scenario_metadata", {}) or {}).get("name")
        if name:
            satirlar.append(f"Senaryo: {name}")

        if not self.path:
            satirlar.append("Uyarı: Yol boş (plan veya PathGenerator çıktısı nokta üretmedi).")

        # Drift / gürültü durumu
        satirlar.append(
            f"Drift: {'AÇIK' if self.drift_enabled else 'KAPALI'} | Gürültü: {'AÇIK' if self.noise_enabled else 'KAPALI'}",
        )

        # Hata metrikleri
        satirlar.append(
            f"Hata anlık: {self.error_instantaneous:6.2f}  |  Hata ortalama: {self.error_mean:6.2f}  |  Hata max: {self.error_max:6.2f}",
        )

        # Executor durum bilgisi (senaryo debug)
        if self.executor is not None:
            state = self.executor.debug_state()
            pen_txt = "DOWN" if state["pen"] else "UP"
            spd_txt = f"{state['speed']:.2f}"
            wait_txt = f"{state['wait']:.2f}s"
            target = state["target"]
            if target is None:
                target_txt = "None"
            else:
                target_txt = f"({target[0]:.2f}, {target[1]:.2f})"
            idx_txt = state["index"]
        else:
            pen_txt = "N/A"
            spd_txt = "N/A"
            wait_txt = "N/A"
            target_txt = "None"
            idx_txt = "N/A"

        satirlar.append(
            f"Executor: idx={idx_txt} | PEN={pen_txt} | SPEED={spd_txt} | WAIT={wait_txt} | TARGET={target_txt}",
        )

        # Komut birimi bilgisi
        satirlar.append(
            f"Komut birimi: {'WORLD' if self.commands_are_world else 'RAW->WORLD'}",
        )

        # Parser / Analysis diagnostics özeti
        if hasattr(self, "parser_diagnostics") and self.parser_diagnostics:
            pe = sum(1 for d in self.parser_diagnostics if d.severity == "ERROR")
            pw = sum(1 for d in self.parser_diagnostics if d.severity == "WARN")
            satirlar.append(f"Parser: {pe} ERROR, {pw} WARN")
        else:
            satirlar.append("Parser: 0 ERROR, 0 WARN")
        if hasattr(self, "analysis_diagnostics") and self.analysis_diagnostics:
            ae = sum(1 for d in self.analysis_diagnostics if d.severity == "ERROR")
            aw = sum(1 for d in self.analysis_diagnostics if d.severity == "WARN")
            satirlar.append(f"Analysis: {ae} ERROR, {aw} WARN")
        else:
            satirlar.append("Analysis: 0 ERROR, 0 WARN")

        y = 10
        for i, metin in enumerate(satirlar):
            if i == 0:
                color = beyaz
            elif "BLOCKED:" in metin:
                color = (255, 120, 120)  # kırmızımsı uyarı
            else:
                color = gri
            render = font.render(metin, True, color)
            surface.blit(render, (10, y))
            y += render.get_height() + 4

    def run(self) -> None:
        """Pygame ana döngüsünü başlatır."""
        pygame.init()
        pygame.display.set_caption("Basit 2B Yerleşim Simülatörü")

        screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        clock = pygame.time.Clock()
        font = pygame.font.SysFont("consolas", 16)

        running = True

        while running:
            dt_ms = clock.tick(60)  # 60 FPS hedef, ama hareket dt tabanlı
            dt = dt_ms / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        # Run Gate: blokluyken çalıştırmaya geçirme
                        if getattr(self, "scenario_blocked", False):
                            self.paused = True
                        else:
                            self.paused = not self.paused
                    elif event.key == pygame.K_r:
                        self.reset()
                    elif event.key == pygame.K_c:
                        self.clear_trace()
                    elif event.key == pygame.K_d:
                        self.drift_enabled = not self.drift_enabled
                    elif event.key == pygame.K_n:
                        self.noise_enabled = not self.noise_enabled
                    elif event.key == pygame.K_p:
                        self.toggle_pen()
                    elif event.key == pygame.K_s:
                        self._save_metrics_to_csv()
                    elif event.key == pygame.K_i:
                        print("BLOCKED:", getattr(self, "scenario_blocked", False))
                        print("---- COMMANDS (active) ----")
                        print(serialize_commands(self.commands))
                        print("---- PARSER DIAGNOSTICS ----")
                        for d in getattr(self, "parser_diagnostics", []):
                            print(f"{d.severity} line {d.line}: {d.message} | {d.text}")
                        print("---- ANALYSIS DIAGNOSTICS ----")
                        for d in getattr(self, "analysis_diagnostics", []):
                            print(f"{d.severity} line {d.line}: {d.message} | {d.text}")
                        if getattr(self, "_last_scenario_stats", None) is not None:
                            s = self._last_scenario_stats
                            print("---- STATS ÖZET ----")
                            print(f"  bounds: {s.bounds}")
                            print(f"  path_length: {s.path_length:.2f}  move_count: {s.move_count}")
                            print(f"  wait_total: {s.wait_total:.2f}s  estimated_time: {s.estimated_time}")
                        print("----------------------------")
                    elif event.key == pygame.K_o:
                        self._save_commands_to_file()
                    elif event.key == pygame.K_l:
                        self._reload_commands_from_file()
                    elif event.key == pygame.K_e:
                        start = self._get_start_point_from_commands()
                        if start is None and self.path:
                            start = (float(self.path[0][0]), float(self.path[0][1]))
                        if start is not None and self.commands:
                            limits_override, md_diags = self._limits_from_metadata()
                            ok = export_commands(
                                self.commands,
                                "robot_export.txt",
                                start,
                                limits=limits_override,
                                format="absolute_only",
                            )
                            print("Export:", "robot_export.txt — güvenli" if ok else "robot_export.txt — BLOCKED (dosya yazıldı, çalıştırma önerilmez)")
                        else:
                            print("Export: başlangıç noktası veya komut yok")

            # Run Gate: blokluyken simülasyon ilerlemesin
            if not getattr(self, "scenario_blocked", False):
                self._update_robot(dt)

            # Çizim
            screen.fill((20, 20, 20))
            self._draw_walls(screen)
            self._draw_ideal_path(screen)
            self._draw_trace(screen)
            self._draw_robot(screen)
            self._draw_info_text(screen, font)

            pygame.display.flip()

        pygame.quit()


if __name__ == "__main__":
    sim = RobotSimulator()
    sim.run()

