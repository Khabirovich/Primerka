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
        
        print(f"Original upper image size: {upper_img.size}")
        print(f"Original lower image size: {lower_img.size}")
        
        # ИСПРАВЛЕННАЯ ЛОГИКА ДЛЯ ВЫСОКОГО КАЧЕСТВА
        
        # Устанавливаем минимальные размеры для соответствия требованиям Kling AI
        min_total_width = 600   # Минимальная ширина итогового изображения
        min_total_height = 400  # Минимальная высота итогового изображения
        target_height = 500     # Увеличили целевую высоту для лучшего качества
        
        # Изменяем размер изображений, сохраняя пропорции
        upper_ratio = target_height / upper_img.height
        upper_new_width = int(upper_img.width * upper_ratio)
        upper_resized = upper_img.resize((upper_new_width, target_height), Image.Resampling.LANCZOS)
        
        lower_ratio = target_height / lower_img.height  
        lower_new_width = int(lower_img.width * lower_ratio)
        lower_resized = lower_img.resize((lower_new_width, target_height), Image.Resampling.LANCZOS)
        
        # Рассчитываем размеры canvas
        spacing = 30  # Отступ между изображениями
        canvas_width = upper_new_width + lower_new_width + spacing + 40  # +40 для боковых отступов
        canvas_height = target_height + 100  # +100 для отступов сверху и снизу
        
        # ВАЖНО: Убеждаемся что размер не меньше минимального
        if canvas_width < min_total_width:
            # Увеличиваем пропорционально
            scale_factor = min_total_width / canvas_width
            canvas_width = min_total_width
            canvas_height = int(canvas_height * scale_factor)
            target_height = int(target_height * scale_factor)
            
            # Пересчитываем размеры изображений
            upper_resized = upper_img.resize((int(upper_new_width * scale_factor), target_height), Image.Resampling.LANCZOS)
            lower_resized = lower_img.resize((int(lower_new_width * scale_factor), target_height), Image.Resampling.LANCZOS)
            upper_new_width = int(upper_new_width * scale_factor)
            lower_new_width = int(lower_new_width * scale_factor)
        
        if canvas_height < min_total_height:
            canvas_height = min_total_height
        
        print(f"Final canvas size: {canvas_width}x{canvas_height}")
        print(f"Upper resized: {upper_resized.size}")
        print(f"Lower resized: {lower_resized.size}")
        
        # Создаем белый canvas
        combined = Image.new('RGB', (canvas_width, canvas_height), (255, 255, 255))
        
        # Позиционируем изображения горизонтально
        upper_x = 20  # Отступ слева
        upper_y = (canvas_height - target_height) // 2  # Центрируем по вертикали
        
        lower_x = upper_new_width + spacing + 20  # После верхней одежды + отступ
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
        
        # УБИРАЕМ ПРИНУДИТЕЛЬНОЕ УМЕНЬШЕНИЕ ДО 512px!
        # НЕ ДЕЛАЕМ resize если изображение больше 512px
        
        # Конвертируем в base64
        buffer = BytesIO()
        combined.save(buffer, format='JPEG', quality=95, optimize=True)
        combined_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        print(f"Combined image created successfully")
        print(f"Final size: {combined.size}")
        print(f"Base64 length: {len(combined_base64)} characters")
        
        # Проверяем что размер соответствует требованиям
        if combined.width < 300 or combined.height < 300:
            return jsonify({
                'success': False,
                'error': f'Generated image is too small: {combined.width}x{combined.height}. Minimum required: 300x300'
            }), 400
        
        return jsonify({
            'success': True,
            'combined_image_base64': combined_base64,
            'combined_image_url': f"data:image/jpeg;base64,{combined_base64}",
            'canvas_size': f"{combined.width}x{combined.height}",
            'layout': 'horizontal',
            'upper_position': f"{upper_x},{upper_y}",
            'lower_position': f"{lower_x},{lower_y}",
            'arrangement': 'left: upper clothing, right: lower clothing',
            'quality_info': f'High quality: {combined.width}x{combined.height}px'
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
