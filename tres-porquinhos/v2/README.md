# Os Três Porquinhos — versão 2D com vozes por personagem

Animação estilo cartoon 2D (cel shading) em que **cada personagem fala com a própria voz**.

## Duração
**~5 min 18 s**

## Vozes
| Personagem | Voz base | Característica |
|------------|----------|----------------|
| Narrador | Thalita (pt-BR) | Contadora da história |
| Mamãe | Francisca | Mais grave / calma |
| Pipoca | Francisca | Aguda / rápida (criança) |
| Tambor | Antonio | Aguda / animada |
| Tijolinho | Antonio | Neutra / segura |
| Lobo Mau | Antonio | Grave / lenta |

## Arquivos (`output/`)
- `tres_porquinhos_2d_youtube_16x9.mp4` — YouTube
- `tres_porquinhos_2d_tiktok_9x16.mp4` — TikTok / Reels / Shorts
- `dialogo_completo_multivozes.mp3` — áudio completo

## Regenerar
```bash
export PATH="$HOME/.local/bin:$PATH"
python3 build/generate_dialogue_audio.py
python3 build/assemble_dialogue_video.py
```
