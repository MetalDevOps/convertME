import os
import mimetypes
import sqlite3
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from datetime import datetime, timedelta
from colorama import Fore, Style

# Configuração de logs
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("video_conversion.log")],
)

DATABASE_FILE = "video_conversion.db"
TEMP_FOLDER_NAME = "_temp"
FFMPEG_LOG_FOLDER = "ffmpeg_output"
DEFAULT_QUALITY = 35
DEFAULT_CODEC = "hevc_nvenc"
MAX_WORKERS = 2  # Quantidade máxima de threads simultâneas

# Inicializa tipos MIME
mimetypes.init()


def format_timedelta(seconds):
    """Converte segundos em formato HH:MM:SS."""
    delta = timedelta(seconds=int(seconds))
    return str(delta)


def init_database():
    """Inicializa o banco de dados SQLite."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS video_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE,
            codec_name TEXT,
            bit_rate INTEGER,
            width INTEGER,
            height INTEGER,
            analyzed INTEGER DEFAULT 0,
            converted INTEGER DEFAULT 0,
            analysis_date TEXT,
            conversion_date TEXT,
            original_size INTEGER DEFAULT 0,
            converted_size INTEGER DEFAULT 0,
            reduction_percentage REAL DEFAULT 0
        )
    """
    )
    conn.commit()
    conn.close()


def insert_file_into_database(file_path):
    """Insere informações iniciais de um arquivo no banco de dados."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO video_files (file_path, analyzed)
        VALUES (?, 0)
    """,
        (file_path,),
    )
    conn.commit()
    conn.close()


def update_file_analysis(file_path, codec_name, bit_rate, width, height):
    """Atualiza as informações de análise do arquivo no banco de dados."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE video_files
        SET codec_name = ?, bit_rate = ?, width = ?, height = ?, analyzed = 1, analysis_date = ?
        WHERE file_path = ?
    """,
        (codec_name, bit_rate, width, height, datetime.now().isoformat(), file_path),
    )
    conn.commit()
    conn.close()


def update_converted_file(
    original_path, new_path, original_size, converted_size, reduction_percentage
):
    """Atualiza o caminho, os tamanhos e o percentual de redução no banco de dados."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE video_files
        SET file_path = ?, converted = 1, original_size = ?, converted_size = ?, reduction_percentage = ?, conversion_date = ?
        WHERE file_path = ?
    """,
        (
            new_path,
            original_size,
            converted_size,
            reduction_percentage,
            datetime.now().isoformat(),
            original_path,
        ),
    )
    conn.commit()
    conn.close()


def is_video_file(file_path):
    """Verifica se o arquivo é um vídeo usando mimetypes."""
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type is not None and mime_type.startswith("video")


def analyze_file(file_path):
    """Analisa um arquivo de vídeo e retorna suas propriedades usando ffprobe."""
    import subprocess

    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,bit_rate,width,height",
            "-of",
            "default=noprint_wrappers=1",
            file_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        props = {}
        for line in result.stdout.strip().split("\n"):
            key, value = line.split("=")
            props[key] = value
        return (
            props.get("codec_name"),
            int(props.get("bit_rate", 0)),
            int(props.get("width", 0)),
            int(props.get("height", 0)),
        )
    except Exception as e:
        logging.error(f"Erro ao analisar {file_path}: {e}")
        return None, None, None, None


def analyze_folder(folder_path, recursive=False):
    """Analisa a pasta para encontrar arquivos de vídeo válidos, ignorando a pasta temporária."""
    valid_files = []
    total_files = 0

    for root, dirs, filenames in os.walk(folder_path):
        # Ignora a pasta temporária
        if TEMP_FOLDER_NAME in dirs:
            dirs.remove(TEMP_FOLDER_NAME)

        for filename in filenames:
            total_files += 1
            file_path = os.path.join(root, filename)
            if is_video_file(file_path):
                insert_file_into_database(file_path)
                codec_name, bit_rate, width, height = analyze_file(file_path)
                if codec_name:
                    update_file_analysis(file_path, codec_name, bit_rate, width, height)
                valid_files.append(file_path)

        if not recursive:
            break

    logging.info(f"Total de arquivos encontrados: {total_files}")
    logging.info(f"Arquivos válidos para conversão: {len(valid_files)}")
    return valid_files


def monitor_gpu_usage():
    """Monitora o uso de GPU e retorna True se o uso ultrapassar 85%."""
    try:
        import pynvml

        # Inicializa a biblioteca NVML
        pynvml.nvmlInit()

        # Obtém o handle da primeira GPU (índice 0)
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)

        # Obtém os dados de utilização da GPU
        utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)

        # Loga a utilização da GPU e memória
        logging.debug(
            f"Uso da GPU: {utilization.gpu}%, Uso da Memória: {utilization.memory}%"
        )

        # Retorna True se o uso da GPU for superior a 85%
        return int(utilization.gpu) > 85

    except pynvml.NVMLError as e:
        # Loga o erro caso a NVML não esteja disponível ou encontre um problema
        logging.warning(f"Erro ao monitorar GPU: {e}")
        return False

    except ImportError:
        # Caso a biblioteca pynvml não esteja instalada, loga um aviso
        logging.warning(
            "A biblioteca 'pynvml' não está instalada. Monitoração de GPU desativada."
        )
        return False


def encode_video(input_file, output_file, target_quality, codec):
    """Realiza a conversão de vídeo usando ffmpeg."""
    import subprocess

    cmd = [
        "ffmpeg",
        "-hwaccel",
        "cuda",
        "-i",
        input_file,
        "-c:v",
        codec,
        "-cq",
        str(target_quality),
        "-rc",
        "vbr",
        "-c:a",
        "copy",
        "-f",
        "mp4",
        output_file,
    ]
    try:
        with open(
            f"{FFMPEG_LOG_FOLDER}/{os.path.basename(input_file)}.log", "w"
        ) as log_file:
            subprocess.run(cmd, check=True, stdout=log_file, stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Erro na conversão de {input_file}: {e}")
        return False


def calculate_time_remaining(progress_data):
    """Calcula o tempo restante baseado no tamanho dos arquivos restantes."""
    completed_size = progress_data["completed_size"]
    elapsed_time = time.time() - progress_data["start_time"]

    if completed_size == 0:
        return float("inf")  # Não podemos estimar sem progresso

    avg_time_per_byte = elapsed_time / completed_size
    remaining_size = progress_data["total_size"] - completed_size
    return avg_time_per_byte * remaining_size


def convert_video(
    file_path, codec, target_quality, temp_folder, progress_data, progress_lock
):
    """Executa a conversão de um único arquivo."""
    file_name = os.path.basename(file_path)
    logging.info(f"Iniciando a conversão de {file_name}...")
    # Verifica o uso da GPU antes de configurar o codec
    if codec == "hevc_nvenc" or codec == "av1_nvenc":
        if monitor_gpu_usage():
            logging.info(f"Uso da GPU acima de 85%. Alternando para codec baseado em CPU (libsvtav1).")
            codec = "libsvtav1"

    start_time = time.time()

    temp_file = os.path.join(temp_folder, os.path.splitext(file_name)[0] + ".mp4")
    success = encode_video(file_path, temp_file, target_quality, codec)

    if success:
        original_size = os.path.getsize(file_path)
        converted_size = os.path.getsize(temp_file)
        reduction_percentage = (
            (1 - converted_size / original_size) * 100 if original_size > 0 else 0
        )

        # Preservar timestamps
        original_creation_time = os.path.getctime(file_path)
        original_modification_time = os.path.getmtime(file_path)

        output_file = os.path.splitext(file_path)[0] + ".mp4"
        os.remove(file_path)
        os.replace(temp_file, output_file)

        # Atualizar timestamps
        os.utime(output_file, (original_creation_time, original_modification_time))

        update_converted_file(
            file_path, output_file, original_size, converted_size, reduction_percentage
        )

        space_saved = original_size - converted_size

        # Atualiza progresso com lock
        with progress_lock:
            progress_data["completed"] += 1
            progress_data["completed_size"] += original_size
            progress_data["total_saved_space"] += space_saved
            remaining_time = calculate_time_remaining(progress_data)

            logging.info(
                f"Progresso: {progress_data['completed']}/{progress_data['total']} arquivos convertidos."
            )
            logging.info(f"Tempo restante estimado: {format_timedelta(remaining_time)}")

        logging.info(
            f"Arquivo {file_name} convertido com sucesso! Economia de espaço: {space_saved / (1024 * 1024):.2f} MB ({reduction_percentage:.2f}%)"
        )
    else:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        logging.error(
            f"Erro ao converter {file_name}. O arquivo original permanece inalterado."
        )

    elapsed_time = time.time() - start_time
    logging.info(f"Tempo gasto para {file_name}: {elapsed_time:.2f} segundos.")


def main():
    print(f"{Fore.CYAN}Bem-vindo ao conversor de vídeos!{Style.RESET_ALL}")
    folder_path = input("Digite o caminho da pasta com os vídeos: ").strip()
    recursive = (
        input("Deseja buscar arquivos recursivamente? (s/n): ").strip().lower() == "s"
    )

    print("\nEscolha o codec para compressão:")
    print("1. HEVC (H.265, hevc_nvenc)")
    print("2. AV1 (av1_nvenc)")
    codec_choice = input("Digite o número correspondente (1 ou 2): ").strip()
    codec = "hevc_nvenc" if codec_choice == "1" else "av1_nvenc"

    target_quality = int(
        input(
            "Escolha a qualidade constante (0-51, onde maior é menor qualidade, recomendado: 35): "
        ).strip()
    )

    os.makedirs(FFMPEG_LOG_FOLDER, exist_ok=True)

    valid_files = analyze_folder(folder_path, recursive)

    temp_folder = os.path.join(folder_path, TEMP_FOLDER_NAME)
    os.makedirs(temp_folder, exist_ok=True)

    progress_data = {
        "total": len(valid_files),
        "completed": 0,
        "start_time": time.time(),
        "total_size": sum(os.path.getsize(file) for file in valid_files),
        "completed_size": 0,
        "total_saved_space": 0,
    }

    progress_lock = Lock()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for file_path in valid_files:
            executor.submit(
                convert_video,
                file_path,
                codec,
                target_quality,
                temp_folder,
                progress_data,
                progress_lock,
            )

    # Exibição do resumo
    total_time = time.time() - progress_data["start_time"]
    total_saved_mb = progress_data["total_saved_space"] / (1024 * 1024)
    logging.info(f"\nResumo Final:")
    logging.info(f"Total de arquivos processados: {progress_data['completed']}")
    logging.info(f"Economia total de espaço: {total_saved_mb:.2f} MB")
    logging.info(f"Tempo total gasto: {format_timedelta(total_time)}")


if __name__ == "__main__":
    init_database()
    main()
