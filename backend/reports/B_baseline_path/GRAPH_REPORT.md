# Geometry Graph Raporu

Bu rapor 2 dosya üzerinden üretilmiştir.

## 1. En yüksek kavşak sayısı (intersection_count)

- **empty_entities.dxf**: 0
- **sample.dxf**: 0

## 2. En yüksek sarkan kenar sayısı (dangling_edges_count)

- **sample.dxf**: 11
- **empty_entities.dxf**: 5

## 3. En yüksek döngü sayısı (closed_cycles_count)

- **sample.dxf**: 3
- **empty_entities.dxf**: 1

## 4. Oda konturu adayları (örnek)

Dosya: **empty_entities.dxf** — ilk birkaç oda adayı:
- Aday 1: perimeter=130.0 m, vertex_count=4, bbox=[-20.0, -12.5, 20.0, 12.5]

## 5. Örnek dosya — graph metrikleri açıklaması

Dosya: **empty_entities.dxf**

| Metrik | Değer | Açıklama |
|--------|-------|----------|
| node_count | 14 | Graf düğüm sayısı (snap sonrası benzersiz uç noktalar) |
| edge_count | 9 | Kenar sayısı |
| connected_components_count | 6 | Bağlantılı bileşen sayısı |
| degree_histogram | {'0': 0, '1': 10, '2': 4, '3+': 0} | 0/1/2/3+ uçlu düğüm dağılımı |
| intersection_count | 0 | Derecesi ≥3 olan kavşak sayısı |
| dangling_edges_count | 5 | Ucu serbest (degree=1) kenar sayısı |
| closed_cycles_count | 1 | Cyclomatic döngü sayısı (E−V+C) |
| edge_length_stats | {'min': 25.0, 'median': 25.0, 'p95': 40.0} | min/median/p95 kenar uzunluğu (m) |
| dominant_angles | {'0': 4, '90': 5, '45': 0, '135': 0, 'other': 0} | 0°/90°/45°/135°/diğer açı dağılımı |
