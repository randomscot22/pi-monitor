#!/bin/bash


LOGFILE="./logfile.log"

exec > >(tee -a "$LOGFILE") 2>&1
export PS4='\n**** Command: \n'
set -x

device=/dev/media3

tail -4 /boot/firmware/config.txt 

v4l2-ctl --list-devices

v4l2-ctl -d /dev/v4l-subdev2 --set-edid=file=/home/pi/1080P60EDID.txt --fix-edid-checksums

v4l2-ctl -d /dev/v4l-subdev2 --query-dv-timings

v4l2-ctl -d /dev/v4l-subdev2 --set-dv-bt-timings query

media-ctl -d $device -r

media-ctl -d $device -l ''\''csi2'\'':4 -> '\''rp1-cfe-csi2_ch0'\'':0 [1]'
media-ctl -d $device -V ''\''csi2'\'':0 [fmt:RGB888_1X24/1920x1080 field:none colorspace:srgb]'
media-ctl -d $device -V ''\''csi2'\'':4 [fmt:RGB888_1X24/1920x1080 field:none colorspace:srgb]'

v4l2-ctl -v width=1920,height=1080,pixelformat=RGB3

v4l2-ctl --verbose -d /dev/video0 --set-fmt-video=width=1920,height=1080,pixelformat='RGB3' --stream-mmap=4 --stream-skip=3 --stream-count=2 --stream-to=csitest.yuv --stream-poll

dmesg | tail -1


