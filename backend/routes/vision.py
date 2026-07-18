"""
이미지 업로드 및 비전 모델 API 라우트
"""
import os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from services.vision_service import identify_sneaker

vision_bp = Blueprint('vision', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@vision_bp.route('/identify', methods=['POST'])
def identify():
    """스니커즈 이미지 업로드 및 식별"""
    if 'image' not in request.files:
        return jsonify({"error": "이미지 파일이 필요합니다."}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "파일이 선택되지 않았습니다."}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": f"허용된 파일 형식: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    # 파일 저장
    filename = secure_filename(file.filename)
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # 비전 모델로 식별
    result = identify_sneaker(filepath)

    return jsonify({
        "success": True,
        "identification": result,
        "uploaded_file": filename
    })
