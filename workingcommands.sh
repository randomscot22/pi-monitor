# Working commands on PI5 with latest OS at 27 May
# Ref: https://forums.raspberrypi.com/viewtopic.php?t=396603\
# Ref: https://github.com/raspberrypi/linux/issues/6068#issuecomment-3421411236

device=/dev/media3

v4l2-ctl -d /dev/v4l-subdev2 --set-edid=file=./1080P60EDID.txt
v4l2-ctl -d /dev/v4l-subdev2 --query-dv-timings
v4l2-ctl -d /dev/v4l-subdev2 --set-dv-bt-timings query
media-ctl -d $device -r

media-ctl -d $device -l ''\''csi2'\'':4 -> '\''rp1-cfe-csi2_ch0'\'':0 [1]'
media-ctl -d $device -V ''\''csi2'\'':0 [fmt:BGR888_1X24/1920x1080 field:none colorspace:srgb]'
media-ctl -d $device -V ''\''csi2'\'':4 [fmt:BGR888_1X24/1920x1080 field:none colorspace:srgb]'
v4l2-ctl -v width=1920,height=1080,pixelformat=BGR3

v4l2-ctl --verbose -d /dev/video0 --set-fmt-video=width=1920,height=1080,pixelformat='BGR3' --stream-mmap=4 --stream-skip=3 --stream-count=2 --stream-to=csitest.yuv --stream-poll

