import os
import subprocess
import json
import mimetypes
import sqlite3
import time
from colorama import init, Fore, Style

# Inicializa o colorama
init(autoreset=True)

DATABASE_FILE = "video_analysis.db"

def is_video_file(file_path):
    """Verifica dinamicamente se um arquivo é de vídeo usando mimetypes."""
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type and mime_type.startswith("video")

def get_video_info(file_path):
    """Retorna informações técnicas do vídeo usando ffprobe."""
    try:
        command = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=bit_rate,codec_name,width,height",
            "-show_entries", "format=duration",
            "-of", "json",
            file_path
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        video_info = json.loads(result.stdout)

        # Obtém informações
        codec_name = video_info.get('streams', [{}])[0].get('codec_name', '')
        bit_rate = video_info.get('streams', [{}])[0].get('bit_rate', 0)
        bit_rate = int(bit_rate) // 1000 if bit_rate else 0  # Converte para kbps

        width = video_info.get('streams', [{}])[0].get('width', 0)
        height = video_info.get('streams', [{}])[0].get('height', 0)
        duration = float(video_info.get('format', {}).get('duration', 0))

        return {
            'codec_name': codec_name,
            'bit_rate': bit_rate,
            'width': width,
            'height': height,
            'duration': duration
        }

    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Erro ao analisar {file_path}: {e}")
        return None
    except Exception as e:
        print(f"{Fore.RED}Erro inesperado ao processar {file_path}: {e}")
        return None

def encode_video(input_file, temp_file, target_quality=35, codec="hevc_nvenc"):
    """Re-encoda o vídeo com o codec especificado."""
    command = [
        "ffmpeg",
        "-hwaccel", "cuda",            # Usa aceleração de hardware
        "-i", input_file,
        "-c:v", codec,                 # Codec (hevc_nvenc ou av1_nvenc)
        "-cq", str(target_quality),    # Qualidade constante
        "-rc", "vbr",                  # Controle de taxa em VBR
        "-c:a", "copy",                # Mantém o áudio original
        "-f", "mp4",                   # Força container MP4
        temp_file
    ]
    try:
        subprocess.run(command, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Erro ao processar {input_file} com {codec}: {e}")
        return False

def init_database():
    """Inicializa o banco de dados SQLite."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS video_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE,
            codec_name TEXT,
            bit_rate INTEGER,
            width INTEGER,
            height INTEGER,
            analyzed INTEGER DEFAULT 0,
            converted INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def save_analysis_to_db(file_path, video_info):
    """Salva os resultados da análise no banco de dados."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO video_files (file_path, codec_name, bit_rate, width, height, analyzed)
        VALUES (?, ?, ?, ?, ?, 1)
    """, (file_path, video_info['codec_name'], video_info['bit_rate'], video_info['width'], video_info['height']))
    conn.commit()
    conn.close()

def get_unanalyzed_files(files):
    """Filtra arquivos que ainda não foram analisados."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT file_path FROM video_files WHERE analyzed = 1")
    analyzed_files = {row[0] for row in cursor.fetchall()}
    conn.close()
    return [file for file in files if file not in analyzed_files]

def get_unconverted_files(codec_name, conversion_criteria):
    """Recupera arquivos para conversão com base no critério."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    if conversion_criteria == "1":
        # Baseado no bitrate
        cursor.execute("""
            SELECT file_path FROM video_files
            WHERE analyzed = 1 AND converted = 0 AND bit_rate > 0
        """)
    elif conversion_criteria == "2":
        # Baseado no codec
        cursor.execute("""
            SELECT file_path FROM video_files
            WHERE analyzed = 1 AND converted = 0 AND codec_name != ?
        """, (codec_name,))
    else:
        conn.close()
        return []

    files = [row[0] for row in cursor.fetchall()]
    conn.close()
    return files

def mark_as_converted(file_path):
    """Marca um arquivo como convertido no banco de dados."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE video_files SET converted = 1 WHERE file_path = ?
    """, (file_path,))
    conn.commit()
    conn.close()

def process_videos_in_folder(folder_path, recursive=False):
    """Analisa e processa vídeos na pasta informada, com ou sem busca recursiva."""
    print(f"{Fore.CYAN}Escolha o codec para compressão:")
    print(f"{Fore.GREEN}1. HEVC (H.265, hevc_nvenc)")
    print(f"{Fore.GREEN}2. AV1 (av1_nvenc)")
    codec_choice = input(f"{Fore.CYAN}Digite o número correspondente (1 ou 2): ").strip()

    if codec_choice == "1":
        codec = "hevc_nvenc"
        codec_name = "hevc"
    elif codec_choice == "2":
        codec = "av1_nvenc"
        codec_name = "av1"
    else:
        print(f"{Fore.RED}Opção inválida. Por favor, execute o script novamente e escolha 1 ou 2.")
        return

    target_quality = int(input(f"{Fore.CYAN}Escolha a qualidade constante (0-51, onde maior é menor qualidade, recomendado: 35): "))
    
    print(f"{Fore.CYAN}Escolha o critério de conversão:")
    print(f"{Fore.GREEN}1. Converter arquivos com base no bitrate (não otimizados).")
    print(f"{Fore.GREEN}2. Converter todos os arquivos que não utilizam o codec escolhido ({codec_name}).")
    conversion_criteria = input(f"{Fore.CYAN}Digite o número correspondente (1 ou 2): ").strip()

    temp_folder = os.path.join(folder_path, "_temp")
    os.makedirs(temp_folder, exist_ok=True)

    if recursive:
        files = [
            os.path.join(root, file)
            for root, _, filenames in os.walk(folder_path)
            for file in filenames if is_video_file(os.path.join(root, file))
        ]
    else:
        files = [
            os.path.join(folder_path, file)
            for file in os.listdir(folder_path)
            if os.path.isfile(os.path.join(folder_path, file)) and is_video_file(os.path.join(folder_path, file))
        ]

    # Inicializa o banco de dados e verifica arquivos não analisados
    init_database()
    unanalyzed_files = get_unanalyzed_files(files)

    for file_path in unanalyzed_files:
        print(f"{Fore.CYAN}Analisando {file_path}...")
        video_info = get_video_info(file_path)
        if video_info:
            save_analysis_to_db(file_path, video_info)
        else:
            print(f"{Fore.RED}Erro ao analisar {file_path}. Arquivo ignorado.")

    valid_files = get_unconverted_files(codec_name, conversion_criteria)
    print(f"{Fore.YELLOW}Análise concluída: {len(valid_files)} arquivos serão convertidos.\n")

    # Processo de conversão
    times = []
    for idx, file_path in enumerate(valid_files, start=1):
        file_name = os.path.basename(file_path)
        print(f"{Fore.YELLOW}Iniciando a conversão de {file_name}... ({idx}/{len(valid_files)})")

        start_time = time.time()

        temp_file = os.path.join(temp_folder, os.path.splitext(file_name)[0] + ".mp4")
        success = encode_video(file_path, temp_file, target_quality=target_quality, codec=codec)
        if success:
            # Define o novo caminho com extensão padronizada .mp4
            output_file = os.path.splitext(file_path)[0] + ".mp4"
            
            # Remove o arquivo original (independentemente da extensão) e substitui pelo novo
            if os.path.exists(file_path):
                os.remove(file_path)
            
            os.replace(temp_file, output_file)
            
            # Atualiza o caminho no banco de dados e marca como convertido
            update_converted_file(file_path, output_file)
            print(f"{Fore.GREEN}Arquivo {file_name} foi substituído por sua versão convertida ({output_file}).")
        else:
            # Remove o arquivo temporário se a conversão falhou
            if os.path.exists(temp_file):
                os.remove(temp_file)
            print(f"{Fore.RED}Erro ao converter {file_name}. O arquivo original permanece inalterado.")


        elapsed_time = time.time() - start_time
        times.append(elapsed_time)

        # Estimativa de tempo restante
        avg_time = sum(times) / len(times)
        remaining_files = len(valid_files) - idx
        remaining_time = avg_time * remaining_files
        print(f"{Fore.MAGENTA}Tempo restante estimado: {int(remaining_time // 60)} minutos e {int(remaining_time % 60)} segundos.\n")



    if os.path.exists(temp_folder) and not os.listdir(temp_folder):
        os.rmdir(temp_folder)

def update_converted_file(original_path, new_path):
    """Atualiza o caminho e marca o arquivo como convertido no banco de dados."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE video_files
        SET file_path = ?, converted = 1
        WHERE file_path = ?
    """, (new_path, original_path))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    folder_path = input(f"{Fore.CYAN}Digite o caminho da pasta com os vídeos: ")
    if not os.path.exists(folder_path):
        print(f"{Fore.RED}Caminho da pasta não encontrado.")
    else:
        recursive = input(f"{Fore.CYAN}Deseja buscar arquivos recursivamente? (s/n): ").strip().lower() == "s"
        process_videos_in_folder(folder_path, recursive=recursive)
