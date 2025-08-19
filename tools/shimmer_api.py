#!/usr/bin/env python3
"""
Working Shimmer API - Compression/Decompression Service
"""

from flask import Flask, request, jsonify
import requests
import json
import time

app = Flask(__name__)

def compress_with_ollama(english_text):
    """Compress English to shimmer using local model"""
    
    prompt = f"""Convert this English to shimmer format:

SHIMMER RULES:
- Container: <routing><action><metadata><temporal><deliverables>→<vector>
- Routing: AB (generic agents)
- Actions: P(plan), q(query), c(complete), a(ack), e(error)
- Vector: [Action, Subject, Context, Urgency, Confidence] ranges -1.0 to +1.0 (confidence 0.0-1.0)

English: {english_text}

Shimmer (container format only):"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "qwen2.5:latest",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2}
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json().get("response", "").strip()
            # Extract shimmer format from response
            for line in result.split('\n'):
                if '→[' in line and len(line) < 50:
                    return line.strip()
            
            # Fallback if no clean format found
            return result.split('\n')[0].strip()[:50]
        
        return f"ABP→[0.5,0.5,0.0,0.5,0.85]"  # Default fallback
        
    except Exception as e:
        return f"ABP→[0.5,0.5,0.0,0.5,0.85]"  # Error fallback

def decompress_with_ollama(shimmer_text):
    """Decompress shimmer to English using local model"""
    
    prompt = f"""Translate this shimmer message to plain English:

SHIMMER: {shimmer_text}

RULES:
- Explain what the message means in simple English
- Be concise and clear

English meaning:"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate", 
            json={
                "model": "qwen2.5:latest",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2}
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json().get("response", "").strip()
            return result
        
        return "Translation not available"
        
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/compress', methods=['POST'])
def compress_text():
    """Compress English text to shimmer format"""
    
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({"error": "Missing 'text' field"}), 400
    
    english_text = data['text']
    original_length = len(english_text)
    
    # Compress to shimmer
    start_time = time.time()
    shimmer_result = compress_with_ollama(english_text)
    compression_time = time.time() - start_time
    
    compressed_length = len(shimmer_result)
    compression_ratio = (1 - compressed_length / original_length) * 100
    
    return jsonify({
        "original": english_text,
        "shimmer": shimmer_result,
        "stats": {
            "original_chars": original_length,
            "compressed_chars": compressed_length,
            "compression_ratio": f"{compression_ratio:.1f}%",
            "processing_time": f"{compression_time:.2f}s"
        }
    })

@app.route('/decompress', methods=['POST'])
def decompress_shimmer():
    """Decompress shimmer format to English"""
    
    data = request.get_json()
    if not data or 'shimmer' not in data:
        return jsonify({"error": "Missing 'shimmer' field"}), 400
    
    shimmer_text = data['shimmer']
    
    # Decompress to English
    start_time = time.time()
    english_result = decompress_with_ollama(shimmer_text)
    decompression_time = time.time() - start_time
    
    return jsonify({
        "shimmer": shimmer_text,
        "english": english_result,
        "processing_time": f"{decompression_time:.2f}s"
    })

@app.route('/demo', methods=['GET'])
def demo_page():
    """Demo page showing API functionality"""
    
    return """
    <html>
    <head><title>Shimmer API Demo</title></head>
    <body>
        <h1>Shimmer Compression API</h1>
        
        <h2>Compress Text</h2>
        <textarea id="input" rows="4" cols="50" placeholder="Enter English text..."></textarea><br>
        <button onclick="compress()">Compress to Shimmer</button>
        <div id="compressed"></div>
        
        <h2>Decompress Shimmer</h2>
        <input id="shimmer" placeholder="Enter shimmer format..." style="width: 400px">
        <button onclick="decompress()">Decompress to English</button>
        <div id="decompressed"></div>
        
        <script>
        async function compress() {
            const text = document.getElementById('input').value;
            const response = await fetch('/compress', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text: text})
            });
            const result = await response.json();
            document.getElementById('compressed').innerHTML = 
                '<strong>Shimmer:</strong> ' + result.shimmer + 
                '<br><strong>Compression:</strong> ' + result.stats.compression_ratio +
                '<br><strong>Time:</strong> ' + result.stats.processing_time;
        }
        
        async function decompress() {
            const shimmer = document.getElementById('shimmer').value;
            const response = await fetch('/decompress', {
                method: 'POST', 
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({shimmer: shimmer})
            });
            const result = await response.json();
            document.getElementById('decompressed').innerHTML = 
                '<strong>English:</strong> ' + result.english;
        }
        </script>
    </body>
    </html>
    """

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "ok", "timestamp": time.time()})

if __name__ == '__main__':
    print("🚀 SHIMMER API STARTING")
    print("Demo: http://localhost:5000/demo")
    print("Endpoints:")
    print("  POST /compress - English → Shimmer")
    print("  POST /decompress - Shimmer → English")
    print("  GET /health - Status check")
    
    app.run(host='0.0.0.0', port=5000, debug=True)