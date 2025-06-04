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
    return jsonify({'status': 'OK', 'message': 'Clothing combiner service with original proportions'})

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
        
        print(f"Processing with original proportions:")
        print(f"Upper: {upper_url[:50]}...")
        print(f"Lower: {lower_url[:50]}...")
        
        # Скачиваем изображения
        upper_response = requests.get(upper_url, timeout=30)
        upper_response.raise_for_status()
        
        lower_response = requests.get(lower_url, timeout=30)
        lower_response.raise_for_status()
        
        # Открываем изображения и сохраняем ОРИГИНАЛЬНЫЕ размеры
        upper_img = Image.open(BytesIO(upper_response.content)).convert('RGBA')
        lower_img = Image.open(BytesIO(lower_response.content)).convert('RGBA')
        
        print(f"Original sizes - Upper: {upper_img.size}, Lower: {lower_img.size}")
        
        # СОХРАНЯЕМ ОРИГИНАЛЬНЫЕ РАЗМЕРЫ - НЕ ИЗМЕНЯЕМ!
        upper_width, upper_height = upper_img.size
        lower_width, lower_height = lower_img.size
        
        # Параметры для композиции
        border_thickness = 15  # Белая рамка вокруг каждого изображения
        separator_width = 50   # Разделитель между изображениями
        padding = 30          # Отступы по краям canvas
        
        # Создаем изображения с белыми рамками (сохраняя оригинальные размеры)
        bordered_upper_width = upper_width + (border_thickness * 2)
        bordered_upper_height = upper_height + (border_thickness * 2)
        
        bordered_lower_width = lower_width + (border_thickness * 2)
        bordered_lower_height = lower_height + (border_thickness * 2)
        
        # Верхняя одежда с белой рамкой
        upper_with_border = Image.new('RGB', (bordered_upper_width, bordered_upper_height), (255, 255, 255))
        upper_with_border.paste(upper_img, (border_thickness, border_thickness), 
                               upper_img if upper_img.mode == 'RGBA' else None)
        
        # Добавляем тонкую серую рамку для четкости
        draw_upper = ImageDraw.Draw(upper_with_border)
        draw_upper.rectangle([border_thickness-2, border_thickness-2, 
                             bordered_upper_width-border_thickness+1, bordered_upper_height-border_thickness+1], 
                            outline=(220, 220, 220), width=2)
        
        # Нижняя одежда с белой рамкой
        lower_with_border = Image.new('RGB', (bordered_lower_width, bordered_lower_height), (255, 255, 255))
        lower_with_border.paste(lower_img, (border_thickness, border_thickness),
                               lower_img if lower_img.mode == 'RGBA' else None)
        
        # Добавляем тонкую серую рамку для четкости
        draw_lower = ImageDraw.Draw(lower_with_border)
        draw_lower.rectangle([border_thickness-2, border_thickness-2, 
                             bordered_lower_width-border_thickness+1, bordered_lower_height-border_thickness+1], 
                            outline=(220, 220, 220), width=2)
        
        # Рассчитываем размер итогового canvas с учетом ОРИГИНАЛЬНЫХ размеров
        canvas_width = bordered_upper_width + bordered_lower_width + separator_width + (padding * 2)
        canvas_height = max(bordered_upper_height, bordered_lower_height) + (padding * 2)
        
        # Обеспечиваем минимальные размеры 400x400
        min_size = 400
        if canvas_width < min_size:
            canvas_width = min_size
        if canvas_height < min_size:
            canvas_height = min_size
        
        print(f"Canvas size: {canvas_width}x{canvas_height}")
        print(f"Upper with border: {bordered_upper_width}x{bordered_upper_height}")
        print(f"Lower with border: {bordered_lower_width}x{bordered_lower_height}")
        
        # Создаем белый canvas
        combined = Image.new('RGB', (canvas_width, canvas_height), (255, 255, 255))
        
        # Позиционируем элементы (горизонтально, по центру по вертикали)
        upper_x = padding
        upper_y = (canvas_height - bordered_upper_height) // 2
        
        lower_x = upper_x + bordered_upper_width + separator_width
        lower_y = (canvas_height - bordered_lower_height) // 2
        
        # Вставляем изображения с рамками
        combined.paste(upper_with_border, (upper_x, upper_y))
        combined.paste(lower_with_border, (lower_x, lower_y))
        
        # Добавляем четкую вертикальную разделительную линию
        draw_main = ImageDraw.Draw(combined)
        separator_line_x = upper_x + bordered_upper_width + (separator_width // 2)
        line_top = min(upper_y, lower_y) + 20
        line_bottom = max(upper_y + bordered_upper_height, lower_y + bordered_lower_height) - 20
        draw_main.line([(separator_line_x, line_top), (separator_line_x, line_bottom)], 
                      fill=(200, 200, 200), width=3)
        
        # Добавляем ЧЕТКИЕ подписи для лучшего распознавания AI
        try:
            # Подписи СВЕРХУ изображений
            upper_center_x = upper_x + bordered_upper_width // 2
            lower_center_x = lower_x + bordered_lower_width // 2
            
            label_y = min(upper_y, lower_y) - 35
            
            draw_main.text((upper_center_x, label_y), "TOP", fill=(100, 100, 100), anchor="mm")
            draw_main.text((lower_center_x, label_y), "BOTTOM", fill=(100, 100, 100), anchor="mm")
            
            # Дополнительные подписи СНИЗУ
            bottom_label_y = max(upper_y + bordered_upper_height, lower_y + bordered_lower_height) + 25
            draw_main.text((upper_center_x, bottom_label_y), "UPPER", fill=(150, 150, 150), anchor="mm")
            draw_main.text((lower_center_x, bottom_label_y), "LOWER", fill=(150, 150, 150), anchor="mm")
            
        except Exception as e:
            print(f"Warning: Could not add text labels: {e}")
        
        # Добавляем общую рамку для композиции
        draw_main.rectangle([3, 3, canvas_width-4, canvas_height-4], 
                           outline=(210, 210, 210), width=2)
        
        # Конвертируем в base64
        buffer = BytesIO()
        combined.save(buffer, format='JPEG', quality=95, optimize=True)
        combined_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        print(f"Combined image created successfully")
        print(f"Final size: {combined.size}")
        print(f"Original proportions preserved!")
        
        # Проверяем соответствие требованиям
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
            'layout': 'horizontal_original_proportions',
            'upper_position': f"{upper_x},{upper_y}",
            'lower_position': f"{lower_x},{lower_y}",
            'original_sizes': {
                'upper': f"{upper_width}x{upper_height}",
                'lower': f"{lower_width}x{lower_height}",
                'upper_with_border': f"{bordered_upper_width}x{bordered_upper_height}",
                'lower_with_border': f"{bordered_lower_width}x{bordered_lower_height}"
            },
            'separator_info': {
                'border_thickness': border_thickness,
                'separator_width': separator_width,
                'has_outline': True,
                'has_labels': True,
                'has_divider_line': True,
                'preserves_original_size': True
            },
            'arrangement': 'Upper clothing (left) and lower clothing (right) with ORIGINAL sizes preserved',
            'ai_optimization': 'Original proportions maintained for better AI recognition, clear labels and separation'
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

@app.route('/test-combine', methods=['GET'])
def test_combine():
    """Test endpoint для проверки микросервиса"""
    return jsonify({
        'message': 'Test endpoint for clothing combiner with original proportions',
        'features': [
            'Preserves original image sizes and proportions',
            'White borders around each clothing item',
            'Clear separator between upper and lower clothing',
            'Optimized for AI recognition with proper labels',
            'Minimum 400x400 resolution guaranteed',
            'Horizontal layout with centered positioning',
            'TOP/BOTTOM and UPPER/LOWER labels for clarity',
            'Divider line between sections'
        ]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
