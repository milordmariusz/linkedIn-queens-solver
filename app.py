import os
from flask import Flask, request, jsonify, render_template
import base64
from image_processor import process_image

app = Flask(__name__, template_folder='templates')

app.config['SECRET_KEY'] = os.urandom(24)

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_image():
    """Handles image uploads, processes them, and returns the result."""
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image file provided.'}), 400

    file = request.files['image']

    if file.filename == '':
        return jsonify({'success': False, 'error': 'No image file selected.'}), 400

    if file:
        try:
            image_data = file.read()

            processed_image_bytes, error_message = process_image(image_data)

            if error_message:
                print(f"Processing Error: {error_message}")
                return jsonify({'success': False, 'error': error_message})
            else:
                img_base64 = base64.b64encode(processed_image_bytes).decode('utf-8')
                data_url = f"data:image/png;base64,{img_base64}"
                return jsonify({'success': True, 'image': data_url})

        except Exception as e:
            import traceback
            print("--- UNEXPECTED SERVER ERROR ---")
            print(traceback.format_exc())
            print("-------------------------------")
            return jsonify({'success': False, 'error': f'An internal server error occurred: {e}'}), 500

    return jsonify({'success': False, 'error': 'Invalid file.'}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)