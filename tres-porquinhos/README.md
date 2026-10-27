# Os Três Porquinhos — vídeo infantil (YouTube + TikTok)

História completa adaptada para alto engajamento, com narração em português (BR), ilustrações, legendas, trilha e duas proporções nativas.

## Duração
**~5 min 42 s** (acima do mínimo de 5 minutos).

## Arquivos finais (`output/`)
| Arquivo | Formato |
|---------|---------|
| `os_tres_porquinhos_youtube_16x9.mp4` | YouTube 1920×1080 |
| `os_tres_porquinhos_tiktok_9x16.mp4` | TikTok / Reels / Shorts 1080×1920 |
| `parte1_palha.mp4` / `parte2_madeira.mp4` / `parte3_tijolos.mp4` | Série TikTok com cliffhangers |
| `thumbnail_youtube.jpg` | Thumbnail |

## Como regenerar
```bash
export PATH="$HOME/.local/bin:$PATH"
pip install edge-tts numpy
python3 build/generate_audio.py
python3 build/assemble_video.py
python3 build/make_tiktok_parts.py
```

## Conteúdo de apoio
- `RESEARCH.md` — pesquisa de tendências TikTok/YouTube
- `PUBLISHING.md` — títulos, hashtags e checklist de postagem
- `script/roteiro.md` — roteiro completo + estratégia de retenção
