# Geometry Graph Raporu

Bu rapor 3 dosya üzerinden üretilmiştir.

## 1. En yüksek kavşak sayısı (intersection_count)

- **empty_entities.dxf**: 0
- **minimal.dxf**: 0
- **sample.dxf**: 0

## 2. En yüksek sarkan kenar sayısı (dangling_edges_count)

- **sample.dxf**: 11
- **minimal.dxf**: 9
- **empty_entities.dxf**: 5

## 3. En yüksek döngü sayısı (closed_cycles_count)

- **sample.dxf**: 3
- **empty_entities.dxf**: 1
- **minimal.dxf**: 1

## 4. Oda konturu adayları (örnek)

Dosya: **minimal.dxf** — ilk birkaç oda adayı:
- Aday 1: perimeter=32.0 m, vertex_count=4, bbox=[-5.0, -3.0, 5.0, 3.0]

## 5. Örnek dosya — graph metrikleri açıklaması

Dosya: **minimal.dxf**

| Metrik | Değer | Açıklama |
|--------|-------|----------|
| node_count | 22 | Graf düğüm sayısı (snap sonrası benzersiz uç noktalar) |
| edge_count | 13 | Kenar sayısı |
| connected_components_count | 10 | Bağlantılı bileşen sayısı |
| degree_histogram | {'0': 0, '1': 18, '2': 4, '3+': 0} | 0/1/2/3+ uçlu düğüm dağılımı |
| intersection_count | 0 | Derecesi ≥3 olan kavşak sayısı |
| dangling_edges_count | 9 | Ucu serbest (degree=1) kenar sayısı |
| closed_cycles_count | 1 | Cyclomatic döngü sayısı (E−V+C) |
| edge_length_stats | {'min': 0.9000000000000004, 'median': 2.6, 'p95': 10.0} | min/median/p95 kenar uzunluğu (m) |
| dominant_angles | {'0': 7, '90': 6, '45': 0, '135': 0, 'other': 0} | 0°/90°/45°/135°/diğer açı dağılımı |
