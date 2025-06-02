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
    return jsonify({'status': 'OK', 'message': 'Clothing combiner service with white separators'})

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
        
        print(f"Processing with white separators:")
        print(f"Upper: {upper_url[:50]}...")
        print(f"Lower: {lower_url[:50]}...")
        
        # Скачиваем изображения
        upper_response = requests.get(upper_url, timeout=30)
        upper_response.raise_for_status()
        
        lower_response = requests.get(lower_url, timeout=30)
        lower_response.raise_for_status()
        
        # Открываем изображения
        upper_img = Image.open(BytesIO(upper_response.content)).convert('RGBA')
        lower_img = Image.open(BytesIO(lower_response.content)).convert('RGBA')
        
        print(f"Original sizes - Upper: {upper_img.size}, Lower: {lower_img.size}")
        
        # СОЗДАНИЕ КОМПОЗИЦИИ С БЕЛЫМИ РАЗДЕЛИТЕЛЯМИ
        
        # Стандартные размеры для каждого элемента
        item_width = 250
        item_height = 300
        border_thickness = 15  # Толщина белой рамки
        separator_width = 40   # Ширина разделителя между элементами
        
        # Изменяем размер изображений
        upper_resized = upper_img.resize((item_width, item_height), Image.Resampling.LANCZOS)
        lower_resized = lower_img.resize((item_width, item_height), Image.Resampling.LANCZOS)
        
        # Создаем изображения с белыми рамками
        bordered_width = item_width + (border_thickness * 2)
        bordered_height = item_height + (border_thickness * 2)
        
        # Верхняя одежда с белой рамкой
        upper_with_border = Image.new('RGB', (bordered_width, bordered_height), (255, 255, 255))
        upper_with_border.paste(upper_resized, (border_thickness, border_thickness), 
                               upper_resized if upper_resized.mode == 'RGBA' else None)
        
        # Добавляем тонкую серую рамку для четкости
        draw_upper = ImageDraw.Draw(upper_with_border)
        draw_upper.rectangle([border_thickness-1, border_thickness-1, 
                             bordered_width-border_thickness, bordered_height-border_thickness], 
                            outline=(220, 220, 220), width=2)
        
        # Нижняя одежда с белой рамкой
        lower_with_border = Image.new('RGB', (bordered_width, bordered_height), (255, 255, 255))
        lower_with_border.paste(lower_resized, (border_thickness, border_thickness),
                               lower_resized if lower_resized.mode == 'RGBA' else None)
        
        # Добавляем тонкую серую рамку для четкости
        draw_lower = ImageDraw.Draw(lower_with_border)
        draw_lower.rectangle([border_thickness-1, border_thickness-1, 
                             bordered_width-border_thickness, bordered_height-border_thickness], 
                            outline=(220, 220, 220), width=2)
        
        # Рассчитываем размер итогового canvas
        canvas_width = (bordered_width * 2) + separator_width + 60  # +60 для боковых отступов
        canvas_height = bordered_height + 80  # +80 для верхних и нижних отступов
        
        # Обеспечиваем минимальные размеры для Kling AI
        min_width = 600
        min_height = 400
        
        if canvas_width < min_width:
            canvas_width = min_width
        if canvas_height < min_height:
            canvas_height = min_height
        
        print(f"Canvas size: {canvas_width}x{canvas_height}")
        
        # Создаем белый canvas
        combined = Image.new('RGB', (canvas_width, canvas_height), (255, 255, 255))
        
        # Позиционируем элементы с большими белыми промежутками
        upper_x = 30  # Отступ слева
        upper_y = (canvas_height - bordered_height) // 2  # Центрируем по вертикали
        
        lower_x = upper_x + bordered_width + separator_width  # После верхней одежды + большой отступ
        lower_y = (canvas_height - bordered_height) // 2  # Центрируем по вертикали
        
        # Вставляем изображения с рамками
        combined.paste(upper_with_border, (upper_x, upper_y))
        combined.paste(lower_with_border, (lower_x, lower_y))
        
        # Добавляем четкую вертикальную разделительную линию
        draw_main = ImageDraw.Draw(combined)
        separator_line_x = upper_x + bordered_width + (separator_width // 2)
        line_top = upper_y + 20
        line_bottom = upper_y + bordered_height - 20
        draw_main.line([(separator_line_x, line_top), (separator_line_x, line_bottom)], 
                      fill=(240, 240, 240), width=3)
        
        # Добавляем подписи для четкости
        try:
            # Простые текстовые метки
            draw_main.text((upper_x + bordered_width//2 - 25, upper_y - 25), 
                          "UPPER", fill=(180, 180, 180))
            draw_main.text((lower_x + bordered_width//2 - 25, lower_y - 25), 
                          "LOWER", fill=(180, 180, 180))
        except Exception as e:
            print(f"Warning: Could not add text labels: {e}")
        
        # Добавляем общую рамку для композиции
        draw_main.rectangle([5, 5, canvas_width-6, canvas_height-6], 
                           outline=(230, 230, 230), width=3)
        
        # Конвертируем в base64
        buffer = BytesIO()
        combined.save(buffer, format='JPEG', quality=95, optimize=True)
        combined_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        print(f"Combined image created successfully")
        print(f"Final size: {combined.size}")
        print(f"Base64 length: {len(combined_base64)} characters")
        
        # Проверяем соответствие требованиям Kling AI
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
            'layout': 'horizontal_with_white_separators',
            'upper_position': f"{upper_x},{upper_y}",
            'lower_position': f"{lower_x},{lower_y}",
            'separator_info': {
                'border_thickness': border_thickness,
                'separator_width': separator_width,
                'has_outline': True,
                'has_labels': True,
                'has_divider_line': True
            },
            'arrangement': 'Upper clothing (left) and lower clothing (right) with clear white separators',
            'ai_optimization': 'White borders and clear separation to help AI distinguish clothing parts'
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
        'message': 'Test endpoint for clothing combiner',
        'features': [
            'White borders around each clothing item',
            'Clear separator between upper and lower clothing',
            'Optimized for AI recognition',
            'Minimum 600x400 resolution',
            'Text labels for clarity',
            'Divider line between sections'
        ]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
