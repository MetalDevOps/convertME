import os
import subprocess
import json
import mimetypes

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
            "-show_entries", "stream=bit_rate,width,height",
            "-show_entries", "format=duration",
            "-of", "json",
            file_path
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        video_info = json.loads(result.stdout)

        bit_rate = video_info.get('streams', [{}])[0].get('bit_rate', 0)
        width = video_info.get('streams', [{}])[0].get('width', 0)
        height = video_info.get('streams', [{}])[0].get('height', 0)
        duration = float(video_info.get('format', {}).get('duration', 0))

        return {
            'bit_rate': int(bit_rate) if bit_rate else 0,
            'width': width,
            'height': height,
            'duration': duration
        }

    except subprocess.CalledProcessError as e:
        print(f"Erro ao analisar {file_path}: {e}")
        return None
    except Exception as e:
        print(f"Erro inesperado ao processar {file_path}: {e}")
        return None

def encode_video(input_file, temp_file, target_quality=35, codec="hevc_nvenc"):
    """Re-encoda o vídeo com o codec especificado."""
    command = [
        "ffmpeg",
        "-hwaccel", "cuda",
        "-i", input_file,
        "-c:v", codec,
        "-cq", str(target_quality),
        "-preset", "fast",
        "-c:a", "copy",
        "-f", "mp4",
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
    """Analisa e processa vídeos na pasta informada."""
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

    for file in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file)
        if os.path.isfile(file_path) and is_video_file(file_path):  # Verifica apenas arquivos
            print(f"Analisando {file}...")

            video_info = get_video_info(file_path)
            if not video_info:
                print(f"Não foi possível obter informações de {file}. Continuando com a conversão.")
                video_info = {'bit_rate': 0, 'width': 0, 'height': 0}

            bitrate = video_info['bit_rate']
            width = video_info['width']
            height = video_info['height']

            if width <= 1280 and height <= 720:
                target_bitrate = 1500
            elif width <= 1920 and height <= 1080:
                target_bitrate = 3000
            else:
                target_bitrate = 6000

            if bitrate == 0 or bitrate > target_bitrate:
                print(f"Arquivo {file} será convertido (Bitrate atual: {bitrate if bitrate else 'desconhecido'}, Alvo: {target_bitrate} kbps).")
                temp_file = os.path.join(temp_folder, os.path.splitext(file)[0] + ".mp4")
                success = encode_video(file_path, temp_file, target_quality=target_quality, codec=codec)
                if success:
                    original_mp4_path = os.path.splitext(file_path)[0] + ".mp4"
                    os.replace(temp_file, original_mp4_path)
                    if file_path != original_mp4_path:
                        os.remove(file_path)
                    print(f"Arquivo {file} foi substituído por sua versão convertida.")
                else:
                    print(f"Erro ao converter {file}. O arquivo original permanece inalterado.")
            else:
                print(f"Arquivo {file} já está otimizado (Bitrate atual: {bitrate} kbps).")

    if os.path.exists(temp_folder) and not os.listdir(temp_folder):
        os.rmdir(temp_folder)

if __name__ == "__main__":
    folder_path = input("Digite o caminho da pasta com os vídeos: ")
    if os.path.exists(folder_path):
        process_videos_in_folder(folder_path)
    else:
        print("Caminho da pasta não encontrado.")
