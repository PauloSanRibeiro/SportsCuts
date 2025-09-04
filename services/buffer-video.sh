#!/bin/bash

# Diretórios
DIR_IP="/home/sysadmin/videosprocessing/camIP"
DIR_WEBCAM="/home/sysadmin/videosprocessing/webCam"

# Dispositivos
CAM_IP="rtsp://admin:Prosseg2018@192.168.100.200:554/cam/realmonitor?channel=1&subtype=0"
CAM_WEBCAM="/dev/video0"

# Criar diretórios se não existirem
mkdir -p "$DIR_IP"
mkdir -p "$DIR_WEBCAM"

# Gravar da câmera IP por 30s
ffmpeg -rtsp_transport tcp -i "$CAM_IP" -c copy -f segment \
-segment_time 30 -segment_wrap 20 -reset_timestamps 1 \
"$DIR_IP/output_%03d.mp4" &

# Gravar da webcam se estiver conectada
if [ -e "$CAM_WEBCAM" ]; then
  ffmpeg -f v4l2 -input_format yuyv422 -video_size 1280x720 -i "$CAM_WEBCAM" \
  -c:v libx264 -preset ultrafast -crf 23 -pix_fmt yuv420p \
  -f segment -segment_time 30 -segment_wrap 20 -reset_timestamps 1 \
  "$DIR_WEBCAM/output_%03d.mp4" &
else
  echo "Webcam não encontrada em $CAM_WEBCAM"
fi

wait
