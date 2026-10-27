#!/usr/bin/env bash
# Junta segmentos + mix, gera a capa e roda o QC automático.
# uso: tools/finalize.sh <dir_video> <NomeArquivo> <tempo_capa_s>
set -eu
D=$1; N=$2; CAPA=$3; O=$D/entrega/$N.mp4
mkdir -p "$D/entrega"
ffmpeg -y -loglevel error -i $D/render/seg/seg_00.mp4 -i $D/render/seg/seg_01.mp4 -i $D/render/seg/seg_02.mp4 -i $D/render/seg/seg_03.mp4 -i $D/audio/mix_final.wav \
  -filter_complex "[0:v][1:v][2:v][3:v]concat=n=4:v=1:a=0,setpts=N/30/TB[v]" -map "[v]" -map 4:a -r 30 \
  -c:v libx264 -preset slow -crf 13 -profile:v high -level 4.2 -pix_fmt yuv420p -color_primaries bt709 -color_trc bt709 -colorspace bt709 -g 60 \
  -c:a aac -b:a 192k -ar 48000 -movflags +faststart "$O"
ffmpeg -loglevel error -y -ss "$CAPA" -i "$O" -frames:v 1 -q:v 2 "$D/entrega/${N}_capa.jpg"
echo "== QC $N"
ffprobe -v error -count_frames -select_streams v -show_entries stream=nb_read_frames,duration -of csv=p=0 "$O" | sed 's/^/quadros: /'
ffprobe -v error -select_streams a -show_entries stream=duration -of csv=p=0 "$O" | sed 's/^/áudio (s): /'
echo -n "maior troca de cena: "; ffmpeg -hide_banner -i "$O" -vf "scdet=threshold=100,metadata=print:file=-" -an -f null - 2>/dev/null | awk '/pts_time/{split($3,a,":");t=a[2]} /scd.score/{split($1,b,"=");print b[2]" @"t"s"}' | sort -rn | head -1
echo -n "pretos/congelamentos: "; ffmpeg -hide_banner -i "$O" -vf "blackdetect=d=0.05:pix_th=0.06,freezedetect=n=0.0005:d=1.2" -an -f null - 2>&1 | grep -cE "black_start|freeze_start" || true
ffmpeg -hide_banner -i "$O" -map 0:a -af ebur128 -f null - 2>&1 | grep -E "^\s+I:" | sed 's/^ */loudness /'
