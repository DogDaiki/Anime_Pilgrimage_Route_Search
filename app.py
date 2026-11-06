import os
import math
from flask import Flask, render_template, request, jsonify, send_from_directory
import requests
import openpyxl

app = Flask(__name__)

EXCEL_PATH = os.path.join(os.path.dirname(__file__), 'spots.xlsx')
PHOTO_DIR = os.path.join(os.path.dirname(__file__), 'photo')
ANIME_PHOTO_DIR = os.path.join(os.path.dirname(__file__), 'anime_photo')

# 起動時にExcelからデータを読み込んで保持するキャッシュ変数
SPOTS_CACHE = []


def load_spots_from_excel():
    """Excelファイルから聖地データを読み込む関数"""
    spots = []
    if not os.path.exists(EXCEL_PATH):
        print(f"警告: Excelファイルが見つかりません: {EXCEL_PATH}")
        return spots

    try:
        wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
        sheet = wb.active

        for row in sheet.iter_rows(min_row=2, values_only=True):
            if not row or row[0] is None:
                continue

            try:
                spot_id = int(row[0])
            except (ValueError, TypeError):
                continue

            name = str(row[1]).strip() if row[1] is not None else ""
            
            lat, lng = 0.0, 0.0
            if len(row) > 3 and row[3] is not None:
                coord_str = str(row[3]).strip()
                if ',' in coord_str:
                    coords = coord_str.split(',')
                    try:
                        lat = float(coords[0].strip())
                        lng = float(coords[1].strip())
                    except ValueError:
                        pass

            sub_names = []
            if len(row) > 4 and row[4] is not None:
                raw_sub = str(row[4]).replace('，', ',')
                sub_names = [s.strip() for s in raw_sub.split(',') if s.strip()]

            works = []
            if len(row) > 5 and row[5] is not None:
                raw_works = str(row[5]).replace('，', ',')
                works = [w.strip() for w in raw_works.split(',') if w.strip()]

            work_title = ", ".join(works) if works else (", ".join(sub_names) if sub_names else "")

            photo_filename = f"{spot_id}.png"
            photo_path = os.path.join(PHOTO_DIR, photo_filename)
            image_url = f"/photo/{photo_filename}" if os.path.exists(photo_path) else None

            spots.append({
                "id": spot_id,
                "name": name,
                "work_title": work_title,
                "sub_names": sub_names,
                "works": works,
                "lat": lat,
                "lng": lng,
                "image_url": image_url
            })

    except Exception as e:
        print(f"Excel読み込みエラー: {e}")

    return spots


# アプリ起動時にデータを一括ロード
SPOTS_CACHE = load_spots_from_excel()


def calculate_distance(lat1, lon1, lat2, lon2):
    """2地点の緯度・経度から直線距離（メートル）を算出"""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c)


@app.route('/')
def index():
    mapbox_config = {
        'username': os.environ.get('MAPBOX_USERNAME', 'YOUR_MAPBOX_USERNAME'),
        'style_id': os.environ.get('MAPBOX_STYLE_ID', 'YOUR_MAPBOX_STYLE_ID'),
        'access_token': os.environ.get('MAPBOX_ACCESS_TOKEN', 'YOUR_MAPBOX_ACCESS_TOKEN')
    }
    return render_template('index.html', mapbox=mapbox_config)


@app.route('/photo/<path:filename>')
def get_photo(filename):
    return send_from_directory(PHOTO_DIR, filename)


@app.route('/anime_photo/<path:filename>')
def get_anime_photo(filename):
    return send_from_directory(ANIME_PHOTO_DIR, filename)


@app.route('/api/geocode', methods=['POST'])
def geocode():
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({'status': 'error', 'message': '不正なJSONリクエストです'}), 400

    address = str(data.get('address', '')).strip()

    if not address:
        return jsonify({'status': 'error', 'message': '住所を入力してください'}), 400

    url = 'https://nominatim.openstreetmap.org/search'
    headers = {'User-Agent': 'SacredSiteTourApp/1.0'}
    params = {'q': address, 'format': 'json', 'limit': 1}

    try:
        res = requests.get(url, params=params, headers=headers, timeout=5)
        res_data = res.json()

        if not res_data:
            return jsonify({'status': 'error', 'message': '該当する住所が見つかりませんでした'}), 404

        lat = float(res_data[0]['lat'])
        lng = float(res_data[0]['lon'])

        return jsonify({'status': 'success', 'lat': lat, 'lng': lng})

    except requests.exceptions.RequestException:
        return jsonify({'status': 'error', 'message': 'ジオコーディングサービスへの接続に失敗しました'}), 502
    except Exception as e:
        return jsonify({'status': 'error', 'message': '内部サーバーエラーが発生しました'}), 500


@app.route('/api/works', methods=['GET'])
def get_works():
    works_set = set()
    for spot in SPOTS_CACHE:
        for w in spot['works']:
            if w:
                works_set.add(w)
    
    sorted_works = sorted(list(works_set))
    result = []
    
    for title in sorted_works:
        photo_filename = f"{title}.png"
        photo_path = os.path.join(ANIME_PHOTO_DIR, photo_filename)
        
        image_url = f"/anime_photo/{photo_filename}" if os.path.exists(photo_path) else None
        result.append({
            "title": title,
            "image_url": image_url
        })

    return jsonify(result)


@app.route('/api/spots', methods=['GET'])
def get_spots():
    query = request.args.get('q', '').strip().lower()
    target_work = request.args.get('work', '').strip()
    
    lat_param = request.args.get('lat')
    lng_param = request.args.get('lng')

    lat, lng = None, None
    if lat_param is not None and lng_param is not None:
        try:
            lat = float(lat_param)
            lng = float(lng_param)
        except ValueError:
            return jsonify({'error': '緯度・経度のフォーマットが不正です'}), 400

    filtered = []
    for spot in SPOTS_CACHE:
        if target_work and target_work not in spot['works']:
            continue

        if query:
            name_match = query in spot['name'].lower()
            sub_match = any(query in sub.lower() for sub in spot['sub_names'])
            work_match = any(query in w.lower() for w in spot['works'])
            if not (name_match or sub_match or work_match):
                continue

        spot_copy = spot.copy()
        if lat is not None and lng is not None:
            spot_copy['distance'] = calculate_distance(lat, lng, spot['lat'], spot['lng'])

        filtered.append(spot_copy)

    if lat is not None and lng is not None:
        filtered.sort(key=lambda x: x.get('distance', float('inf')))

    return jsonify(filtered)


@app.route('/api/nearby_spots', methods=['GET'])
def get_nearby_spots():
    try:
        lat = float(request.args.get('lat'))
        lng = float(request.args.get('lng'))
        limit = int(request.args.get('limit', 3))
    except (TypeError, ValueError):
        return jsonify({'error': 'パラメータが正しくありません'}), 400

    spots_with_dist = []
    for spot in SPOTS_CACHE:
        spot_copy = spot.copy()
        spot_copy['distance'] = calculate_distance(lat, lng, spot['lat'], spot['lng'])
        spots_with_dist.append(spot_copy)

    sorted_spots = sorted(spots_with_dist, key=lambda x: x['distance'])[:limit]
    return jsonify(sorted_spots)


@app.route('/api/optimize', methods=['POST'])
def optimize_route():
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({'error': 'リクエストデータが無効です'}), 400

    points = data.get('points', [])
    if not isinstance(points, list) or len(points) < 2:
        return jsonify({'error': '地点が足りません'}), 400

    validated_points = []
    for pt in points:
        if not isinstance(pt, dict) or 'lat' not in pt or 'lng' not in pt or 'name' not in pt:
            return jsonify({'error': '地点データのフォーマットが不正です'}), 400
        try:
            validated_points.append({
                'name': str(pt['name']),
                'work_title': str(pt.get('work_title', '')),
                'lat': float(pt['lat']),
                'lng': float(pt['lng']),
                'isStart': bool(pt.get('isStart', False))
            })
        except (TypeError, ValueError):
            return jsonify({'error': '緯度・経度の値が数値ではありません'}), 400

    start_pt = validated_points[0]
    unvisited = validated_points[1:]
    optimized = [start_pt]

    current = start_pt
    while unvisited:
        next_pt = min(
            unvisited,
            key=lambda p: calculate_distance(current['lat'], current['lng'], p['lat'], p['lng'])
        )
        optimized.append(next_pt)
        unvisited.remove(next_pt)
        current = next_pt

    return jsonify({'optimized_points': optimized})


if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1']
    port_num = int(os.environ.get('PORT', 5000))
    app.run(debug=debug_mode, port=port_num)