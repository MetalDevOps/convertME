
# Conversor de Vídeos com FFMPEG

Este script em Python permite a compressão e otimização de arquivos de vídeo em uma pasta específica utilizando os codecs HEVC (H.265) ou AV1, com suporte a aceleração por hardware (NVIDIA GPU). Ele processa apenas arquivos na pasta informada, sem buscar em subpastas.

## Requisitos

### 1. Dependências
- **Python 3.x** instalado
- **FFmpeg** instalado com suporte a codecs NVIDIA (`hevc_nvenc`, `av1_nvenc`, etc.)

### 2. Instalação do FFmpeg
1. Baixe o FFmpeg em: [FFmpeg Builds](https://www.gyan.dev/ffmpeg/builds/)
2. Certifique-se de que o `ffmpeg` e `ffprobe` estejam acessíveis no `PATH` do sistema.

### 3. Instalação de Dependências Python
O script usa bibliotecas padrão do Python e não requer pacotes adicionais.

---

## Como Usar

1. Clone ou copie o script para uma pasta local.
2. Execute o script:
   ```bash
   python main.py
   ```

3. Siga as etapas interativas:
   - Informe o **caminho da pasta** onde os vídeos estão localizados.
   - Escolha o codec:
     - `1`: HEVC (H.265)
     - `2`: AV1
   - Defina o nível de qualidade (valor entre 0 e 51):
     - Recomendado: `35` (boa qualidade com compressão eficiente).

4. O script processará os arquivos na pasta e substituirá os originais pelas versões otimizadas.

---

## Estrutura do Projeto

- **`main.py`**: Arquivo principal do script.
- **`_temp/`**: Pasta temporária criada para armazenar arquivos convertidos antes de substituir os originais (removida automaticamente).

---

## Recursos do Script

1. **Busca de Arquivos de Vídeo**:
   - O script identifica arquivos de vídeo dinamicamente com base no tipo MIME, sem depender exclusivamente da extensão.

2. **Análise de Arquivos**:
   - Utiliza `ffprobe` para determinar `bit_rate`, resolução e duração.

3. **Conversão Condicional**:
   - Converte vídeos apenas se o bitrate for superior ao limite definido ou se o bitrate for desconhecido.

4. **Substituição de Arquivos**:
   - Após a conversão bem-sucedida, o arquivo convertido substitui o original.

5. **Aceleração por Hardware**:
   - Compatível com GPUs NVIDIA para melhorar a performance.

---

## Exemplos

### Entrada
Pasta de entrada contendo:
- `video1.mp4` (4K, 16 Mbps)
- `video2.ts` (HD, bitrate desconhecido)

### Saída
- `video1.mp4` (4K, ~6 Mbps, HEVC/AV1)
- `video2.mp4` (HD, HEVC/AV1)

---

## Notas

1. **Qualidade Constante (`CQ`)**:
   - Valores mais baixos resultam em maior qualidade e arquivos maiores.
   - Valores recomendados: `25-35`.

2. **Limitações do Codec AV1**:
   - O AV1 pode ser significativamente mais lento do que HEVC.

3. **Erros Potenciais**:
   - Arquivos corrompidos ou com streams incompletos podem gerar falhas no processamento.

---

## Contribuições

Contribuições e melhorias são bem-vindas! Sinta-se à vontade para enviar sugestões ou relatórios de bugs.

---

## Licença

Este projeto é de uso livre sob a licença MIT. Consulte o arquivo `LICENSE` para mais detalhes.
