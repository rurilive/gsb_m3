# geogrid

本地经纬度点位索引，纯标准库，无第三方依赖。

## 现状

- `geogrid/geo.py`：坐标校验、经度归一（180 折到 -180）与 `haversine_m` 球面距离
- `geogrid/cells.py`：固定边长格网切分，`cell_of(lat, lon, cell_deg)` 给出 `(row, col)`
- `geogrid/geocode.py`：类 geohash 前缀码，`encode`/`decode`/`neighbors`；截断即降精度，短码格子包住长码格子，邻格跨 ±180 度经线绕回
- `geogrid/index.py`：`PointIndex`，`add` 登记、`remove` 摘除、`at` 精确坐标查询、`scan` 全量遍历、`stats` 状态快照；id 为任意可哈希对象，查询结果按登记顺序返回
  - `box(lat_min, lat_max, lon_min, lon_max)` 矩形片区查询，`lon_min > lon_max` 视为跨 ±180 度经线
  - `circle(lat, lon, radius_m)` 圆形查询，半径按米，先格子粗筛再按球面距离逐点过滤
  - 格子超过 `max_cell_points` 自动四叉分裂，深度封顶 `max_depth`，热点查询不退回线性
  - `stats()["cells_visited"]` 累计查询翻开的叶子格数，可和耗时对照看

数据都是普通浮点，不引入任何坐标系转换。

## 运行

```bash
python3 demo.py                           # 精确查询与遍历演示
python3 -m unittest discover -s tests -v  # 行为基线测试
```
