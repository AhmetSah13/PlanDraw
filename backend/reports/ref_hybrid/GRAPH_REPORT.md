# Geometry Graph Raporu

Bu rapor 6 dosya üzerinden üretilmiştir.

## 1. En yüksek kavşak sayısı (intersection_count)

- **double_wall_L_shape.dxf**: 0
- **double_wall_T_junction.dxf**: 0
- **double_wall_rectangle.dxf**: 0
- **empty_entities.dxf**: 0
- **minimal.dxf**: 0
- **sample.dxf**: 0

## 2. En yüksek sarkan kenar sayısı (dangling_edges_count)

- **sample.dxf**: 11
- **minimal.dxf**: 9
- **empty_entities.dxf**: 5
- **double_wall_T_junction.dxf**: 4
- **double_wall_L_shape.dxf**: 0
- **double_wall_rectangle.dxf**: 0

## 3. En yüksek döngü sayısı (closed_cycles_count)

- **sample.dxf**: 3
- **double_wall_L_shape.dxf**: 2
- **double_wall_rectangle.dxf**: 2
- **empty_entities.dxf**: 1
- **minimal.dxf**: 1
- **double_wall_T_junction.dxf**: 0

## 4. Oda konturu adayları (örnek)

Dosya: **double_wall_L_shape.dxf** — ilk birkaç oda adayı:
- Aday 1: perimeter=32.0 m, vertex_count=6, bbox=[-4.0, -4.0, 4.0, 4.0]
- Aday 2: perimeter=30.4 m, vertex_count=6, bbox=[-3.8, -3.8, 3.8, 3.8]

## 5. Örnek dosya — graph metrikleri açıklaması

Dosya: **double_wall_L_shape.dxf**

| Metrik | Değer | Açıklama |
|--------|-------|----------|
| node_count | 12 | Graf düğüm sayısı (snap sonrası benzersiz uç noktalar) |
| edge_count | 12 | Kenar sayısı |
| connected_components_count | 2 | Bağlantılı bileşen sayısı |
| degree_histogram | {'0': 0, '1': 0, '2': 12, '3+': 0} | 0/1/2/3+ uçlu düğüm dağılımı |
| intersection_count | 0 | Derecesi ≥3 olan kavşak sayısı |
| dangling_edges_count | 0 | Ucu serbest (degree=1) kenar sayısı |
| closed_cycles_count | 2 | Cyclomatic döngü sayısı (E−V+C) |
| edge_length_stats | {'min': 3.5999999999999996, 'median': 4.0, 'p95': 8.0} | min/median/p95 kenar uzunluğu (m) |
| dominant_angles | {'0': 6, '90': 6, '45': 0, '135': 0, 'other': 0} | 0°/90°/45°/135°/diğer açı dağılımı |
