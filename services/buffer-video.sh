#!/bin/bash

#Directorys
DIR_IP="/home/sysadmin/videosprocessing/camIP"
DIR_WEBCAM="/home/sysadmin/videosprocessing/webCam"

#Diveces
CAM_IP="rtsp://admin:Prosseg2018@192.168.100.200:552/cam/realmonitor?channel=1&subtype="
CAM_WEBCAM="/dev/video0"

#Create Directory if Not Exists
mkdir -p "$DIRIP"
mkdir -p "$DIR_WEBCAM"

#Record Camera 30s
ffmpeg -rtsp_transport tcp -i "$CAM_IP" -c copy -f segment - segment_time 30 -segment_wrap 20 -reset_timestamps 1 "$DIR_IP/output_%3d.mp4" &

#Record Webcam 30s
ffmpeg -f v4l2 -input_format yuyv422 -video_size 1280x720 -i "$CAM_WEBCAM" \
-c:v libx264 -preset ultrafast -crf 23 -pix_fmt yuv420p \
-f segment -segment_time 30 -segment_wrap 20 -reset_timestamps 1 "$DIR_WEBCAM/output_%03d.mp4" &

wait
