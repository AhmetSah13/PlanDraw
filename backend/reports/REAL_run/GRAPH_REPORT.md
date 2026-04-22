# Geometry Graph Raporu

Bu rapor 1 dosya üzerinden üretilmiştir.

## 1. En yüksek kavşak sayısı (intersection_count)

- **sample.dxf**: 0

## 2. En yüksek sarkan kenar sayısı (dangling_edges_count)

- **sample.dxf**: 11

## 3. En yüksek döngü sayısı (closed_cycles_count)

- **sample.dxf**: 3

## 4. Oda konturu adayları (örnek)

Dosya: **sample.dxf** — ilk birkaç oda adayı:
- Aday 1: perimeter=64.0 m, vertex_count=4, bbox=[-10.0, -6.0, 10.0, 6.0]
- Aday 2: perimeter=4.40645 m, vertex_count=4, bbox=[6.0, 3.0, 8.1, 3.1999999999999997]
- Aday 3: perimeter=4.1 m, vertex_count=4, bbox=[-8.0, -4.0, -6.0, -3.9499999999999997]

## 5. Örnek dosya — graph metrikleri açıklaması

Dosya: **sample.dxf**

| Metrik | Değer | Açıklama |
|--------|-------|----------|
| node_count | 33 | Graf düğüm sayısı (snap sonrası benzersiz uç noktalar) |
| edge_count | 23 | Kenar sayısı |
| connected_components_count | 13 | Bağlantılı bileşen sayısı |
| degree_histogram | {'0': 0, '1': 20, '2': 13, '3+': 0} | 0/1/2/3+ uçlu düğüm dağılımı |
| intersection_count | 0 | Derecesi ≥3 olan kavşak sayısı |
| dangling_edges_count | 11 | Ucu serbest (degree=1) kenar sayısı |
| closed_cycles_count | 3 | Cyclomatic döngü sayısı (E−V+C) |
| edge_length_stats | {'min': 0.050000000000000266, 'median': 5.5, 'p95': 20.0} | min/median/p95 kenar uzunluğu (m) |
| dominant_angles | {'0': 10, '90': 10, '45': 1, '135': 0, 'other': 2} | 0°/90°/45°/135°/diğer açı dağılımı |
