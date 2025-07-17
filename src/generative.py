import os
import google.generativeai as genai

def is_generative_ai_available():
    """
    Checks if the Gemini API key is configured in the environment variables.
    If available, it configures the genai library.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("\nWarning: GEMINI_API_KEY not found in environment variables.")
        print("AI features will be disabled. To enable them, please set the key in your .env file.")
        return False
    try:
        genai.configure(api_key=api_key)
        return True
    except Exception as e:
        print(f"An error occurred while configuring Generative AI: {e}")
        return False

def generate_content(prompt: str) -> str:
    """
    Generates content using the Gemini Pro model based on a given prompt.
    """
    print("Calling Gemini API...")
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"An error occurred during content generation: {e}")
        return "Gagal menghasilkan konten dari AI."

def generate_description_prompt(proker_title: str, kegiatan_title: str) -> str:
    """
    Creates a tailored prompt to generate a professional 'Deskripsi Kegiatan'.
    """
    return (
        f"Anda adalah seorang mahasiswa KKN UGM yang sedang mengisi logbook SIMASTER.\n"
        f"Buatkan 'Deskripsi Kegiatan' yang baik dan profesional untuk sebuah sub-kegiatan dalam logbook KKN.\n\n"
        f"**Informasi Konteks:**\n"
        f"- **Judul Program Kerja (Proker) Utama:** {proker_title}\n"
        f"- **Judul Kegiatan Harian / Sub-Kegiatan:** {kegiatan_title}\n\n"
        f"**Instruksi:**\n"
        f"1. Tulis deskripsi dalam Bahasa Indonesia yang formal dan jelas.\n"
        f"2. Deskripsi harus menjelaskan secara singkat apa yang dilakukan dalam kegiatan '{kegiatan_title}' sebagai bagian dari program kerja '{proker_title}'.\n"
        f"3. Jelaskan tujuan singkat dari kegiatan ini dan relevansinya terhadap proker utama.\n"
        f"4. Buat deskripsi sekitar 300 karakter yang menjelsakan tahapan kegiatan dan kaitannya dengan proker. Jangan terlalu panjang. Jangan gunakan formatting, hanya response dengan deskripsi kegiatan.\n\n"
        f"**Contoh Output:**\n"
        f"Kegiatan ini merupakan bagian dari pelaksanaan program kerja '{proker_title}'. "
        f"Fokus dari kegiatan ini adalah untuk [jelaskan tujuan singkat kegiatan]. "
        f"Hal ini dilakukan untuk mendukung pencapaian tujuan utama program kerja dalam [sebutkan relevansi dengan proker]."
    )

def generate_hasil_kegiatan_prompt(proker_title: str, kegiatan_title: str, description: str) -> str:
    """
    Creates a tailored prompt to generate a positive 'Hasil Kegiatan' based on the context.
    """
    return (
        f"Anda adalah seorang mahasiswa KKN UGM yang sedang mengisi logbook SIMASTER.\n"
        f"Buatkan 'Hasil Kegiatan' yang baik dan positif untuk sebuah sub-kegiatan dalam logbook KKN.\n\n"
        f"**Informasi Konteks:**\n"
        f"- **Judul Program Kerja (Proker) Utama:** {proker_title}\n"
        f"- **Judul Kegiatan Harian / Sub-Kegiatan:** {kegiatan_title}\n"
        f"- **Deskripsi Kegiatan yang sudah dibuat:** {description}\n\n"
        f"**Instruksi:**\n"
        f"1. Tulis hasil kegiatan dalam Bahasa Indonesia yang formal.\n"
        f"2. Tuliskan bahwa kegiatan telah dilaksanakan dengan baik dan lancar.\n"
        f"3. Sebutkan output atau hasil positif yang singkat dan jelas dari kegiatan tersebut.\n"
        f"4. Buat hasil kegiatan dalam 1-2 kalimat saja. Jangan terlalu panjang. Jangan gunakan formatting, hanya response dengan hasil kegiatan saja\n\n"
        f"**Contoh Output:**\n"
        f"Kegiatan ini telah berhasil dilaksanakan sesuai dengan rencana dan berjalan dengan lancar. "
        f"Hasil yang dicapai adalah [sebutkan hasil positif singkat], memberikan kontribusi positif terhadap program kerja."
    )
