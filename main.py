from flask import Flask, jsonify, request
import requests
import time
import os
import asyncio

app = Flask(__name__)

# Authorization token
AUTHORIZATION_TOKEN = '4e834e9332301d12878eeb9c93110de1f2e7f387'

# API Headers
HEADERS = {
    'authorization': AUTHORIZATION_TOKEN,
    'content-type': 'application/json'
}

# Aspect ratio mapping (add more ratios as needed)
aspect_ratios = {
    "1:1": (1024, 1024),
    "16:9": (1344, 768),
    "4:3": (1152, 896),
    "3:2": (1216, 832),
    "9:16": (1344, 768),
    "3:4": (1152, 896),
    "2:3": (1216, 832),
}

# Endpoint to trigger the generation and check the status
@app.route('/generate_image', methods=['POST'])
def generate_image():
    # Get the prompt and aspect ratio from the request
    request_data = request.json
    prompt = request_data.get('prompt', 'default prompt')  # Use 'default prompt' if none provided
    aspect_ratio = request_data.get('aspect_ratio', '1:1')  # Default to 1:1 if not provided

    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400

    # Get the width and height based on the aspect ratio
    if aspect_ratio not in aspect_ratios:
        return jsonify({"error": "Invalid aspect ratio"}), 400

    width, height = aspect_ratios[aspect_ratio]
    
    # 1. Request to create the image (First Request)
    create_url = 'https://piclumen.com/api/gen/create'
    payload = {
        "model_id": "34ec1b5a-8962-4a93-b047-68cec9691dc2",
        "prompt": prompt,
        "negative_prompt": "NSFW, watermark",
        "resolution": {"width": width, "height": height, "batch_size": 1},
        "model_ability": {"anime_style_control": None},
        "seed": 23066087366,
        "steps": 25,
        "cfg": 4.5,
        "sampler_name": "dpmpp_2m_sde_gpu",
        "scheduler": "karras",
        "denoise": 1,
        "hires_fix_denoise": 0.5,
        "hires_scale": 2,
        "gen_mode": "quality",
        "img2img_info": {"weight": 0}
    }
    
    response = requests.post(create_url, headers=HEADERS, json=payload)
    
    if response.status_code == 200:
        response_json = response.json()
        if response_json.get('status') == 0:
            mark_id = response_json['data']['markId']
        else:
            return jsonify({"error": f"Task creation failed: {response_json.get('message')}"}), 400
    else:
        return jsonify({"error": f"Failed to create the task. HTTP Status: {response.status_code}", "response": response.text}), 400

    # 2. Check the status of the task (Second Request)
    process_url = 'https://piclumen.com/api/task/processTask'
    # Custom boundary for multipart/form-data
    boundary = '----WebKitFormBoundaryJbEXBGu884mVa3mq'
    multipart_headers = {
        'authorization': AUTHORIZATION_TOKEN,
        'content-type': f'multipart/form-data; boundary={boundary}'
    }

    # Prepare the multipart form data for the second request
    form_data = f'--{boundary}\r\nContent-Disposition: form-data; name="markId"\r\n\r\n{mark_id}\r\n--{boundary}--\r\n'
    
    attempt = 0
    
    while True:
        attempt += 1
        time.sleep(5)  # Wait 5 seconds before each status check
        process_response = requests.post(process_url, headers=multipart_headers, data=form_data)

        if process_response.status_code == 200:
            process_json = process_response.json()
            if process_json.get('status') == 0:
                data = process_json['data']
                if data['status'] == 'success':
                    # If the task is successful, return the image URLs
                    img_urls = data['img_urls']
                    return jsonify({
                        'status': 'success',
                        'images': img_urls
                    })
                elif data['status'] == 'running':
                    # If still running, log attempt and continue checking
                    print(f"Attempt {attempt}: Task still running")
                    continue
            else:
                return jsonify({"error": f"Task processing failed: {process_json.get('message')}"}), 400
        else:
            return jsonify({"error": f"Failed to process the task. HTTP Status: {process_response.status_code}", "response": process_response.text}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5050)), debug=True)

