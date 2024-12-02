import os
import subprocess
import json
import mimetypes
import shutil

def is_video_file(file_path):
    """Verifica dinamicamente se um arquivo é de vídeo usando mimetypes."""
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type and mime_type.startswith("video")

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

def encode_video(input_file, temp_file, target_quality=35, codec="hevc_nvenc"):
    """Re-encoda o vídeo com o codec especificado."""
    command = [
        "ffmpeg",
        "-i", input_file,
        "-c:v", codec,
        "-cq", str(target_quality),    # Define o nível de qualidade constante
        "-preset", "slow",             # Melhor compressão
        "-c:a", "copy",                # Mantém o áudio original
        "-f", "mp4",                   # Força o container MP4
        temp_file
    ]
    try:
        subprocess.run(command, check=True)
        print(f"Arquivo processado com {codec}: {temp_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Erro ao processar {input_file} com {codec}: {e}")
        return False

def process_videos_in_folder(folder_path):
    """Analisa e processa vídeos na pasta."""
    print("Escolha o codec para compressão:")
    print("1. HEVC (H.265, hevc_nvenc)")
    print("2. AV1 (av1_nvenc)")
    codec_choice = input("Digite o número correspondente (1 ou 2): ").strip()
    
    if codec_choice == "1":
        codec = "hevc_nvenc"
    elif codec_choice == "2":
        codec = "av1_nvenc"
    else:
        print("Opção inválida. Por favor, execute o script novamente e escolha 1 ou 2.")
        return

    target_quality = int(input("Escolha a qualidade constante (0-51, onde maior é menor qualidade, recomendado: 35): "))

    temp_folder = os.path.join(folder_path, "_temp")
    os.makedirs(temp_folder, exist_ok=True)

    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            if is_video_file(file_path):  # Detecção dinâmica de vídeos
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
                    # Salvar o arquivo temporário como .mp4
                    temp_file = os.path.join(temp_folder, os.path.splitext(file)[0] + ".mp4")
                    success = encode_video(file_path, temp_file, target_quality=target_quality, codec=codec)
                    if success:
                        # Renomeia o arquivo original para .mp4 antes de substituir
                        original_mp4_path = os.path.splitext(file_path)[0] + ".mp4"
                        os.replace(temp_file, original_mp4_path)
                        if file_path != original_mp4_path:
                            os.remove(file_path)  # Remove o arquivo original se a extensão era diferente
                        print(f"Arquivo original substituído por: {original_mp4_path}")
                    else:
                        print(f"Erro ao converter {file}. O arquivo original não foi alterado.")
                else:
                    print(f"Arquivo {file} já está otimizado (Bitrate atual: {bitrate} kbps).")

    # Remove a pasta temporária após o processamento
    if os.path.exists(temp_folder) and not os.listdir(temp_folder):
        os.rmdir(temp_folder)

if __name__ == "__main__":
    folder_path = input("Digite o caminho da pasta com os vídeos: ")
    if os.path.exists(folder_path):
        process_videos_in_folder(folder_path)
    else:
        print("Caminho da pasta não encontrado.")
