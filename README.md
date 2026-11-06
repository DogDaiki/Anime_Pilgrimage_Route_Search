# 聖地巡礼 徒歩ルート最適化アプリ
聖地巡礼の訪問スポットを効率的に巡るための徒歩ルート最適化Webアプリケーションです。

## 主な機能
- 現在地および聖地の検索・入力
- OSRM (Open Source Routing Machine) による最適な訪問順序の自動計算(デモ版のため、ルート計算は最適とは言えない)
- Mapbox / Leaflet を活用したマップ表示・ピン挿入
- お気に入り機能（LocalStorage連携）

## 使用技術
- **Backend**: Python (Flask)
- **Frontend**: HTML5, CSS3, JavaScript, Leaflet.js
- **API/Data**: Mapbox GL API, OSRM API, OpenStreetMap
