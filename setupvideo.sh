#!/bin/bash

# Select the Video EDID File
VIDEDID=1080P60EDID.txt


# Find the device automatically
MEDIADEVICE=-1
i=0
while true ; do
    MEDIADEVICE=$(udevadm info -a -n /dev/media$i | grep --line-buffered 'DRIVERS=="\rp1-cfe"' | while read -r line; do echo $i ; done)
    if ! [[ $MEDIADEVICE = '' ]];  then
        break
    fi
    i=$((i+1))
done

# For debugging: will list the /dev/media device
# v4l2-ctl --list-devices

# Load the Video Driver
v4l2-ctl -d /dev/v4l-subdev2 --set-edid=file=./$VIDEDID

# Wait until driver is loaded
sleep 5

# Detect the video timings from the source

# v4l2-ctl -d /dev/v4l-subdev2 --query-dv-timings
v4l2-ctl -d /dev/v4l-subdev2 --set-dv-bt-timings query

# Initialise the media
media-ctl -d /dev/media$MEDIADEVICE -r

# Link the camera CSI input to the media node
media-ctl -d /dev/media$MEDIADEVICE -l ''\''csi2'\'':4 -> '\''rp1-cfe-csi2_ch0'\'':0 [1]'


# Configure the media node - note for latest Kernel the format is 'BGR'
media-ctl -d /dev/media$MEDIADEVICE -V ''\''csi2'\'':0 [fmt:BGR888_1X24/1920x1080 field:none colorspace:srgb]'
media-ctl -d /dev/media$MEDIADEVICE -V ''\''csi2'\'':4 [fmt:BGR888_1X24/1920x1080 field:none colorspace:srgb]'
v4l2-ctl -v width=1920,height=1080,pixelformat=BGR3


# Debug: a command to output stream to a file (will fail if device not set up correctly)
# v4l2-ctl --verbose -d /dev/video0 --set-fmt-video=width=1920,height=1080,pixelformat='BGR3' --stream-mmap=4 --stream-skip=3 --stream-count=2 --stream-to=csitest.yuv --stream-poll
# ffmpeg -f v4l2 -video_size 1920x1080 -pixel_format bgr24 -i /dev/video0 -t 5 test.mp4


#dmesg | tail -50
