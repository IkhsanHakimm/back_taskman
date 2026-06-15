from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# API KEY
genai.configure(api_key="AIzaSyAxsCqfj1A0X1mDBnB-sjwlzeD-Sum7in8")

# MODEL
model = genai.GenerativeModel("gemini-1.5-flash")

SYSTEM_PROMPT = """
Kamu adalah AI pembimbing mahasiswa berbasis tugas.

Jika user memberikan sebuah tugas, kamu harus:
1. Mengidentifikasi topik utama dari tugas
2. Mengubahnya menjadi roadmap pembelajaran
3. Menyusun langkah dari dasar ke tingkat lanjut
4. Memberikan penjelasan singkat tiap langkah
5. Memberikan sumber belajar yang relevan
6. Maksimal 6 langkah

FORMAT OUTPUT HARUS JSON:
{
  "task": "",
  "learning_path": [
    {
      "step": 1,
      "topic": "",
      "explanation": "",
      "resources": [
        {
          "title": "",
          "type": "",
          "platform": "",
          "link": ""
        }
      ]
    }
  ]
}
"""

@app.route('/generate-learning', methods=['POST'])
def generate_learning():
    data = request.json
    task = data['task_title']

    prompt = f"""
    {SYSTEM_PROMPT}

    Buat roadmap belajar dari tugas berikut:
    Tugas: {task}
    """

    response = model.generate_content(prompt)

    return jsonify({
        "result": response.text
    })

if __name__ == "__main__":
    app.run(debug=True)