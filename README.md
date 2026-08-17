# TP-Scenario-Generator

交通规划场景生成器（Traffic Planning Scenario Generator）- 用于验证交通路由生成方法的真实交通网络和路线数据集，涵盖5个城市的60条路由场景。

## 数据集

### 下载链接

数据集已上传至Google Drive，请点击以下链接下载：

**[TP-Scenario-Generator 完整数据集](https://drive.google.com/file/d/12hLrhwCu_HESeeWFLU2WxDnRa93tFNvs/view?usp=drive_link)**

### 数据集说明

本数据集包含5个城市的交通网络数据和路线信息，适用于交通流仿真、路由规划和场景分析。

#### 目录结构

```
TP_SG_5cities_60routes/
├── BOS/                          # 波士顿 (Boston)
│   ├── networks/
│   │   └── BOS_5km.net.xml       # 波士顿5km范围网络定义
│   └── routes/
│       ├── BOS_5km_subnet_020000_030000.rou.xml
│       ├── BOS_5km_subnet_030000_040000.rou.xml
│       ├── BOS_5km_subnet_040000_050000.rou.xml
│       ├── BOS_5km_subnet_050000_060000.rou.xml
│       ├── BOS_5km_subnet_060000_070000.rou.xml
│       ├── BOS_5km_subnet_070000_080000.rou.xml
│       ├── BOS_5km_subnet_080000_090000.rou.xml
│       ├── BOS_5km_subnet_090000_100000.rou.xml
│       ├── BOS_5km_subnet_100000_110000.rou.xml
│       ├── BOS_5km_subnet_110000_120000.rou.xml
│       ├── BOS_5km_subnet_120000_130000.rou.xml
│       └── BOS_5km_subnet_130000_140000.rou.xml
├── LAX/                          # 洛杉矶 (Los Angeles)
│   ├── networks/
│   │   └── LAX_5km.net.xml       # 洛杉矶5km范围网络定义
│   └── routes/                   # 12个时间段的路线数据
├── LIS/                          # 里斯本 (Lisbon)
│   ├── networks/
│   │   └── LIS_5km.net.xml       # 里斯本5km范围网络定义
│   └── routes/                   # 12个时间段的路线数据
├── RIO/                          # 里约热内卢 (Rio de Janeiro)
│   ├── networks/
│   │   └── RIO_5km.net.xml       # 里约热内卢5km范围网络定义
│   └── routes/                   # 12个时间段的路线数据
├── SFO/                          # 旧金山 (San Francisco)
│   ├── networks/
│   │   └── SFO_5km.net.xml       # 旧金山5km范围网络定义
│   └── routes/                   # 12个时间段的路线数据
├── README.md                     # 本说明文档
└── fastmcp_server.py             # MCP服务器脚本
```

#### 数据文件说明

- **网络文件 (.net.xml)**
  - SUMO格式的网络定义文件
  - 包含道路网络的拓扑结构和几何信息
  - 每个城市包含一个5km范围内的网络

- **路线文件 (.rou.xml)**
  - SUMO格式的路线定义文件
  - 包含车辆的出发、到达和经过的路线信息
  - 按时间段组织（020000-030000、030000-040000等），表示不同的出发时间段
  - 共12个时间段，覆盖整个交通流量分布

#### 城市信息

| 城市 | 英文名 | 代码 | 地区 |
|------|--------|------|------|
| 波士顿 | Boston | BOS | 美国东部 |
| 洛杉矶 | Los Angeles | LAX | 美国西部 |
| 里斯本 | Lisbon | LIS | 葡萄牙 |
| 里约热内卢 | Rio de Janeiro | RIO | 巴西 |
| 旧金山 | San Francisco | SFO | 美国西部 |

#### 数据格式

本数据集采用 **SUMO (Simulation of Urban Mobility)** 格式：
- 网络文件：标准的SUMO .net.xml格式
- 路线文件：标准的SUMO .rou.xml格式
- 可直接用于SUMO交通仿真或其他支持SUMO格式的工具

### 使用建议

1. 下载并解压数据集
2. 使用SUMO仿真工具或自开发的解析工具处理数据
3. 根据研究需求选择特定城市或时间段的数据
4. 可结合网络文件和路线文件进行交通流仿真分析
