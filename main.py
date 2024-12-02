import os
import subprocess
import json

def get_video_info(file_path):
    """Retorna informações técnicas do vídeo usando ffprobe."""
    command = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=bit_rate,width,height",
        "-of", "json",
        file_path
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        video_info = json.loads(result.stdout)
        return video_info['streams'][0] if 'streams' in video_info and video_info['streams'] else None
    except subprocess.CalledProcessError as e:
        print(f"Erro ao analisar {file_path}: {e}")
        return None

def encode_video(input_file, output_file, target_quality=35):
    """Re-encoda o vídeo com nvenc_hevc ajustando a qualidade constante (cq)."""
    if not (0 <= target_quality <= 51):
        print(f"Erro: Valor de qualidade constante (cq) deve estar entre 0 e 51. Valor recebido: {target_quality}")
        return

    command = [
        "ffmpeg",
        "-i", input_file,
        "-c:v", "hevc_nvenc",
        "-cq", str(target_quality),    # Define o nível de qualidade constante
        "-preset", "slow",             # Melhor compressão
        "-c:a", "copy",                # Mantém o áudio original
        output_file
    ]
    try:
        subprocess.run(command, check=True)
        print(f"Arquivo processado: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"Erro ao processar {input_file}: {e}")

def process_videos_in_folder(folder_path):
    """Analisa e processa vídeos na pasta."""
    target_quality = int(input("Escolha a qualidade constante (0-51, onde maior é menor qualidade, recomendado: 35): "))
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                file_path = os.path.join(root, file)
                print(f"Analisando {file}...")

                video_info = get_video_info(file_path)
                if not video_info:
                    print(f"Não foi possível obter informações de {file}. Pulando...")
                    continue

                # Coletando informações do vídeo
                bitrate = int(video_info.get("bit_rate", 0)) // 1000  # Converte para kbps
                width = video_info.get("width", 0)
                height = video_info.get("height", 0)

                # Define um bitrate-alvo com base na resolução
                if width <= 1280 and height <= 720:  # HD
                    target_bitrate = 1500  # kbps
                elif width <= 1920 and height <= 1080:  # Full HD
                    target_bitrate = 3000  # kbps
                else:  # Resoluções maiores (4K, etc.)
                    target_bitrate = 6000  # kbps

                if bitrate > target_bitrate:
                    print(f"Arquivo {file} pode ser reduzido (Bitrate atual: {bitrate} kbps, Alvo: {target_bitrate} kbps).")
                    output_file = os.path.join(root, f"encoded_{file}")
                    encode_video(file_path, output_file, target_quality=target_quality)
                else:
                    print(f"Arquivo {file} já está otimizado (Bitrate atual: {bitrate} kbps).")

if __name__ == "__main__":
    folder_path = input("Digite o caminho da pasta com os vídeos: ")
    if os.path.exists(folder_path):
        process_videos_in_folder(folder_path)
    else:
        print("Caminho da pasta não encontrado.")