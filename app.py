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
        
        # ГОРИЗОНТАЛЬНОЕ ОБЪЕДИНЕНИЕ
        # Создаем белый фон (ширина = сумма ширин, высота = максимальная высота)
        target_height = 400  # Стандартная высота для обеих частей
        
        # Изменяем размер изображений, сохраняя пропорции
        upper_ratio = target_height / upper_img.height
        upper_new_width = int(upper_img.width * upper_ratio)
        upper_resized = upper_img.resize((upper_new_width, target_height), Image.Resampling.LANCZOS)
        
        lower_ratio = target_height / lower_img.height  
        lower_new_width = int(lower_img.width * lower_ratio)
        lower_resized = lower_img.resize((lower_new_width, target_height), Image.Resampling.LANCZOS)
        
        # Рассчитываем общие размеры canvas
        canvas_width = upper_new_width + lower_new_width + 20  # +20 для небольшого отступа между изображениями
        canvas_height = target_height + 100  # +100 для отступов сверху и снизу
        
        # Создаем белый canvas
        combined = Image.new('RGB', (canvas_width, canvas_height), (255, 255, 255))
        
        # Позиционируем изображения горизонтально
        upper_x = 10  # Отступ слева
        upper_y = (canvas_height - target_height) // 2  # Центрируем по вертикали
        
        lower_x = upper_new_width + 20  # После верхней одежды + отступ
        lower_y = (canvas_height - target_height) // 2  # Центрируем по вертикали
        
        # Вставляем изображения
        if upper_resized.mode == 'RGBA':
            combined.paste(upper_resized, (upper_x, upper_y), upper_resized)
        else:
            combined.paste(upper_resized, (upper_x, upper_y))
            
        if lower_resized.mode == 'RGBA':
            combined.paste(lower_resized, (lower_x, lower_y), lower_resized)
        else:
            combined.paste(lower_resized, (lower_x, lower_y))
        
        # Оптимизируем размер для Kling AI (максимум 512px по ширине)
        if canvas_width > 512:
            resize_ratio = 512 / canvas_width
            new_height = int(canvas_height * resize_ratio)
            combined = combined.resize((512, new_height), Image.Resampling.LANCZOS)
            canvas_width = 512
            canvas_height = new_height
        
        # Конвертируем в base64
        buffer = BytesIO()
        combined.save(buffer, format='JPEG', quality=95, optimize=True)
        combined_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        print(f"Combined image created successfully")
        print(f"Final size: {canvas_width}x{canvas_height}")
        print(f"Base64 length: {len(combined_base64)} characters")
        
        return jsonify({
            'success': True,
            'combined_image_base64': combined_base64,
            'combined_image_url': f"data:image/jpeg;base64,{combined_base64}",
            'canvas_size': f"{canvas_width}x{canvas_height}",
            'layout': 'horizontal',
            'upper_position': f"{upper_x},{upper_y}",
            'lower_position': f"{lower_x},{lower_y}",
            'arrangement': 'left: upper clothing, right: lower clothing'
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
