from flask import Flask, request, jsonify, send_file
from PIL import Image, ImageDraw, ImageFilter
import requests
from io import BytesIO
import base64
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({'status': 'OK', 'message': 'Clothing combiner service is running'})

@app.route('/combine-clothing', methods=['POST'])
def combine_clothing():
    try:
        data = request.json
        upper_url = data.get('upper_url')
        lower_url = data.get('lower_url')
        
        if not upper_url or not lower_url:
            return jsonify({
                'success': False, 
                'error': 'Both upper_url and lower_url are required'
            }), 400
        
        print(f"Processing: upper={upper_url[:50]}..., lower={lower_url[:50]}...")
        
        # Скачиваем изображения
        upper_response = requests.get(upper_url, timeout=30)
        upper_response.raise_for_status()
        
        lower_response = requests.get(lower_url, timeout=30)
        lower_response.raise_for_status()
        
        # Открываем изображения
        upper_img = Image.open(BytesIO(upper_response.content)).convert('RGBA')
        lower_img = Image.open(BytesIO(lower_response.content)).convert('RGBA')
        
        print(f"Upper image size: {upper_img.size}")
        print(f"Lower image size: {lower_img.size}")
        
        # Создаем белый фон 512x768 (оптимальный размер для Kling AI)
        canvas_width = 512
        canvas_height = 768
        combined = Image.new('RGB', (canvas_width, canvas_height), (255, 255, 255))
        
        # Рассчитываем размеры для размещения
        upper_target_height = 300
        lower_target_height = 300
        
        # Изменяем размер верхней одежды (сохраняем пропорции)
        upper_ratio = upper_target_height / upper_img.height
        upper_new_width = int(upper_img.width * upper_ratio)
        upper_resized = upper_img.resize((upper_new_width, upper_target_height), Image.Resampling.LANCZOS)
        
        # Изменяем размер нижней одежды
        lower_ratio = lower_target_height / lower_img.height
        lower_new_width = int(lower_img.width * lower_ratio)
        lower_resized = lower_img.resize((lower_new_width, lower_target_height), Image.Resampling.LANCZOS)
        
        # Центрируем изображения по горизонтали
        upper_x = (canvas_width - upper_new_width) // 2
        lower_x = (canvas_width - lower_new_width) // 2
        
        # Размещаем на canvas
        upper_y = 50  # Отступ сверху
        lower_y = canvas_height - lower_target_height - 50  # Отступ снизу
        
        # Вставляем изображения (обрабатываем прозрачность)
        if upper_resized.mode == 'RGBA':
            combined.paste(upper_resized, (upper_x, upper_y), upper_resized)
        else:
            combined.paste(upper_resized, (upper_x, upper_y))
            
        if lower_resized.mode == 'RGBA':
            combined.paste(lower_resized, (lower_x, lower_y), lower_resized)
        else:
            combined.paste(lower_resized, (lower_x, lower_y))
        
        # Конвертируем в base64
        buffer = BytesIO()
        combined.save(buffer, format='JPEG', quality=95, optimize=True)
        combined_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        print(f"Combined image created successfully, size: {len(combined_base64)} characters")
        
        return jsonify({
            'success': True,
            'combined_image_base64': combined_base64,
            'combined_image_url': f"data:image/jpeg;base64,{combined_base64}",
            'canvas_size': f"{canvas_width}x{canvas_height}",
            'upper_position': f"{upper_x},{upper_y}",
            'lower_position': f"{lower_x},{lower_y}"
        })
        
    except requests.RequestException as e:
        return jsonify({
            'success': False, 
            'error': f'Failed to download image: {str(e)}'
        }), 400
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({
            'success': False, 
            'error': f'Processing error: {str(e)}'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
