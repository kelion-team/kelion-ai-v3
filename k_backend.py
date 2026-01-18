"""
K - Minimal AI Hologram Backend
Only voice AI, no login, no database, no complexity
"""
from flask import Flask, request, jsonify, send_file
import os
import requests
import tempfile

app = Flask(__name__, static_folder='.', static_url_path='')

# Environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_BASE_URL = 'https://api.openai.com/v1'

@app.route('/')
def index():
    return send_file('k_minimal.html')

@app.route('/api/k/voice', methods=['POST'])
def k_voice():
    """
    Handle voice input from user
    1. Transcribe audio to text
    2. Get AI response
    3. Convert response to speech
    4. Return audio URL
    """
    try:
        audio_file = request.files.get('audio')
        if not audio_file:
            return jsonify({"error": "No audio provided"}), 400
        
        # Save temp audio file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp:
            audio_file.save(tmp.name)
            audio_path = tmp.name
        
        # 1. Transcribe with Whisper (auto-detect language)
        transcription = transcribe_audio(audio_path)
        os.unlink(audio_path)
        
        text = transcription.get('text', '')
        language = transcription.get('language', 'en')
        
        if not text:
            return jsonify({"error": "Could not understand audio"}), 400
        
        print(f"Detected language: {language}")
        
        # 2. Get AI response in detected language
        ai_response = get_ai_response(text, language)
        
        # 3. Convert to speech in detected language
        audio_url = text_to_speech(ai_response, language)
        
        return jsonify({
            "text": ai_response,
            "audio_url": audio_url,
            "original_text": text
        })
        
    except Exception as e:
        print(f"Voice error: {e}")
        return jsonify({"error": str(e)}), 500

def transcribe_audio(audio_path):
    """Transcribe audio using OpenAI Whisper - detects language automatically"""
    try:
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
        
        with open(audio_path, 'rb') as f:
            files = {'file': ('audio.webm', f, 'audio/webm')}
            data = {
                'model': 'whisper-1',
                'response_format': 'verbose_json'  # Get language detection
            }
            
            r = requests.post(
                f"{OPENAI_BASE_URL}/audio/transcriptions",
                headers=headers,
                files=files,
                data=data,
                timeout=30
            )
            r.raise_for_status()
            result = r.json()
            return {
                'text': result.get('text', ''),
                'language': result.get('language', 'en')  # Detected language
            }
    except Exception as e:
        print(f"Transcription error: {e}")
        return {'text': '', 'language': 'en'}

def get_ai_response(user_text, language='en'):
    """Get AI response using GPT - responds in detected language"""
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Language-specific system prompts
        lang_prompts = {
            'ro': 'Ești K, un asistent AI holografic avansat. Fii concis, util și conversațional. Răspunsuri sub 100 cuvinte.',
            'en': 'You are K, an advanced AI hologram assistant. Be concise, helpful, and conversational. Keep responses under 100 words.',
            'es': 'Eres K, un asistente holográfico de IA avanzado. Sé conciso, útil y conversacional. Respuestas de menos de 100 palabras.',
            'fr': 'Vous êtes K, un assistant holographique IA avancé. Soyez concis, utile et conversationnel. Réponses de moins de 100 mots.',
            'de': 'Du bist K, ein fortschrittlicher KI-Hologramm-Assistent. Sei prägnant, hilfreich und gesprächig. Antworten unter 100 Wörtern.'
        }
        
        system_prompt = lang_prompts.get(language, lang_prompts['en'])
        system_prompt += f" IMPORTANT: Always respond in {language.upper()} language."
        
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            "max_tokens": 150,
            "temperature": 0.7
        }
        
        r = requests.post(
            f"{OPENAI_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        r.raise_for_status()
        
        return r.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"AI response error: {e}")
        return "I'm having trouble processing that right now."

def text_to_speech(text, language='en'):
    """Convert text to speech using OpenAI TTS - uses language-appropriate voice"""
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Select voice based on language (onyx is male, works for all languages)
        voice = "onyx"  # Male voice, supports all OpenAI TTS languages
        
        payload = {
            "model": "tts-1",
            "input": text,
            "voice": voice
        }
        
        r = requests.post(
            f"{OPENAI_BASE_URL}/audio/speech",
            headers=headers,
            json=payload,
            timeout=30
        )
        r.raise_for_status()
        
        # Save audio file
        audio_filename = f"k_response_{os.urandom(8).hex()}.mp3"
        audio_path = os.path.join(tempfile.gettempdir(), audio_filename)
        
        with open(audio_path, 'wb') as f:
            f.write(r.content)
        
        # Return URL (this would need proper hosting in production)
        return f"/audio/{audio_filename}"
    except Exception as e:
        print(f"TTS error: {e}")
        return ""

@app.route('/audio/<filename>')
def serve_audio(filename):
    """Serve generated audio files"""
    audio_path = os.path.join(tempfile.gettempdir(), filename)
    if os.path.exists(audio_path):
        return send_file(audio_path, mimetype='audio/mpeg')
    return "Audio not found", 404

if __name__ == '__main__':
    PORT = int(os.getenv('PORT', 8080))
    print(f"🎭 K Hologram starting on port {PORT}...")
    print(f"🌐 Open http://localhost:{PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=True)
